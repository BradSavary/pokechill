"""
Condition engine: evaluates the arrival conditions of a species.

A condition is a JSON tree, stored in each species data file:

    {"all": [cond, ...]}   AND: every sub-condition is true (empty -> true)
    {"any": [cond, ...]}   OR: at least one sub-condition is true
    {"not": cond}          NOT
    {"time_of_day": "night"}             a leaf: one simple condition

The leaves:

    {"time_of_day": "day" | "night"}     Paris time (day 6:00-21:00)
    {"feeder": "berry"}                  this resource is in the feeder
    {"owns": "nidoran-f"}                the player owns this species
    {"zone_occupied": "meadow"}          at least one Pokémon works there
    {"works_in": {"species": "paras", "zone": "orchard"}}
                                         this species works in this zone
    {"zone_level": {"zone": "meadow", "level": 2}}
                                         the zone reached this level (skill tree)

Example: "at night, with berries in the feeder" ->
    {"all": [{"time_of_day": "night"}, {"feeder": "berry"}]}

Zones and resources may be planned ones (game.zones.PLANNED_ZONES): the
condition is valid, and never met until that zone is in the game.

Leaves are declared in the LEAVES registry below: supporting a new kind of
condition (day of the week, Pokémon level...) only means adding an entry.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from . import clock
from .zones import KNOWN_RESOURCES, KNOWN_ZONES

COMBINATORS = ("all", "any", "not")


class ConditionError(ValueError):
    """Raised when a condition tree is malformed."""


@dataclass(frozen=True)
class GameContext:
    """
    Everything a condition may look at, for one hourly slot.

    Frozen (immutable): evaluating conditions can never change the game state.
    Only `slot` changes from one hour to the next during a catch-up, with the
    feeder: the rest stays as the player left it.
    """

    slot: datetime
    feeder: frozenset[str] = frozenset()  # resources currently in the feeder (any slot)
    owned: frozenset[str] = frozenset()  # slugs of the species the player owns
    # Who works where: (zone, species slug) pairs, e.g. ("orchard", "paras")
    workers: frozenset[tuple[str, str]] = frozenset()
    # The level of each zone of the player (1 at the start, its skill tree's
    # milestones raise it); a zone the player hasn't got is not there
    zone_levels: Mapping[str, int] = field(default_factory=dict)

    @property
    def time_of_day(self) -> str:
        return clock.time_of_day(self.slot)

    @property
    def occupied_zones(self) -> frozenset[str]:
        """The zones where at least one Pokémon works."""
        return frozenset(zone for zone, _ in self.workers)


@dataclass(frozen=True)
class Leaf:
    """A kind of simple condition: how to check it, and how to validate its value."""

    check: Callable[[Any, GameContext], bool]
    validate: Callable[[Any], None]


def _validate_time_of_day(value: Any) -> None:
    if value not in ("day", "night"):
        raise ConditionError(f'time_of_day must be "day" or "night", got {value!r}')


def _one_of(name: str, allowed) -> Callable[[Any], None]:
    """A validator accepting only the given values (e.g. the known zones)."""

    def check(value: Any) -> None:
        if value not in allowed:
            raise ConditionError(f"{name} must be one of {sorted(allowed)}, got {value!r}")

    return check


def _validate_species_slug(value: Any) -> None:
    if not isinstance(value, str) or not value:
        raise ConditionError(f"owns expects a species slug, got {value!r}")


def _validate_works_in(value: Any) -> None:
    if not isinstance(value, dict) or value.keys() != {"species", "zone"}:
        raise ConditionError(f'works_in expects {{"species": ..., "zone": ...}}, got {value!r}')
    _validate_species_slug(value["species"])
    _one_of("works_in zone", KNOWN_ZONES)(value["zone"])


def _validate_zone_level(value: Any) -> None:
    if not isinstance(value, dict) or value.keys() != {"zone", "level"}:
        raise ConditionError(f'zone_level expects {{"zone": ..., "level": ...}}, got {value!r}')
    _one_of("zone_level zone", KNOWN_ZONES)(value["zone"])
    level = value["level"]
    if not isinstance(level, int) or isinstance(level, bool) or level < 1:
        raise ConditionError(f"zone_level level must be a positive integer, got {level!r}")


LEAVES: dict[str, Leaf] = {
    "time_of_day": Leaf(
        check=lambda value, context: context.time_of_day == value,
        validate=_validate_time_of_day,
    ),
    "feeder": Leaf(
        check=lambda value, context: value in context.feeder,
        validate=_one_of("feeder", KNOWN_RESOURCES),
    ),
    "owns": Leaf(
        check=lambda value, context: value in context.owned,
        validate=_validate_species_slug,
    ),
    "zone_occupied": Leaf(
        check=lambda value, context: value in context.occupied_zones,
        validate=_one_of("zone_occupied", KNOWN_ZONES),
    ),
    "works_in": Leaf(
        check=lambda value, context: (value["zone"], value["species"]) in context.workers,
        validate=_validate_works_in,
    ),
    "zone_level": Leaf(
        check=lambda value, context: context.zone_levels.get(value["zone"], 0) >= value["level"],
        validate=_validate_zone_level,
    ),
}


def _single_key(node: Any) -> tuple[str, Any]:
    """Every node is a one-key dict: {"all": [...]}, {"time_of_day": "day"}..."""
    if not isinstance(node, dict) or len(node) != 1:
        raise ConditionError(f"A condition must be an object with exactly one key, got {node!r}")
    return next(iter(node.items()))


def validate(node: Any) -> None:
    """Check a condition tree without evaluating it (used when loading data files)."""
    key, value = _single_key(node)
    if key in ("all", "any"):
        if not isinstance(value, list):
            raise ConditionError(f'"{key}" expects a list of conditions')
        for child in value:
            validate(child)
    elif key == "not":
        validate(value)
    elif key in LEAVES:
        LEAVES[key].validate(value)
    else:
        raise ConditionError(f"Unknown condition {key!r}")


def evaluate(node: dict | None, context: GameContext) -> bool:
    """True if the condition holds in this context. No condition (None) means always."""
    if node is None:
        return True
    key, value = _single_key(node)
    if key == "all":
        return all(evaluate(child, context) for child in value)
    if key == "any":
        return any(evaluate(child, context) for child in value)
    if key == "not":
        return not evaluate(value, context)
    if key in LEAVES:
        return LEAVES[key].check(value, context)
    raise ConditionError(f"Unknown condition {key!r}")
