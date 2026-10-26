"""
Condition engine: evaluates the arrival conditions of a species.

A condition is a JSON tree, stored in each species data file:

    {"all": [cond, ...]}   AND: every sub-condition is true (empty -> true)
    {"any": [cond, ...]}   OR: at least one sub-condition is true
    {"not": cond}          NOT
    {"time_of_day": "night"}             a leaf: one simple condition

Example: "only at night" -> {"time_of_day": "night"}

Leaves are declared in the LEAVES registry below: supporting a new kind of
condition (berry in the feeder, zone level...) only means adding an entry.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from . import clock

COMBINATORS = ("all", "any", "not")


class ConditionError(ValueError):
    """Raised when a condition tree is malformed."""


@dataclass(frozen=True)
class GameContext:
    """
    Everything a condition may look at, for one hourly slot.

    Frozen (immutable): evaluating conditions can never change the game state.
    It will grow with the game (owned species, zones, feeder...).
    """

    slot: datetime

    @property
    def time_of_day(self) -> str:
        return clock.time_of_day(self.slot)


@dataclass(frozen=True)
class Leaf:
    """A kind of simple condition: how to check it, and how to validate its value."""

    check: Callable[[Any, GameContext], bool]
    validate: Callable[[Any], None]


def _validate_time_of_day(value: Any) -> None:
    if value not in ("day", "night"):
        raise ConditionError(f'time_of_day must be "day" or "night", got {value!r}')


LEAVES: dict[str, Leaf] = {
    "time_of_day": Leaf(
        check=lambda value, context: context.time_of_day == value,
        validate=_validate_time_of_day,
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
