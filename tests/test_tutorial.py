"""Tests of the tutorial: the Ranch, the Pokédex, the gift, then the zones and the feeder."""

import pytest
from django.urls import reverse

from game import balance
from pokedex.models import EvolutionChain
from ranch import tutorial
from ranch.models import OwnedPokemon, Player, ResourceStock
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
    assert current_step() == tutorial.ZONES  # then the zones

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


# --- After the gift: the zones, then the feeder ------------------------------------------


def at_step(client, step):
    """A guest at a given step of the tutorial (owning Bulbasaur, if it exists)."""
    client.get(reverse("ranch:index"))  # the first visit creates the guest
    Player.objects.update(tutorial_step=step)
    return Player.objects.get()


def place(client, pokemon):
    return client.post(reverse("zones:assign", args=["orchard"]), {"pokemon": pokemon.pk})


def test_the_zones_step_leads_from_the_ranch_to_a_zone(client, bulbasaur):
    at_step(client, tutorial.ZONES)
    html = client.get(reverse("ranch:index")).content.decode()
    assert "Put them to work" in html
    assert """data-spot='.menu-item[href="/zones/"]'""" in html  # spotlight on the tab
    assert "Your zones" in client.get(reverse("zones:index")).content.decode()
    html = client.get(reverse("zones:detail", args=["orchard"])).content.decode()
    assert "Send a Pokémon" in html


def test_the_zones_step_needs_a_pokemon_at_work(client, bulbasaur):
    at_step(client, tutorial.ZONES)
    next_step(client, tutorial.ZONES)  # no button can skip it
    assert current_step() == tutorial.ZONES


def test_placing_a_pokemon_gives_berries_for_the_feeder_step(client, bulbasaur):
    player = at_step(client, tutorial.ZONES)
    pokemon = OwnedPokemon.objects.get(species=bulbasaur)
    place(client, pokemon)
    assert current_step() == tutorial.FEEDER
    resource, amount = balance.TUTORIAL_FEEDER_GIFT
    assert ResourceStock.objects.get(player=player, resource=resource).amount == amount

    html = client.get(reverse("zones:detail", args=["orchard"])).content.decode()
    assert "Hard at work!" in html and f"{amount} berries" in html

    # Once only: moving it again gives nothing more
    client.post(reverse("zones:remove", args=["orchard"]), {"pokemon": pokemon.pk})
    place(client, pokemon)
    assert ResourceStock.objects.get(player=player, resource=resource).amount == amount


def test_filling_the_feeder_ends_the_tutorial(client, bulbasaur):
    player = at_step(client, tutorial.FEEDER)
    ResourceStock.objects.create(player=player, resource="berry", amount=10)
    html = client.get(reverse("ranch:index")).content.decode()
    assert "The feeder" in html and "put your berries in" in html
    client.post(reverse("ranch:feeder_fill"), {"resource": "berry", "units": "10"})
    assert current_step() == tutorial.DONE


def test_a_full_feeder_lets_the_feeder_step_end_with_a_click(client, bulbasaur):
    player = at_step(client, tutorial.FEEDER)
    Player.objects.filter(pk=player.pk).update(feeder=[["berry", 5]])
    assert "Got it" in client.get(reverse("ranch:index")).content.decode()
    next_step(client, tutorial.FEEDER)
    assert current_step() == tutorial.DONE
