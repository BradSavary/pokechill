"""Tests of the zones and the feeder saved in the database (ranch.zones)."""

from datetime import UTC, datetime, timedelta

import pytest
from django.db import IntegrityError

from game import balance
from game.experience import add_experience
from game.zones import ZONES, Worker, experience_per_hour, production_per_hour
from pokedex.models import Species
from ranch.models import OwnedPokemon, Player, ResourceStock
from ranch.services import catch_up_player, ensure_player
from ranch.zones import ZoneError, collect, fill_feeder, give_starting_zones, move_pokemon
from tests.conftest import make_species

pytestmark = pytest.mark.django_db

START = datetime(2026, 1, 15, 8, tzinfo=UTC)
CAP = balance.ZONE_WORK_HOURS_CAP


@pytest.fixture
def player(django_user_model):
    user = django_user_model.objects.create_user("ash")
    player = Player.objects.create(user=user, last_slot=START)
    give_starting_zones(player)
    return player


@pytest.fixture
def bulbasaur_owned(player, bulbasaur):
    """A level 10 Bulbasaur (Grass/Poison: at home in the Orchard), medium curve."""
    return OwnedPokemon.objects.create(player=player, species=bulbasaur, level=10)


def zone(player, slug):
    return player.zones.get(zone=slug)


def stock(player, resource):
    row = ResourceStock.objects.filter(player=player, resource=resource).first()
    return row.amount if row else 0


BULBASAUR_AT_10 = Worker(types=("grass", "poison"), level=10)


# --- Starting zones -----------------------------------------------------------


def test_a_new_save_has_the_starting_zones(django_user_model):
    player = ensure_player(django_user_model.objects.create_user("misty"))
    assert sorted(player.zones.values_list("zone", flat=True)) == sorted(balance.STARTING_ZONES)


# --- Status -------------------------------------------------------------------------


def test_a_pokemon_goes_to_work_and_comes_back(player, bulbasaur_owned):
    orchard = zone(player, "orchard")
    pokemon = move_pokemon(bulbasaur_owned, orchard)
    assert (pokemon.status, pokemon.zone) == (OwnedPokemon.IN_ZONE, orchard)

    pokemon = move_pokemon(pokemon, None)
    assert (pokemon.status, pokemon.zone) == (OwnedPokemon.FREE, None)


def test_a_zone_holds_a_limited_number_of_pokemon(player, bulbasaur, grass):
    meadow = zone(player, "meadow")
    for number in range(balance.ZONE_SLOTS_BASE):
        species = make_species(100 + number, f"Test{number}", bulbasaur.evolution_chain, grass)
        move_pokemon(OwnedPokemon.objects.create(player=player, species=species), meadow)
    with pytest.raises(ZoneError, match="full"):
        move_pokemon(OwnedPokemon.objects.create(player=player, species=bulbasaur), meadow)


def test_a_pokemon_cannot_work_in_another_players_zone(player, bulbasaur_owned, django_user_model):
    other = ensure_player(django_user_model.objects.create_user("brock"))
    with pytest.raises(ZoneError):
        move_pokemon(bulbasaur_owned, other.zones.first())


def test_the_database_refuses_a_half_assigned_pokemon(bulbasaur_owned):
    # Status "in a zone" without a zone: the check constraint says no
    bulbasaur_owned.status = OwnedPokemon.IN_ZONE
    with pytest.raises(IntegrityError):
        bulbasaur_owned.save()


# --- Work and collection -------------------------------------------------------


def test_zones_work_during_the_catch_up(player, bulbasaur_owned):
    orchard = zone(player, "orchard")
    move_pokemon(bulbasaur_owned, orchard)
    catch_up_player(player, now=START + timedelta(hours=3, minutes=20))

    orchard.refresh_from_db()
    bulbasaur_owned.refresh_from_db()
    assert orchard.hours_worked == 3
    assert orchard.stock_centi == 3 * production_per_hour(ZONES["orchard"], BULBASAUR_AT_10)
    assert bulbasaur_owned.pending_experience == 3 * experience_per_hour(
        ZONES["orchard"], BULBASAUR_AT_10
    )
    assert bulbasaur_owned.level == 10  # experience waits for the collection


def test_work_stops_when_the_storage_is_full(player, bulbasaur_owned):
    orchard = zone(player, "orchard")
    move_pokemon(bulbasaur_owned, orchard)
    catch_up_player(player, now=START + timedelta(days=3))
    orchard.refresh_from_db()
    assert orchard.hours_worked == CAP
    assert orchard.is_full


def test_collecting_pays_resources_and_experience(player, bulbasaur_owned):
    orchard = zone(player, "orchard")
    move_pokemon(bulbasaur_owned, orchard)
    catch_up_player(player, now=START + timedelta(days=1))

    harvest = collect(orchard)

    hourly = production_per_hour(ZONES["orchard"], BULBASAUR_AT_10)  # 110 hundredths
    assert harvest.hours == CAP
    assert harvest.resource == CAP * hourly // 100
    assert stock(player, "apricorn") == harvest.resource
    orchard.refresh_from_db()
    assert orchard.stock_centi == CAP * hourly % 100  # the hundredths left stay
    assert (orchard.hours_worked, orchard.is_full) == (0, False)  # back to work

    bulbasaur_owned.refresh_from_db()
    gained = CAP * experience_per_hour(ZONES["orchard"], BULBASAUR_AT_10)
    assert harvest.growths[0].experience == gained
    assert bulbasaur_owned.pending_experience == 0
    # The engine's curve decides the new level (medium curve for this species)
    expected = add_experience("medium", 10, 0, gained)
    assert (bulbasaur_owned.level, bulbasaur_owned.experience) == expected
    assert harvest.growths[0].levels == expected[0] - 10


def test_leaving_a_zone_collects_it_first(player, bulbasaur_owned):
    orchard = zone(player, "orchard")
    move_pokemon(bulbasaur_owned, orchard)
    catch_up_player(player, now=START + timedelta(hours=4))

    pokemon = move_pokemon(bulbasaur_owned, None)
    assert stock(player, "apricorn") > 0  # earned before leaving: paid
    assert pokemon.pending_experience == 0


def test_an_empty_zone_does_not_fill_up(player):
    catch_up_player(player, now=START + timedelta(days=2))
    meadow = zone(player, "meadow")
    assert (meadow.hours_worked, meadow.stock_centi) == (0, 0)


# --- Feeder --------------------------------------------------------------------------


@pytest.fixture
def berries(player):
    ResourceStock.objects.create(player=player, resource="berry", amount=10)


def test_filling_the_feeder_takes_from_the_stock(player, berries):
    fill_feeder(player, "berry", 4)
    player.refresh_from_db()
    assert player.feeder == {"berry": 4}
    assert stock(player, "berry") == 6


def test_the_feeder_needs_enough_resources(player, berries):
    with pytest.raises(ZoneError, match="Not enough"):
        fill_feeder(player, "berry", 11)
    assert stock(player, "berry") == 10  # nothing taken


def test_the_feeder_has_limited_slots(player, berries):
    ResourceStock.objects.create(player=player, resource="apricorn", amount=5)
    fill_feeder(player, "berry", 2)
    fill_feeder(player, "berry", 1)  # same resource: same slot
    with pytest.raises(ZoneError, match="full"):
        fill_feeder(player, "apricorn", 1)


def test_the_feeder_only_takes_resources_of_the_players_zones(player, berries):
    player.zones.filter(zone="meadow").delete()
    with pytest.raises(ZoneError):
        fill_feeder(player, "berry", 1)


def test_arrivals_eat_from_the_feeder(player, berries, bulbasaur):
    Species.objects.filter(pk=bulbasaur.pk).update(is_available=True, rarity="common")
    fill_feeder(player, "berry", 5)
    catch_up_player(player, now=START + timedelta(hours=3))
    player.refresh_from_db()
    assert player.arrivals.count() == 3
    assert player.feeder == {"berry": 2}


def test_arrival_conditions_see_the_occupied_zones(player, bulbasaur, bulbasaur_owned):
    # A species that only comes while someone works in the Orchard
    Species.objects.filter(pk=bulbasaur.pk).update(
        is_available=True, rarity="common", arrival_conditions={"zone_occupied": "orchard"}
    )
    catch_up_player(player, now=START + timedelta(hours=2))
    assert player.arrivals.count() == 0

    move_pokemon(bulbasaur_owned, zone(player, "orchard"))
    catch_up_player(player, now=START + timedelta(hours=4))
    assert player.arrivals.count() == 2
