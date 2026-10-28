"""URLs of the zone pages, under /zones/ (the "Zones" tab of the menu)."""

from django.urls import path

from . import zone_views as views

app_name = "zones"

urlpatterns = [
    path("", views.index, name="index"),
    path("<slug:slug>/", views.detail, name="detail"),
    path("<slug:slug>/open/", views.open_zone, name="open"),
    path("<slug:slug>/assign/", views.assign, name="assign"),
    path("<slug:slug>/remove/", views.remove, name="remove"),
]
