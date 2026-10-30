"""
The research of the player: Pokédex challenges, stages and research points.

The rules live in the pure engine (game.objectives, game.challenges). This
module loads what they need and saves the progress. The rewards are not
given at once: the player claims them on the Pokédex entry, to see what
each one brings.

    something happens in the game (a Pokémon obtained, a zone's work...)
      └─▶ record(player, events)                            [transaction]
            ├─ the challenges of the species concerned (from their data)
            ├─ game.objectives.apply: the new progress
            └─ a challenge completed: the "!" of rewards to claim

    the player clicks "Claim" on the Pokédex entry
      └─▶ claim(player, species, what)                       [transaction]
            ├─ a challenge: its research points
            ├─ a stage reached: its reward (points, candies, mastery)
            └─ the "!" is recomputed

The challenges are never stored: they are rebuilt from the species data.
Only the progress is (ObjectiveProgress, one row per challenge that moved).
"""

from collections import Counter
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from game import balance
from game.challenges import Challenge, challenge_points, challenges_for, stage
from game.objectives import FAMILY, HARVESTED, LEVEL, NATURES, OBTAINED, WORKED, Event, apply
from pokedex.models import Species

from .models import CandyStock, ObjectiveProgress, OwnedPokemon, Player

STAGE_NAMES = {0: "Unknown", 1: "Encountered", 2: "Studied", 3: "Mastered"}


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


def in_game(species: Species) -> bool:
    """Only the species of the game (with a data file) have challenges."""
    return species.is_available and bool(species.rarity)


# --- Progress: fed by the events of the game -----------------------------------------


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
def record(player: Player, events) -> list[str]:
    """Feed game events to the player's challenges. Returns the keys they completed."""
    events = list(events)
    species_list = _concerned_species(events) if events else []
    if not species_list:
        return []
    challenges = challenges_of(species_list)
    objectives = [challenge.objective for found in challenges.values() for challenge in found]

    # Lock the rows: two requests at once can't both write the same progress
    rows = {
        row.key: row
        for row in ObjectiveProgress.objects.select_for_update().filter(
            player=player, key__in=[objective.key for objective in objectives]
        )
    }
    changed, _ = apply(objectives, {key: row.progress for key, row in rows.items()}, events)

    now = timezone.now()
    targets = {objective.key: objective.target for objective in objectives}
    new_rows, updated_rows, newly_done = [], [], []
    for key, progress in changed.items():
        row = rows.get(key)
        if row is None:
            row = rows[key] = ObjectiveProgress(player=player, key=key)
            new_rows.append(row)
        else:
            updated_rows.append(row)
        row.progress = progress
        # Completed once: a challenge done before (then raised by a data
        # change) keeps its date, and its reward is never claimed twice
        if progress >= targets[key] and row.completed_at is None:
            row.completed_at = now
            newly_done.append(key)
    ObjectiveProgress.objects.bulk_create(new_rows)
    ObjectiveProgress.objects.bulk_update(updated_rows, ["progress", "completed_at"])

    # A reward to claim: a challenge completed, or a new species (its stage 1).
    # FAMILY events only come with a new species (and when a save is set up).
    new_species = any(event.kind == FAMILY for event in events)
    if newly_done or new_species:
        Player.objects.filter(pk=player.pk).update(has_rewards=True)
        player.has_rewards = True
    return newly_done


# --- What the research of a species stands at -----------------------------------------


@dataclass(frozen=True)
class StageReward:
    stage: int
    at: int  # challenges completed to reach it
    points: int
    candies: int = 0
    mastery: bool = False  # stage 3: the species' mastery bonuses


def stage_rewards(total: int) -> list[StageReward]:
    """The rewards of the three stages of a species with `total` challenges."""
    return [
        StageReward(1, 0, balance.STAGE_1_RESEARCH_POINTS),
        StageReward(
            2, balance.STAGE_2_CHALLENGES, balance.STAGE_2_RESEARCH_POINTS, balance.STAGE_2_CANDIES
        ),
        StageReward(3, total, 0, mastery=True),
    ]


@dataclass
class SpeciesResearch:
    """The research of one species for a player: challenges, rows, stages."""

    species: Species
    owned: OwnedPokemon | None
    challenges: list[Challenge]
    rows: dict[str, ObjectiveProgress]  # by objective key (missing: no progress yet)

    def progress(self, challenge: Challenge) -> int:
        row = self.rows.get(challenge.objective.key)
        return row.progress if row else 0

    def is_done(self, challenge: Challenge) -> bool:
        return self.progress(challenge) >= challenge.objective.target

    def is_claimed(self, challenge: Challenge) -> bool:
        row = self.rows.get(challenge.objective.key)
        return bool(row and row.claimed_at)

    @property
    def done(self) -> int:
        return sum(self.is_done(challenge) for challenge in self.challenges)

    @property
    def claimed(self) -> int:
        return sum(self.is_claimed(challenge) for challenge in self.challenges)

    @property
    def reached(self) -> int:
        """
        The stage reached: counted on the challenges claimed, so that claiming
        one moves the bar of the stages (the player sees it fill up).
        """
        return stage(self.owned is not None, self.claimed, len(self.challenges))

    @property
    def claimed_stage(self) -> int:
        """The last stage whose reward was claimed."""
        return self.owned.research_stage if self.owned else 0

    def to_claim(self) -> list[Challenge]:
        """Challenges completed whose points wait to be claimed."""
        return [c for c in self.challenges if self.is_done(c) and not self.is_claimed(c)]

    @property
    def has_rewards(self) -> bool:
        return self.owned is not None and (
            bool(self.to_claim()) or self.reached > self.claimed_stage
        )


def with_bonus(player: Player, points: int) -> int:
    """Research points as claimed: the skill tree's bonus included."""
    return points * (100 + player.skill_bonuses.research_percent) // 100


def research_of(player: Player, owned_list: list[OwnedPokemon], *, lock=False):
    """
    The research of the player's species (by species id), in two queries:
    the family sizes, then the progress rows of their challenges.
    """
    species_list = [pokemon.species for pokemon in owned_list if in_game(pokemon.species)]
    challenges = challenges_of(species_list)
    keys = [c.objective.key for found in challenges.values() for c in found]
    rows = ObjectiveProgress.objects.filter(player=player, key__in=keys)
    if lock:
        rows = rows.select_for_update()
    rows = {row.key: row for row in rows}
    owned = {pokemon.species_id: pokemon for pokemon in owned_list}
    return {
        species.id: SpeciesResearch(species, owned[species.id], challenges[species.id], rows)
        for species in species_list
    }


def species_with_rewards(player: Player, collection: dict[int, OwnedPokemon]) -> set[int]:
    """
    The ids of the species with rewards to claim (the "!" of the list).
    Free most of the time: nothing is computed when the player has none.
    """
    if not player.has_rewards:
        return set()
    research = research_of(player, list(collection.values()))
    return {species_id for species_id, found in research.items() if found.has_rewards}


# --- Claiming the rewards ------------------------------------------------------------


class ClaimError(ValueError):
    """Nothing to claim there (already claimed, not completed yet...)."""


@dataclass
class Claimed:
    """What a claim gave: shown to the player."""

    points: int = 0
    candies: int = 0
    stages: tuple[int, ...] = ()


@transaction.atomic
def claim(player: Player, species: Species, what: str) -> Claimed:
    """
    Claim a reward of a species: `what` is a challenge id ("obtain-10"),
    "stage" (the next stage reached), or "all" (everything waiting).
    """
    locked = Player.objects.select_for_update().get(pk=player.pk)
    owned = (
        OwnedPokemon.objects.select_for_update()
        .select_related("species")
        .filter(player=locked, species=species)
        .first()
    )
    if owned is None or not in_game(species):
        raise ClaimError("You don't own this Pokémon.")
    research = research_of(locked, [owned], lock=True)[species.id]
    now, claimed = timezone.now(), Claimed()

    challenges = research.to_claim()
    if what not in ("all", "stage"):
        challenges = [c for c in challenges if c.id == what]
        if not challenges:
            raise ClaimError("Nothing to claim for this challenge.")
    if what != "stage":
        for challenge in challenges:
            row = research.rows[challenge.objective.key]
            row.claimed_at = now
            row.save(update_fields=["claimed_at"])
            claimed.points += with_bonus(locked, challenge_points(species.rarity))

    if what in ("all", "stage"):
        rewards = {reward.stage: reward for reward in stage_rewards(len(research.challenges))}
        reached = research.reached
        if what == "stage" and reached <= owned.research_stage:
            raise ClaimError("No stage to claim yet.")
        while owned.research_stage < reached:
            owned.research_stage += 1
            reward = rewards[owned.research_stage]
            claimed.points += with_bonus(locked, reward.points)
            claimed.candies += reward.candies
            claimed.stages += (owned.research_stage,)
            if what == "stage":
                break  # one stage at a time
        owned.save(update_fields=["research_stage"])
        if claimed.candies:
            _add_candies(locked, species, claimed.candies)

    Player.objects.filter(pk=locked.pk).update(
        research_points=F("research_points") + claimed.points
    )
    refresh_rewards(locked)
    return claimed


def refresh_rewards(player: Player) -> None:
    """Recompute the "!" of the Pokédex menu: are there rewards left to claim?"""
    owned = list(player.pokemon.select_related("species"))
    waiting = any(found.has_rewards for found in research_of(player, owned).values())
    Player.objects.filter(pk=player.pk).update(has_rewards=waiting)
    player.has_rewards = waiting


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
    # The caller's object sees the rewards waiting, for the "!" of this page
    player.refresh_from_db(fields=["research_synced", "has_rewards"])


# --- The research part of a Pokédex entry ------------------------------------------------


def entry_research(player: Player | None, species: Species, owned: OwnedPokemon | None) -> dict:
    """
    The research part of a Pokédex entry: its challenges with the player's
    progress and what waits to be claimed, and the bar of its stages. A
    visitor (no save) sees the challenges only.
    """
    if not in_game(species):
        return {"challenges": [], "stage": 0, "stage_name": STAGE_NAMES[0]}
    if player is not None and owned is not None:
        owned.species = species
        research = research_of(player, [owned])[species.id]
    else:
        research = SpeciesResearch(species, None, challenges_of([species])[species.id], {})

    rows = []
    for challenge in research.challenges:
        objective = challenge.objective
        done = research.progress(challenge)
        # Resources are counted in hundredths: shown as whole resources
        scale = 100 if objective.event == HARVESTED else 1
        rows.append(
            {
                "id": challenge.id,
                "text": challenge.text,
                "progress": done // scale,
                "target": objective.target // scale,
                "done": research.is_done(challenge),
                "claimed": research.is_claimed(challenge),
                # Completed, its points not claimed yet (never for a visitor)
                "ready": owned is not None
                and research.is_done(challenge)
                and not research.is_claimed(challenge),
                "percent": 100 * done // objective.target,
                # What claiming it gives (the skill tree's bonus included)
                "points": with_bonus(player, challenge_points(species.rarity))
                if player
                else challenge_points(species.rarity),
            }
        )

    total = len(research.challenges)
    stages = []
    for reward in stage_rewards(total):
        if reward.stage <= research.claimed_stage:
            state = "claimed"
        elif reward.stage <= research.reached and reward.stage == research.claimed_stage + 1:
            state = "ready"  # the next one to claim
        elif reward.stage <= research.reached:
            state = "waiting"  # reached, after the one before is claimed
        else:
            state = "locked"
        stages.append(
            {
                "reward": reward,
                "name": STAGE_NAMES[reward.stage],
                "state": state,
                "position": 100 * reward.at // total if total else 0,
            }
        )
    # An owned species is at stage 1 at least (shown even before its claim)
    shown_stage = research.claimed_stage if owned else 0
    return {
        "challenges": rows,
        "done_count": research.done,
        "claimed_count": research.claimed,
        "total": total,
        # Two columns filled one after the other: the tiers of a challenge follow
        "rows_per_column": -(-total // 2),
        "bar_percent": 100 * research.claimed // total if total else 0,
        "stages": stages,
        "stage": shown_stage,
        "stage_name": STAGE_NAMES[max(shown_stage, 1) if owned else 0],
        "to_claim": len(research.to_claim()) + (research.reached - research.claimed_stage)
        if owned
        else 0,
    }
