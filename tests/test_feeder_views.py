"""Tests of the feeder on the Ranch page: showing it, filling and taking back a slot."""

import pytest
from django.urls import reverse

from ranch.models import Player, ResourceStock

pytestmark = pytest.mark.django_db


@pytest.fixture
def guest(client, bulbasaur):
    """A guest with 10 berries and 4 apricorns in stock."""
    client.get(reverse("ranch:index"))  # the first visit creates the guest
    player = Player.objects.get()
    ResourceStock.objects.create(player=player, resource="berry", amount=10)
    ResourceStock.objects.create(player=player, resource="apricorn", amount=4)
    return client, player


def stock(player, resource):
    return ResourceStock.objects.get(player=player, resource=resource).amount


def test_the_ranch_shows_an_empty_feeder_and_what_could_go_in(guest):
    client, _ = guest
    html = client.get(reverse("ranch:index")).content.decode()
    assert 'data-open="#feeder"' in html  # its spot on the map
    assert 'Slots <span class="text-muted">0/1</span>' in html  # seen at once
    assert "Free slot" in html
    # One tile per resource, with its stock; the slider goes up to it
    assert 'value="berry" data-max="10"' in html
    assert 'value="apricorn" data-max="4"' in html
    assert 'class="feeder-badge"' not in html


def test_filling_the_feeder(guest):
    client, player = guest
    response = client.post(reverse("ranch:feeder_fill"), {"resource": "berry", "units": "6"})
    assert response.url == reverse("ranch:index")
    player.refresh_from_db()
    assert player.feeder == [["berry", 6]]
    assert stock(player, "berry") == 4

    html = client.get(reverse("ranch:index")).content.decode()
    assert 'class="feeder-badge"' in html  # the next slot shows on the map
    assert "+6 %" in html  # its bonus
    # One slot: nothing else goes in until it is eaten or taken back
    assert "No free slot" in html
    assert 'name="units"' not in html


def test_the_feeder_needs_enough_resources(guest):
    client, player = guest
    response = client.post(
        reverse("ranch:feeder_fill"), {"resource": "apricorn", "units": "5"}, follow=True
    )
    assert "Not enough apricorns." in response.content.decode()
    player.refresh_from_db()
    assert player.feeder == []


def test_a_wrong_number_of_units_is_refused(guest):
    client, player = guest
    response = client.post(
        reverse("ranch:feeder_fill"), {"resource": "berry", "units": "many"}, follow=True
    )
    assert response.status_code == 200
    player.refresh_from_db()
    assert player.feeder == []


def test_taking_back_a_slot(guest):
    client, player = guest
    client.post(reverse("ranch:feeder_fill"), {"resource": "berry", "units": "6"})
    client.post(reverse("ranch:feeder_take_back"), {"slot": "0"})
    player.refresh_from_db()
    assert player.feeder == []
    assert stock(player, "berry") == 10


def test_feeder_actions_require_post(guest):
    client, _ = guest
    assert client.get(reverse("ranch:feeder_fill")).status_code == 405
    assert client.get(reverse("ranch:feeder_take_back")).status_code == 405
