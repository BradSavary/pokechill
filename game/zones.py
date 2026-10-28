"""
Harvest zones: what they are, and what their Pokémon produce.

A zone favours some types: a Pokémon of one of them works at full rate (and
earns a bit more experience), any other at a reduced rate. Each zone
produces one resource.

While the player is away nothing changes in a zone (same Pokémon, same
levels: experience is only applied when collecting), so its work over a
period is computed at once, without replaying the hours one by one.
"""

from dataclasses import dataclass

from . import balance


@dataclass(frozen=True)
class Zone:
    slug: str
    name: str
    types: frozenset[str]  # types working at full rate (PokéAPI slugs)
    resource: str  # slug of the resource it produces
    resource_name: str  # "Berry"
    resource_plural: str  # "Berries": not always the name + "s"


# The two zones of the start. The other six come with the skill tree.
ZONES = {
    zone.slug: zone
    for zone in (
        Zone(
            "meadow",
            "Meadow",
            frozenset({"normal", "flying", "fairy"}),
            "berry",
            "Berry",
            "Berries",
        ),
        Zone(
            "orchard", "Orchard", frozenset({"grass", "bug"}), "apricorn", "Apricorn", "Apricorns"
        ),
    )
}
# Resource slug -> its zone (the feeder looks up a resource's types this way)
ZONE_OF_RESOURCE = {zone.resource: zone for zone in ZONES.values()}


@dataclass(frozen=True)
class Worker:
    """A Pokémon working in a zone, as the engine sees it."""

    types: tuple[str, ...]
    level: int


def is_efficient(zone: Zone, worker: Worker) -> bool:
    """True if one of the Pokémon's types is favoured by the zone."""
    return not zone.types.isdisjoint(worker.types)


def production_per_hour(zone: Zone, worker: Worker) -> int:
    """Resource made in one hour, in hundredths (100 = 1 resource)."""
    rate = 100 if is_efficient(zone, worker) else balance.OFF_TYPE_PRODUCTION_PERCENT
    level_bonus = 100 + worker.level * balance.PRODUCTION_BONUS_PER_LEVEL_PERCENT
    return balance.PRODUCTION_PER_HOUR_CENTI * rate * level_bonus // 10_000


def experience_per_hour(zone: Zone, worker: Worker) -> int:
    """Experience earned in one hour of work."""
    base = balance.XP_PER_HOUR_BASE + balance.XP_PER_HOUR_PER_LEVEL * worker.level
    bonus = balance.XP_TYPE_BONUS_PERCENT if is_efficient(zone, worker) else 0
    return base * (100 + bonus) // 100


@dataclass(frozen=True)
class Work:
    """What a zone's Pokémon did over a period."""

    hours: int  # hours actually worked (the storage may fill up before the end)
    resource_centi: int  # resource made, in hundredths
    experience: tuple[int, ...]  # experience of each worker, in the given order


def work(zone: Zone, workers: list[Worker], hours_done: int, hours_elapsed: int) -> Work:
    """
    The work of a zone over `hours_elapsed` hours.

    `hours_done`: hours already worked since the last collection. The
    Pokémon stop once the storage holds ZONE_WORK_HOURS_CAP hours of work.
    An empty zone does nothing (its storage doesn't fill up either).
    """
    if not workers:
        return Work(hours=0, resource_centi=0, experience=())
    hours = max(0, min(hours_elapsed, balance.ZONE_WORK_HOURS_CAP - hours_done))
    return Work(
        hours=hours,
        resource_centi=hours * sum(production_per_hour(zone, w) for w in workers),
        experience=tuple(hours * experience_per_hour(zone, w) for w in workers),
    )
