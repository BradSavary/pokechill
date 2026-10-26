"""
Django command: `uv run python manage.py purge_guests [--days 180] [--dry-run]`.

Deletes guest accounts (and their saves) that stayed inactive too long.
Registered players are never deleted.
"""

from django.core.management.base import BaseCommand

from ranch.services import inactive_guests

DEFAULT_DAYS = 180


class Command(BaseCommand):
    help = "Delete guest accounts inactive for more than --days days."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
        parser.add_argument("--dry-run", action="store_true", help="Only count, delete nothing.")

    def handle(self, *args, days, dry_run, **options):
        guests = inactive_guests(days)
        if dry_run:
            self.stdout.write(f"{guests.count()} guests inactive for {days}+ days (dry run).")
            return
        # delete() also removes what depends on each user (CASCADE): the save
        _total, per_model = guests.delete()
        deleted = per_model.get("auth.User", 0)
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} inactive guests."))
