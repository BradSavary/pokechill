"""Tests of the Pokédex pages: full pages, HTMX fragments and filters."""

import pytest
from django.urls import reverse

from pokedex.models import Move, SpeciesMove, Type

pytestmark = pytest.mark.django_db

# Headers sent by HTMX; Django exposes them to views as request.headers
HTMX = {"HTTP_HX_REQUEST": "true"}


def test_index_selects_the_first_species(client, bulbasaur, charmander):
    html = client.get(reverse("pokedex:index")).content.decode()
    assert "Charmander" in html  # in the list
    assert "<h1" in html and "Bulbasaur</h1>" in html  # entry of #001


def test_index_without_data_shows_the_import_hint(client):
    response = client.get(reverse("pokedex:index"))
    assert response.status_code == 200
    assert "import_pokeapi" in response.content.decode()


def test_detail_is_a_full_page_without_htmx(client, bulbasaur, charmander):
    html = client.get(reverse("pokedex:detail", args=[4])).content.decode()
    assert "<html" in html
    assert "Charmander</h1>" in html
    assert 'aria-current="page"' in html  # Charmander highlighted in the list


def test_detail_is_a_fragment_for_htmx(client, bulbasaur, charmander):
    html = client.get(reverse("pokedex:detail", args=[4]), **HTMX).content.decode()
    assert "<html" not in html
    assert "Charmander</h1>" in html


def test_history_restore_gets_the_full_page(client, bulbasaur):
    headers = HTMX | {"HTTP_HX_HISTORY_RESTORE_REQUEST": "true"}
    html = client.get(reverse("pokedex:detail", args=[1]), **headers).content.decode()
    assert "<html" in html


def test_unknown_species_returns_404(client, bulbasaur):
    assert client.get(reverse("pokedex:detail", args=[999])).status_code == 404


def test_entry_shows_family_and_level_up_moves(client, bulbasaur, ivysaur, grass):
    vine_whip = Move.objects.create(
        slug="vine-whip", name="Vine Whip", type=grass, damage_class="physical", power=45, pp=25
    )
    SpeciesMove.objects.create(species=bulbasaur, move=vine_whip, learn_method="level-up", level=7)

    html = client.get(reverse("pokedex:detail", args=[1]), **HTMX).content.decode()
    assert "Ivysaur" in html  # family section
    assert "Vine Whip" in html


def test_list_filters_by_name(client, bulbasaur, charmander):
    html = client.get(reverse("pokedex:list"), {"q": "char"}).content.decode()
    assert "Charmander" in html
    assert "Bulbasaur" not in html


def test_list_filters_by_secondary_type(client, bulbasaur, charmander):
    html = client.get(reverse("pokedex:list"), {"type": "poison"}).content.decode()
    assert "Bulbasaur" in html
    assert "Charmander" not in html


def test_list_keeps_the_selected_species_highlighted(client, bulbasaur, charmander):
    html = client.get(reverse("pokedex:list"), {"selected": "4"}).content.decode()
    assert html.count('aria-current="page"') == 1


def test_list_with_no_match(client, bulbasaur):
    html = client.get(reverse("pokedex:list"), {"q": "mewtwo"}).content.decode()
    assert "No Pokémon match" in html


def test_no_template_comment_leaks_into_the_page(client, bulbasaur, ivysaur):
    # Django's {# #} only works on one line: a multi-line one is printed as text
    html = client.get(reverse("pokedex:detail", args=[1])).content.decode()
    assert "{#" not in html and "#}" not in html


def test_type_filter_only_lists_types_carried_by_species(client, bulbasaur):
    Type.objects.create(slug="dark", name="Dark")  # used by moves only
    html = client.get(reverse("pokedex:index")).content.decode()
    assert 'value="poison"' in html
    assert 'value="dark"' not in html
