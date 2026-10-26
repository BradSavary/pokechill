"""
Ranch pages.

The Welcome area keeps arrivals hidden: they are discovered in a reveal
dialog, one by one (with an animation and the cry) or all at once.
"""

from datetime import timedelta

from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import tutorial
from .decorators import player_required
from .services import reveal_all, reveal_next


@player_required
def index(request):
    """The Ranch, main page of the game: absence summary and Welcome area."""
    player = request.player
    waiting = player.arrivals.count()
    return render(
        request,
        "ranch/index.html",
        {
            "active_tab": "ranch",
            "waiting": waiting,
            "waiting_range": range(waiting),  # one Poké Ball drawn per arrival
            "catch_up": request.catch_up,  # what happened since the last visit
            # The next arrival comes at the next full hour
            "next_arrival": player.last_slot + timedelta(hours=1),
            "tutorial_step": tutorial.step_for_page(player, "ranch"),
            # The reveal dialog opens by itself, but never over the tutorial
            "auto_open": waiting and player.tutorial_step == tutorial.DONE,
        },
    )


@require_POST  # changes the game state: never through a simple link
@player_required
def reveal(request):
    """Reveal the next waiting Pokémon (HTMX fragment of the reveal dialog)."""
    result = reveal_next(request.player)
    return render(
        request,
        "ranch/_reveal.html",
        {"reveal": result, "remaining": request.player.arrivals.count()},
    )


@require_POST
@player_required
def reveal_everything(request):
    """Skip the one-by-one reveal: every waiting Pokémon at once."""
    return render(request, "ranch/_reveal_all.html", {"reveals": reveal_all(request.player)})


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
    """Last tutorial step: reveal the gift Pokémon in the reveal dialog."""
    return render(
        request,
        "ranch/_reveal.html",
        {"reveal": tutorial.receive_gift(request.player), "remaining": 0},
    )
