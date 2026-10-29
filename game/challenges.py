"""
The challenges of the research Pokédex: what each species asks to reach its
stages 2 and 3.

Every species gets the same generic challenges (obtain it, raise it, unlock
its natures, make it work...), scaled to its rarity and level. Its data file
may add challenges of its own ("obtain a shiny one"), or skip generic ones
that make no sense for it:

    "challenges": {
        "add": [{"id": "shiny", "event": "obtained", "filters": {"shiny": true}, "target": 1}],
        "skip": ["family"]
    }

Each challenge is an objective of game.objectives, with a text for the
Pokédex entry.
"""

from dataclasses import dataclass
from typing import Any

from . import balance
from .objectives import (
    FAMILY,
    HARVESTED,
    LEVEL,
    NATURES,
    OBTAINED,
    WORKED,
    Objective,
)
from .zones import ZONES

NATURE_COUNT = 6

# The details a custom challenge may filter on, for each event. The species
# (or its family) is always added: a challenge only counts its own species.
ALLOWED_FILTERS = {
    OBTAINED: {"shiny"},
    LEVEL: set(),
    NATURES: set(),
    FAMILY: set(),
    HARVESTED: {"zone", "resource"},
    WORKED: {"zone"},
}


class ChallengeError(ValueError):
    """Raised when a custom challenge of a species file is malformed."""


@dataclass(frozen=True)
class ChallengeSpecies:
    """What the challenges of a species depend on."""

    slug: str
    rarity: str
    min_level: int
    family: str  # identifies its evolution family (the same for all its members)
    family_size: int  # species in the family (1: no family challenge)


@dataclass(frozen=True)
class Challenge:
    id: str  # "obtain-2": unique within the species, used by "skip"
    objective: Objective
    text: str  # shown on the Pokédex entry


def objective_key(slug: str, challenge_id: str) -> str:
    """The key of a species' challenge in the player's progress."""
    return f"dex:{slug}:{challenge_id}"


def describe(event: str, target: int, filters: dict[str, Any]) -> str:
    """The English text of a challenge, e.g. "Obtain it 5 times"."""
    zone = f" in the {ZONES[filters['zone']].name}" if filters.get("zone") in ZONES else ""
    if event == OBTAINED:
        what = "a shiny one" if filters.get("shiny") else "it"
        return f"Obtain {what} once" if target == 1 else f"Obtain {what} {target} times"
    if event == LEVEL:
        return f"Reach level {target}"
    if event == NATURES:
        return "Unlock all 6 natures" if target >= NATURE_COUNT else f"Unlock {target} natures"
    if event == FAMILY:
        return "Own its whole family"
    if event == HARVESTED:
        return f"Gather {target // 100} resources{zone}"  # counted in hundredths
    if event == WORKED:
        return f"Work {target} hours{zone or ' in a zone'}"
    raise ChallengeError(f"Unknown event {event!r}")


def _challenge(species: ChallengeSpecies, challenge_id: str, event: str, target: int, filters=None):
    own = {"family": species.family} if event == FAMILY else {"species": species.slug}
    filters = {**(filters or {}), **own}
    return Challenge(
        id=challenge_id,
        objective=Objective(objective_key(species.slug, challenge_id), event, target, filters),
        text=describe(event, target, filters),
    )


def level_targets(min_level: int) -> list[int]:
    """The levels to reach: a few levels above its arrival level, rounded up to 5."""
    targets = []
    for offset in balance.CHALLENGE_LEVEL_OFFSETS:
        level = -(-(min_level + offset) // 5) * 5  # rounded up to a multiple of 5
        targets.append(min(level, 100))
    return targets


def generic_challenges(species: ChallengeSpecies) -> list[Challenge]:
    """The challenges every species has (8 to 10, depending on its family)."""
    challenges = [
        _challenge(species, f"obtain-{tier}", OBTAINED, times)
        for tier, times in enumerate(balance.CHALLENGE_OBTAIN_TIERS[species.rarity], start=1)
    ]
    challenges += [
        _challenge(species, f"level-{tier}", LEVEL, level)
        for tier, level in enumerate(level_targets(species.min_level), start=1)
    ]
    challenges += [
        _challenge(species, f"natures-{count}", NATURES, count)
        for count in balance.CHALLENGE_NATURE_TIERS
    ]
    challenges.append(
        _challenge(species, "harvest", HARVESTED, balance.CHALLENGE_HARVEST_RESOURCES * 100)
    )
    challenges.append(_challenge(species, "work", WORKED, balance.CHALLENGE_WORK_HOURS))
    if species.family_size > 1:
        challenges.append(_challenge(species, "family", FAMILY, species.family_size))
    return challenges


def validate_custom(raw: Any) -> None:
    """Check the "challenges" value of a species file (used when loading data)."""
    if not isinstance(raw, dict) or not raw.keys() <= {"add", "skip"}:
        raise ChallengeError('challenges must be {"add": [...], "skip": [...]}')
    for item in raw.get("add", []):
        if not isinstance(item, dict) or not item.keys() <= {"id", "event", "target", "filters"}:
            raise ChallengeError(f"a challenge has id, event, target and filters, got {item!r}")
        if not isinstance(item.get("id"), str) or not item["id"]:
            raise ChallengeError(f"a challenge needs an id, got {item!r}")
        event = item.get("event")
        if event not in ALLOWED_FILTERS:
            raise ChallengeError(f"event must be one of {sorted(ALLOWED_FILTERS)}, got {event!r}")
        target = item.get("target")
        if not isinstance(target, int) or isinstance(target, bool) or target < 1:
            raise ChallengeError(f"target must be a positive integer, got {target!r}")
        if unknown := set(item.get("filters", {})) - ALLOWED_FILTERS[event]:
            raise ChallengeError(f"{event} challenges can't filter on {sorted(unknown)}")
        zone = item.get("filters", {}).get("zone")
        if zone is not None and zone not in ZONES:
            raise ChallengeError(f"unknown zone {zone!r}")
    if not all(isinstance(skipped, str) for skipped in raw.get("skip", [])):
        raise ChallengeError("skip lists the ids of generic challenges")


def challenges_for(species: ChallengeSpecies, custom: dict | None = None) -> list[Challenge]:
    """All the challenges of a species: the generic ones (minus skipped), then its own."""
    custom = custom or {}
    skipped = set(custom.get("skip", []))
    generic = generic_challenges(species)
    if unknown := skipped - {challenge.id for challenge in generic}:
        raise ChallengeError(f"{species.slug}: no generic challenge {sorted(unknown)} to skip")
    challenges = [challenge for challenge in generic if challenge.id not in skipped]
    for item in custom.get("add", []):
        if any(challenge.id == item["id"] for challenge in challenges):
            raise ChallengeError(f"{species.slug}: two challenges are called {item['id']!r}")
        challenges.append(
            _challenge(species, item["id"], item["event"], item["target"], item.get("filters"))
        )
    return challenges


def stage(owned: bool, completed: int, total: int) -> int:
    """
    The research stage of a species: 0 unknown, 1 met (obtained once),
    2 studied (a few challenges done), 3 mastered (all of them).
    """
    if not owned:
        return 0
    if total and completed >= total:
        return 3
    if completed >= balance.STAGE_2_CHALLENGES:
        return 2
    return 1


def challenge_points(rarity: str) -> int:
    """Research points earned by completing one challenge of a species."""
    return balance.RESEARCH_POINTS_PER_CHALLENGE[rarity]
