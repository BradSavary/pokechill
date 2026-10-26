from django.shortcuts import render

from .decorators import player_required


@player_required
def index(request):
    """The Ranch, main page of the game (its content arrives with arrivals)."""
    return render(request, "ranch/index.html", {"active_tab": "ranch"})
