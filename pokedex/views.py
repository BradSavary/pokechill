"""
Pokédex pages.

The page has two panes: the species list (left) and the entry of the
selected species (right). Every entry has its own URL (/pokedex/25/), so the
page works without JavaScript; with HTMX, clicking a species only swaps the
right pane instead of reloading the whole page.
"""

from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, render

from .models import Species, SpeciesMove, Type


def is_htmx(request) -> bool:
    """
    True for a request sent by HTMX that expects an HTML fragment.

    When the user goes back in history and HTMX has no cached copy of the
    page, it asks for the full page (HX-History-Restore-Request): that one
    must get the whole layout, not a fragment.
    """
    return (
        request.headers.get("HX-Request") == "true"
        and request.headers.get("HX-History-Restore-Request") != "true"
    )


def filter_species(params):
    """Species matching the search box (`q`) and the type filter (`type`)."""
    species = Species.objects.select_related("primary_type", "secondary_type")
    if query := params.get("q", "").strip():
        species = species.filter(name__icontains=query)
    if type_slug := params.get("type"):
        # Q objects combine conditions with OR (|), here: either type matches
        species = species.filter(
            Q(primary_type__slug=type_slug) | Q(secondary_type__slug=type_slug)
        )
    return species


def get_entry(number: int) -> Species:
    """A species with everything its entry displays, in a handful of SQL queries."""
    learnset = SpeciesMove.objects.select_related("move__type")
    return get_object_or_404(
        Species.objects.select_related(
            "primary_type", "secondary_type", "evolution_chain"
        ).prefetch_related(Prefetch("learnset", queryset=learnset)),
        number=number,
    )


def entry_context(species: Species) -> dict:
    """Template values of a species entry."""
    learnset = list(species.learnset.all())
    return {
        "species": species,
        "family": species.evolution_chain.species.order_by("evolution_stage", "number"),
        "level_up_moves": [
            m for m in learnset if m.learn_method == SpeciesMove.LearnMethod.LEVEL_UP
        ],
        "machine_moves": [m for m in learnset if m.learn_method == SpeciesMove.LearnMethod.MACHINE],
        "stats": [
            ("HP", species.hp),
            ("Attack", species.attack),
            ("Defense", species.defense),
            ("Sp. Atk", species.special_attack),
            ("Sp. Def", species.special_defense),
            ("Speed", species.speed),
        ],
    }


def render_page(request, species: Species | None):
    """The full Pokédex page, with `species` selected in the right pane."""
    context = {
        "active_tab": "pokedex",
        "species_list": filter_species(request.GET),
        # Moves bring types no Kanto species has (e.g. Dark): hide them
        "types": Type.objects.filter(
            Q(primary_species__isnull=False) | Q(secondary_species__isnull=False)
        ).distinct(),
        "selected": species.number if species else None,
    }
    if species:
        context |= entry_context(species)
    return render(request, "pokedex/index.html", context)


def index(request):
    """Pokédex home: the first species is selected (empty state if none imported)."""
    return render_page(request, Species.objects.first())


def species_detail(request, number: int):
    """Entry of one species: a fragment for HTMX, the full page otherwise."""
    species = get_entry(number)
    if is_htmx(request):
        return render(request, "pokedex/_entry.html", entry_context(species))
    return render_page(request, species)


def species_list(request):
    """The filtered species list, requested by HTMX while typing in the search box."""
    selected = request.GET.get("selected")
    return render(
        request,
        "pokedex/_species_list.html",
        {
            "species_list": filter_species(request.GET),
            "selected": int(selected) if selected and selected.isdigit() else None,
        },
    )
