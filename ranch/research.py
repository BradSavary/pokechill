"""
The research of the player: Pokédex challenges, stages and research points.

The rules live in the pure engine (game.objectives, game.challenges). This
module loads what they need, saves the progress, and gives the rewards:

    something happens in the game (a Pokémon obtained, a zone's work...)
      └─▶ record(player, events)                            [transaction]
            ├─ the challenges of the species concerned (from their data)
            ├─ game.objectives.apply: the new progress
            ├─ research points for each challenge completed
            └─ the rewards of each new stage reached (once per species)

The challenges are never stored: they are rebuilt from the species data.
Only the progress is (ObjectiveProgress, one row per challenge that moved).
"""

from collections import Counter
from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from game import balance
from game.challenges import Challenge, challenge_points, challenges_for, stage
from game.objectives import FAMILY, HARVESTED, LEVEL, NATURES, OBTAINED, WORKED, Event, apply
from pokedex.models import Species

from .models import CandyStock, ObjectiveProgress, OwnedPokemon, Player


@dataclass
class ResearchResult:
    """What a batch of events brought: for the messages shown to the player."""

    completed: list[tuple[Species, Challenge]] = field(default_factory=list)
    stage_ups: list[tuple[Species, int]] = field(default_factory=list)  # (species, new stage)
    points: int = 0


def challenges_of(species_list) -> dict[int, list[Challenge]]:
    """The challenges of each species (by id), family sizes counted in one query."""
    chains = {species.evolution_chain_id for species in species_list}
    sizes = dict(
        Species.objects.filter(evolution_chain_id__in=chains)
        .values_list("evolution_chain_id")
        .annotate(size=Count("id"))
    )
    return {
        species.id: challenges_for(
            species.challenge_species(sizes[species.evolution_chain_id]),
            species.custom_challenges,
        )
        for species in species_list
    }


def _concerned_species(events: list[Event]) -> list[Species]:
    """The species whose challenges these events may move (in the game only)."""
    slugs = {event.details["species"] for event in events if "species" in event.details}
    families = {int(event.details["family"]) for event in events if "family" in event.details}
    return list(
        Species.objects.filter(Q(slug__in=slugs) | Q(evolution_chain_id__in=families))
        .filter(is_available=True)
        .exclude(rarity="")
    )


@transaction.atomic
def record(player: Player, events) -> ResearchResult:
    """Feed game events to the player's challenges, and give what they earned."""
    events = list(events)
    result = ResearchResult()
    species_list = _concerned_species(events) if events else []
    if not species_list:
        return result
    challenges = challenges_of(species_list)
    objectives = [challenge.objective for found in challenges.values() for challenge in found]

    # Lock the rows: two requests at once can't both complete (and reward) one
    rows = {
        row.key: row
        for row in ObjectiveProgress.objects.select_for_update().filter(
            player=player, key__in=[objective.key for objective in objectives]
        )
    }
    changed, _ = apply(objectives, {key: row.progress for key, row in rows.items()}, events)

    now = timezone.now()
    targets = {objective.key: objective.target for objective in objectives}
    new_rows, updated_rows, newly_done = [], [], set()
    for key, progress in changed.items():
        row = rows.get(key)
        if row is None:
            row = rows[key] = ObjectiveProgress(player=player, key=key)
            new_rows.append(row)
        else:
            updated_rows.append(row)
        row.progress = progress
        # Rewarded once: a challenge completed before (then raised by a data
        # change) doesn't pay again
        if progress >= targets[key] and row.completed_at is None:
            row.completed_at = now
            newly_done.add(key)
    ObjectiveProgress.objects.bulk_create(new_rows)
    ObjectiveProgress.objects.bulk_update(updated_rows, ["progress", "completed_at"])

    for species in species_list:
        for challenge in challenges[species.id]:
            if challenge.objective.key in newly_done:
                result.completed.append((species, challenge))
                result.points += challenge_points(species.rarity)

    progress = {key: row.progress for key, row in rows.items()}
    _reward_stages(player, species_list, challenges, progress, result)
    if result.points:
        Player.objects.filter(pk=player.pk).update(
            research_points=F("research_points") + result.points
        )
    return result


def _reward_stages(player, species_list, challenges, progress, result: ResearchResult) -> None:
    """Give the rewards of the stages newly reached by the player's species."""
    owned = OwnedPokemon.objects.select_for_update().filter(player=player, species__in=species_list)
    by_id = {species.id: species for species in species_list}
    for pokemon in owned:
        species = by_id[pokemon.species_id]
        found = challenges[species.id]
        done = sum(progress.get(c.objective.key, 0) >= c.objective.target for c in found)
        reached = stage(owned=True, completed=done, total=len(found))
        for new_stage in range(pokemon.research_stage + 1, reached + 1):
            result.stage_ups.append((species, new_stage))
            if new_stage == 1:
                result.points += balance.STAGE_1_RESEARCH_POINTS
            elif new_stage == 2:
                result.points += balance.STAGE_2_RESEARCH_POINTS
                _add_candies(player, species, balance.STAGE_2_CANDIES)
            # Stage 3 gives the species its mastery bonuses (read from the stage)
        if reached > pokemon.research_stage:
            pokemon.research_stage = reached
            pokemon.save(update_fields=["research_stage"])


def _add_candies(player: Player, species: Species, amount: int) -> None:
    stock, _ = CandyStock.objects.get_or_create(player=player, family_id=species.evolution_chain_id)
    CandyStock.objects.filter(pk=stock.pk).update(amount=F("amount") + amount)


# --- The events of the game ------------------------------------------------------------


def obtention_events(pokemon: OwnedPokemon, *, is_new: bool, shiny: bool) -> list[Event]:
    """A Pokémon was obtained (new species or duplicate): what it tells the challenges."""
    slug = pokemon.species.slug
    events = [
        Event(OBTAINED, details={"species": slug, "shiny": shiny}),
        Event(NATURES, len(pokemon.unlocked_natures), {"species": slug}),
    ]
    if is_new:
        family = pokemon.species.evolution_chain_id
        owned_in_family = OwnedPokemon.objects.filter(
            player_id=pokemon.player_id, species__evolution_chain_id=family
        ).count()
        events += [
            Event(LEVEL, pokemon.level, {"species": slug}),
            Event(FAMILY, owned_in_family, {"family": str(family)}),
        ]
    return events


def work_events(zone, workers, done) -> list[Event]:
    """A zone's work (game.zones.Work): hours and resources of each of its workers."""
    events = []
    for pokemon, gathered in zip(workers, done.resources, strict=True):
        details = {"species": pokemon.species.slug, "zone": zone.zone}
        events.append(Event(WORKED, done.hours, details))
        events.append(Event(HARVESTED, gathered, {**details, "resource": zone.spec.resource}))
    return events


def level_event(pokemon: OwnedPokemon) -> Event:
    return Event(LEVEL, pokemon.level, {"species": pokemon.species.slug})


# --- Saves made before the research ----------------------------------------------------


def sync_research(player: Player) -> None:
    """
    Set up the challenges of a save made before the research, from its
    current state: levels, natures, families, and one obtention per species
    owned (the game never counted more). Counters start from zero. Once.
    """
    if player.research_synced:
        return
    with transaction.atomic():
        locked = Player.objects.select_for_update().get(pk=player.pk)
        if not locked.research_synced:
            owned = list(locked.pokemon.select_related("species"))
            per_family = Counter(pokemon.species.evolution_chain_id for pokemon in owned)
            events = []
            for pokemon in owned:
                slug = pokemon.species.slug
                events += [
                    Event(OBTAINED, details={"species": slug, "shiny": pokemon.shiny_unlocked}),
                    Event(LEVEL, pokemon.level, {"species": slug}),
                    Event(NATURES, len(pokemon.unlocked_natures), {"species": slug}),
                ]
            events += [
                Event(FAMILY, count, {"family": str(family)})
                for family, count in per_family.items()
            ]
            record(locked, events)
            locked.research_synced = True
            locked.save(update_fields=["research_synced"])
    player.research_synced = True
