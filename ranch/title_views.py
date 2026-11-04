"""
The title screen (/): where the game starts.

A visitor without a registered account lands here: a new one starts a game,
a guest continues theirs. A registered player goes straight to the Ranch.

A guest is only created by the Start button (a POST): a crawler or a link
preview that opens a page of the game creates nothing (see
ranch.decorators.player_required, which sends such visitors here).
"""

from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.views.decorators.http import require_POST

from accounts.services import is_guest, login_as_new_guest

from .news import latest
from .services import ensure_player

# Pokémon hopping on the map around the title panel: (Pokédex number, left %,
# top % of the map). On grass or on the path, on both sides of the panel.
TITLE_POKEMON = (
    (25, 13, 51),  # Pikachu, on the path
    (1, 8, 67),  # Bulbasaur
    (7, 19, 37),  # Squirtle, by the PC
    (4, 81, 51),  # Charmander, on the path
    (16, 87, 35),  # Pidgey, by the house
)


def home(request):
    """The title screen, or the Ranch for a registered player."""
    if request.user.is_authenticated and not is_guest(request.user):
        return redirect("ranch:index")
    hoppers = [
        # A different delay for each one, so that they don't hop together
        {"icon": static(f"pokemon/icons/{number}.png"), "left": left, "top": top, "delay": i * 0.35}
        for i, (number, left, top) in enumerate(TITLE_POKEMON)
    ]
    return render(request, "ranch/title.html", {"news": latest(), "hoppers": hoppers})


@require_POST
def start(request):
    """Start a game: a new visitor becomes a guest, with a fresh save (its starters)."""
    if not request.user.is_authenticated:
        login_as_new_guest(request)
    ensure_player(request.user)
    return redirect("ranch:index")
