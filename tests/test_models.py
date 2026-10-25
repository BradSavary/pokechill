"""Tests of the Pokédex models: derived values and database constraints."""

import pytest
from django.db import IntegrityError

from pokedex.models import Move, SpeciesMove

# Every test in this module needs the (temporary) test database
pytestmark = pytest.mark.django_db


def test_str_pads_the_pokedex_number(bulbasaur):
    assert str(bulbasaur) == "#001 Bulbasaur"


def test_types_are_listed_in_order(bulbasaur, grass, poison):
    assert bulbasaur.types == [grass, poison]


def test_single_type_species_has_one_type(bulbasaur):
    bulbasaur.secondary_type = None
    assert bulbasaur.types == [bulbasaur.primary_type]


def test_base_stat_total(bulbasaur):
    assert bulbasaur.base_stat_total == 318


def test_body_measurements_are_converted(bulbasaur):
    assert bulbasaur.height_m == 0.7
    assert bulbasaur.weight_kg == 6.9


def test_media_urls_follow_the_number_convention(bulbasaur):
    assert bulbasaur.sprite_url.endswith("pokemon/sprites/1.png")
    assert bulbasaur.shiny_sprite_url.endswith("pokemon/sprites/shiny/1.png")
    assert bulbasaur.cry_url.endswith("pokemon/cries/1.ogg")


def test_evolution_chain_is_named_after_its_base_form(bulbasaur):
    assert str(bulbasaur.evolution_chain) == "Bulbasaur family"


def test_same_learnset_entry_cannot_be_added_twice(bulbasaur, grass):
    vine_whip = Move.objects.create(
        slug="vine-whip", name="Vine Whip", type=grass, damage_class="physical", power=45, pp=25
    )
    SpeciesMove.objects.create(species=bulbasaur, move=vine_whip, learn_method="level-up", level=10)
    with pytest.raises(IntegrityError):
        SpeciesMove.objects.create(
            species=bulbasaur, move=vine_whip, learn_method="level-up", level=10
        )
