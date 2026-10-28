"""
Pokédex pages.

The page has two panes: the species list (left) and the entry of the
selected species (right). Every entry has its own URL (/pokedex/25/), so the
page works without JavaScript; with HTMX, clicking a species only swaps the
right pane instead of reloading the whole page.

For a player, the Pokédex is personal: species they own appear in full, the
others as silhouettes. A visitor without a save (crawler, portfolio visitor)
sees the whole catalogue, and no account is created for them.

The player's data comes from the ranch app: views may combine apps, while
the pokedex models never depend on ranch (no circular dependency).
"""

from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, render

from game.moves import default_moves
from ranch import tutorial
from ranch.services import candies_of, collection_of, player_for

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


def filter_species(params, known_ids: set[int] | None = None):
    """
    Species matching the search box (`q`) and the type filter (`type`).

    For a player (`known_ids` given), the name search only matches species
    they own: searching must not reveal the names of unknown species.
    """
    species = Species.objects.select_related("primary_type", "secondary_type")
    if query := params.get("q", "").strip():
        species = species.filter(name__icontains=query)
        if known_ids is not None:
            species = species.filter(id__in=known_ids)
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


def dex_context(request) -> dict:
    """
    Who is looking at the Pokédex.

    `owned_ids` is None for a visitor without a save (full catalogue), or the
    set of species ids the player owns.
    """
    player = player_for(request.user)
    collection = collection_of(player) if player else None
    return {
        "player": player,
        "collection": collection,
        "owned_ids": set(collection) if collection is not None else None,
    }


def entry_context(species: Species, dex: dict) -> dict:
    """Template values of a species entry."""
    owned = dex["collection"].get(species.id) if dex["player"] else None
    # The player's Pokémon knows the moves of its level; the public catalogue
    # shows the moves a species has when it arrives at the ranch
    level = owned.level if owned else species.min_level
    level_up = [
        entry
        for entry in species.learnset.all()
        if entry.learn_method == SpeciesMove.LearnMethod.LEVEL_UP
    ]
    move_by_slug = {entry.move.slug: entry.move for entry in level_up}
    known_moves = default_moves([(entry.level, entry.move.slug) for entry in level_up], level)
    return {
        "species": species,
        # Shown in full for its owner, or in the public catalogue
        "known": dex["player"] is None or owned is not None,
        "owned": owned,
        "candies": candies_of(dex["player"], species.evolution_chain) if owned else 0,
        "owned_ids": dex["owned_ids"],
        "moves": [move_by_slug[slug] for slug in known_moves],
        "moves_level": level,
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
    dex = dex_context(request)
    context = {
        "active_tab": "pokedex",
        "species_list": filter_species(request.GET, dex["owned_ids"]),
        # Moves bring types no Kanto species has (e.g. Dark): hide them
        "types": Type.objects.filter(
            Q(primary_species__isnull=False) | Q(secondary_species__isnull=False)
        ).distinct(),
        "selected": species.number if species else None,
        "owned_ids": dex["owned_ids"],
        "owned_count": len(dex["owned_ids"]) if dex["owned_ids"] is not None else None,
        "total_count": Species.objects.count(),
        **tutorial.context(dex["player"], "pokedex"),
    }
    if species:
        context |= entry_context(species, dex)
    return render(request, "pokedex/index.html", context)


def index(request):
    """Pokédex home: the first species is selected (empty state if none imported)."""
    return render_page(request, Species.objects.first())


def species_detail(request, number: int):
    """Entry of one species: a fragment for HTMX, the full page otherwise."""
    species = get_entry(number)
    if is_htmx(request):
        return render(request, "pokedex/_entry.html", entry_context(species, dex_context(request)))
    return render_page(request, species)


def species_list(request):
    """The filtered species list, requested by HTMX while typing in the search box."""
    dex = dex_context(request)
    selected = request.GET.get("selected")
    return render(
        request,
        "pokedex/_species_list.html",
        {
            "species_list": filter_species(request.GET, dex["owned_ids"]),
            "owned_ids": dex["owned_ids"],
            "selected": int(selected) if selected and selected.isdigit() else None,
        },
    )
