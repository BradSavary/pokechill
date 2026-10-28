"""
Hourly arrivals: which species may come, which one comes, and the catch-up.

Every hour, one Pokémon shows up at the ranch. The game lists the species
whose conditions hold at that hour, draws one weighted by rarity (and by the
feeder, which favours some types), then rolls its nature and shiny status.
All randomness comes from the slot's seeded generator, so the outcome of an
hour never depends on when it is computed.
"""

import random
from dataclasses import dataclass, field
from datetime import datetime

from . import balance, clock
from .conditions import GameContext, evaluate

# The six natures, one per stat. Each unlocks a bonus once per species.
NATURES = ("hp", "attack", "defense", "special_attack", "special_defense", "speed")


@dataclass(frozen=True)
class SpeciesRule:
    """What the engine needs to know about a species (loaded from its data file)."""

    slug: str
    rarity: str
    conditions: dict | None = None
    types: tuple[str, ...] = ()  # for the feeder bonus


@dataclass(frozen=True)
class Arrival:
    """A Pokémon that showed up at a given slot."""

    slot: datetime
    slug: str
    nature: str
    is_shiny: bool


def eligible_species(rules: list[SpeciesRule], context: GameContext) -> list[SpeciesRule]:
    """
    Species whose conditions hold in this context.

    Sorted by slug: the draw must not depend on the order of the input list
    (e.g. database order), otherwise the same seed could pick another species.
    """
    candidates = [rule for rule in rules if evaluate(rule.conditions, context)]
    return sorted(candidates, key=lambda rule: rule.slug)


def weight(rule: SpeciesRule, context: GameContext) -> float:
    """Weight of a species in the draw: its rarity, times the feeder bonus if it attracts it."""
    attracted = not context.attracted_types.isdisjoint(rule.types)
    bonus = balance.FEEDER_WEIGHT_MULTIPLIER if attracted else 1
    return balance.RARITY_WEIGHTS[rule.rarity] * bonus


def draw_arrival(
    rules: list[SpeciesRule], context: GameContext, rng: random.Random
) -> Arrival | None:
    """Draw the arrival of one slot, or None if no species is eligible."""
    candidates = eligible_species(rules, context)
    if not candidates:
        return None
    weights = [weight(rule, context) for rule in candidates]
    # The random calls always happen in the same order: species, nature, shiny
    chosen = rng.choices(candidates, weights=weights)[0]
    nature = rng.choice(NATURES)
    is_shiny = rng.randrange(balance.SHINY_ODDS) == 0
    return Arrival(slot=context.slot, slug=chosen.slug, nature=nature, is_shiny=is_shiny)


@dataclass(frozen=True)
class CatchUp:
    """Result of a catch-up."""

    arrivals: list[Arrival]
    last_slot: datetime  # the current hour: the next catch-up starts after it
    # Hours replayed while the Welcome area was full: their arrivals are lost
    hours_while_full: int = 0
    # What is left in the feeder: resource -> quantity (emptied ones removed)
    feeder: dict[str, int] = field(default_factory=dict)


def catch_up(
    player_id: int,
    rules: list[SpeciesRule],
    last_slot: datetime,
    now: datetime,
    free_places: int,
    feeder: dict[str, int] | None = None,
    owned: frozenset[str] = frozenset(),
    occupied_zones: frozenset[str] = frozenset(),
) -> CatchUp:
    """
    Replay every hour since `last_slot`, in chronological order.

    `feeder` (resource -> quantity), `owned` and `occupied_zones` describe the
    ranch as the player left it. Only the feeder changes along the way: each
    arrival eats some of it, which may end its bonus for the following hours.
    That is why the hours are replayed in order.

    Arrivals fill the free places of the Welcome area. Once it is full, the
    following arrivals are lost (the offline cap): nobody comes to eat any
    more, nothing else changes in the arrivals, so the loop stops and only
    counts the hours left. The zones' work is computed apart (game.zones).
    The last processed slot is always the current hour.
    """
    feeder = {resource: quantity for resource, quantity in (feeder or {}).items() if quantity > 0}
    slots = list(clock.slots_after(last_slot, now))
    arrivals: list[Arrival] = []
    hours_while_full = 0
    for index, slot in enumerate(slots):
        if len(arrivals) >= free_places:
            hours_while_full = len(slots) - index
            break
        context = GameContext(
            slot=slot, feeder=frozenset(feeder), owned=owned, occupied_zones=occupied_zones
        )
        arrival = draw_arrival(rules, context, clock.slot_rng(player_id, slot))
        if arrival is not None:
            arrivals.append(arrival)
            feeder = eat(feeder)
    return CatchUp(
        arrivals=arrivals,
        last_slot=max(clock.floor_to_hour(now), last_slot),
        hours_while_full=hours_while_full,
        feeder=feeder,
    )


def eat(feeder: dict[str, int]) -> dict[str, int]:
    """The feeder after one arrival: a bit less of every resource (empty ones go)."""
    after = {r: q - balance.FEEDER_CONSUMPTION_PER_ARRIVAL for r, q in feeder.items()}
    return {resource: quantity for resource, quantity in after.items() if quantity > 0}
