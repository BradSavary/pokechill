"""
Internal URLs, called by the Vercel Crons (scheduled tasks), never by players.

A Vercel Cron is a GET request that Vercel sends on a schedule (vercel.json,
"crons"). When the project has a CRON_SECRET environment variable, Vercel
adds it to the request: "Authorization: Bearer <secret>". The view checks
it, so nobody else can trigger the task by visiting the URL.

GET is the only method Vercel uses, so these views change data on a GET:
usually avoided, acceptable here because the secret is required.
"""

import secrets

from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_GET

from .services import GUEST_RETENTION_DAYS, purge_inactive_guests


def is_cron(request) -> bool:
    """True if the request carries the cron secret (and one is configured)."""
    if not settings.CRON_SECRET:
        return False  # no secret set (e.g. locally): nothing gets in
    sent = request.headers.get("Authorization", "")
    # compare_digest takes the same time whatever the input: an attacker
    # can't guess the secret character by character from response times
    return secrets.compare_digest(sent, f"Bearer {settings.CRON_SECRET}")


@require_GET
def purge_guests(request):
    """Every day: delete the guests inactive for GUEST_RETENTION_DAYS days."""
    if not is_cron(request):
        return HttpResponseForbidden()
    deleted = purge_inactive_guests()
    # What a function prints goes to its Vercel logs (no logging set up)
    print(f"Cron purge_guests: deleted {deleted} inactive guests.")
    return JsonResponse({"deleted": deleted, "days": GUEST_RETENTION_DAYS})
