from django.contrib.auth import login, update_session_auth_hash
from django.shortcuts import redirect, render

from .forms import SignUpForm
from .services import is_guest


def sign_up(request):
    """
    Create an account, or convert the current guest into one (the save is kept).
    """
    if request.user.is_authenticated and not is_guest(request.user):
        return redirect("ranch:index")  # already registered

    guest = request.user if is_guest(request.user) else None
    form = SignUpForm(request.POST or None, instance=guest)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        if guest:
            # Changing the password invalidates the session: refresh it so the
            # player stays logged in after the conversion
            update_session_auth_hash(request, user)
        else:
            login(request, user)
        return redirect("ranch:index")
    return render(request, "accounts/sign_up.html", {"form": form, "converting": bool(guest)})
