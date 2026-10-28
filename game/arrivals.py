"""
Hourly arrivals: which species may come, which one comes, and the catch-up.

Every hour, one Pokémon shows up at the ranch. The game lists the species
whose conditions hold at that hour, draws one weighted by rarity (the feeder
may raise the chance of some types), then rolls its nature and shiny status.
All randomness comes from the slot's seeded generator, so the outcome of an
hour never depends on when it is computed.
"""

import random
from dataclasses import dataclass, field
from datetime import datetime

from . import balance, clock
from .conditions import GameContext, evaluate
from .zones import ZONE_OF_RESOURCE

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


@dataclass(frozen=True)
class Lure:
    """What the first slot of the feeder does to the next arrival."""

    types: frozenset[str]  # the types of the resource's zone
    chance: float  # extra chance that the arrival has one of them (0.13 = +13 points)


def lure_of(slot: tuple[str, int]) -> Lure:
    """The lure of a feeder slot: (resource, units)."""
    resource, units = slot
    units = min(units, balance.FEEDER_MAX_UNITS)
    return Lure(
        types=ZONE_OF_RESOURCE[resource].types,
        chance=units * balance.FEEDER_BONUS_PER_UNIT_PERCENT / 100,
    )


def weight(rule: SpeciesRule) -> float:
    """Weight of a species in the draw: its rarity."""
    return balance.RARITY_WEIGHTS[rule.rarity]


def pick(candidates: list[SpeciesRule], rng: random.Random) -> SpeciesRule:
    return rng.choices(candidates, weights=[weight(rule) for rule in candidates])[0]


def draw_arrival(
    rules: list[SpeciesRule], context: GameContext, rng: random.Random, lure: Lure | None = None
) -> Arrival | None:
    """
    Draw the arrival of one slot, or None if no species is eligible.

    With a lure, the draw happens in two steps: first, is it one of the lured
    types? Its usual chance (the weight of those species among all of them)
    plus the lure's bonus. Then which species, within that group. If every
    candidate, or none, has the lured types, the lure changes nothing.
    """
    candidates = eligible_species(rules, context)
    if not candidates:
        return None
    lured = [r for r in candidates if lure and not lure.types.isdisjoint(r.types)]
    others = [r for r in candidates if r not in lured]
    # The random calls always happen in the same order: (group), species, nature, shiny
    if lured and others:
        usual = sum(map(weight, lured)) / sum(map(weight, candidates))
        chosen = pick(lured if rng.random() < usual + lure.chance else others, rng)
    else:
        chosen = pick(candidates, rng)
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
    # The feeder's slots left uneaten, in order: [(resource, units), ...]
    feeder: list[tuple[str, int]] = field(default_factory=list)


def catch_up(
    player_id: int,
    rules: list[SpeciesRule],
    last_slot: datetime,
    now: datetime,
    free_places: int,
    feeder: list[tuple[str, int]] | None = None,
    owned: frozenset[str] = frozenset(),
    occupied_zones: frozenset[str] = frozenset(),
) -> CatchUp:
    """
    Replay every hour since `last_slot`, in chronological order.

    `feeder` (its slots in order: [(resource, units), ...]), `owned` and
    `occupied_zones` describe the ranch as the player left it. Only the
    feeder changes along the way: each arrival eats its first slot, whose
    lure only acted on that arrival. That is why the hours are replayed in
    order.

    Arrivals fill the free places of the Welcome area. Once it is full, the
    following arrivals are lost (the offline cap): nobody comes to eat any
    more, nothing else changes in the arrivals, so the loop stops and only
    counts the hours left. The zones' work is computed apart (game.zones).
    The last processed slot is always the current hour.
    """
    feeder = [(resource, units) for resource, units in (feeder or []) if units > 0]
    slots = list(clock.slots_after(last_slot, now))
    arrivals: list[Arrival] = []
    hours_while_full = 0
    for index, slot in enumerate(slots):
        if len(arrivals) >= free_places:
            hours_while_full = len(slots) - index
            break
        context = GameContext(
            slot=slot,
            feeder=frozenset(resource for resource, _ in feeder),
            owned=owned,
            occupied_zones=occupied_zones,
        )
        lure = lure_of(feeder[0]) if feeder else None
        arrival = draw_arrival(rules, context, clock.slot_rng(player_id, slot), lure)
        if arrival is not None:
            arrivals.append(arrival)
            feeder = feeder[1:]  # the arrival ate the whole first slot
    return CatchUp(
        arrivals=arrivals,
        last_slot=max(clock.floor_to_hour(now), last_slot),
        hours_while_full=hours_while_full,
        feeder=feeder,
    )
