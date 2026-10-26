"""
Hourly arrivals: which species may come, which one comes, and the catch-up.

Every hour, one Pokémon shows up at the ranch. The game lists the species
whose conditions hold at that hour, draws one weighted by rarity, then rolls
its nature and shiny status. All randomness comes from the slot's seeded
generator, so the outcome of an hour never depends on when it is computed.
"""

import random
from dataclasses import dataclass
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


def draw_arrival(
    rules: list[SpeciesRule], context: GameContext, rng: random.Random
) -> Arrival | None:
    """Draw the arrival of one slot, or None if no species is eligible."""
    candidates = eligible_species(rules, context)
    if not candidates:
        return None
    weights = [balance.RARITY_WEIGHTS[rule.rarity] for rule in candidates]
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


def catch_up(
    player_id: int,
    rules: list[SpeciesRule],
    last_slot: datetime,
    now: datetime,
    free_places: int,
) -> CatchUp:
    """
    Replay every hour since `last_slot`, in chronological order.

    Arrivals fill the free places of the Welcome area. Once it is full, the
    following arrivals are lost (the offline cap): nothing else can change
    while the player is away, so the loop stops and only counts the hours
    left. The last processed slot is always the current hour.
    """
    slots = list(clock.slots_after(last_slot, now))
    arrivals: list[Arrival] = []
    hours_while_full = 0
    for index, slot in enumerate(slots):
        if len(arrivals) >= free_places:
            hours_while_full = len(slots) - index
            break
        arrival = draw_arrival(rules, GameContext(slot=slot), clock.slot_rng(player_id, slot))
        if arrival is not None:
            arrivals.append(arrival)
    return CatchUp(
        arrivals=arrivals,
        last_slot=max(clock.floor_to_hour(now), last_slot),
        hours_while_full=hours_while_full,
    )
