"""Tests of the development commands: players, rewind_clock, reset_player."""

from datetime import UTC, datetime, timedelta
from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from ranch.models import Player

pytestmark = pytest.mark.django_db

START = datetime(2026, 1, 15, 8, tzinfo=UTC)


@pytest.fixture
def players(django_user_model):
    """Two players: misty played long ago, ash just now."""
    old = Player.objects.create(
        user=django_user_model.objects.create_user("misty"),
        last_slot=START,
        last_seen_at=START - timedelta(days=3),
    )
    recent = Player.objects.create(
        user=django_user_model.objects.create_user("ash"), last_slot=START
    )
    return old, recent


def run(*args, **options):
    out = StringIO()
    call_command(*args, stdout=out, **options)
    return out.getvalue()


def test_players_lists_the_most_recent_first(players):
    lines = run("players").splitlines()
    assert lines[1].startswith("ash")
    assert lines[2].startswith("misty")


def test_rewind_clock_targets_the_last_active_player_by_default(players):
    _misty, ash = players
    run("rewind_clock", 5)
    ash.refresh_from_db()
    assert ash.last_slot == START - timedelta(hours=5)


def test_rewind_clock_of_a_named_player(players):
    misty, _ash = players
    run("rewind_clock", 2, player="misty")
    misty.refresh_from_db()
    assert misty.last_slot == START - timedelta(hours=2)


def test_reset_player_deletes_the_save_but_keeps_the_account(players, django_user_model):
    run("reset_player", player="misty")
    assert not Player.objects.filter(user__username="misty").exists()
    assert django_user_model.objects.filter(username="misty").exists()


def test_unknown_player(players):
    with pytest.raises(CommandError, match="No player named"):
        run("rewind_clock", 1, player="gary")
