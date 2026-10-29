"""
Tests of the research saved in the database (ranch.research): challenges,
stages, rewards claimed by the player, and the candies given to a Pokémon.
"""

import re
from datetime import UTC, datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from game import balance
from game.challenges import challenge_points
from pokedex.models import Species
from ranch import research
from ranch.models import CandyStock, ObjectiveProgress, OwnedPokemon, Player
from ranch.research import ClaimError, claim, sync_research
from ranch.services import CandyError, catch_up_player, receive_pokemon, use_candies
from ranch.zones import collect, give_starting_zones, move_pokemon

pytestmark = pytest.mark.django_db

START = datetime(2026, 1, 15, 8, tzinfo=UTC)
COMMON = challenge_points("common")
HTMX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def player():
    user = get_user_model().objects.create_user("ash")
    player = Player.objects.create(user=user, last_slot=START)
    give_starting_zones(player)
    return player


@pytest.fixture
def in_game(bulbasaur, ivysaur):
    """Bulbasaur and Ivysaur are in the game (a data file each), both common."""
    Species.objects.filter(pk__in=[bulbasaur.pk, ivysaur.pk]).update(
        is_available=True, rarity="common"
    )
    bulbasaur.refresh_from_db()
    ivysaur.refresh_from_db()
    return bulbasaur, ivysaur


def progress(player, key):
    row = ObjectiveProgress.objects.filter(player=player, key=key).first()
    return row.progress if row else 0


def fresh(player):
    return Player.objects.get(pk=player.pk)


def obtain(player, species, nature="attack", shiny=False):
    return receive_pokemon(player, species, nature=nature, is_shiny=shiny)


# --- Progress ----------------------------------------------------------------------------


def test_a_first_obtention_completes_challenges_but_pays_nothing_yet(player, in_game):
    bulbasaur, _ = in_game
    obtain(player, bulbasaur)
    assert progress(player, "dex:bulbasaur:obtain-10") == 1
    assert progress(player, "dex:bulbasaur:natures-3") == 1
    assert progress(player, "dex:bulbasaur:family") == 1  # 1 of its 2 species
    # The rewards wait to be claimed: the "!" of the menu shows
    assert fresh(player).research_points == 0
    assert fresh(player).has_rewards


def test_duplicates_count_and_new_natures_count(player, in_game):
    bulbasaur, _ = in_game
    obtain(player, bulbasaur, "attack")
    obtain(player, bulbasaur, "speed")
    obtain(player, bulbasaur, "speed")
    assert progress(player, "dex:bulbasaur:obtain-10") == 3
    assert progress(player, "dex:bulbasaur:natures-3") == 2  # attack and speed


def test_owning_the_whole_family_completes_it_for_every_member(player, in_game):
    bulbasaur, ivysaur = in_game
    obtain(player, bulbasaur)
    obtain(player, ivysaur)
    assert progress(player, "dex:bulbasaur:family") == 2
    assert progress(player, "dex:ivysaur:family") == 2


def test_species_out_of_the_game_have_no_challenges(player, charmander):
    obtain(player, charmander)  # no data file: not in the game
    assert not ObjectiveProgress.objects.exists()
    assert not fresh(player).has_rewards


def test_zone_work_counts_hours_and_resources_for_each_worker(player, in_game):
    bulbasaur, _ = in_game
    obtain(player, bulbasaur)
    owned = OwnedPokemon.objects.get(player=player)
    move_pokemon(owned, player.zones.get(zone="orchard"))
    catch_up_player(player, now=START + timedelta(hours=3))
    assert progress(player, "dex:bulbasaur:work") == 3
    zone = player.zones.get(zone="orchard")
    assert progress(player, "dex:bulbasaur:harvest") == zone.stock_centi  # its whole work


def test_levels_reached_in_a_zone_count(player, in_game):
    bulbasaur, _ = in_game
    obtain(player, bulbasaur)
    owned = OwnedPokemon.objects.get(player=player)
    move_pokemon(owned, player.zones.get(zone="orchard"))
    catch_up_player(player, now=START + timedelta(hours=8))
    collect(player.zones.get(zone="orchard"))
    owned.refresh_from_db()
    assert owned.level > 1
    assert progress(player, "dex:bulbasaur:level-1") == owned.level


def test_custom_challenges_of_a_species_file(player, in_game):
    bulbasaur, _ = in_game
    Species.objects.filter(pk=bulbasaur.pk).update(
        custom_challenges={
            "add": [{"id": "shiny", "event": "obtained", "filters": {"shiny": True}, "target": 1}]
        }
    )
    obtain(player, bulbasaur)
    assert progress(player, "dex:bulbasaur:shiny") == 0
    obtain(player, bulbasaur, shiny=True)
    assert progress(player, "dex:bulbasaur:shiny") == 1


# --- Claiming the rewards --------------------------------------------------------------


def test_claiming_a_challenge_then_the_stage(player, in_game):
    bulbasaur, _ = in_game
    for nature in ("attack", "speed", "defense"):
        obtain(player, bulbasaur, nature)  # natures-3 done; stage 1 reached
    assert claim(player, bulbasaur, "natures-3").points == COMMON
    with pytest.raises(ClaimError):
        claim(player, bulbasaur, "natures-3")  # never twice
    with pytest.raises(ClaimError):
        claim(player, bulbasaur, "obtain-10")  # not completed (3 of 10)
    claimed = claim(player, bulbasaur, "stage")
    assert (claimed.points, claimed.stages) == (balance.STAGE_1_RESEARCH_POINTS, (1,))
    assert fresh(player).research_points == COMMON + balance.STAGE_1_RESEARCH_POINTS
    assert OwnedPokemon.objects.get(player=player).research_stage == 1
    assert not fresh(player).has_rewards  # nothing left: the "!" goes


def test_claiming_all_gives_challenges_and_stages_in_order(player, in_game):
    bulbasaur, ivysaur = in_game
    obtain(player, ivysaur)
    natures = ("attack", "speed", "defense", "hp", "special_attack", "special_defense")
    for time in range(10):  # obtain-10, natures-3, natures-6, and the family
        obtain(player, bulbasaur, natures[time % 6])
    owned = OwnedPokemon.objects.get(player=player, species=bulbasaur)
    OwnedPokemon.objects.filter(pk=owned.pk).update(level=30)
    owned.refresh_from_db()
    research.record(player, [research.level_event(owned)])  # and both levels: 6 in all

    claimed = claim(player, bulbasaur, "all")
    assert claimed.stages == (1, 2)
    assert claimed.points == (
        6 * COMMON + balance.STAGE_1_RESEARCH_POINTS + balance.STAGE_2_RESEARCH_POINTS
    )
    assert claimed.candies == balance.STAGE_2_CANDIES
    candies = CandyStock.objects.get(player=player, family=bulbasaur.evolution_chain).amount
    assert candies >= balance.STAGE_2_CANDIES
    assert claim(player, bulbasaur, "all").points == 0  # nothing left


def test_a_species_not_owned_has_nothing_to_claim(player, in_game):
    _, ivysaur = in_game
    with pytest.raises(ClaimError):
        claim(player, ivysaur, "all")


def test_the_rewards_of_a_species_are_marked_in_the_list(client, in_game):
    client.get("/ranch/")  # a guest: Bulbasaur is one of its starters
    html = client.get(reverse("pokedex:index")).content.decode()
    assert 'class="reward-badge"' in html  # the "!" of its row
    # The "!" of the menu shows (not hidden)
    assert re.search(r'id="menu-badge-pokedex" class="menu-badge"\s+title', html)


def test_claiming_from_the_entry_refreshes_the_page_parts(client, in_game):
    bulbasaur, _ = in_game
    client.get("/ranch/")
    url = reverse("pokedex:claim", args=[bulbasaur.number])
    html = client.post(url, {"what": "all"}, **HTMX).content.decode()
    assert 'class="points-up"' in html  # what was claimed rises next to the total
    # The parts swapped out of band: the points, the menu "!", the list row
    assert 'id="research-points" hx-swap-oob="true"' in html
    assert 'id="menu-badge-pokedex" hx-swap-oob="true"' in html
    assert 'id="species-row-1" hx-swap-oob="true"' in html
    assert fresh(Player.objects.get()).research_points > 0


def test_claim_actions_require_post(client, in_game):
    client.get("/ranch/")
    assert client.get(reverse("pokedex:claim", args=[1])).status_code == 405


# --- Candies ---------------------------------------------------------------------------


def test_candies_raise_the_level_and_count_for_the_challenges(player, in_game):
    bulbasaur, _ = in_game
    obtain(player, bulbasaur)
    # Level 10 (at level 1, a single candy is worth several levels)
    OwnedPokemon.objects.filter(player=player).update(level=10)
    CandyStock.objects.create(player=player, family=bulbasaur.evolution_chain, amount=50)
    eaten, levels = use_candies(player, bulbasaur, None)  # just enough for one level
    assert (eaten, levels) == (4, 1)  # 331 experience to earn, 100 per candy
    owned = OwnedPokemon.objects.get(player=player)
    assert owned.level == 11
    assert CandyStock.objects.get(player=player).amount == 50 - eaten
    assert progress(player, "dex:bulbasaur:level-1") == 11


def test_candies_are_limited_by_the_stock(player, in_game):
    bulbasaur, _ = in_game
    obtain(player, bulbasaur)
    with pytest.raises(CandyError, match="Not enough"):
        use_candies(player, bulbasaur, 3)  # no candies yet


# --- Saves made before the research ----------------------------------------------------


def test_a_save_made_before_the_research_is_set_up_from_its_state(player, in_game):
    bulbasaur, ivysaur = in_game
    # A save of step 2: Pokémon owned, no progress recorded
    for species, level in ((bulbasaur, 18), (ivysaur, 16)):
        OwnedPokemon.objects.create(
            player=player, species=species, level=level, unlocked_natures=["attack", "hp", "speed"]
        )
    Player.objects.filter(pk=player.pk).update(research_synced=False)
    player.refresh_from_db()

    sync_research(player)
    # Owned: obtained once at least (the rest was never counted)
    assert progress(player, "dex:bulbasaur:obtain-10") == 1
    assert progress(player, "dex:bulbasaur:level-1") == 15  # level 18: done (capped)
    assert progress(player, "dex:bulbasaur:natures-3") == 3
    assert progress(player, "dex:ivysaur:family") == 2
    assert player.research_synced and player.has_rewards  # rewards to claim at once

    rows = ObjectiveProgress.objects.count()
    sync_research(fresh(player))  # once only
    assert ObjectiveProgress.objects.count() == rows


def test_new_saves_need_no_set_up(client, bulbasaur):
    client.get("/ranch/")
    assert Player.objects.get().research_synced


def test_claiming_a_challenge_fills_the_stage_bar_from_where_it_was(client, in_game):
    bulbasaur, _ = in_game
    client.get("/ranch/")  # Bulbasaur, a starter
    player = Player.objects.get()
    for nature in ("speed", "defense", "attack"):  # natures-3 done
        obtain(player, bulbasaur, nature)
    url = reverse("pokedex:claim", args=[bulbasaur.number])
    html = client.post(url, {"what": "natures-3"}, **HTMX).content.decode()
    # The bar of the stages counts the claimed challenges: 1 of 9, from 0
    assert re.search(r'class="fill fill-from" style="width: 11%; --from: 0%"', html)
