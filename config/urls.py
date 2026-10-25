"""Root URL configuration of PokéChill."""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("pokedex/", include("pokedex.urls")),
    # Until the Ranch page exists (step 1), the home page is the Pokédex.
    path("", RedirectView.as_view(pattern_name="pokedex:index"), name="home"),
]
