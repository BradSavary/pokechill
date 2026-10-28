"""Tests of the harvest zones: efficiency, production, experience and storage."""

from game import balance
from game.zones import (
    ZONE_OF_RESOURCE,
    ZONES,
    Worker,
    experience_per_hour,
    is_efficient,
    production_per_hour,
    work,
)

MEADOW, ORCHARD = ZONES["meadow"], ZONES["orchard"]
PIDGEY = Worker(types=("normal", "flying"), level=5)
BULBASAUR = Worker(types=("grass", "poison"), level=10)

# The 18 types of PokéAPI (modern chart): zones may only favour real types
TYPES = {
    "normal", "fire", "water", "electric", "grass", "ice", "fighting", "poison", "ground",
    "flying", "psychic", "bug", "rock", "ghost", "dragon", "dark", "steel", "fairy",
}  # fmt: skip


def test_zones_and_their_resources():
    assert MEADOW.resource == "berry"
    assert ORCHARD.resource == "apricorn"
    assert ZONE_OF_RESOURCE["apricorn"] is ORCHARD
    for zone in ZONES.values():
        assert zone.types <= TYPES


def test_one_matching_type_is_enough():
    assert is_efficient(MEADOW, PIDGEY)
    assert is_efficient(ORCHARD, BULBASAUR)  # Grass/Poison: Grass matches
    assert not is_efficient(ORCHARD, PIDGEY)


def test_production_depends_on_type_and_level():
    # 1 resource an hour, +1 % per level: a level 5 makes 1.05 per hour
    assert production_per_hour(MEADOW, PIDGEY) == 105
    # Off type: 25 % of the rate
    assert production_per_hour(ORCHARD, PIDGEY) == 26


def test_experience_has_a_type_bonus():
    # Level 10: 20 + 3 x 10 = 50 an hour, +25 % in a matching zone
    assert experience_per_hour(MEADOW, BULBASAUR) == 50
    assert experience_per_hour(ORCHARD, BULBASAUR) == 62


def test_work_adds_up_every_worker():
    result = work(MEADOW, [PIDGEY, BULBASAUR], hours_done=0, hours_elapsed=3)
    assert result.hours == 3
    hourly = production_per_hour(MEADOW, PIDGEY) + production_per_hour(MEADOW, BULBASAUR)
    assert result.resource_centi == 3 * hourly
    assert result.experience == (
        3 * experience_per_hour(MEADOW, PIDGEY),
        3 * experience_per_hour(MEADOW, BULBASAUR),
    )


def test_work_stops_when_the_storage_is_full():
    cap = balance.ZONE_WORK_HOURS_CAP
    assert work(MEADOW, [PIDGEY], hours_done=0, hours_elapsed=100).hours == cap
    assert work(MEADOW, [PIDGEY], hours_done=cap - 2, hours_elapsed=5).hours == 2
    full = work(MEADOW, [PIDGEY], hours_done=cap, hours_elapsed=5)
    assert (full.hours, full.resource_centi, full.experience) == (0, 0, (0,))


def test_an_empty_zone_does_nothing():
    assert work(MEADOW, [], hours_done=0, hours_elapsed=10).hours == 0


def test_working_in_two_visits_or_one_gives_the_same():
    # The storage cap is reached at the same point, whenever the player looks
    once = work(MEADOW, [PIDGEY], hours_done=0, hours_elapsed=20)
    first = work(MEADOW, [PIDGEY], hours_done=0, hours_elapsed=7)
    second = work(MEADOW, [PIDGEY], hours_done=first.hours, hours_elapsed=13)
    assert once.resource_centi == first.resource_centi + second.resource_centi
