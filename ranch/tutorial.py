"""
The tutorial: a few guided steps that present the game and end with a gift.

Each step is shown on one page. The player moves forward by clicking (POST
to ranch:tutorial_next) or, for the Pokédex step, by clicking its button on
the Pokédex page. The last step reveals the gift Pokémon.
"""

from django.db import transaction

from game import balance
from game.arrivals import NATURES
from pokedex.models import Species

from .models import Player
from .services import Reveal, receive_pokemon, seeded_rng

WELCOME = 0  # Ranch: the starters
WELCOME_AREA = 1  # Ranch: hourly arrivals and the Welcome area -> open the Pokédex
POKEDEX = 2  # Pokédex: silhouettes and stages -> back to the Ranch
GIFT = 3  # Ranch: reveal the gift Pokémon
DONE = 4

# The page where each step is displayed
STEP_PAGE = {WELCOME: "ranch", WELCOME_AREA: "ranch", POKEDEX: "pokedex", GIFT: "ranch"}


def step_for_page(player: Player | None, page: str) -> int | None:
    """The tutorial step to display on `page`, or None."""
    if player is None or STEP_PAGE.get(player.tutorial_step) != page:
        return None
    return player.tutorial_step


def advance(player: Player, from_step: int) -> None:
    """
    Move to the step after `from_step`.

    The caller says which step it completes: a double click or a re-sent form
    can't skip a step, and the gift step can only end through receive_gift.
    """
    if player.tutorial_step == from_step and from_step < GIFT:
        player.tutorial_step = from_step + 1
        player.save(update_fields=["tutorial_step"])


@transaction.atomic
def receive_gift(player: Player) -> Reveal | None:
    """Last step: give the gift Pokémon and end the tutorial (None if already done)."""
    player = Player.objects.select_for_update().get(pk=player.pk)
    if player.tutorial_step != GIFT:
        return None  # never give the gift twice
    species = Species.objects.select_related("evolution_chain").get(
        slug=balance.TUTORIAL_GIFT_SPECIES
    )
    nature = seeded_rng(player, "gift").choice(NATURES)
    outcome = receive_pokemon(player, species, nature=nature, is_shiny=False)
    player.tutorial_step = DONE
    player.save(update_fields=["tutorial_step"])
    return Reveal(species, nature, False, outcome)
