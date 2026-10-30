"""Tests of the reveal of waiting arrivals (services and HTMX views)."""

from datetime import UTC, datetime, timedelta

import pytest
from django.urls import reverse

from game import balance
from pokedex.models import Species
from ranch import tutorial
from ranch.models import Arrival, CandyStock, OwnedPokemon, Player
from ranch.services import reveal_all, reveal_next
from ranch.templatetags.ranch_extras import balanced_rows, ball_name, ball_sprite

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


def test_each_waiting_pokemon_shows_the_ball_of_its_rarity(guest_with_arrivals, common):
    html = guest_with_arrivals.get(reverse("ranch:index")).content.decode()
    # 3 common arrivals: Poké Balls, in the Welcome area and in the dialog
    assert html.count('aria-label="Poké Ball"') == 6

    Species.objects.filter(pk=common.pk).update(rarity="very_rare")
    html = guest_with_arrivals.get(reverse("ranch:index")).content.decode()
    assert html.count('aria-label="Cherish Ball"') == 6
    assert "pokemon/cherish-ball.png" in html
    assert "Ivysaur" not in html  # the ball tells the rarity, not the species


def test_the_reveal_opens_the_ball_of_the_rarity(guest_with_arrivals, common):
    Species.objects.filter(pk=common.pk).update(rarity="legendary")
    html = guest_with_arrivals.post(reverse("ranch:reveal")).content.decode()
    assert 'aria-label="Master Ball"' in html


@pytest.mark.parametrize(
    ("rarity", "ball"),
    [
        ("common", "Poké Ball"),
        ("uncommon", "Great Ball"),
        ("rare", "Ultra Ball"),
        ("very_rare", "Cherish Ball"),
        ("legendary", "Master Ball"),
        ("", "Poké Ball"),  # a species without rarity yet
    ],
)
def test_every_rarity_has_its_ball(rarity, ball):
    assert ball_name(rarity) == ball
    assert ball_sprite(rarity).endswith(ball.lower().replace("é", "e").replace(" ", "-") + ".png")


def test_the_door_on_the_map_shows_the_waiting_count(guest_with_arrivals):
    html = guest_with_arrivals.get(reverse("ranch:index")).content.decode()
    assert "img/ranch-map.png" in html
    assert 'title="Welcome area: 3 waiting"' in html
    assert '<span class="map-badge animate-hop">3</span>' in html


def test_revealing_one_pokemon(guest_with_arrivals):
    html = guest_with_arrivals.post(reverse("ranch:reveal")).content.decode()
    assert "Ivysaur" in html
    assert "NEW!" in html
    assert '1 <span class="text-muted">/ 3</span>' in html  # its rank in the series
    assert ">Next</button>" in html
    assert "Skip to the summary" in html


def summary_cards(html):
    """Number of Pokémon cards in the summary."""
    return html.count('class="summary-card')


def test_the_last_reveal_of_a_series_leads_to_its_summary(guest_with_arrivals):
    for _ in range(2):
        guest_with_arrivals.post(reverse("ranch:reveal"))
    last = guest_with_arrivals.post(reverse("ranch:reveal")).content.decode()
    assert "See the summary" in last
    assert "Next" not in last

    html = guest_with_arrivals.post(reverse("ranch:reveal_summary")).content.decode()
    assert "Your new arrivals" in html
    assert summary_cards(html) == 3  # every Pokémon of the series, not just the last
    # The first Ivysaur is new, the two others turn into candies
    assert html.count("NEW!") == 1
    # The series is over: asking again shows an empty summary
    again = guest_with_arrivals.post(reverse("ranch:reveal_summary")).content.decode()
    assert summary_cards(again) == 0


def test_skipping_goes_to_the_summary_of_the_whole_series(guest_with_arrivals):
    guest_with_arrivals.post(reverse("ranch:reveal"))  # one revealed before skipping
    html = guest_with_arrivals.post(reverse("ranch:reveal_all")).content.decode()
    assert "Your new arrivals" in html
    assert summary_cards(html) == 3
    assert not Arrival.objects.exists()


def test_a_single_arrival_ends_without_summary(client, common, monkeypatch):
    now = START + timedelta(minutes=5)
    monkeypatch.setattr("django.utils.timezone.now", lambda: now)
    client.get(reverse("ranch:index"))
    Player.objects.update(tutorial_step=tutorial.DONE)
    monkeypatch.setattr("django.utils.timezone.now", lambda: now + timedelta(hours=1))
    client.get(reverse("ranch:index"))  # the catch-up brings one arrival

    html = client.post(reverse("ranch:reveal")).content.decode()
    assert "data-close-dialog" in html  # "Done"
    assert "See the summary" not in html
    assert "/ 1" not in html  # no "1 / 1" counter
    assert "reveal_series" not in client.session  # nothing left to summarise


def test_reveals_require_post(guest_with_arrivals):
    # A GET must never change the game state (links, prefetching, crawlers...)
    assert guest_with_arrivals.get(reverse("ranch:reveal")).status_code == 405
    assert guest_with_arrivals.get(reverse("ranch:reveal_all")).status_code == 405
    assert guest_with_arrivals.get(reverse("ranch:reveal_summary")).status_code == 405


def test_the_dialog_stays_closed_when_nobody_is_waiting(client):
    html = client.get(reverse("ranch:index")).content.decode()
    assert "data-auto-open" not in html
    assert "Welcome back" not in html
    # The door is then a plain link to the Welcome area, without a badge
    assert 'title="Welcome area"' in html
    assert "map-badge" not in html


def test_balls_make_rows_of_even_lengths():
    assert [len(row) for row in balanced_rows(range(13), 10)] == [7, 6]
    assert [len(row) for row in balanced_rows(range(8), 6)] == [4, 4]
    assert [len(row) for row in balanced_rows(range(5), 10)] == [5]
    assert balanced_rows([], 10) == []
