from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("sign-up/", views.sign_up, name="sign_up"),
    # Django's built-in views handle log in/out; we only provide the template
    path(
        "log-in/",
        auth_views.LoginView.as_view(template_name="accounts/log_in.html"),
        name="login",
    ),
    path("log-out/", auth_views.LogoutView.as_view(), name="logout"),
]
