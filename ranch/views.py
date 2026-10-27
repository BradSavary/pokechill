"""
Ranch pages.

The Welcome area keeps arrivals hidden: they are discovered in a reveal
dialog, one by one (with an animation and the cry). When more than one came,
a summary of them all ends the series; skipping goes straight to it.
"""

from dataclasses import asdict
from datetime import timedelta

from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from game import balance
from game.collection import Obtention
from pokedex.models import Species

from . import tutorial
from .decorators import player_required
from .services import Reveal, reveal_all, reveal_next


@player_required
def index(request):
    """The Ranch, main page of the game: absence summary and Welcome area."""
    player = request.player
    # One ball per waiting Pokémon, oldest first (the reveal order). Only the
    # rarities reach the template: the species stay hidden until revealed.
    rarities = list(player.arrivals.values_list("species__rarity", flat=True))
    waiting = len(rarities)
    tutorial_step = tutorial.step_for_page(player, "ranch")
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
            "tutorial_step": tutorial_step,
            # The intro of the tutorial shows the starters hopping
            "starters": Species.objects.filter(slug__in=balance.STARTER_SPECIES)
            if tutorial_step == tutorial.WELCOME
            else [],
            # The reveal dialog opens by itself, but never over the tutorial
            "auto_open": waiting and player.tutorial_step == tutorial.DONE,
        },
    )


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
    page = tutorial.STEP_PAGE.get(request.player.tutorial_step, "ranch")
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
