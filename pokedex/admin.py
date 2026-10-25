"""Admin pages to browse and check the imported Pokédex data."""

from django.contrib import admin

from .models import EvolutionChain, Move, Species, SpeciesMove, Type


@admin.register(Type)
class TypeAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]


class SpeciesMoveInline(admin.TabularInline):
    """Shows the learnset directly on the species page."""

    model = SpeciesMove
    extra = 0
    # A dropdown with every move would be huge: use a search field instead
    autocomplete_fields = ["move"]


@admin.register(Species)
class SpeciesAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "primary_type", "secondary_type", "evolution_stage"]
    list_display_links = ["number", "name"]
    list_filter = ["primary_type", "evolution_stage", "is_legendary"]
    search_fields = ["name", "slug"]
    # Loads the related rows in the same SQL query (avoids one query per row)
    list_select_related = ["primary_type", "secondary_type"]
    inlines = [SpeciesMoveInline]


class SpeciesInline(admin.TabularInline):
    model = Species
    fields = ["number", "name", "evolution_stage", "evolves_from"]
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True


@admin.register(EvolutionChain)
class EvolutionChainAdmin(admin.ModelAdmin):
    list_display = ["__str__", "pokeapi_id"]
    inlines = [SpeciesInline]


@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    list_display = ["name", "type", "damage_class", "power", "accuracy", "pp"]
    list_filter = ["type", "damage_class"]
    search_fields = ["name", "slug"]  # required by autocomplete_fields above
