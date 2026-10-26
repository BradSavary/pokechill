"""Tests of the pure obtention rule (new species, duplicates, natures, shiny)."""

from game import balance
from game.collection import OwnedState, resolve_obtention

OWNED = OwnedState(unlocked_natures=frozenset({"attack"}), shiny_unlocked=False)


def test_first_catch_adds_the_species():
    outcome = resolve_obtention(None, "common", "speed", is_shiny=False)
    assert outcome.is_new
    assert outcome.candies == 0
    assert outcome.new_nature == "speed"


def test_duplicates_give_candies_by_rarity():
    common = resolve_obtention(OWNED, "common", "attack", is_shiny=False)
    rare = resolve_obtention(OWNED, "rare", "attack", is_shiny=False)
    assert not common.is_new
    assert common.candies == balance.CANDIES_PER_DUPLICATE["common"]
    assert rare.candies > common.candies


def test_a_nature_is_unlocked_only_once():
    assert resolve_obtention(OWNED, "common", "attack", is_shiny=False).new_nature is None
    assert resolve_obtention(OWNED, "common", "defense", is_shiny=False).new_nature == "defense"


def test_shiny_look_is_unlocked_by_a_shiny_catch_only_once():
    assert resolve_obtention(OWNED, "common", "attack", is_shiny=True).new_shiny
    already = OwnedState(frozenset({"attack"}), shiny_unlocked=True)
    assert not resolve_obtention(already, "common", "attack", is_shiny=True).new_shiny
