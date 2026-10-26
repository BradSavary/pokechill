"""
The player's game state.

Django's User handles identity (username, password); Player holds the game
save attached to it. Every table of the game state points to a Player.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Player(models.Model):
    # One user has at most one game save, and a save belongs to one user.
    # CASCADE: deleting a user deletes their save.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="player"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    # Last hourly slot processed by the catch-up (UTC, on the hour). The next
    # visit replays every hour after this one (see game.arrivals.catch_up).
    last_slot = models.DateTimeField()
    # Last visit to a game page: inactive guests are purged after a while
    last_seen_at = models.DateTimeField(default=timezone.now)

    def __str__(self) -> str:
        return f"Player of {self.user.username}"
