"""Tests of the tutorial: steps across the Ranch and the Pokédex, then the gift."""

import pytest
from django.urls import reverse

from game import balance
from pokedex.models import EvolutionChain
from ranch import tutorial
from ranch.models import OwnedPokemon, Player
from tests.conftest import make_species

pytestmark = pytest.mark.django_db


@pytest.fixture
def pikachu(fire):
    chain = EvolutionChain.objects.create(pokeapi_id=10)
    species = make_species(25, "Pikachu", chain, fire, is_available=True, rarity="rare")
    assert species.slug == balance.TUTORIAL_GIFT_SPECIES
    return species


def next_step(client, step):
    return client.post(reverse("ranch:tutorial_next"), {"step": step})


def current_step():
    return Player.objects.get().tutorial_step


def test_a_new_player_starts_the_tutorial(client):
    html = client.get(reverse("ranch:index")).content.decode()
    assert "Welcome to PokéChill!" in html
    assert current_step() == tutorial.WELCOME


def test_the_intro_shows_the_starters(client, bulbasaur, charmander):
    html = client.get(reverse("ranch:index")).content.decode()
    assert "You're not alone" in html
    assert "<figcaption" in html and "Bulbasaur</figcaption>" in html


def test_the_tutorial_goes_through_the_pokedex_and_back(client):
    client.get(reverse("ranch:index"))

    assert next_step(client, tutorial.WELCOME)["Location"] == reverse("ranch:index")
    response = next_step(client, tutorial.WELCOME_AREA)
    assert response["Location"] == reverse("pokedex:index")
    assert "Your Pokédex" in client.get(reverse("pokedex:index")).content.decode()

    assert next_step(client, tutorial.POKEDEX)["Location"] == reverse("ranch:index")
    assert "Someone is waiting for you" in client.get(reverse("ranch:index")).content.decode()


def test_a_double_click_never_skips_a_step(client):
    client.get(reverse("ranch:index"))
    next_step(client, tutorial.WELCOME)
    next_step(client, tutorial.WELCOME)  # the same form sent twice
    assert current_step() == tutorial.WELCOME_AREA


def test_the_gift_ends_the_tutorial_once(client, pikachu):
    client.get(reverse("ranch:index"))
    Player.objects.update(tutorial_step=tutorial.GIFT)

    html = client.post(reverse("ranch:tutorial_gift")).content.decode()
    assert "Pikachu" in html
    assert "NEW!" in html
    assert current_step() == tutorial.DONE

    client.post(reverse("ranch:tutorial_gift"))  # never twice
    assert OwnedPokemon.objects.filter(species=pikachu).count() == 1


def test_the_tutorial_disappears_once_done(client):
    client.get(reverse("ranch:index"))
    Player.objects.update(tutorial_step=tutorial.DONE)
    html = client.get(reverse("ranch:index")).content.decode()
    assert 'aria-label="Tutorial"' not in html


def test_a_tampered_step_is_ignored(client):
    client.get(reverse("ranch:index"))
    assert next_step(client, "abc").status_code == 302  # no server error
    assert current_step() == tutorial.WELCOME
