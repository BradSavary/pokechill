from django.urls import path

from . import views

# Namespace used in templates: {% url 'pokedex:index' %}
app_name = "pokedex"

urlpatterns = [
    path("", views.index, name="index"),
    path("list/", views.species_list, name="list"),
    # <int:number> captures the number from the URL and passes it to the view
    path("<int:number>/", views.species_detail, name="detail"),
    # Actions of an entry (POST)
    path("<int:number>/claim/", views.claim_reward, name="claim"),
    path("<int:number>/candies/", views.give_candies, name="candies"),
]
