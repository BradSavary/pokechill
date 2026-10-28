"""
Django command: `uv run python manage.py purge_guests [--days 180] [--dry-run]`.

Deletes guest accounts (and their saves) that stayed inactive too long.
Registered players are never deleted. In production it also runs every day,
through a Vercel Cron (see ranch/internal_views.py).
"""

from django.core.management.base import BaseCommand

from ranch.services import GUEST_RETENTION_DAYS, inactive_guests, purge_inactive_guests


class Command(BaseCommand):
    help = "Delete guest accounts inactive for more than --days days."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=GUEST_RETENTION_DAYS)
        parser.add_argument("--dry-run", action="store_true", help="Only count, delete nothing.")

    def handle(self, *args, days, dry_run, **options):
        if dry_run:
            count = inactive_guests(days).count()
            self.stdout.write(f"{count} guests inactive for {days}+ days (dry run).")
            return
        deleted = purge_inactive_guests(days)
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} inactive guests."))
