"""
Obtaining a Pokémon: what a new catch brings to the player.

There is only one Pokémon per species. The first catch adds the species to
the collection. Any later catch of the same species is converted:
- candies of its evolution family (more for rarer species);
- its nature, if this nature was never obtained for this species;
- the shiny look, if the catch is shiny and the look wasn't unlocked yet.
"""

from dataclasses import dataclass

from . import balance


@dataclass(frozen=True)
class OwnedState:
    """What the player already has for a species."""

    unlocked_natures: frozenset[str]
    shiny_unlocked: bool


@dataclass(frozen=True)
class Obtention:
    """The outcome of one catch."""

    is_new: bool  # first time this species is obtained
    candies: int  # candies of the family earned (duplicates only)
    new_nature: str | None  # nature unlocked by this catch, if any
    new_shiny: bool  # shiny look unlocked by this catch


def resolve_obtention(
    owned: OwnedState | None, rarity: str, nature: str, is_shiny: bool
) -> Obtention:
    """Compute what a catch brings, given what the player already owns (None: nothing)."""
    if owned is None:
        return Obtention(is_new=True, candies=0, new_nature=nature, new_shiny=is_shiny)
    return Obtention(
        is_new=False,
        candies=balance.CANDIES_PER_DUPLICATE[rarity],
        new_nature=None if nature in owned.unlocked_natures else nature,
        new_shiny=is_shiny and not owned.shiny_unlocked,
    )
