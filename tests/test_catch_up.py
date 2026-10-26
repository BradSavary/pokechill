"""Tests of the hourly catch-up saved in the database (ranch.services.catch_up_player)."""

from datetime import UTC, datetime, timedelta

import pytest
from django.db import IntegrityError
from django.urls import reverse

from game import balance
from game.arrivals import catch_up
from pokedex.models import Species
from ranch.models import Arrival, Player
from ranch.services import catch_up_player

pytestmark = pytest.mark.django_db

START = datetime(2026, 1, 15, 8, tzinfo=UTC)


@pytest.fixture
def always(bulbasaur):
    """One species that may arrive at any hour."""
    Species.objects.filter(pk=bulbasaur.pk).update(is_available=True, rarity="common")
    return Species.objects.get(pk=bulbasaur.pk)


@pytest.fixture
def player(django_user_model):
    user = django_user_model.objects.create_user("ash")
    return Player.objects.create(user=user, last_slot=START)


def test_each_elapsed_hour_brings_an_arrival(player, always):
    result = catch_up_player(player, now=START + timedelta(hours=3, minutes=10))

    assert list(player.arrivals.values_list("slot", flat=True)) == [
        START + timedelta(hours=h) for h in (1, 2, 3)
    ]
    assert len(result.arrivals) == 3
    player.refresh_from_db()
    assert player.last_slot == START + timedelta(hours=3)


def test_a_second_catch_up_replays_nothing(player, always):
    now = START + timedelta(hours=3)
    catch_up_player(player, now=now)
    catch_up_player(player, now=now)
    assert player.arrivals.count() == 3


def test_the_welcome_area_caps_arrivals(player, always):
    result = catch_up_player(player, now=START + timedelta(hours=20))

    assert player.arrivals.count() == balance.WELCOME_CAPACITY_BASE
    assert result.hours_while_full == 20 - balance.WELCOME_CAPACITY_BASE


def test_waiting_arrivals_take_places(player, always):
    for hour in range(5):
        Arrival.objects.create(
            player=player, species=always, slot=START - timedelta(hours=hour), nature="hp"
        )
    catch_up_player(player, now=START + timedelta(hours=10))
    assert player.arrivals.count() == balance.WELCOME_CAPACITY_BASE  # 5 + 3


def test_unavailable_species_never_arrive(player, always, charmander):
    catch_up_player(player, now=START + timedelta(hours=6))
    assert set(player.arrivals.values_list("species__slug", flat=True)) == {"bulbasaur"}


def test_saved_arrivals_match_the_pure_engine(player, always):
    now = START + timedelta(hours=6)
    expected = catch_up(player.pk, [always.to_rule()], START, now, free_places=8).arrivals
    catch_up_player(player, now=now)
    saved = [(a.slot, a.nature, a.is_shiny) for a in player.arrivals.all()]
    assert saved == [(a.slot, a.nature, a.is_shiny) for a in expected]


def test_the_database_refuses_two_arrivals_in_one_hour(player, always):
    Arrival.objects.create(player=player, species=always, slot=START, nature="hp")
    with pytest.raises(IntegrityError):
        Arrival.objects.create(player=player, species=always, slot=START, nature="speed")


def test_visiting_the_ranch_runs_the_catch_up(client, always, monkeypatch):
    now = START + timedelta(minutes=30)
    monkeypatch.setattr("django.utils.timezone.now", lambda: now)
    client.get(reverse("ranch:index"))  # new guest: the clock starts at START

    now = START + timedelta(hours=2, minutes=5)  # two hours later
    html = client.get(reverse("ranch:index")).content.decode()

    assert Arrival.objects.count() == 2
    assert f"2/{balance.WELCOME_CAPACITY_BASE}" in html
