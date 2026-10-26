from django.shortcuts import render

from .decorators import player_required


@player_required
def index(request):
    """The Ranch, main page of the game."""
    arrivals = request.player.arrivals.select_related("species")
    return render(request, "ranch/index.html", {"active_tab": "ranch", "arrivals": arrivals})
