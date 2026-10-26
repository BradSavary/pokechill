"""Tests of guest mode, sign up (guest conversion), log in and log out."""

from datetime import UTC, datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from accounts.services import is_guest
from ranch.models import Player

pytestmark = pytest.mark.django_db

User = get_user_model()
PASSWORD = "a-strong-pass-1234"


def sign_up(client, username="ash"):
    return client.post(
        reverse("accounts:sign_up"),
        {"username": username, "password1": PASSWORD, "password2": PASSWORD},
    )


def logged_in_user(client):
    """The user of the client's session (Django's auth key in the session)."""
    return User.objects.get(pk=client.session["_auth_user_id"])


# --- Guest mode --------------------------------------------------------------


def test_first_visit_to_the_ranch_creates_a_guest_with_a_save(client):
    response = client.get(reverse("ranch:index"))

    assert response.status_code == 200
    user = logged_in_user(client)
    assert is_guest(user)
    assert user.username.startswith("guest-")
    assert Player.objects.filter(user=user).exists()


def test_the_guest_is_kept_across_visits(client):
    client.get(reverse("ranch:index"))
    client.get(reverse("ranch:index"))
    assert User.objects.count() == 1


def test_a_new_save_starts_at_the_current_hour(client, monkeypatch):
    now = datetime(2026, 10, 26, 14, 37, tzinfo=UTC)
    monkeypatch.setattr("django.utils.timezone.now", lambda: now)
    client.get(reverse("ranch:index"))
    assert Player.objects.get().last_slot == datetime(2026, 10, 26, 14, tzinfo=UTC)


def test_browsing_the_pokedex_creates_no_account(client):
    # Web crawlers browse public pages: they must not create guests
    client.get(reverse("pokedex:index"))
    assert User.objects.count() == 0


def test_guests_are_invited_to_save_their_game(client):
    html = client.get(reverse("ranch:index")).content.decode()
    assert "Save your game" in html
    assert "Log out" not in html  # logging out would lose the save


# --- Sign up -------------------------------------------------------------------


def test_signing_up_converts_the_guest_and_keeps_the_save(client):
    client.get(reverse("ranch:index"))
    guest = logged_in_user(client)
    save = Player.objects.get(user=guest)

    response = sign_up(client)

    assert response.status_code == 302
    user = logged_in_user(client)  # still logged in after the password change
    assert user.pk == guest.pk  # same user, not a new one
    assert user.username == "ash"
    assert not is_guest(user)
    assert Player.objects.get(user=user) == save
    assert User.objects.count() == 1


def test_signing_up_without_playing_first_creates_an_account(client):
    sign_up(client)
    assert logged_in_user(client).username == "ash"


def test_guest_usernames_are_reserved(client):
    response = sign_up(client, username="guest-123")
    assert response.status_code == 200
    assert "cannot start with" in response.content.decode()


def test_passwords_must_match(client):
    response = client.post(
        reverse("accounts:sign_up"),
        {"username": "ash", "password1": PASSWORD, "password2": "something-else-987"},
    )
    assert response.status_code == 200
    assert User.objects.count() == 0


def test_registered_players_are_sent_back_to_the_ranch(client):
    sign_up(client)
    response = client.get(reverse("accounts:sign_up"))
    assert response.status_code == 302


# --- Log in / log out ----------------------------------------------------------


def test_log_in_and_log_out(client):
    User.objects.create_user("misty", password=PASSWORD)

    response = client.post(reverse("accounts:login"), {"username": "misty", "password": PASSWORD})
    assert response["Location"] == reverse("ranch:index")
    assert logged_in_user(client).username == "misty"

    client.post(reverse("accounts:logout"))
    assert "_auth_user_id" not in client.session


def test_nobody_can_log_in_as_a_guest(client):
    client.get(reverse("ranch:index"))
    guest = logged_in_user(client)
    client.post(reverse("accounts:logout"))

    # A guest has no usable password: even an empty one is refused
    response = client.post(reverse("accounts:login"), {"username": guest.username, "password": ""})
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


def test_the_generated_guest_username_is_not_suggested(client):
    client.get(reverse("ranch:index"))
    guest = logged_in_user(client)
    html = client.get(reverse("accounts:sign_up")).content.decode()
    assert guest.username not in html
