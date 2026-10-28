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
from ranch.zone_maps import ZONE_SPOTS
from ranch.zones import (
    ZoneError,
    collect,
    fill_feeder,
    give_starting_zones,
    move_pokemon,
    take_back_slot,
)
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


@pytest.fixture
def two_slots(monkeypatch):
    """A feeder of two slots (one at the start; the skill tree will add more)."""
    monkeypatch.setattr(balance, "FEEDER_SLOTS_BASE", 2)


def test_filling_the_feeder_takes_from_the_stock(player, berries):
    fill_feeder(player, "berry", 4)
    player.refresh_from_db()
    assert player.feeder == [["berry", 4]]
    assert stock(player, "berry") == 6


def test_the_feeder_needs_enough_resources(player, berries):
    with pytest.raises(ZoneError, match="Not enough"):
        fill_feeder(player, "berry", 11)
    assert stock(player, "berry") == 10  # nothing taken


@pytest.mark.parametrize("units", [0, balance.FEEDER_MAX_UNITS + 1])
def test_a_slot_holds_a_limited_number_of_units(player, berries, units):
    with pytest.raises(ZoneError, match="A slot holds"):
        fill_feeder(player, "berry", units)


def test_the_feeder_has_limited_slots(player, berries):
    fill_feeder(player, "berry", 2)
    # The same resource does not join the slot: each filling takes a slot
    with pytest.raises(ZoneError, match="No free slot"):
        fill_feeder(player, "berry", 1)


def test_two_slots_may_hold_the_same_resource(player, berries, two_slots):
    fill_feeder(player, "berry", 2)
    fill_feeder(player, "berry", 3)
    player.refresh_from_db()
    assert player.feeder == [["berry", 2], ["berry", 3]]  # in the order they will be eaten


def test_the_feeder_only_takes_resources_of_the_players_zones(player, berries):
    player.zones.filter(zone="meadow").delete()
    with pytest.raises(ZoneError):
        fill_feeder(player, "berry", 1)


def test_taking_back_a_slot(player, berries, two_slots):
    fill_feeder(player, "berry", 2)
    fill_feeder(player, "berry", 3)
    take_back_slot(player, 0)
    player.refresh_from_db()
    assert player.feeder == [["berry", 3]]  # the other slot moves up
    assert stock(player, "berry") == 7
    with pytest.raises(ZoneError, match="already empty"):
        take_back_slot(player, 1)


def test_each_arrival_eats_a_whole_slot(player, berries, bulbasaur, two_slots):
    Species.objects.filter(pk=bulbasaur.pk).update(is_available=True, rarity="common")
    fill_feeder(player, "berry", 5)
    fill_feeder(player, "berry", 3)
    catch_up_player(player, now=START + timedelta(hours=1))
    player.refresh_from_db()
    assert player.feeder == [["berry", 3]]  # the first arrival ate the first slot
    catch_up_player(player, now=START + timedelta(hours=3))
    player.refresh_from_db()
    assert player.arrivals.count() == 3
    assert player.feeder == []


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


def test_arrival_conditions_see_who_works_where(player, bulbasaur, charmander, bulbasaur_owned):
    # Charmander only comes while a Bulbasaur works in the Orchard
    Species.objects.filter(pk=charmander.pk).update(
        is_available=True,
        rarity="common",
        arrival_conditions={"works_in": {"species": "bulbasaur", "zone": "orchard"}},
    )
    move_pokemon(bulbasaur_owned, zone(player, "meadow"))
    catch_up_player(player, now=START + timedelta(hours=2))
    assert player.arrivals.count() == 0

    move_pokemon(bulbasaur_owned, zone(player, "orchard"))
    catch_up_player(player, now=START + timedelta(hours=4))
    assert player.arrivals.count() == 2


# --- Spots on the map ------------------------------------------------------------------


def test_pokemon_keep_their_spot_when_others_come_and_go(player, bulbasaur, charmander):
    meadow = zone(player, "meadow")
    charmander_owned = move_pokemon(
        OwnedPokemon.objects.create(player=player, species=charmander), meadow
    )
    bulbasaur_owned = move_pokemon(
        OwnedPokemon.objects.create(player=player, species=bulbasaur), meadow
    )
    # Bulbasaur (#1) came second: it takes the next spot, Charmander (#4) stays first
    assert (charmander_owned.spot, bulbasaur_owned.spot) == (0, 1)

    move_pokemon(charmander_owned, None)
    bulbasaur_owned.refresh_from_db()
    assert bulbasaur_owned.spot == 1  # still there, not moved up
    assert move_pokemon(charmander_owned, meadow).spot == 0  # the first free spot again


def test_the_chosen_spot_is_used_if_free(player, bulbasaur, charmander):
    meadow = zone(player, "meadow")
    first = move_pokemon(OwnedPokemon.objects.create(player=player, species=bulbasaur), meadow, 2)
    assert first.spot == 2
    # Spot 2 is taken: the next one goes to the first free spot
    second = move_pokemon(OwnedPokemon.objects.create(player=player, species=charmander), meadow, 2)
    assert second.spot == 0


def test_a_freed_pokemon_has_no_spot(bulbasaur_owned, player):
    pokemon = move_pokemon(move_pokemon(bulbasaur_owned, zone(player, "orchard")), None)
    assert (pokemon.zone, pokemon.spot) == (None, None)


def test_the_maps_have_a_spot_for_each_place_of_a_zone():
    for slug in ZONES:
        assert len(ZONE_SPOTS[slug]) >= balance.ZONE_SLOTS_BASE
