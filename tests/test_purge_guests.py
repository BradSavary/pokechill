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
