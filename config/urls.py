"""Root URL configuration of PokéChill."""

from django.contrib import admin
from django.templatetags.static import static
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("pokedex/", include("pokedex.urls")),
    path("ranch/", include("ranch.urls")),
    path("zones/", include("ranch.zone_urls")),
    # Professor Oak's lab: the skill tree
    path("lab/", include("ranch.lab_urls")),
    # Called by the Vercel Crons only (protected by a secret)
    path("internal/", include("ranch.internal_urls")),
    # The Ranch is the main page of the game
    path("", RedirectView.as_view(pattern_name="ranch:index"), name="home"),
    # Some browsers ask for /favicon.ico whatever the page says: point them to
    # the real icon (permanent redirect, cached by the browser)
    path("favicon.ico", RedirectView.as_view(url=static("img/favicon.png"), permanent=True)),
]
