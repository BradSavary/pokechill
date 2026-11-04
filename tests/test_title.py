"""Tests of the title screen (/): who sees it, the Start button, what's new."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from ranch.models import Player
from ranch.news import NewsError, all_news, latest, parse_news
from tests.conftest import start_game

pytestmark = pytest.mark.django_db

User = get_user_model()


def test_a_new_visitor_sees_the_title_screen_and_creates_nothing(client):
    html = client.get(reverse("home")).content.decode()
    assert "In development" in html
    assert f'action="{reverse("start")}"' in html  # the Start button, a POST
    assert "Log in" in html
    assert 'aria-label="Main navigation"' not in html  # no menu yet
    assert User.objects.count() == 0  # only Start creates the guest


def test_the_next_steps_of_the_roadmap_are_not_announced(client):
    html = client.get(reverse("home")).content.decode()
    assert "Step" not in html
    assert "Expedition" not in html


def test_starting_creates_a_guest_and_its_save(client):
    response = client.post(reverse("start"))
    assert response["Location"] == reverse("ranch:index")
    player = Player.objects.get()
    assert not player.user.has_usable_password()  # a guest


def test_start_only_accepts_post(client):
    assert client.get(reverse("start")).status_code == 405
    assert User.objects.count() == 0


def test_a_guest_continues_their_game(client):
    start_game(client)
    html = client.get(reverse("home")).content.decode()
    assert "Continue" in html
    assert f'href="{reverse("ranch:index")}"' in html
    assert "Save your game" in html  # invited to create an account
    assert f'action="{reverse("start")}"' not in html


def test_a_registered_player_goes_straight_to_the_ranch(client):
    User.objects.create_user("ash", password="a-strong-pass-1234")
    client.login(username="ash", password="a-strong-pass-1234")
    response = client.get(reverse("home"))
    assert response.status_code == 302
    assert response["Location"] == reverse("ranch:index")


@pytest.mark.parametrize("page", ["ranch:index", "zones:index", "lab:index"])
def test_a_game_page_without_a_game_leads_to_the_title_screen(client, page):
    response = client.get(reverse(page))
    assert response.status_code == 302
    assert response["Location"] == reverse("home")
    assert User.objects.count() == 0  # a crawler or a link preview creates nothing


def test_an_htmx_request_without_a_game_reloads_the_title_screen(client):
    response = client.post(reverse("ranch:feeder_fill"), HTTP_HX_REQUEST="true")
    assert response["HX-Redirect"] == "/"


def test_logging_out_leads_to_the_title_screen(client):
    User.objects.create_user("ash", password="a-strong-pass-1234")
    client.login(username="ash", password="a-strong-pass-1234")
    response = client.post(reverse("accounts:logout"))
    assert response["Location"] == reverse("home")


# --- What's new ----------------------------------------------------------------------


def test_the_title_screen_shows_the_latest_news(client):
    html = client.get(reverse("home")).content.decode()
    for news in latest():
        assert news.text.replace("'", "&#x27;") in html
    assert len(latest()) <= 3


def test_the_news_file_is_valid():
    assert all_news()  # parsed (and sorted) without error


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({"date": "2026-10-30"}, "holds a list"),
        ([{"date": "2026-10-30"}], "each news is"),
        ([{"date": "30/10/2026", "text": "Hi"}], "invalid date"),
        ([{"date": "2026-10-30", "text": " "}], "needs a text"),
        (
            [{"date": "2026-10-28", "text": "Old"}, {"date": "2026-10-30", "text": "New"}],
            "newest first",
        ),
    ],
)
def test_malformed_news_are_refused(raw, message):
    with pytest.raises(NewsError, match=message):
        parse_news(raw)
