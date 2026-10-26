"""
Django command: `uv run python manage.py rewind_clock <hours> [--player NAME]`.

Development tool: moves a player's clock back, as if they had been away for
<hours> hours. Their next visit to a game page then replays those hours.
Without --player, the most recently active player is used (you, in your
browser). Player names are listed by `manage.py players`.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand

from ._players import find_player


class Command(BaseCommand):
    help = "Move a player's clock back by N hours, to test the hourly catch-up."

    def add_arguments(self, parser):
        parser.add_argument("hours", type=int)
        parser.add_argument("--player", help="Username (default: last active player).")

    def handle(self, *args, hours, player, **options):
        target = find_player(player)
        target.last_slot -= timedelta(hours=hours)
        target.save(update_fields=["last_slot"])
        self.stdout.write(
            self.style.SUCCESS(
                f"{target.user.username}: clock moved back {hours} h. Reload the Ranch."
            )
        )
