"""
Harvest zones: what they are, and what their Pokémon produce.

A zone favours some types: a Pokémon of one of them works at full rate (and
earns a bit more experience), any other at a reduced rate. A mastered
Pokémon (game.mastery) works at full rate everywhere, and gathers and learns
more. Each zone produces one resource.

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

# The other zones of the concept, not in the game yet: zone slug -> resource
# slug. Only their names are known here, so that species files can already
# refer to them (Blastoise needs a Squirtle at work in the Pond): such a
# condition is valid, and simply never met until the zone comes. A zone
# moves from here to ZONES when it is built.
PLANNED_ZONES = {
    "pond": "pearl",
    "quarry": "ore",
    "volcano": "ember",
    "power-plant": "energy",
    "swamp": "root",
    "tower": "mystic-dust",
}

# Everything a condition may name: the zones and resources of the game, and
# the planned ones
KNOWN_ZONES = frozenset(ZONES) | frozenset(PLANNED_ZONES)
KNOWN_RESOURCES = frozenset(ZONE_OF_RESOURCE) | frozenset(PLANNED_ZONES.values())


@dataclass(frozen=True)
class Worker:
    """A Pokémon working in a zone, as the engine sees it."""

    types: tuple[str, ...]
    level: int
    mastered: bool = False  # its species is mastered (research stage 3)


def is_efficient(zone: Zone, worker: Worker) -> bool:
    """True if one of the Pokémon's types is favoured by the zone, or if it is mastered."""
    return worker.mastered or not zone.types.isdisjoint(worker.types)


def production_per_hour(zone: Zone, worker: Worker, bonus_percent: int = 0) -> int:
    """
    Resource made in one hour, in hundredths (100 = 1 resource). `bonus_percent`:
    the yield bonus of the zone (its skill tree), on top of the level bonus;
    a mastered Pokémon adds its own.
    """
    rate = 100 if is_efficient(zone, worker) else balance.OFF_TYPE_PRODUCTION_PERCENT
    level_bonus = 100 + worker.level * balance.PRODUCTION_BONUS_PER_LEVEL_PERCENT
    made = balance.PRODUCTION_PER_HOUR_CENTI * rate * level_bonus // 10_000
    mastery = balance.MASTERY_YIELD_PERCENT if worker.mastered else 0
    return made * (100 + bonus_percent + mastery) // 100


def base_experience_per_hour(level: int) -> int:
    """Experience of one hour of work at this level, before the type bonus."""
    return balance.XP_PER_HOUR_BASE + balance.XP_PER_HOUR_PER_LEVEL * level


def experience_per_hour(zone: Zone, worker: Worker, bonus_percent: int = 0) -> int:
    """Experience earned in one hour of work (`bonus_percent`: the zone's skill tree)."""
    base = base_experience_per_hour(worker.level)
    bonus = balance.XP_TYPE_BONUS_PERCENT if is_efficient(zone, worker) else 0
    mastery = balance.MASTERY_XP_PERCENT if worker.mastered else 0
    return base * (100 + bonus + bonus_percent + mastery) // 100


@dataclass(frozen=True)
class Work:
    """What a zone's Pokémon did over a period."""

    hours: int  # hours actually worked (the storage may fill up before the end)
    resource_centi: int  # resource made, in hundredths
    experience: tuple[int, ...]  # experience of each worker, in the given order
    # Resource made by each worker, in hundredths (same order): their sum is
    # resource_centi. The Pokédex challenges count what each one gathered.
    resources: tuple[int, ...] = ()


def work(
    zone: Zone,
    workers: list[Worker],
    hours_done: int,
    hours_elapsed: int,
    *,
    cap_hours: int | None = None,
    yield_percent: int = 0,
    xp_percent: int = 0,
) -> Work:
    """
    The work of a zone over `hours_elapsed` hours.

    `hours_done`: hours already worked since the last collection. The
    Pokémon stop once the storage holds `cap_hours` hours of work
    (ZONE_WORK_HOURS_CAP by default; the skill tree adds to it, like it adds
    `yield_percent` and `xp_percent`). An empty zone does nothing (its
    storage doesn't fill up either).
    """
    if not workers:
        return Work(hours=0, resource_centi=0, experience=())
    cap = balance.ZONE_WORK_HOURS_CAP if cap_hours is None else cap_hours
    hours = max(0, min(hours_elapsed, cap - hours_done))
    resources = tuple(hours * production_per_hour(zone, w, yield_percent) for w in workers)
    return Work(
        hours=hours,
        resource_centi=sum(resources),
        experience=tuple(hours * experience_per_hour(zone, w, xp_percent) for w in workers),
        resources=resources,
    )
