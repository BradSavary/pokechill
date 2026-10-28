from django.urls import path

from . import views

app_name = "ranch"

urlpatterns = [
    path("", views.index, name="index"),
    path("reveal/", views.reveal, name="reveal"),
    path("reveal/all/", views.reveal_everything, name="reveal_all"),
    path("reveal/summary/", views.reveal_summary, name="reveal_summary"),
    path("feeder/fill/", views.feeder_fill, name="feeder_fill"),
    path("feeder/take-back/", views.feeder_take_back, name="feeder_take_back"),
    path("tutorial/next/", views.tutorial_next, name="tutorial_next"),
    path("tutorial/gift/", views.tutorial_gift, name="tutorial_gift"),
]
