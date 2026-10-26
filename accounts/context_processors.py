"""Values added to the context of every template."""

from .services import is_guest


def account(request):
    """`is_guest` lets the base layout invite guests to save their game."""
    return {"is_guest": is_guest(request.user)}
