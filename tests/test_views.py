"""Tests of the Pokédex pages: full pages, HTMX fragments and filters."""

import re

import pytest
from django.urls import reverse

from config.assets import fingerprint
from pokedex.models import Species, Type

pytestmark = pytest.mark.django_db

# Headers sent by HTMX; Django exposes them to views as request.headers
HTMX = {"HTTP_HX_REQUEST": "true"}


def test_index_selects_the_first_species(client, bulbasaur, charmander):
    html = client.get(reverse("pokedex:index")).content.decode()
    assert "Charmander" in html  # in the list
    assert "Bulbasaur</h2>" in html  # entry of #001


def test_index_without_data_shows_the_import_hint(client):
    response = client.get(reverse("pokedex:index"))
    assert response.status_code == 200
    assert "import_pokeapi" in response.content.decode()


def test_detail_is_a_full_page_without_htmx(client, bulbasaur, charmander):
    html = client.get(reverse("pokedex:detail", args=[4])).content.decode()
    assert "<html" in html
    assert "Charmander</h2>" in html
    assert 'aria-current="page"' in html  # Charmander highlighted in the list


def test_detail_is_a_fragment_for_htmx(client, bulbasaur, charmander):
    html = client.get(reverse("pokedex:detail", args=[4]), **HTMX).content.decode()
    assert "<html" not in html
    assert "Charmander</h2>" in html


def test_history_restore_gets_the_full_page(client, bulbasaur):
    headers = HTMX | {"HTTP_HX_HISTORY_RESTORE_REQUEST": "true"}
    html = client.get(reverse("pokedex:detail", args=[1]), **headers).content.decode()
    assert "<html" in html


def test_unknown_species_returns_404(client, bulbasaur):
    assert client.get(reverse("pokedex:detail", args=[999])).status_code == 404


def test_a_visitor_sees_the_challenges_without_progress(client, bulbasaur):
    Species.objects.filter(pk=bulbasaur.pk).update(is_available=True, rarity="common")
    url = reverse("pokedex:detail", args=[1]) + "?view=challenges"
    html = client.get(url, **HTMX).content.decode()
    assert "Obtain it 10 times" in html
    assert "completed" not in html  # no save, no progress
    assert "Claim" not in html
    # No Pokémon to train for a visitor: no level nor candies
    html = client.get(reverse("pokedex:detail", args=[1]), **HTMX).content.decode()
    assert "1 = +" not in html  # the value of a candy


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


@pytest.mark.parametrize(
    ("page", "script"),
    [("pokedex:index", "js/pokedex.js"), ("ranch:index", "js/ranch.js")],
)
def test_pages_load_htmx_and_their_own_script(client, bulbasaur, page, script):
    # Without them the page still renders, but nothing reacts: no reveal
    # dialog, no countdown, no HTMX requests (and Python tests run no JS)
    html = client.get(reverse(page)).content.decode()
    assert "js/htmx.min.js" in html
    assert script in html


def test_css_and_scripts_are_versioned(client, bulbasaur):
    # ?v=<fingerprint>: after a CSS rebuild, browsers fetch the new file
    # instead of mixing new templates with a stylesheet kept in their cache
    html = client.get(reverse("pokedex:index")).content.decode()
    assert re.search(r"css/main\.css\?v=[0-9a-f]{10}\"", html)
    assert re.search(r"js/pokedex\.js\?v=[0-9a-f]{10}\"", html)


def test_the_version_follows_the_content_not_the_date(tmp_path):
    # On Vercel every file has the same date: only the content tells versions apart
    first, second = tmp_path / "a.css", tmp_path / "b.css"
    first.write_text("body { color: red }")
    second.write_text("body { color: blue }")
    same_date = first.stat().st_mtime_ns
    assert fingerprint(str(first), same_date, 1) != fingerprint(str(second), same_date, 1)
