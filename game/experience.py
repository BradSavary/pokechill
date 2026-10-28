"""
Experience curves of the games: how much experience each level costs.

Not every species levels up at the same pace: each one follows one of the
official growth rates (given by PokéAPI). The 151 Kanto species use four:
fast (5 species), medium (80), medium-slow (40) and slow (26).

The formulas are those of the games: total_experience(curve, n) is the
experience a Pokémon needs, from zero, to reach level n.
"""

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
