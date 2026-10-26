"""Tests of the player's collection: receive_pokemon and the starters."""

import pytest
from django.db import IntegrityError
from django.urls import reverse

from game import balance
from pokedex.models import EvolutionChain, Species
from ranch.models import CandyStock, OwnedPokemon, Player
from ranch.services import receive_pokemon
from tests.conftest import make_species

pytestmark = pytest.mark.django_db


@pytest.fixture
def available(bulbasaur, ivysaur):
    """Bulbasaur and Ivysaur available in the game, same family."""
    Species.objects.filter(pk__in=[bulbasaur.pk, ivysaur.pk]).update(
        is_available=True, rarity="common"
    )
    Species.objects.filter(pk=ivysaur.pk).update(rarity="rare", min_level=16)
    bulbasaur.refresh_from_db()
    ivysaur.refresh_from_db()
    return bulbasaur, ivysaur


@pytest.fixture
def player(django_user_model):
    user = django_user_model.objects.create_user("ash")
    return Player.objects.create(user=user, last_slot="2026-01-01T00:00Z")


def candies(player, species):
    stock = CandyStock.objects.filter(player=player, family=species.evolution_chain).first()
    return stock.amount if stock else 0


def test_first_catch_adds_the_pokemon_at_its_arrival_level(player, available):
    _bulbasaur, ivysaur = available
    outcome = receive_pokemon(player, ivysaur, nature="speed", is_shiny=False)

    assert outcome.is_new
    owned = OwnedPokemon.objects.get(player=player, species=ivysaur)
    assert owned.level == 16
    assert owned.unlocked_natures == ["speed"]


def test_duplicates_feed_the_family_candy_stock(player, available):
    bulbasaur, ivysaur = available
    receive_pokemon(player, bulbasaur, nature="hp", is_shiny=False)
    receive_pokemon(player, ivysaur, nature="hp", is_shiny=False)

    receive_pokemon(player, bulbasaur, nature="hp", is_shiny=False)  # common duplicate
    receive_pokemon(player, ivysaur, nature="hp", is_shiny=False)  # rare duplicate

    # One shared stock for the whole family
    expected = balance.CANDIES_PER_DUPLICATE["common"] + balance.CANDIES_PER_DUPLICATE["rare"]
    assert candies(player, bulbasaur) == expected
    assert OwnedPokemon.objects.filter(player=player).count() == 2


def test_duplicates_unlock_new_natures_and_the_shiny_look(player, available):
    bulbasaur, _ivysaur = available
    receive_pokemon(player, bulbasaur, nature="hp", is_shiny=False)
    receive_pokemon(player, bulbasaur, nature="speed", is_shiny=True)
    receive_pokemon(player, bulbasaur, nature="hp", is_shiny=False)

    owned = OwnedPokemon.objects.get(player=player, species=bulbasaur)
    assert owned.unlocked_natures == ["hp", "speed"]
    assert owned.shiny_unlocked


def test_the_database_forbids_two_pokemon_of_one_species(player, available):
    bulbasaur, _ivysaur = available
    OwnedPokemon.objects.create(player=player, species=bulbasaur)
    with pytest.raises(IntegrityError):
        OwnedPokemon.objects.create(player=player, species=bulbasaur)


def test_a_new_player_owns_the_three_starters(client, bulbasaur, charmander, grass):
    squirtle_chain = EvolutionChain.objects.create(pokeapi_id=3)
    make_species(7, "Squirtle", squirtle_chain, grass)  # type irrelevant here
    Species.objects.filter(slug__in=balance.STARTER_SPECIES).update(
        is_available=True, rarity="rare"
    )

    client.get(reverse("ranch:index"))

    owned = OwnedPokemon.objects.filter(player=Player.objects.get())
    assert sorted(owned.values_list("species__slug", flat=True)) == sorted(balance.STARTER_SPECIES)
    assert all(len(p.unlocked_natures) == 1 for p in owned)
