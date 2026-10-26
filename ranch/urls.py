from django.urls import path

from . import views

app_name = "ranch"

urlpatterns = [
    path("", views.index, name="index"),
    path("reveal/", views.reveal, name="reveal"),
    path("reveal/all/", views.reveal_everything, name="reveal_all"),
]
