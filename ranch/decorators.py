from functools import wraps

from accounts.services import login_as_new_guest

from .services import ensure_player, mark_seen


def player_required(view):
    """
    Decorator for game pages: guarantees a player, creating a guest if needed.

    A first-time visitor is logged in as a new guest, so playing never
    requires an account. The view then finds the save in `request.player`.
    Only game pages use it: browsing the Pokédex creates no account, so web
    crawlers don't fill the database with guests.
    """

    @wraps(view)  # keeps the view's name and docstring
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            login_as_new_guest(request)
        request.player = ensure_player(request.user)
        mark_seen(request.player)
        return view(request, *args, **kwargs)

    return wrapper
