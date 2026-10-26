"""
Django command: `uv run python manage.py players`.

Development tool: lists the players, most recently active first.
"""

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from accounts.services import is_guest
from ranch.models import Player


class Command(BaseCommand):
    help = "List players: name, guest or not, last visit, waiting arrivals, collection."

    def handle(self, *args, **options):
        players = (
            Player.objects.select_related("user")
            # distinct=True: two joined tables would otherwise multiply the counts
            .annotate(
                waiting=Count("arrivals", distinct=True), owned=Count("pokemon", distinct=True)
            )
            .order_by("-last_seen_at")
        )
        if not players:
            self.stdout.write("No player yet: open the Ranch in your browser.")
            return

        now = timezone.now()
        self.stdout.write(
            f"{'username':<22} {'kind':<6} {'last seen':>10} {'waiting':>8} {'owned':>6}"
        )
        for player in players:
            minutes = int((now - player.last_seen_at).total_seconds() // 60)
            seen = f"{minutes} min" if minutes < 120 else f"{minutes // 60} h"
            kind = "guest" if is_guest(player.user) else "user"
            self.stdout.write(
                f"{player.user.username:<22} {kind:<6} {seen:>10} "
                f"{player.waiting:>8} {player.owned:>6}"
            )
