"""
Moves known by a Pokémon.

Like in the main games, a Pokémon knows at most four moves. Until players can
choose them (once Pokémon gain levels), its moves are the last four learned
by level-up up to its current level.
"""

MAX_MOVES = 4


def default_moves(level_up: list[tuple[int, str]], level: int) -> list[str]:
    """
    Moves known at `level`, oldest first, from (level learned, move slug) pairs.

    Moves are learned in level order; a fifth move replaces the oldest one.
    A move learned again (listed twice) only counts once, at its latest level.
    """
    known: list[str] = []
    # sorted() is stable: moves of the same level keep their given order
    for learned_at, move in sorted(level_up, key=lambda entry: entry[0]):
        if learned_at > level:
            break
        if move in known:
            known.remove(move)
        known.append(move)
    return known[-MAX_MOVES:]
