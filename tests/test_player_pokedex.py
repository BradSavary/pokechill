"""Tests of the player's Pokédex: known species, silhouettes, research stage 1."""

import re

import pytest
from django.urls import reverse

from pokedex.models import Species
from ranch.models import CandyStock, OwnedPokemon, Player

pytestmark = pytest.mark.django_db

HTMX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def player_client(client, bulbasaur, ivysaur, charmander):
    """A player who owns Bulbasaur only; Ivysaur is available, Charmander isn't."""
    Species.objects.filter(pk__in=[bulbasaur.pk, ivysaur.pk]).update(
        is_available=True, rarity="common"
    )
    client.get(reverse("ranch:index"))  # creates the guest and the save
    player = Player.objects.get()
    OwnedPokemon.objects.filter(player=player).delete()  # ignore the starters
    OwnedPokemon.objects.create(
        player=player, species=bulbasaur, level=5, unlocked_natures=["speed"]
    )
    return client


def test_the_list_hides_unknown_species(player_client):
    html = player_client.get(reverse("pokedex:index")).content.decode()
    assert "Bulbasaur" in html
    assert "Ivysaur" not in html
    assert "???" in html
    assert "1 / 3" in html  # owned / total


def test_unknown_entry_shows_a_silhouette(player_client):
    html = player_client.get(reverse("pokedex:detail", args=[2]), **HTMX).content.decode()
    assert "Ivysaur" not in html
    assert "You haven't met this Pokémon yet" in html


def test_species_not_in_the_game_yet(player_client):
    html = player_client.get(reverse("pokedex:detail", args=[4]), **HTMX).content.decode()
    assert "not in the game yet" in html


def test_owned_entry_shows_the_research_stage(player_client):
    html = player_client.get(reverse("pokedex:detail", args=[1]), **HTMX).content.decode()
    assert "Encountered" in html
    assert re.search(r"Lv\.\s+5", html)  # its level, in the level and candies panel
    assert "Speed" in html  # its nature


def test_the_overview_leaves_out_description_cry_stats_and_moves(player_client, bulbasaur):
    Species.objects.filter(pk=bulbasaur.pk).update(flavor_text="A strange seed.")
    html = player_client.get(reverse("pokedex:detail", args=[1]), **HTMX).content.decode()
    assert "A strange seed." not in html
    assert "Cry" not in html
    assert "Base stats" not in html
    assert "?view=challenges" in html  # its only action button


def test_the_challenges_action_lists_them_with_the_stage_bar(player_client):
    url = reverse("pokedex:detail", args=[1]) + "?view=challenges"
    html = player_client.get(url, **HTMX).content.decode()
    assert "Obtain it 10 times" in html
    # As a starter, Bulbasaur already completed a few of its 10 challenges
    assert re.search(r"\d+/9 challenges claimed", html)
    assert 'class="stage-bar"' in html
    assert 'aria-pressed="true"' in html  # its button is the active one


def test_the_default_view_shows_level_and_candies(player_client):
    html = player_client.get(reverse("pokedex:detail", args=[1]), **HTMX).content.decode()
    assert re.search(r"Lv\.\s+5", html)
    assert re.search(r"1 = \+\d+ XP", html)  # what a candy is worth
    # No candies yet: the level up button is greyed out, and says why
    assert re.search(r"<button class=\"btn\" disabled>\s*Level up", html)
    assert "Not enough candies" in html


def test_candies_roll_the_level_up(player_client, bulbasaur):
    player = Player.objects.get()
    CandyStock.objects.create(player=player, family=bulbasaur.evolution_chain, amount=50)
    url = reverse("pokedex:candies", args=[1])
    html = player_client.post(url, {"count": "level"}, **HTMX).content.decode()
    assert 'class="level-roll"' in html  # the counter rolls from 5 to 6
    assert "<span>5</span><span>6</span>" in html
    assert "given" not in html  # no notice: the animation tells it


def test_the_challenges_have_no_claim_all_button(player_client):
    url = reverse("pokedex:detail", args=[1]) + "?view=challenges"
    html = player_client.get(url, **HTMX).content.decode()
    assert "Claim all" not in html
    assert 'role="tooltip"' in html  # the rewards of the stages show on hover


def test_the_list_marks_studied_and_mastered_species(player_client):
    OwnedPokemon.objects.update(research_stage=2)
    html = player_client.get(reverse("pokedex:index")).content.decode()
    assert 'class="stage-mark is-studied"' in html
    assert "Research points" in html


def test_the_family_hides_unknown_members(player_client):
    html = player_client.get(reverse("pokedex:detail", args=[1]), **HTMX).content.decode()
    assert "Ivysaur" not in html  # family member not met yet


def test_searching_never_reveals_unknown_names(player_client):
    html = player_client.get(reverse("pokedex:list"), {"q": "ivy"}).content.decode()
    assert "No Pokémon match" in html


def test_visitors_without_a_save_see_the_whole_catalogue(client, bulbasaur, ivysaur):
    html = client.get(reverse("pokedex:index")).content.decode()
    assert "Ivysaur" in html
    assert "???" not in html


def test_the_mastery_bonuses_wait_for_the_last_stage(player_client):
    url = reverse("pokedex:detail", args=[1]) + "?view=challenges"
    html = player_client.get(url, **HTMX).content.decode()
    assert 'class="mastery-box "' in html  # greyed out: not mastered yet
    assert "At the stage Mastered" in html
    # Under the challenges, and in the bubble of the gift of the stage 3
    assert html.count("Works at full rate in every zone") == 2
    assert html.index('class="challenge-columns') < html.index('class="mastery-box')
    # Not in the default view
    overview = player_client.get(reverse("pokedex:detail", args=[1]), **HTMX).content.decode()
    assert "mastery-box" not in overview
    OwnedPokemon.objects.filter(species__number=1).update(research_stage=3)
    html = player_client.get(url, **HTMX).content.decode()
    assert 'class="mastery-box is-mastered"' in html
    assert "Active" in html
