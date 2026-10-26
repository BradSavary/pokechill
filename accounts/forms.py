from django import forms
from django.contrib.auth.forms import UserCreationForm

from .services import GUEST_PREFIX


class SignUpForm(UserCreationForm):
    """
    Django's sign-up form (username + password twice, password validators).

    Given `instance=<guest user>`, it updates that user instead of creating a
    new one: this is how a guest is converted into a real account.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A guest's generated username ("guest-3f9a...") is not theirs:
        # show an empty field instead of pre-filling it
        if self.instance.username.startswith(GUEST_PREFIX):
            self.initial["username"] = ""

    def clean_username(self):
        username = super().clean_username()
        # Keep the guest namespace for generated accounts only
        if username.lower().startswith(GUEST_PREFIX):
            raise forms.ValidationError(f'Usernames cannot start with "{GUEST_PREFIX}".')
        return username
