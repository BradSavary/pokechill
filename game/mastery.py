"""
Mastery: what a species gains at its last research stage ("Mastered").

Reaching it is meant to be hard (every challenge of the species), so every
species gains the same four bonuses at once. They are all about the Pokémon
itself; the improvements of the ranch belong to the skill tree:

- affinity: it works at full rate in every zone, as if the zone favoured
  its types (with their experience bonus);
- harvest: it gathers MASTERY_YIELD_PERCENT % more resources;
- experience: it earns MASTERY_XP_PERCENT % more experience in its zone;
- candies: its candies give MASTERY_CANDY_PERCENT % more experience.

The zones (game.zones) and the candies (game.experience) apply them; this
module says who is mastered and describes the bonuses for the interface.
"""

from dataclasses import dataclass

from . import balance

# The research stage of a mastered species (1 Encountered, 2 Studied, 3 Mastered)
MASTERED_STAGE = 3


def is_mastered(research_stage: int) -> bool:
    """True once the stage "Mastered" has been claimed."""
    return research_stage >= MASTERED_STAGE


def candy_percent(mastered: bool) -> int:
    """Experience bonus of the candies given to a Pokémon, in percent."""
    return balance.MASTERY_CANDY_PERCENT if mastered else 0


@dataclass(frozen=True)
class MasteryBonus:
    """One of the four bonuses, as the interface shows it."""

    effect: str  # "affinity", "harvest", "experience", "candies"
    label: str  # a few words: "+25 % XP"
    text: str  # one short sentence


def bonuses() -> tuple[MasteryBonus, ...]:
    """The four bonuses of a mastered species (written from the balance values)."""
    return (
        MasteryBonus("affinity", "Any zone", "Works at full rate in every zone"),
        MasteryBonus(
            "harvest",
            f"+{balance.MASTERY_YIELD_PERCENT} % harvest",
            f"Gathers {balance.MASTERY_YIELD_PERCENT} % more resources",
        ),
        MasteryBonus(
            "experience",
            f"+{balance.MASTERY_XP_PERCENT} % XP",
            f"Earns {balance.MASTERY_XP_PERCENT} % more experience",
        ),
        MasteryBonus(
            "candies",
            f"+{balance.MASTERY_CANDY_PERCENT} % candy XP",
            f"Candies give {balance.MASTERY_CANDY_PERCENT} % more experience",
        ),
    )
