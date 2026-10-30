"""
Tests of what keeps pages fast: few queries from one page to the next, and
the Server-Timing header that measures it in production.
"""

import re
from datetime import timedelta

import pytest
from django.urls import reverse

from pokedex.models import Species
from ranch.models import Player

pytestmark = pytest.mark.django_db


@pytest.fixture
def guest(client, bulbasaur):
    """A guest who already visited the Ranch, tutorial done."""
    client.get(reverse("ranch:index"))
    Player.objects.update(tutorial_step=6)
    client.get(reverse("ranch:index"))
    return client


def test_browsing_within_the_hour_replays_nothing(guest, django_assert_max_num_queries):
    # Session, user, player, then the page itself: no catch-up transaction,
    # no write. The Zones page needs 7 queries of its own, so 10 in all.
    with django_assert_max_num_queries(10):
        guest.get(reverse("zones:index"))


def test_a_new_hour_still_replays(guest):
    current = Player.objects.get().last_slot
    Player.objects.update(last_slot=current - timedelta(hours=3))
    guest.get(reverse("zones:index"))
    assert Player.objects.get().last_slot == current  # the three hours were replayed


def test_a_visit_is_recorded_at_most_once_a_minute(guest):
    player = Player.objects.get()
    seen = player.last_seen_at
    guest.get(reverse("zones:index"))
    assert Player.objects.get().last_seen_at == seen  # a few seconds later: not written

    Player.objects.update(last_seen_at=seen - timedelta(minutes=2))
    guest.get(reverse("zones:index"))
    assert Player.objects.get().last_seen_at > seen  # a while later: written again


def test_every_response_tells_its_server_timing(client):
    header = client.get(reverse("pokedex:index"))["Server-Timing"]
    assert re.fullmatch(r'db;dur=[\d.]+;desc="\d+ queries", app;dur=[\d.]+', header)


def test_the_pokedex_loads_an_entry_in_a_fixed_number_of_queries(
    guest, bulbasaur, django_assert_max_num_queries
):
    # An entry in the game, with its challenges: its types come with the
    # species (select_related), its challenges' progress in a single query,
    # the skill tree's bonuses (points, candies) in another
    Species.objects.filter(pk=bulbasaur.pk).update(is_available=True, rarity="common")
    with django_assert_max_num_queries(13):
        guest.get(reverse("pokedex:index"))
