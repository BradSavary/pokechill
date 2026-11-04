from functools import wraps

from django.http import HttpResponse
from django.shortcuts import redirect

from .research import sync_research
from .services import catch_up_player, ensure_player, mark_seen


def player_required(view):
    """
    Decorator for game pages: guarantees a player.

    A visitor who hasn't started a game yet is sent to the title screen: its
    Start button creates the guest (ranch.title_views), so playing never
    requires an account, and a crawler or a link preview creates nothing.
    The hours since the last visit are replayed, then the view finds the
    save in `request.player` and the catch-up result in `request.catch_up`.
    Only game pages use it: the Pokédex can be browsed without a game.
    """

    @wraps(view)  # keeps the view's name and docstring
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if "HX-Request" in request.headers:
                # An HTMX request would put the whole title screen in a corner
                # of the page: HTMX loads it as a full page instead
                return HttpResponse(headers={"HX-Redirect": "/"})
            return redirect("home")
        request.player = ensure_player(request.user)
        sync_research(request.player)  # once, for a save made before step 3
        mark_seen(request.player)
        # Every visit to a game page replays the hours since the last one
        request.catch_up = catch_up_player(request.player)
        return view(request, *args, **kwargs)

    return wrapper
