from django.contrib import admin

from .models import Arrival, CandyStock, OwnedPokemon, Player


class OwnedPokemonInline(admin.TabularInline):
    model = OwnedPokemon
    extra = 0
    fields = ["species", "level", "unlocked_natures", "shiny_unlocked", "obtained_at"]
    readonly_fields = ["obtained_at"]


class CandyStockInline(admin.TabularInline):
    model = CandyStock
    extra = 0


class ArrivalInline(admin.TabularInline):
    """The Welcome area: Pokémon waiting to be revealed."""

    model = Arrival
    extra = 0


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ["user", "created_at", "last_seen_at", "last_slot"]
    search_fields = ["user__username"]
    list_select_related = ["user"]
    inlines = [ArrivalInline, OwnedPokemonInline, CandyStockInline]
