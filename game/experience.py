"""
Experience curves of the games: how much experience each level costs.

Not every species levels up at the same pace: each one follows one of the
official growth rates (given by PokéAPI). The 151 Kanto species use four:
fast (5 species), medium (80), medium-slow (40) and slow (26).

The formulas are those of the games: total_experience(curve, n) is the
experience a Pokémon needs, from zero, to reach level n.
"""

from . import balance
from .zones import base_experience_per_hour

MAX_LEVEL = 100

# Total experience to reach level n, by growth rate (PokéAPI names).
# Integer divisions, like the games (which round the results down).
CURVES = {
    "fast": lambda n: 4 * n**3 // 5,
    "medium": lambda n: n**3,
    "medium-slow": lambda n: 6 * n**3 // 5 - 15 * n**2 + 100 * n - 140,
    "slow": lambda n: 5 * n**3 // 4,
}


def total_experience(curve: str, level: int) -> int:
    """Experience needed to reach `level` (level 1 needs none)."""
    if curve not in CURVES:
        raise ValueError(f"Unknown growth rate {curve!r}")
    if not 1 <= level <= MAX_LEVEL:
        raise ValueError(f"Level must be between 1 and {MAX_LEVEL}, got {level}")
    # Level 1 is the start: 0, even where the formula says otherwise
    # (the medium-slow one gives -54 for n = 1)
    return 0 if level == 1 else CURVES[curve](level)


def level_for(curve: str, experience: int) -> int:
    """The level reached with this much experience (at most MAX_LEVEL)."""
    level = 1
    while level < MAX_LEVEL and total_experience(curve, level + 1) <= experience:
        level += 1
    return level


def add_experience(curve: str, level: int, progress: int, gained: int) -> tuple[int, int]:
    """
    Level and progress after gaining experience.

    `progress` is the experience earned since the current level was reached
    (the blue bar of the games), not a total: a Pokémon keeps its level even
    if its species' curve is corrected later. At MAX_LEVEL, progress stays 0.
    """
    total = total_experience(curve, level) + progress + gained
    new_level = level_for(curve, total)
    if new_level == MAX_LEVEL:
        return MAX_LEVEL, 0
    return new_level, total - total_experience(curve, new_level)


def candy_experience(level: int, evolution_stage: int) -> int:
    """
    Experience given by one candy of its family to a Pokémon (see
    balance.CANDY_WORK_HOURS): hours of zone work at its level, divided by
    its evolution stage (1 for a base form, 2 or 3 for evolved ones).
    """
    hours = balance.CANDY_WORK_HOURS * base_experience_per_hour(level)
    return max(1, hours // evolution_stage)


def feed_candies(
    curve: str, level: int, progress: int, evolution_stage: int, candies: int
) -> tuple[int, int, int]:
    """
    Give candies one by one: each is worth the experience of the level the
    Pokémon has when it eats it (a candy given after a level up is worth a
    little more). Stops at MAX_LEVEL. Returns (level, progress, candies eaten).
    """
    eaten = 0
    while eaten < candies and level < MAX_LEVEL:
        gained = candy_experience(level, evolution_stage)
        level, progress = add_experience(curve, level, progress, gained)
        eaten += 1
    return level, progress, eaten


def candies_to_next_level(curve: str, level: int, progress: int, evolution_stage: int) -> int:
    """Candies needed to reach the next level (0 at MAX_LEVEL)."""
    if level >= MAX_LEVEL:
        return 0
    needed, candies = total_experience(curve, level + 1) - total_experience(curve, level), 0
    while progress < needed:
        progress += candy_experience(level, evolution_stage)
        candies += 1
    return candies
