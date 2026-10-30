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

from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.http import require_POST

from game import experience, mastery
from game.conditions import describe, species_named
from ranch import tutorial
from ranch.research import (
    ClaimError,
    claim,
    entry_research,
    species_with_rewards,
    sync_research,
)
from ranch.services import (
    CandyError,
    candies_of,
    candy_bonus,
    collection_of,
    player_for,
    use_candies,
)

from .models import Species, Type


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


def entries():
    """
    Species with everything their entry displays, in one SQL query: the
    species with its types and family (joins). Without it, each type shown
    would cost a query of its own (the "N+1 queries" problem).
    """
    return Species.objects.select_related("primary_type", "secondary_type", "evolution_chain")


def get_entry(number: int) -> Species:
    """A species with everything its entry displays (404 if unknown)."""
    return get_object_or_404(entries(), number=number)


def dex_context(request) -> dict:
    """
    Who is looking at the Pokédex.

    `owned_ids` is None for a visitor without a save (full catalogue), or the
    set of species ids the player owns.
    """
    player = player_for(request.user)
    if player:
        sync_research(player)  # once, for a save made before step 3
        request.player = player  # for the "!" of the menu (base.html)
    collection = collection_of(player) if player else None
    return {
        "player": player,
        "collection": collection,
        "owned_ids": set(collection) if collection is not None else None,
        # Research stage of each owned species, for the stars of the list
        "stages": {sid: owned.research_stage for sid, owned in (collection or {}).items()},
        # Species with rewards to claim, for the "!" of the list
        "with_rewards": species_with_rewards(player, collection) if player else set(),
    }


# The actions of an entry: each one focuses the entry on one thing (the
# buttons at its bottom). None: the default view, with the level and the
# candies of the player's Pokémon.
VIEWS = ("challenges",)


def experience_percent(species: Species, owned) -> int:
    """How full its experience bar is (0 to 100)."""
    curve = species.growth_rate
    if owned.level >= experience.MAX_LEVEL:
        return 100
    needed = experience.total_experience(curve, owned.level + 1) - experience.total_experience(
        curve, owned.level
    )
    return 100 * owned.experience // needed


def training_context(species: Species, owned, candies: int) -> dict:
    """The "Level & candies" action: the experience bar and what candies give."""
    curve, stage = species.growth_rate, species.evolution_stage
    bonus = candy_bonus(owned.player, owned)  # sweeter candies (skill tree, mastery)
    at_max = owned.level >= experience.MAX_LEVEL
    needed = (
        0
        if at_max
        else experience.total_experience(curve, owned.level + 1)
        - experience.total_experience(curve, owned.level)
    )
    to_next = experience.candies_to_next_level(curve, owned.level, owned.experience, stage, bonus)
    return {
        "at_max": at_max,
        "xp": owned.experience,
        "xp_needed": needed,
        "xp_percent": experience_percent(species, owned),
        "candy_xp": experience.candy_experience(owned.level, stage, bonus),
        "to_next": to_next,
        "can_feed": not at_max and candies > 0,
        "can_level": not at_max and 0 < to_next <= candies,
        "missing": max(0, to_next - candies),  # candies lacking for the next level
        "stage_multiplier": stage,
    }


# The sprite of each mastery bonus (game.mastery)
MASTERY_ICONS = {
    "affinity": "pokemon/items/soothe-bell.png",
    "harvest": "pokemon/items/amulet-coin.png",
    "experience": "pokemon/items/lucky-egg.png",
    "candies": "pokemon/items/rare-candy.png",
}


def mastery_context(owned) -> dict:
    """The four mastery bonuses of an entry: lit once the species is mastered."""
    return {
        "mastered": mastery.is_mastered(owned.research_stage),
        "bonuses": [
            {"label": bonus.label, "text": bonus.text, "icon": static(MASTERY_ICONS[bonus.effect])}
            for bonus in mastery.bonuses()
        ],
    }


def arrival_lines(species: Species) -> list[str]:
    """
    How a species comes to the ranch, one line per condition, in plain English
    (game.conditions.describe). The names of the species it mentions come
    from one query, only when it mentions some.
    """
    names = {}
    if slugs := species_named(species.arrival_conditions):
        names = dict(Species.objects.filter(slug__in=slugs).values_list("slug", "name"))
    return describe(species.arrival_conditions, lambda slug: names.get(slug, slug))


def entry_context(species: Species, dex: dict, view: str | None = None) -> dict:
    """Template values of a species entry, focused on the action `view`."""
    owned = dex["collection"].get(species.id) if dex["player"] else None
    candies = candies_of(dex["player"], species.evolution_chain) if owned else 0
    view = view if view in VIEWS else None
    # Stats and moves are not shown yet: they only matter with the expeditions
    return {
        "species": species,
        # Shown in full for its owner, or in the public catalogue
        "known": dex["player"] is None or owned is not None,
        "owned": owned,
        "is_visitor": dex["player"] is None,
        "candies": candies,
        "owned_ids": dex["owned_ids"],
        "view": view,
        "research": entry_research(dex["player"], species, owned),
        # The default view of an owned species shows its level and candies
        "training": training_context(species, owned, candies) if owned and not view else None,
        # How it comes: its true conditions once obtained (before, the hint of
        # its file), in the default view
        "arrival": arrival_lines(species) if owned and not view else None,
        # Its mastery bonuses (under the challenges, and the gift of the stage 3)
        "mastery": mastery_context(owned) if owned else None,
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
        "stages": dex["stages"],
        "with_rewards": dex["with_rewards"],
        "research_points": dex["player"].research_points if dex["player"] else None,
        "owned_count": len(dex["owned_ids"]) if dex["owned_ids"] is not None else None,
        "total_count": Species.objects.count(),
        **tutorial.context(dex["player"], "pokedex"),
    }
    if species:
        context |= entry_context(species, dex, request.GET.get("view"))
    return render(request, "pokedex/index.html", context)


def index(request):
    """Pokédex home: the first species is selected (empty state if none imported)."""
    return render_page(request, entries().order_by("number").first())


def species_detail(request, number: int):
    """Entry of one species: a fragment for HTMX, the full page otherwise."""
    species = get_entry(number)
    if is_htmx(request):
        context = entry_context(species, dex_context(request), request.GET.get("view"))
        return render(request, "pokedex/_entry.html", context)
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
            "stages": dex["stages"],
            "with_rewards": dex["with_rewards"],
            "selected": int(selected) if selected and selected.isdigit() else None,
        },
    )


# --- Actions of an entry (POST): claiming rewards, giving candies ------------------------


def entry_action(request, number: int, view: str | None, act) -> HttpResponse:
    """
    Run `act(player, species)` (a claim, candies...), then answer with the
    entry focused on `view`. `act` returns what the entry shows of it (a
    notice, the growth to animate...). With HTMX: the entry, plus the parts
    of the page the action may change (the "!" of the menu and of the list,
    the points), swapped "out of band". Without JavaScript: back to the
    entry's page.
    """
    player = player_for(request.user)
    if player is None:
        raise Http404("No save")
    species = get_entry(number)
    shown = {}
    try:
        shown = act(player, species)
    except (ClaimError, CandyError) as problem:
        shown = {"error": str(problem)}
    if not is_htmx(request):
        url = reverse("pokedex:detail", args=[number])
        return redirect(f"{url}?view={view}" if view else url)
    dex = dex_context(request)
    context = (
        entry_context(species, dex, view)
        | shown
        | {
            "research_points": dex["player"].research_points,
            "s": species,  # the row of the list to refresh
            "stages": dex["stages"],
            "with_rewards": dex["with_rewards"],
            "selected": number,
        }
    )
    return render(request, "pokedex/_entry_action.html", context)


@require_POST
def claim_reward(request, number: int):
    """Claim a reward of an entry (POST "what": a challenge id, "stage" or "all")."""

    def act(player, species):
        owned = collection_of(player).get(species.id)
        # Where the bar of the stages was: it fills from there to its new place
        bar_from = entry_research(player, species, owned)["bar_percent"] if owned else 0
        claimed = claim(player, species, request.POST.get("what", ""))
        # No notice (it would push the entry down): the points rise next to
        # the total, the bar of the stages fills, the gift turns green
        return {"bar_from": bar_from, "points_gained": claimed.points}

    return entry_action(request, number, "challenges", act)


@require_POST
def give_candies(request, number: int):
    """Give candies to the player's Pokémon (POST "count": a number, or "level")."""

    def act(player, species):
        count = request.POST.get("count", "")
        wanted = None if count == "level" else int(count) if count.isdigit() else 0
        before = collection_of(player)[species.id]
        _, levels = use_candies(player, species, wanted)
        # No notice: the level and the experience bar move on the entry
        return {
            "growth": {
                "levels": levels,
                # The levels passed, for the number that rolls (from the old one)
                "rolled": list(range(before.level, before.level + levels + 1)),
                # Where the bar starts from: empty after a level up
                "xp_from": 0 if levels else experience_percent(species, before),
            }
        }

    return entry_action(request, number, None, act)
