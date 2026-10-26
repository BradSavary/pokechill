"""
Django command: `uv run python manage.py reset_player [--player NAME]`.

Development tool: deletes a player's game save (collection, candies, waiting
arrivals) but keeps the account. The next visit to a game page starts a
fresh save with the three starters. Without --player, the most recently
active player is used.
"""

from django.core.management.base import BaseCommand

from ._players import find_player


class Command(BaseCommand):
    help = "Delete a player's game save (the account is kept) to start over."

    def add_arguments(self, parser):
        parser.add_argument("--player", help="Username (default: last active player).")

    def handle(self, *args, player, **options):
        target = find_player(player)
        username = target.user.username
        target.delete()  # CASCADE: Pokémon, candies and arrivals go with it
        self.stdout.write(self.style.SUCCESS(f"{username}: save deleted. Reload the Ranch."))
