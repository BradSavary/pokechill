"""Tests of the player's Pokédex: known species, silhouettes, research stage 1."""

import pytest
from django.urls import reverse

from pokedex.models import Species
from ranch.models import OwnedPokemon, Player

pytestmark = pytest.mark.django_db

HTMX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def player_client(client, bulbasaur, ivysaur, charmander):
    """A player who owns Bulbasaur only; Ivysaur is available, Charmander isn't."""
    Species.objects.filter(pk__in=[bulbasaur.pk, ivysaur.pk]).update(
        is_available=True, rarity="common"
    )
    client.get(reverse("ranch:index"))  # creates the guest and the save
    player = Player.objects.get()
    OwnedPokemon.objects.filter(player=player).delete()  # ignore the starters
    OwnedPokemon.objects.create(
        player=player, species=bulbasaur, level=5, unlocked_natures=["speed"]
    )
    return client


def test_the_list_hides_unknown_species(player_client):
    html = player_client.get(reverse("pokedex:index")).content.decode()
    assert "Bulbasaur" in html
    assert "Ivysaur" not in html
    assert "???" in html
    assert "1 / 3" in html  # owned / total


def test_unknown_entry_shows_a_silhouette(player_client):
    html = player_client.get(reverse("pokedex:detail", args=[2]), **HTMX).content.decode()
    assert "Ivysaur" not in html
    assert "You haven't met this Pokémon yet" in html


def test_species_not_in_the_game_yet(player_client):
    html = player_client.get(reverse("pokedex:detail", args=[4]), **HTMX).content.decode()
    assert "not in the game yet" in html


def test_owned_entry_shows_the_research_stage(player_client):
    html = player_client.get(reverse("pokedex:detail", args=[1]), **HTMX).content.decode()
    assert "Encountered" in html
    assert "Lv. 5" in html
    assert "Speed" in html


def test_the_family_hides_unknown_members(player_client):
    html = player_client.get(reverse("pokedex:detail", args=[1]), **HTMX).content.decode()
    assert "Ivysaur" not in html  # family member not met yet


def test_searching_never_reveals_unknown_names(player_client):
    html = player_client.get(reverse("pokedex:list"), {"q": "ivy"}).content.decode()
    assert "No Pokémon match" in html


def test_visitors_without_a_save_see_the_whole_catalogue(client, bulbasaur, ivysaur):
    html = client.get(reverse("pokedex:index")).content.decode()
    assert "Ivysaur" in html
    assert "???" not in html
