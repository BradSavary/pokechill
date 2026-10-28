"""Tests of the zone pages: list, collection on opening, map, assignment."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from game import balance
from ranch.models import OwnedPokemon, Player, ResourceStock
from ranch.services import catch_up_player
from ranch.templatetags.ranch_extras import resource_word
from ranch.zones import move_pokemon
from tests.conftest import make_species

pytestmark = pytest.mark.django_db


@pytest.fixture
def guest(client, bulbasaur, charmander):
    """A guest with two Pokémon: Bulbasaur (fits the Orchard) and Charmander."""
    client.get(reverse("zones:index"))  # the first visit creates the guest...
    player = Player.objects.get()
    # ...who gets the starters that exist in the test database: these two
    player.pokemon.update(level=10)
    return client, player


def pokemon_of(player, slug):
    return OwnedPokemon.objects.get(player=player, species__slug=slug)


def test_the_list_shows_the_starting_zones(guest):
    client, _ = guest
    html = client.get(reverse("zones:index")).content.decode()
    assert "Meadow" in html and "Orchard" in html
    assert reverse("zones:open", args=["orchard"]) in html


def test_the_picker_lists_the_free_pokemon_best_production_first(guest):
    client, _ = guest
    html = client.get(reverse("zones:detail", args=["orchard"])).content.decode()
    assert html.count('class="map-slot"') == balance.ZONE_SLOTS_BASE  # all spots empty
    # Bulbasaur (Grass) works at full rate in the Orchard: it comes first, and
    # the table shows it is sorted by production (▼ on Per hour)
    assert html.index("Bulbasaur") < html.index("Charmander")
    assert 'data-sort="rate" data-list="#picker-list" data-direction="desc"' in html
    # Only Bulbasaur's type is favoured here: it alone shows the experience bonus
    assert html.count('class="xp-badge') == 1
    assert 'class="info-tip' in html  # the rules are one tap away


def test_assigning_and_bringing_back_a_pokemon(guest):
    client, player = guest
    bulbasaur = pokemon_of(player, "bulbasaur")
    url = reverse("zones:assign", args=["orchard"])
    assert client.post(url, {"pokemon": bulbasaur.pk}).status_code == 302
    bulbasaur.refresh_from_db()
    assert bulbasaur.status == OwnedPokemon.IN_ZONE

    html = client.get(reverse("zones:detail", args=["orchard"])).content.decode()
    assert html.count('class="map-pokemon"') == 1
    assert "pokemon/icons/1.png" in html  # its Sun/Moon icon on the map

    client.post(reverse("zones:remove", args=["orchard"]), {"pokemon": bulbasaur.pk})
    bulbasaur.refresh_from_db()
    assert bulbasaur.status == OwnedPokemon.FREE


def test_opening_a_zone_collects_it_and_shows_the_harvest_once(guest):
    client, player = guest
    move_pokemon(pokemon_of(player, "bulbasaur"), player.zones.get(zone="orchard"))
    # Five hours later...
    catch_up_player(player, now=timezone.now() + timedelta(hours=5))

    response = client.post(reverse("zones:open", args=["orchard"]))
    assert response.url == reverse("zones:detail", args=["orchard"])
    assert ResourceStock.objects.get(player=player, resource="apricorn").amount > 0

    first = client.get(response.url).content.decode()
    assert 'id="harvest"' in first
    again = client.get(response.url).content.decode()
    assert 'id="harvest"' not in again  # shown once: reloading doesn't repeat it


def test_opening_an_empty_zone_goes_straight_to_its_map(guest):
    client, _ = guest
    response = client.post(reverse("zones:open", args=["meadow"]))
    html = client.get(response.url).content.decode()
    assert 'id="harvest"' not in html


def test_a_full_zone_says_so(guest, grass, bulbasaur):
    client, player = guest

    meadow = player.zones.get(zone="meadow")
    for number in range(balance.ZONE_SLOTS_BASE):
        species = make_species(200 + number, f"Filler{number}", bulbasaur.evolution_chain, grass)
        move_pokemon(OwnedPokemon.objects.create(player=player, species=species), meadow)

    response = client.post(
        reverse("zones:assign", args=["meadow"]),
        {"pokemon": pokemon_of(player, "charmander").pk},
        follow=True,
    )
    assert "is full" in response.content.decode()


def test_another_players_pokemon_cannot_be_sent(guest, client, django_user_model, bulbasaur):
    client_, _ = guest
    other = Player.objects.create(
        user=django_user_model.objects.create_user("gary"), last_slot=timezone.now()
    )
    theirs = OwnedPokemon.objects.create(player=other, species=bulbasaur)
    response = client_.post(reverse("zones:assign", args=["orchard"]), {"pokemon": theirs.pk})
    assert response.status_code == 404


def test_actions_require_post_and_unknown_zones_are_404(guest):
    client, _ = guest
    for name in ("open", "assign", "remove"):
        assert client.get(reverse(f"zones:{name}", args=["orchard"])).status_code == 405
    assert client.get(reverse("zones:detail", args=["volcano"])).status_code == 404


def test_the_clicked_spot_is_where_the_pokemon_goes(guest):
    client, player = guest
    bulbasaur = pokemon_of(player, "bulbasaur")
    client.post(reverse("zones:assign", args=["orchard"]), {"pokemon": bulbasaur.pk, "spot": "2"})
    bulbasaur.refresh_from_db()
    assert bulbasaur.spot == 2
    html = client.get(reverse("zones:detail", args=["orchard"])).content.decode()
    # The two other spots are offered, each with its own number
    assert 'data-spot="0"' in html and 'data-spot="1"' in html and 'data-spot="2"' not in html


def test_resource_words_follow_the_count():
    assert resource_word(1, "berry") == "berry"
    assert resource_word(0, "berry") == "berries"  # not "berrys"
    assert resource_word(2.5, "apricorn") == "apricorns"


def test_the_cards_show_production_and_time_before_full(guest):
    client, player = guest
    move_pokemon(pokemon_of(player, "bulbasaur"), player.zones.get(zone="orchard"))
    catch_up_player(player, now=timezone.now() + timedelta(hours=3))

    html = client.get(reverse("zones:index")).content.decode()
    assert "img/zone-orchard-banner.png" in html  # a banner, not the whole map
    assert f"Full in {balance.ZONE_WORK_HOURS_CAP - 3} h" in html
    # A level 10 Grass Pokémon in the Orchard: 1 an hour, +10 %
    assert "1.10<span" in html  # floatformat:"-2": two decimals unless whole
