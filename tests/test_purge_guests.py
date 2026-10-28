"""Tests of the purge of inactive guest accounts."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from ranch.models import Player
from ranch.services import ensure_player

pytestmark = pytest.mark.django_db

User = get_user_model()


def make_user(username, *, guest, days_inactive, with_player=True, staff=False):
    """A user whose last activity (or sign-up, without a save) was `days_inactive` ago."""
    long_ago = timezone.now() - timedelta(days=days_inactive)
    user = User(username=username, is_staff=staff, date_joined=long_ago)
    if guest:
        user.set_unusable_password()
    else:
        user.set_password("a-strong-pass-1234")
    user.save()
    if with_player:
        player = ensure_player(user)
        Player.objects.filter(pk=player.pk).update(last_seen_at=long_ago)
    return user


def remaining_usernames():
    return set(User.objects.values_list("username", flat=True))


def test_only_long_inactive_guests_are_deleted():
    make_user("guest-old", guest=True, days_inactive=200)
    make_user("guest-recent", guest=True, days_inactive=10)
    make_user("ash", guest=False, days_inactive=900)  # registered: never deleted
    make_user("admin", guest=True, days_inactive=900, staff=True)

    call_command("purge_guests")

    assert remaining_usernames() == {"guest-recent", "ash", "admin"}


def test_the_save_is_deleted_with_the_guest():
    make_user("guest-old", guest=True, days_inactive=200)
    call_command("purge_guests")
    assert not Player.objects.exists()


def test_a_guest_without_save_is_judged_on_its_sign_up_date():
    make_user("guest-no-save", guest=True, days_inactive=200, with_player=False)
    call_command("purge_guests")
    assert remaining_usernames() == set()


def test_days_option_and_dry_run():
    make_user("guest-old", guest=True, days_inactive=40)
    call_command("purge_guests", days=30, dry_run=True)
    assert remaining_usernames() == {"guest-old"}  # dry run: nothing deleted
    call_command("purge_guests", days=30)
    assert remaining_usernames() == set()


def test_playing_keeps_a_guest_active(client):
    client.get(reverse("ranch:index"))
    player = Player.objects.get()
    Player.objects.filter(pk=player.pk).update(last_seen_at=timezone.now() - timedelta(days=200))

    client.get(reverse("ranch:index"))  # the guest comes back

    player.refresh_from_db()
    assert timezone.now() - player.last_seen_at < timedelta(minutes=1)
    call_command("purge_guests")
    assert Player.objects.exists()


# --- The daily Vercel Cron --------------------------------------------------------------

CRON_URL = "/internal/purge-guests/"


@pytest.fixture
def cron_secret(settings):
    settings.CRON_SECRET = "s3cret"
    return "s3cret"


def test_the_cron_purges_with_the_secret(client, cron_secret):
    make_user("guest-old", guest=True, days_inactive=200)
    make_user("guest-recent", guest=True, days_inactive=10)
    response = client.get(CRON_URL, headers={"Authorization": f"Bearer {cron_secret}"})
    assert response.json() == {"deleted": 1, "days": 180}
    assert remaining_usernames() == {"guest-recent"}


@pytest.mark.parametrize("header", [None, "Bearer wrong", "s3cret"])
def test_the_cron_url_refuses_anyone_else(client, cron_secret, header):
    make_user("guest-old", guest=True, days_inactive=200)
    headers = {"Authorization": header} if header else {}
    assert client.get(CRON_URL, headers=headers).status_code == 403
    assert remaining_usernames() == {"guest-old"}  # nothing deleted


def test_without_a_configured_secret_the_cron_url_is_closed(client, settings):
    settings.CRON_SECRET = ""
    make_user("guest-old", guest=True, days_inactive=200)
    # Even an empty "Bearer " can't match an empty secret
    assert client.get(CRON_URL, headers={"Authorization": "Bearer "}).status_code == 403
    assert remaining_usernames() == {"guest-old"}


def test_visiting_the_cron_url_creates_no_guest(client, cron_secret):
    client.get(CRON_URL)
    assert not User.objects.exists()
