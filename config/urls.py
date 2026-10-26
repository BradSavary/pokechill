"""Root URL configuration of PokéChill."""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("pokedex/", include("pokedex.urls")),
    path("ranch/", include("ranch.urls")),
    # The Ranch is the main page of the game
    path("", RedirectView.as_view(pattern_name="ranch:index"), name="home"),
]
