"""
Harvest zones and feeder: operations on the player's state.

The rules live in the engine (game.zones, game.experience); these functions
load what the engine needs, ask it, and save the outcome, always inside a
transaction with the rows locked (select_for_update), so two requests at
the same moment can't both spend the same resources or fill the same slot.
"""

from dataclasses import dataclass

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from game import balance, experience, mastery
from game.zones import ZONE_OF_RESOURCE, Worker, work

from . import research
from .models import OwnedPokemon, Player, PlayerZone, ResourceStock


class ZoneError(ValueError):
    """An action the rules forbid (full zone, not enough resources...): shown to the player."""


def give_starting_zones(player: Player) -> None:
    """The zones every player has from the start (called when the save is created)."""
    PlayerZone.objects.bulk_create(
        PlayerZone(player=player, zone=zone) for zone in balance.STARTING_ZONES
    )


def as_worker(pokemon: OwnedPokemon) -> Worker:
    """A Pokémon as the engine sees it at work: its types and level."""
    return Worker(
        types=tuple(t.slug for t in pokemon.species.types),
        level=pokemon.level,
        mastered=mastery.is_mastered(pokemon.research_stage),
    )


def workers_of(zone: PlayerZone) -> list[OwnedPokemon]:
    """The Pokémon working in a zone, by spot."""
    return list(
        zone.workers.select_related("species__primary_type", "species__secondary_type").order_by(
            "spot"
        )
    )


# --- Work during the catch-up --------------------------------------------------


def work_zones(player: Player, hours_elapsed: int) -> None:
    """
    Add `hours_elapsed` hours of work to every zone of the player.

    Called by the catch-up, in its transaction. Nothing changes in a zone
    while the player is away, so the engine computes the period at once.
    """
    if hours_elapsed <= 0:
        return
    events = []
    for zone in player.zones.select_for_update():
        workers = workers_of(zone)
        done = work(
            zone.spec,
            [as_worker(p) for p in workers],
            zone.hours_worked,
            hours_elapsed,
            # The skill tree of the zone: storage, yield, experience
            cap_hours=zone.work_cap,
            yield_percent=zone.yield_percent,
            xp_percent=zone.xp_percent,
        )
        if not done.hours:
            continue  # empty zone, or storage already full
        zone.hours_worked += done.hours
        zone.stock_centi += done.resource_centi
        zone.save(update_fields=["hours_worked", "stock_centi"])
        for pokemon, gained in zip(workers, done.experience, strict=True):
            # F(): the database adds, no lost update if two requests race
            OwnedPokemon.objects.filter(pk=pokemon.pk).update(
                pending_experience=F("pending_experience") + gained
            )
        events += research.work_events(zone, workers, done)
    # Hours worked and resources gathered count for each worker's challenges
    research.record(player, events)


# --- Collection ------------------------------------------------------------------


@dataclass(frozen=True)
class Growth:
    """What a collection did to one Pokémon."""

    pokemon: OwnedPokemon
    experience: int
    old_level: int

    @property
    def levels(self) -> int:
        return self.pokemon.level - self.old_level


@dataclass(frozen=True)
class Harvest:
    """What a collection brought."""

    zone: PlayerZone
    resource: int  # whole resources moved to the stock
    hours: int  # hours of work collected
    growths: list[Growth]

    @property
    def is_empty(self) -> bool:
        return not self.resource and not any(g.experience for g in self.growths)


def add_resource(player: Player, resource: str, amount: int) -> None:
    """Add to the player's stock of a resource (the row is created on first use)."""
    stock, _ = ResourceStock.objects.get_or_create(player=player, resource=resource)
    ResourceStock.objects.filter(pk=stock.pk).update(amount=F("amount") + amount)


@transaction.atomic
def collect(zone: PlayerZone) -> Harvest:
    """
    Collect a zone: its whole resources go to the stock (the hundredths left
    stay for next time), its Pokémon get their experience, and the storage
    is empty again, so they work anew.
    """
    zone = PlayerZone.objects.select_for_update().get(pk=zone.pk)
    resource, zone.stock_centi = divmod(zone.stock_centi, 100)
    hours, zone.hours_worked = zone.hours_worked, 0
    zone.collected_at = timezone.now()
    zone.save(update_fields=["stock_centi", "hours_worked", "collected_at"])
    if resource:
        add_resource(zone.player, zone.spec.resource, resource)

    growths, events = [], []
    for pokemon in workers_of(zone):
        gained, old_level = pokemon.pending_experience, pokemon.level
        pokemon.level, pokemon.experience = experience.add_experience(
            pokemon.species.growth_rate, pokemon.level, pokemon.experience, gained
        )
        pokemon.pending_experience = 0
        pokemon.save(update_fields=["level", "experience", "pending_experience"])
        growths.append(Growth(pokemon, gained, old_level))
        if pokemon.level > old_level:
            events.append(research.level_event(pokemon))
    research.record(zone.player, events)  # levels reached count for the challenges
    return Harvest(zone=zone, resource=resource, hours=hours, growths=growths)


# --- Status: the single way to move a Pokémon ----------------------------------


@transaction.atomic
def move_pokemon(
    pokemon: OwnedPokemon, zone: PlayerZone | None, spot: int | None = None
) -> OwnedPokemon:
    """
    Send a Pokémon to work in `zone`, on `spot` if it is free (else the
    first free one), or free it (zone=None).

    The only function that changes a Pokémon's status. The zones it leaves
    and joins are collected first: what was earned at the old rate is paid
    before the team changes (and a leaving Pokémon gets its experience).
    """
    pokemon = OwnedPokemon.objects.select_for_update().get(pk=pokemon.pk)
    if zone is not None and zone.player_id != pokemon.player_id:
        raise ZoneError("This zone belongs to another player.")
    if pokemon.zone_id == (zone.pk if zone else None):
        return pokemon  # already there: nothing to do

    if zone is not None:
        zone = PlayerZone.objects.select_for_update().get(pk=zone.pk)
        taken = set(zone.workers.values_list("spot", flat=True))
        free_spots = [s for s in range(zone.capacity) if s not in taken]
        if not free_spots:
            raise ZoneError(f"The {zone.spec.name} is full.")
        if spot not in free_spots:
            spot = free_spots[0]
        collect(zone)
    if pokemon.zone_id is not None:
        collect(pokemon.zone)
        pokemon.refresh_from_db()  # the collection may have changed its level

    pokemon.zone = zone
    pokemon.spot = spot if zone else None
    pokemon.status = OwnedPokemon.IN_ZONE if zone else OwnedPokemon.FREE
    pokemon.save(update_fields=["zone", "spot", "status"])
    return pokemon


# --- Feeder ----------------------------------------------------------------------


@transaction.atomic
def fill_feeder(player: Player, resource: str, units: int) -> None:
    """
    Fill a free slot of the feeder with `units` of a resource, from the stock.

    The resource must come from a zone the player has. A slot holds 1 to
    balance.FEEDER_MAX_UNITS units (one point of chance each): more would
    add nothing.
    """
    if not 1 <= units <= player.feeder_max_units:
        raise ZoneError(f"A slot holds 1 to {player.feeder_max_units} units.")
    zone = ZONE_OF_RESOURCE.get(resource)
    if zone is None or not player.zones.filter(zone=zone.slug).exists():
        raise ZoneError("This resource doesn't come from one of your zones.")

    player = Player.objects.select_for_update().get(pk=player.pk)
    if len(player.feeder) >= player.feeder_capacity:
        raise ZoneError("No free slot: wait until a Pokémon eats one, or take one back.")
    # The stock only goes down if there is enough: the condition is checked by
    # the database itself, in the same UPDATE
    taken = ResourceStock.objects.filter(
        player=player, resource=resource, amount__gte=units
    ).update(amount=F("amount") - units)
    if not taken:
        raise ZoneError(f"Not enough {zone.resource_plural.lower()}.")
    player.feeder = [*player.feeder, [resource, units]]
    player.save(update_fields=["feeder"])


@transaction.atomic
def take_back_slot(player: Player, index: int) -> None:
    """Take back a slot of the feeder: its units return to the stock."""
    player = Player.objects.select_for_update().get(pk=player.pk)
    if not 0 <= index < len(player.feeder):
        raise ZoneError("This slot is already empty.")
    resource, units = player.feeder[index]
    add_resource(player, resource, units)
    player.feeder = [slot for i, slot in enumerate(player.feeder) if i != index]
    player.save(update_fields=["feeder"])
