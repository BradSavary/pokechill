"""
Objective engine: the Pokédex challenges (and, at step 4, the quests) are
objectives fed by game events.

The game emits an event for each thing that happens: a Pokémon obtained, a
level reached, resources gathered... An objective follows one kind of event,
keeps only those whose details match its filters, and has a target:

    "Obtain Pidgey 5 times"
        Objective(event="obtained", filters={"species": "pidgey"}, target=5)

Its progress is either:
- a SUM: each matching event adds its amount (obtain it 5 times, work 48 h);
- a MAX: the event tells a value reached, the best one counts (reach level 30,
  unlock 6 natures). Sending the same value twice changes nothing, so the
  game can always resend the current state, e.g. to set up an existing save.

The engine is pure: it receives the progress so far and the events, and
returns the new progress. Storing it is the caller's job (ranch).
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

# The events of the game, and their details (what filters can look at)
OBTAINED = "obtained"  # species, shiny ; amount: 1
LEVEL = "level"  # species ; amount: the level reached
NATURES = "natures"  # species ; amount: how many natures are unlocked
FAMILY = "family"  # family ; amount: how many species of the family are owned
HARVESTED = "harvested"  # species, zone, resource ; amount: hundredths gathered
WORKED = "worked"  # species, zone ; amount: hours worked

SUM, MAX = "sum", "max"

# How each event counts: summed, or the best value reached
EVENT_MODES = {
    OBTAINED: SUM,
    LEVEL: MAX,
    NATURES: MAX,
    FAMILY: MAX,
    HARVESTED: SUM,
    WORKED: SUM,
}


def _frozen(mapping: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """A read-only copy: events and objectives never change once made."""
    return MappingProxyType(dict(mapping or {}))


@dataclass(frozen=True)
class Event:
    kind: str
    amount: int = 1
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # object.__setattr__: the way to set a field of a frozen dataclass
        object.__setattr__(self, "details", _frozen(self.details))


@dataclass(frozen=True)
class Objective:
    key: str  # unique for a player, e.g. "dex:pidgey:obtain-2"
    event: str  # the kind of event it follows
    target: int
    filters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "filters", _frozen(self.filters))

    @property
    def mode(self) -> str:
        return EVENT_MODES[self.event]

    def matches(self, event: Event) -> bool:
        """Is this event one the objective counts? Every filter must match."""
        return event.kind == self.event and all(
            event.details.get(name) == value for name, value in self.filters.items()
        )

    def advance(self, progress: int, event: Event) -> int:
        """The progress after `event`, never above the target (done is done)."""
        if not self.matches(event):
            return progress
        value = progress + event.amount if self.mode == SUM else max(progress, event.amount)
        return min(value, self.target)


def apply(
    objectives: Iterable[Objective], progress: Mapping[str, int], events: Iterable[Event]
) -> tuple[dict[str, int], list[str]]:
    """
    Feed events to objectives.

    `progress` maps objective keys to their progress (missing: 0). Returns the
    new progress of the objectives that moved, and the keys of those these
    events completed (in the order of the objectives).
    """
    objectives, events = list(objectives), list(events)
    changed: dict[str, int] = {}
    completed: list[str] = []
    for objective in objectives:
        before = progress.get(objective.key, 0)
        after = before
        for event in events:
            after = objective.advance(after, event)
        if after != before:
            changed[objective.key] = after
            if before < objective.target <= after:
                completed.append(objective.key)
    return changed, completed
