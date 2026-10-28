"""
Ranch pages.

The Welcome area keeps arrivals hidden: they are discovered in a reveal
dialog, one by one (with an animation and the cry). When more than one came,
a summary of them all ends the series; skipping goes straight to it.
"""

from dataclasses import asdict
from datetime import timedelta

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from game import balance
from game.collection import Obtention
from game.zones import ZONE_OF_RESOURCE
from pokedex.models import Species, Type

from . import tutorial
from .decorators import player_required
from .models import ResourceStock
from .services import Reveal, reveal_all, reveal_next
from .zones import ZoneError, fill_feeder, take_back_slot


def feeder_state(player) -> dict:
    """
    The feeder as the Ranch shows it: its slots in the order they will be
    eaten (full ones with their lure, then the free ones), and the resources
    the player could put in a free slot.
    """
    types = Type.objects.in_bulk(
        {t for zone in ZONE_OF_RESOURCE.values() for t in zone.types}, field_name="slug"
    )

    def types_of(zone):
        return [types[slug] for slug in sorted(zone.types) if slug in types]

    def bonus(units):
        return min(units, balance.FEEDER_MAX_UNITS) * balance.FEEDER_BONUS_PER_UNIT_PERCENT

    filled = [
        {
            "index": index,
            "zone": ZONE_OF_RESOURCE[resource],
            "units": units,
            "bonus": bonus(units),
            "types": types_of(ZONE_OF_RESOURCE[resource]),
        }
        for index, (resource, units) in enumerate(player.feeder)
    ]
    stock = dict(ResourceStock.objects.filter(player=player).values_list("resource", "amount"))
    return {
        "slots": filled + [None] * (player.feeder_capacity - len(filled)),
        "filled": filled,
        "free": player.feeder_capacity - len(filled),
        "capacity": player.feeder_capacity,
        # One choice per zone of the player: its resource, the stock, the types
        "choices": [
            {
                "zone": zone.spec,
                "stock": stock.get(zone.spec.resource, 0),
                "max": min(stock.get(zone.spec.resource, 0), balance.FEEDER_MAX_UNITS),
                "types": types_of(zone.spec),
            }
            for zone in player.zones.all()
        ],
        "max_units": balance.FEEDER_MAX_UNITS,
        "bonus_per_unit": balance.FEEDER_BONUS_PER_UNIT_PERCENT,
        # The rule, for its "i" bubble (written from the balance values)
        "tip": (
            f"Each unit in a slot adds {balance.FEEDER_BONUS_PER_UNIT_PERCENT} % of chance "
            "that the next Pokémon to arrive has one of the zone's types (up to "
            f"+{bonus(balance.FEEDER_MAX_UNITS)} % with {balance.FEEDER_MAX_UNITS} units). "
            "That Pokémon eats the whole slot; the next one eats the next slot."
        ),
    }


@player_required
def index(request):
    """The Ranch, main page of the game: absence summary, Welcome area, feeder."""
    player = request.player
    # One ball per waiting Pokémon, oldest first (the reveal order). Only the
    # rarities reach the template: the species stay hidden until revealed.
    rarities = list(player.arrivals.values_list("species__rarity", flat=True))
    waiting = len(rarities)
    tutorial_context = tutorial.context(player, "ranch")
    return render(
        request,
        "ranch/index.html",
        {
            "active_tab": "ranch",
            "waiting": waiting,
            "rarities": rarities,
            "catch_up": request.catch_up,  # what happened since the last visit
            # The next arrival comes at the next full hour
            "next_arrival": player.last_slot + timedelta(hours=1),
            **tutorial_context,
            # The intro of the tutorial shows the starters hopping
            "starters": Species.objects.filter(slug__in=balance.STARTER_SPECIES)
            if tutorial_context["tutorial_step"] == tutorial.WELCOME
            else [],
            # The reveal dialog opens by itself, but not during the tutorial's
            # first steps (the gift is revealed by the tutorial itself)
            "auto_open": waiting and player.tutorial_step > tutorial.GIFT,
            "feeder": feeder_state(player),
        },
    )


@require_POST  # changes the game state
@player_required
def feeder_fill(request):
    """Fill a free slot of the feeder (POST "resource", "units")."""
    units = request.POST.get("units", "")
    try:
        fill_feeder(
            request.player, request.POST.get("resource", ""), int(units) if units.isdigit() else 0
        )
    except ZoneError as error:
        messages.error(request, str(error))
    else:
        tutorial.feeder_filled(request.player)
    return redirect("ranch:index")


@require_POST
@player_required
def feeder_take_back(request):
    """Take back a slot of the feeder (POST "slot": its index): its units return to the stock."""
    index = request.POST.get("slot", "")
    try:
        take_back_slot(request.player, int(index) if index.isdigit() else -1)
    except ZoneError as error:
        messages.error(request, str(error))
    return redirect("ranch:index")


# --- The series of reveals, kept in the session until its summary -----------
# Each reveal is its own request: the session remembers the Pokémon revealed
# so far, so the summary lists them all, even after a page reload in between.
# Only ids and plain values are stored (the session is saved as JSON).
SERIES_KEY = "reveal_series"


def remember(request, reveals: list[Reveal]) -> int:
    """Add reveals to the current series; return its new length."""
    series = request.session.get(SERIES_KEY, [])
    series += [
        {
            "species": reveal.species.pk,
            "nature": reveal.nature,
            "is_shiny": reveal.is_shiny,
            "outcome": asdict(reveal.outcome),
        }
        for reveal in reveals
    ]
    # Assigning the key (not just mutating the list) tells Django to save the session
    request.session[SERIES_KEY] = series
    return len(series)


def end_series(request) -> list[Reveal]:
    """The reveals of the current series, which ends: the session forgets it."""
    series = request.session.pop(SERIES_KEY, [])
    species = Species.objects.select_related(
        "evolution_chain", "primary_type", "secondary_type"
    ).in_bulk({item["species"] for item in series})
    return [
        Reveal(
            species[item["species"]],
            item["nature"],
            item["is_shiny"],
            Obtention(**item["outcome"]),
        )
        for item in series
        if item["species"] in species  # a species removed since then is skipped
    ]


def render_summary(request):
    """The summary of the series (HTMX fragment of the reveal dialog)."""
    reveals = end_series(request)
    return render(
        request,
        "ranch/_reveal_summary.html",
        {
            "reveals": reveals,
            "new_count": sum(reveal.outcome.is_new for reveal in reveals),
            "candies": sum(reveal.outcome.candies for reveal in reveals),
        },
    )


@require_POST  # changes the game state: never through a simple link
@player_required
def reveal(request):
    """Reveal the next waiting Pokémon (HTMX fragment of the reveal dialog)."""
    result = reveal_next(request.player)
    # Nothing left (a double click): the series stays as it is
    revealed = remember(request, [result] if result else [])
    remaining = request.player.arrivals.count()
    if not remaining and revealed <= 1:
        end_series(request)  # a single Pokémon needs no summary
    return render(
        request,
        "ranch/_reveal.html",
        {
            "reveal": result,
            "remaining": remaining,
            # "2 / 3": this one's rank in the series, and the series' length
            "position": revealed,
            "total": revealed + remaining,
        },
    )


@require_POST
@player_required
def reveal_everything(request):
    """Skip: reveal every waiting Pokémon at once and go to the summary."""
    remember(request, reveal_all(request.player))
    return render_summary(request)


@require_POST
@player_required
def reveal_summary(request):
    """The summary at the end of a one-by-one series ("See the summary")."""
    return render_summary(request)


@require_POST
@player_required
def tutorial_next(request):
    """Complete a tutorial step (its number is posted), then go to the next step's page."""
    step = request.POST.get("step", "")
    if step.isdigit():  # anything else (tampered form) is simply ignored
        tutorial.advance(request.player, int(step))
    page = tutorial.STEP_PAGES.get(request.player.tutorial_step, ("ranch",))[0]
    return redirect(f"{page}:index")


@require_POST
@player_required
def tutorial_gift(request):
    """Last tutorial step: reveal the gift Pokémon in the tutorial popup."""
    return render(
        request,
        "ranch/_reveal.html",
        {"reveal": tutorial.receive_gift(request.player), "remaining": 0},
    )
