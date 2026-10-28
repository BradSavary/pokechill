"""
Zone pages: the list of the player's zones, and the map of one zone.

Opening a zone collects it, then shows its map. Collecting changes the game
state, so it is a POST followed by a redirect to the map (Post/Redirect/Get):
reloading the map never collects twice. The summary of the harvest travels
in the session, and is shown once.
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from game import balance, experience
from game.zones import experience_per_hour, is_efficient, production_per_hour
from pokedex.models import Type

from .decorators import player_required
from .models import OwnedPokemon, PlayerZone
from .zone_maps import ZONE_SPOTS, spot_style
from .zones import Harvest, ZoneError, as_worker, collect, move_pokemon, workers_of

HARVEST_KEY = "harvest"  # session key of the summary shown after a collection


def player_zone(request, slug: str) -> PlayerZone:
    """The player's zone `slug` (404 if they don't have it)."""
    return get_object_or_404(PlayerZone, player=request.player, zone=slug)


def level_span(pokemon: OwnedPokemon) -> int | None:
    """Experience needed from its level to the next one (None at the maximum level)."""
    if pokemon.level >= experience.MAX_LEVEL:
        return None
    curve = pokemon.species.growth_rate
    return experience.total_experience(curve, pokemon.level + 1) - experience.total_experience(
        curve, pokemon.level
    )


def at_work(zone: PlayerZone, pokemon: OwnedPokemon) -> dict:
    """A Pokémon as the zone page shows it: efficiency, production and experience per hour."""
    worker = as_worker(pokemon)
    return {
        "pokemon": pokemon,
        "efficient": is_efficient(zone.spec, worker),
        "per_hour": production_per_hour(zone.spec, worker) / 100,
        "xp_per_hour": experience_per_hour(zone.spec, worker),
        # Towards the next level: "245 / 860 XP" and the blue bar of the games
        "xp_span": (span := level_span(pokemon)),
        "progress": min(100, 100 * pokemon.experience // span) if span else 100,
    }


def rule_tips(zone: PlayerZone) -> dict:
    """
    The rules of a zone, explained in the "i" bubbles of its page. Written
    from the balance values, so they stay true when the game is tuned.
    """
    resource = zone.spec.resource_name.lower()  # "berry"
    return {
        "per_hour": (
            f"{zone.spec.resource_plural} gathered each hour: 1 for a Pokémon of a favoured "
            f"type, {balance.OFF_TYPE_PRODUCTION_PERCENT} % of that for the others, "
            f"+{balance.PRODUCTION_BONUS_PER_LEVEL_PERCENT} % per level. Favoured types "
            f"also earn {balance.XP_TYPE_BONUS_PERCENT} % more experience."
        ),
        "storage": (
            f"The Pokémon work up to {balance.ZONE_WORK_HOURS_CAP} hours between two "
            "collections. Then the storage is full: they stop (no "
            f"{resource}, no experience) until you collect."
        ),
        "types": (
            f"Pokémon of these types gather 1 {resource} an hour and earn "
            f"{balance.XP_TYPE_BONUS_PERCENT} % more experience. Other types work too, "
            f"at {balance.OFF_TYPE_PRODUCTION_PERCENT} %."
        ),
    }


def harvest_summary(harvest: Harvest) -> dict:
    """A collection, in plain values that fit in the session (saved as JSON)."""
    spec = harvest.zone.spec
    return {
        "zone": spec.name,
        "resource": harvest.resource,
        "resource_slug": spec.resource,
        "hours": harvest.hours,
        "growths": [
            {
                "name": g.pokemon.species.name,
                "icon": g.pokemon.species.icon_url,
                "experience": g.experience,
                "level": g.pokemon.level,
                "levels": g.levels,
            }
            for g in harvest.growths
        ],
    }


def zone_card(zone: PlayerZone) -> dict:
    """What the card of a zone shows: its Pokémon, current production, storage."""
    workers = workers_of(zone)
    cap = balance.ZONE_WORK_HOURS_CAP
    return {
        "zone": zone,
        "workers": workers,
        "types": sorted(zone.spec.types),
        "per_hour": sum(production_per_hour(zone.spec, as_worker(p)) for p in workers) / 100,
        # Hours until the storage is full (and they stop): only if someone works
        "hours_left": cap - zone.hours_worked if workers else None,
    }


@player_required
def index(request):
    """The cards of the player's zones: who works there, what is ready, how full."""
    zones = [zone_card(zone) for zone in request.player.zones.all()]
    types = {
        t.slug: t for t in Type.objects.filter(slug__in={s for c in zones for s in c["types"]})
    }
    for card in zones:
        card["types"] = [types[slug] for slug in card["types"] if slug in types]
    return render(
        request,
        "zones/index.html",
        {"active_tab": "zones", "zones": zones, "work_cap": balance.ZONE_WORK_HOURS_CAP},
    )


@require_POST  # collecting changes the game state
@player_required
def open_zone(request, slug):
    """Collect a zone, then show its map (with the summary, if anything was collected)."""
    harvest = collect(player_zone(request, slug))
    if not harvest.is_empty:
        request.session[HARVEST_KEY] = harvest_summary(harvest)
    return redirect("zones:detail", slug=slug)


@player_required
def detail(request, slug):
    """The map of a zone, its Pokémon on their spots, and the free ones to send there."""
    zone = player_zone(request, slug)
    workers = [
        at_work(zone, p) | {"style": spot_style(zone.zone, p.spot)} for p in workers_of(zone)
    ]
    # The free spots: each "+" sends the chosen Pokémon to its own spot
    taken = {w["pokemon"].spot for w in workers}
    empty_spots = [
        (spot, spot_style(zone.zone, spot))
        for spot in range(min(zone.capacity, len(ZONE_SPOTS[zone.zone])))
        if spot not in taken
    ]

    # Free Pokémon, the best production first (the table's default order)
    free = OwnedPokemon.objects.filter(player=request.player, status=OwnedPokemon.FREE)
    candidates = [
        at_work(zone, p)
        for p in free.select_related("species__primary_type", "species__secondary_type")
    ]
    candidates.sort(key=lambda c: (-c["per_hour"], -c["pokemon"].level))

    return render(
        request,
        "zones/detail.html",
        {
            "active_tab": "zones",
            "zone": zone,
            "zone_types": Type.objects.filter(slug__in=zone.spec.types).order_by("name"),
            "workers": workers,
            "empty_spots": empty_spots,
            "candidates": candidates,
            "per_hour": sum(w["per_hour"] for w in workers),
            "work_cap": balance.ZONE_WORK_HOURS_CAP,
            "xp_bonus": balance.XP_TYPE_BONUS_PERCENT,
            "tips": rule_tips(zone),
            "harvest": request.session.pop(HARVEST_KEY, None),  # shown once
        },
    )


@require_POST
@player_required
def assign(request, slug):
    """
    Send a free Pokémon (POST "pokemon": its id) to work in this zone, on the
    spot whose "+" was clicked (POST "spot"; the first free one otherwise).
    """
    pokemon = get_object_or_404(OwnedPokemon, pk=request.POST.get("pokemon"), player=request.player)
    spot = request.POST.get("spot", "")
    try:
        move_pokemon(pokemon, player_zone(request, slug), int(spot) if spot.isdigit() else None)
    except ZoneError as error:
        messages.error(request, str(error))
    return redirect("zones:detail", slug=slug)


@require_POST
@player_required
def remove(request, slug):
    """Bring a Pokémon of this zone back to the ranch (it becomes free)."""
    zone = player_zone(request, slug)
    pokemon = get_object_or_404(
        OwnedPokemon, pk=request.POST.get("pokemon"), player=request.player, zone=zone
    )
    move_pokemon(pokemon, None)
    return redirect("zones:detail", slug=slug)
