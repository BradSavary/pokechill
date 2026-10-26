"""
Ranch pages.

The Welcome area keeps arrivals hidden: they are discovered in a reveal
dialog, one by one (with an animation and the cry) or all at once.
"""

from datetime import timedelta

from django.shortcuts import render
from django.views.decorators.http import require_POST

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
