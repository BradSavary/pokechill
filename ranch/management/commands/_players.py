"""
Helpers shared by the development commands.

Django ignores files starting with an underscore in management/commands/:
this module is not a command itself.
"""

from django.core.management.base import CommandError

from ranch.models import Player


def find_player(username: str | None) -> Player:
    """The player named `username`, or the most recently active one if None."""
    players = Player.objects.select_related("user")
    if username:
        player = players.filter(user__username=username).first()
        if player is None:
            raise CommandError(f"No player named {username!r} (see: manage.py players).")
        return player
    player = players.order_by("-last_seen_at").first()
    if player is None:
        raise CommandError("No player yet: open the Ranch in your browser first.")
    return player
