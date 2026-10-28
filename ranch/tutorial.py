"""
The tutorial: a few guided steps that present the game.

Each step is shown on one or more pages. The player moves forward by
clicking (POST to ranch:tutorial_next), or by doing what the step asks:
revealing the gift, sending a Pokémon to work, filling the feeder.

New steps always go at the end, before DONE (which moves up): players who
finished the tutorial before they existed are then on the first new step,
and discover the new features at their next visit. This is how the players
of step 1 meet the zones and the feeder.
"""

from django.db import transaction

from game import balance
from game.arrivals import NATURES
from pokedex.models import Species

from .models import Player
from .services import Reveal, receive_pokemon, seeded_rng
from .zones import add_resource

WELCOME = 0  # Ranch: the starters
WELCOME_AREA = 1  # Ranch: hourly arrivals and the Welcome area -> open the Pokédex
POKEDEX = 2  # Pokédex: silhouettes and stages -> back to the Ranch
GIFT = 3  # Ranch: reveal the gift Pokémon
ZONES = 4  # Ranch -> Zones -> a zone's map: send a Pokémon to work there
FEEDER = 5  # Ranch: put the berries received in the feeder
DONE = 6

# The pages where each step is displayed ("zone": the map of one zone). The
# first one is where tutorial_next leads.
STEP_PAGES = {
    WELCOME: ("ranch",),
    WELCOME_AREA: ("ranch",),
    POKEDEX: ("pokedex",),
    GIFT: ("ranch",),
    ZONES: ("ranch", "zones", "zone"),
    # On the zone's map, a word of praise sends the player back to the Ranch
    FEEDER: ("ranch", "zone"),
}

# The steps completed by a click on their button. The others end when the
# player does what they ask (see receive_gift, pokemon_placed, feeder_filled).
# FEEDER is there too: its button only shows when the feeder has no free slot.
CLICK_STEPS = (WELCOME, WELCOME_AREA, POKEDEX, FEEDER)


def step_for_page(player: Player | None, page: str) -> int | None:
    """The tutorial step to display on `page`, or None."""
    if player is None or page not in STEP_PAGES.get(player.tutorial_step, ()):
        return None
    return player.tutorial_step


def context(player: Player | None, page: str) -> dict:
    """What the tutorial template needs on `page` (tutorial_step None: nothing to show)."""
    resource, amount = balance.TUTORIAL_FEEDER_GIFT
    return {
        "tutorial_step": step_for_page(player, page),
        "tutorial_page": page,
        "tutorial_gift": {"resource": resource, "amount": amount},
    }


def advance(player: Player, from_step: int) -> None:
    """
    Move to the step after `from_step`.

    The caller says which step it completes: a double click or a re-sent form
    can't skip a step, and the other steps can only end by doing what they ask.
    """
    if player.tutorial_step == from_step and from_step in CLICK_STEPS:
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
    player.tutorial_step = ZONES
    player.save(update_fields=["tutorial_step"])
    return Reveal(species, nature, False, outcome)


@transaction.atomic
def pokemon_placed(player: Player) -> None:
    """
    A Pokémon was sent to work: that ends the zones step, and the player
    receives a few berries for the feeder step. Locked, so the berries are
    given once even if two placements arrive together.
    """
    player = Player.objects.select_for_update().get(pk=player.pk)
    if player.tutorial_step != ZONES:
        return
    resource, amount = balance.TUTORIAL_FEEDER_GIFT
    add_resource(player, resource, amount)
    player.tutorial_step = FEEDER
    player.save(update_fields=["tutorial_step"])


def feeder_filled(player: Player) -> None:
    """A slot of the feeder was filled: that ends the feeder step, and the tutorial."""
    Player.objects.filter(pk=player.pk, tutorial_step=FEEDER).update(tutorial_step=DONE)
