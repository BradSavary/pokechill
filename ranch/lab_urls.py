"""URLs of Professor Oak's lab (the skill tree), under /lab/."""

from django.urls import path

from . import lab_views as views

app_name = "lab"

urlpatterns = [
    path("", views.index, name="index"),
    path("intro/seen/", views.intro_seen, name="intro_seen"),
    path("<slug:tree_id>/", views.tree, name="tree"),
    path("<slug:tree_id>/<slug:node_id>/", views.node, name="node"),
    path("<slug:tree_id>/<slug:node_id>/unlock/", views.unlock, name="unlock"),
]
