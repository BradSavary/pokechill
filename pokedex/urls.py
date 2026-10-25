from django.urls import path

from . import views

# Namespace used in templates: {% url 'pokedex:index' %}
app_name = "pokedex"

urlpatterns = [
    path("", views.index, name="index"),
]
