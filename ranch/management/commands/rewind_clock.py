"""
Django command: `uv run python manage.py rewind_clock <username> <hours>`.

Development tool: moves a player's clock back, as if they had been away for
<hours> hours. Their next visit to a game page then replays those hours.
Usernames of guests are visible in the admin (guest-...).
"""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError

from ranch.models import Player


class Command(BaseCommand):
    help = "Move a player's clock back by N hours, to test the hourly catch-up."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("hours", type=int)

    def handle(self, *args, username, hours, **options):
        player = Player.objects.filter(user__username=username).first()
        if player is None:
            raise CommandError(f"No player named {username!r}.")
        player.last_slot -= timedelta(hours=hours)
        player.save(update_fields=["last_slot"])
        self.stdout.write(
            self.style.SUCCESS(f"{username}'s clock moved back {hours} h: visit the Ranch.")
        )
