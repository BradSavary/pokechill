"""Internal URLs (prefix /internal/), called by the Vercel Crons only."""

from django.urls import path

from . import internal_views

app_name = "internal"

urlpatterns = [
    path("purge-guests/", internal_views.purge_guests, name="purge_guests"),
]
