"""Operations on the player's game state, used by the views."""

import random
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from game import balance
from game.arrivals import NATURES, CatchUp, catch_up
from game.clock import floor_to_hour
from game.collection import Obtention, OwnedState, resolve_obtention
from pokedex.models import Species

from .models import Arrival, CandyStock, OwnedPokemon, Player


def ensure_player(user) -> Player:
    """
    The game save of `user`, created on first use with the three starters.

    A new save starts at the current hour: arrivals begin with the next one.
    """
    with transaction.atomic():  # the save and its starters, or nothing
        player, created = Player.objects.get_or_create(
            user=user, defaults={"last_slot": floor_to_hour(timezone.now())}
        )
        if created:
            give_starters(player)
    return player


def seeded_rng(player: Player, purpose: str) -> random.Random:
    """A generator dedicated to one player and one purpose: same draws every time."""
    return random.Random(f"{purpose}:{player.pk}")


def give_starters(player: Player) -> None:
    """The three Kanto starters, with a nature drawn from the player's own seed."""
    rng = seeded_rng(player, "starters")
    for species in Species.objects.filter(slug__in=balance.STARTER_SPECIES).order_by("number"):
        receive_pokemon(player, species, nature=rng.choice(NATURES), is_shiny=False)


@transaction.atomic
def receive_pokemon(player: Player, species: Species, *, nature: str, is_shiny: bool) -> Obtention:
    """
    The single entry point for obtaining a Pokémon (starter, arrival, gift...).

    The game rule lives in game.collection.resolve_obtention; this function
    loads the current state, asks the rule, and saves its outcome.
    """
    # select_for_update locks the row until the end of the transaction, so two
    # simultaneous requests can't both convert the same catch
    owned = OwnedPokemon.objects.select_for_update().filter(player=player, species=species).first()
    state = OwnedState(frozenset(owned.unlocked_natures), owned.shiny_unlocked) if owned else None
    outcome = resolve_obtention(state, species.rarity, nature, is_shiny)

    if outcome.is_new:
        OwnedPokemon.objects.create(
            player=player,
            species=species,
            level=species.min_level,
            unlocked_natures=[nature],
            shiny_unlocked=is_shiny,
        )
        return outcome

    if outcome.new_nature:
        owned.unlocked_natures = sorted([*owned.unlocked_natures, outcome.new_nature])
    owned.shiny_unlocked = owned.shiny_unlocked or outcome.new_shiny
    owned.save(update_fields=["unlocked_natures", "shiny_unlocked"])

    stock, _ = CandyStock.objects.get_or_create(player=player, family=species.evolution_chain)
    # F() makes the database do the addition: no lost update if two requests race
    CandyStock.objects.filter(pk=stock.pk).update(amount=F("amount") + outcome.candies)
    return outcome


def catch_up_player(player: Player, now=None) -> CatchUp:
    """
    Replay the hours elapsed since the player's last visit.

    The game rules run in game.arrivals.catch_up (pure Python); this function
    loads what they need, then saves the new arrivals and the new clock.
    """
    now = now or timezone.now()
    with transaction.atomic():
        # Lock the player's row: a second request arriving at the same moment
        # waits here, then finds the clock already moved and replays nothing
        locked = Player.objects.select_for_update().get(pk=player.pk)
        available = list(Species.objects.filter(is_available=True))
        result = catch_up(
            player_id=locked.pk,
            rules=[species.to_rule() for species in available],
            last_slot=locked.last_slot,
            now=now,
            free_places=max(locked.welcome_capacity - locked.arrivals.count(), 0),
        )
        species_by_slug = {species.slug: species for species in available}
        Arrival.objects.bulk_create(
            Arrival(
                player=locked,
                species=species_by_slug[arrival.slug],
                slot=arrival.slot,
                nature=arrival.nature,
                is_shiny=arrival.is_shiny,
            )
            for arrival in result.arrivals
        )
        locked.last_slot = result.last_slot
        locked.save(update_fields=["last_slot"])
    player.last_slot = result.last_slot  # keep the caller's object in sync
    return result


def mark_seen(player: Player) -> None:
    """Record a visit (one small UPDATE, without reloading the player)."""
    player.last_seen_at = timezone.now()
    Player.objects.filter(pk=player.pk).update(last_seen_at=player.last_seen_at)


def inactive_guests(days: int):
    """
    Guest users who haven't played for `days` days.

    A guest's password starts with Django's "unusable" marker. Registered
    players and staff are never selected, however long their absence.
    A guest without a save (none created yet) is judged on its sign-up date.
    """
    cutoff = timezone.now() - timedelta(days=days)
    return get_user_model().objects.filter(
        Q(player__last_seen_at__lt=cutoff) | Q(player__isnull=True, date_joined__lt=cutoff),
        password__startswith=UNUSABLE_PASSWORD_PREFIX,
        is_staff=False,
    )


@dataclass(frozen=True)
class Reveal:
    """A Pokémon taken from the Welcome area, and what its catch brought."""

    species: Species
    nature: str
    is_shiny: bool
    outcome: Obtention


def _reveal(player: Player, arrival: Arrival) -> Reveal:
    outcome = receive_pokemon(
        player, arrival.species, nature=arrival.nature, is_shiny=arrival.is_shiny
    )
    arrival.delete()
    return Reveal(arrival.species, arrival.nature, arrival.is_shiny, outcome)


# What a reveal shows of a species (its types, its family for the candies), loaded
# in the same query as the arrival. The lock only takes the arrival rows
# (of=("self",)): PostgreSQL refuses FOR UPDATE on the nullable side of an
# outer join, which the optional secondary type needs.
REVEAL_RELATED = (
    "species__evolution_chain",
    "species__primary_type",
    "species__secondary_type",
)


@transaction.atomic
def reveal_next(player: Player) -> Reveal | None:
    """Reveal the oldest waiting arrival (None if the Welcome area is empty)."""
    arrival = (
        player.arrivals.select_for_update(of=("self",)).select_related(*REVEAL_RELATED).first()
    )
    return _reveal(player, arrival) if arrival else None


@transaction.atomic
def reveal_all(player: Player) -> list[Reveal]:
    """Reveal every waiting arrival at once, oldest first."""
    arrivals = player.arrivals.select_for_update(of=("self",)).select_related(*REVEAL_RELATED)
    return [_reveal(player, arrival) for arrival in arrivals]


def player_for(user) -> Player | None:
    """The save of `user` if there is one. Unlike ensure_player, never creates it."""
    if not user.is_authenticated:
        return None
    return Player.objects.filter(user=user).first()


def collection_of(player: Player) -> dict[int, OwnedPokemon]:
    """The player's Pokémon, indexed by species id (for the Pokédex)."""
    return {owned.species_id: owned for owned in player.pokemon.all()}


def candies_of(player: Player, family) -> int:
    """Candies of one evolution family (0 if none yet)."""
    stock = CandyStock.objects.filter(player=player, family=family).first()
    return stock.amount if stock else 0
