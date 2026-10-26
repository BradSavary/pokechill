"""Operations on the player's game state, used by the views."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.db.models import Q
from django.utils import timezone

from game.clock import floor_to_hour

from .models import Player


def ensure_player(user) -> Player:
    """
    The game save of `user`, created on first use.

    A new save starts at the current hour: arrivals begin with the next one.
    """
    player, _created = Player.objects.get_or_create(
        user=user, defaults={"last_slot": floor_to_hour(timezone.now())}
    )
    return player


def mark_seen(player: Player) -> None:
    """Record a visit (one small UPDATE, without reloading the player)."""
    player.last_seen_at = timezone.now()
    Player.objects.filter(pk=player.pk).update(last_seen_at=player.last_seen_at)


def inactive_guests(days: int):
    """
    Guest users who haven't played for `days` days.

    A guest's password starts with Django's "unusable" marker. Registered
    players and staff are never selected, however long their absence.
    A guest without a save (none created yet) is judged on its sign-up date.
    """
    cutoff = timezone.now() - timedelta(days=days)
    return get_user_model().objects.filter(
        Q(player__last_seen_at__lt=cutoff) | Q(player__isnull=True, date_joined__lt=cutoff),
        password__startswith=UNUSABLE_PASSWORD_PREFIX,
        is_staff=False,
    )
