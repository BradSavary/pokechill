"""
Guest accounts.

A guest is a regular Django User whose password is "unusable": nobody can log
in as them, the session cookie is their only key. Signing up later simply
gives this same user a real username and password, so everything attached to
it (the game save) is kept. No extra field or model is needed.
"""

import secrets

from django.contrib.auth import get_user_model, login

GUEST_PREFIX = "guest-"


def is_guest(user) -> bool:
    """True for a logged-in guest (an account without a usable password)."""
    return user.is_authenticated and not user.has_usable_password()


def login_as_new_guest(request):
    """Create a guest user and log the current visitor in as this guest."""
    User = get_user_model()
    # A random suffix: guests never choose or see their username
    user = User(username=f"{GUEST_PREFIX}{secrets.token_hex(6)}")
    user.set_unusable_password()
    user.save()
    login(request, user)
    return user
