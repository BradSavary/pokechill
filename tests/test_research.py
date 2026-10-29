"""Tests of the research saved in the database (ranch.research): challenges, stages, points."""

from datetime import UTC, datetime, timedelta

import pytest
from django.contrib.auth import get_user_model

from game import balance
from game.challenges import challenge_points
from pokedex.models import Species
from ranch import research
from ranch.models import CandyStock, ObjectiveProgress, OwnedPokemon, Player
from ranch.research import sync_research
from ranch.services import catch_up_player, receive_pokemon
from ranch.zones import collect, give_starting_zones, move_pokemon

pytestmark = pytest.mark.django_db

START = datetime(2026, 1, 15, 8, tzinfo=UTC)
COMMON = challenge_points("common")


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


def points(player):
    return Player.objects.get(pk=player.pk).research_points


def obtain(player, species, nature="attack", shiny=False):
    return receive_pokemon(player, species, nature=nature, is_shiny=shiny)


def test_a_first_obtention_completes_a_challenge_and_reaches_stage_1(player, in_game):
    bulbasaur, _ = in_game
    obtain(player, bulbasaur)
    assert progress(player, "dex:bulbasaur:obtain-1") == 1
    assert progress(player, "dex:bulbasaur:natures-3") == 1
    assert progress(player, "dex:bulbasaur:family") == 1  # 1 of its 2 species
    # "Obtain it once" pays its points, and the stage 1 its own
    assert points(player) == COMMON + balance.STAGE_1_RESEARCH_POINTS
    assert OwnedPokemon.objects.get(player=player).research_stage == 1


def test_duplicates_count_and_new_natures_count(player, in_game):
    bulbasaur, _ = in_game
    obtain(player, bulbasaur, "attack")
    obtain(player, bulbasaur, "speed")
    obtain(player, bulbasaur, "speed")
    assert progress(player, "dex:bulbasaur:obtain-2") == 3
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
    assert points(player) == 0


def test_stage_2_is_rewarded_once(player, in_game):
    bulbasaur, ivysaur = in_game
    obtain(player, ivysaur)
    for nature in ("attack", "speed", "defense"):
        obtain(player, bulbasaur, nature)
    owned = OwnedPokemon.objects.get(player=player, species=bulbasaur)
    assert owned.research_stage == 1  # obtain-1, natures-3, family: 3 challenges

    # Level 30: both level challenges at once, 5 in all
    OwnedPokemon.objects.filter(pk=owned.pk).update(level=30)
    owned.refresh_from_db()
    result = research.record(player, [research.level_event(owned)])
    assert [new_stage for _, new_stage in result.stage_ups] == [2]
    assert result.points == 2 * COMMON + balance.STAGE_2_RESEARCH_POINTS
    owned.refresh_from_db()
    assert owned.research_stage == 2
    candies = CandyStock.objects.get(player=player, family=bulbasaur.evolution_chain).amount
    assert candies >= balance.STAGE_2_CANDIES

    # Nothing new: no second reward
    assert research.record(player, [research.level_event(owned)]).points == 0


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
    assert progress(player, "dex:bulbasaur:obtain-1") == 1  # owned: obtained once at least
    assert progress(player, "dex:bulbasaur:obtain-2") == 1  # the rest was never counted
    assert progress(player, "dex:bulbasaur:level-1") == 15  # level 18: done (capped)
    assert progress(player, "dex:bulbasaur:natures-3") == 3
    assert progress(player, "dex:ivysaur:family") == 2
    assert Player.objects.get(pk=player.pk).research_synced

    before = points(player)
    sync_research(Player.objects.get(pk=player.pk))  # once only
    assert points(player) == before


def test_new_saves_need_no_set_up(client, bulbasaur):
    client.get("/ranch/")
    assert Player.objects.get().research_synced
