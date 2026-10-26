"""Tests of the reveal of waiting arrivals (services and HTMX views)."""

from datetime import UTC, datetime, timedelta

import pytest
from django.urls import reverse

from game import balance
from pokedex.models import Species
from ranch import tutorial
from ranch.models import Arrival, CandyStock, OwnedPokemon, Player
from ranch.services import reveal_all, reveal_next

pytestmark = pytest.mark.django_db

START = datetime(2026, 1, 15, 8, tzinfo=UTC)


@pytest.fixture
def common(ivysaur):
    """The only species that arrives. Not a starter: a new player doesn't own it."""
    Species.objects.filter(pk=ivysaur.pk).update(is_available=True, rarity="common")
    return Species.objects.get(pk=ivysaur.pk)


@pytest.fixture
def player(django_user_model):
    user = django_user_model.objects.create_user("ash")
    return Player.objects.create(user=user, last_slot=START)


def wait(player, species, count, nature="hp"):
    """Put `count` arrivals of `species` in the Welcome area."""
    for hour in range(count):
        Arrival.objects.create(
            player=player, species=species, slot=START - timedelta(hours=hour), nature=nature
        )


# --- Services --------------------------------------------------------------


def test_reveal_next_turns_the_oldest_arrival_into_a_catch(player, common):
    wait(player, common, 2)
    oldest = player.arrivals.first()

    result = reveal_next(player)

    assert result.outcome.is_new
    assert not Arrival.objects.filter(pk=oldest.pk).exists()
    assert player.arrivals.count() == 1
    assert OwnedPokemon.objects.filter(player=player, species=common).exists()


def test_the_second_copy_is_converted_into_candies(player, common):
    wait(player, common, 2)
    reveal_next(player)
    second = reveal_next(player)

    assert not second.outcome.is_new
    stock = CandyStock.objects.get(player=player)
    assert stock.amount == balance.CANDIES_PER_DUPLICATE["common"]


def test_reveal_next_on_an_empty_welcome_area(player):
    assert reveal_next(player) is None


def test_reveal_all_empties_the_welcome_area(player, common):
    wait(player, common, 3)
    results = reveal_all(player)
    assert [r.outcome.is_new for r in results] == [True, False, False]
    assert not player.arrivals.exists()


# --- Pages ---------------------------------------------------------------------


@pytest.fixture
def guest_with_arrivals(client, common, monkeypatch):
    """A guest who comes back after 3 hours: 3 arrivals are waiting."""
    now = START + timedelta(minutes=5)
    monkeypatch.setattr("django.utils.timezone.now", lambda: now)
    client.get(reverse("ranch:index"))
    Player.objects.update(tutorial_step=tutorial.DONE)  # tutorial already done
    monkeypatch.setattr("django.utils.timezone.now", lambda: now + timedelta(hours=3))
    return client


def test_the_ranch_hides_arrivals_and_opens_the_reveal_dialog(guest_with_arrivals):
    html = guest_with_arrivals.get(reverse("ranch:index")).content.decode()
    assert "data-auto-open" in html
    assert "3/8" in html
    assert "Ivysaur" not in html  # hidden until revealed


def test_revealing_one_pokemon(guest_with_arrivals):
    html = guest_with_arrivals.post(reverse("ranch:reveal")).content.decode()
    assert "Ivysaur" in html
    assert "NEW!" in html
    assert "Next (2 left)" in html


def test_skipping_reveals_everything(guest_with_arrivals):
    guest_with_arrivals.post(reverse("ranch:reveal"))
    html = guest_with_arrivals.post(reverse("ranch:reveal_all")).content.decode()
    assert html.count("Ivysaur") >= 2
    assert not Arrival.objects.exists()


def test_reveals_require_post(guest_with_arrivals):
    # A GET must never change the game state (links, prefetching, crawlers...)
    assert guest_with_arrivals.get(reverse("ranch:reveal")).status_code == 405
    assert guest_with_arrivals.get(reverse("ranch:reveal_all")).status_code == 405


def test_the_dialog_stays_closed_when_nobody_is_waiting(client):
    html = client.get(reverse("ranch:index")).content.decode()
    assert "data-auto-open" not in html
    assert "Welcome back" not in html
