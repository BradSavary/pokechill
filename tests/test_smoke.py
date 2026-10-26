"""Smoke tests: the site boots and the base layout is rendered."""

import pytest
from django.urls import reverse


def test_home_redirects_to_the_ranch(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response["Location"] == reverse("ranch:index")


@pytest.mark.django_db  # the Pokédex page reads the species table
def test_pokedex_page_shows_legal_notice(client):
    response = client.get(reverse("pokedex:index"))
    assert response.status_code == 200
    # The disclaimer is mandatory on every page (see CLAUDE.md)
    assert "Not affiliated with Nintendo" in response.content.decode()


def test_favicon_ico_redirects_to_the_icon(client):
    response = client.get("/favicon.ico")
    assert response.status_code == 301
    assert response["Location"].endswith("img/favicon.png")
