"""Tests of the Pokédex challenges: generic ones, custom ones, stages and rewards."""

import pytest

from game import balance
from game.challenges import (
    ChallengeError,
    ChallengeSpecies,
    challenge_points,
    challenges_for,
    generic_challenges,
    level_targets,
    stage,
    validate_custom,
)
from game.objectives import FAMILY, OBTAINED, Event, apply

PIDGEY = ChallengeSpecies("pidgey", "common", 1, family="pidgey", family_size=3)
CHARIZARD = ChallengeSpecies("charizard", "very_rare", 36, family="charmander", family_size=3)
TAUROS = ChallengeSpecies("tauros", "rare", 1, family="tauros", family_size=1)


def ids(challenges):
    return [challenge.id for challenge in challenges]


def test_every_species_has_8_to_10_generic_challenges():
    for species in (PIDGEY, CHARIZARD, TAUROS):
        assert 8 <= len(generic_challenges(species)) <= 10
    assert "family" not in ids(generic_challenges(TAUROS))  # alone in its family


def test_generic_challenges_of_a_common_species():
    texts = [challenge.text for challenge in generic_challenges(PIDGEY)]
    # The tiers come from the balance (they may be tuned)
    _, second, third = balance.CHALLENGE_OBTAIN_TIERS["common"]
    assert texts == [
        "Obtain it once",
        f"Obtain it {second} times",
        f"Obtain it {third} times",
        "Reach level 15",
        "Reach level 30",
        "Unlock 3 natures",
        "Unlock all 6 natures",
        "Gather 100 resources",
        "Work 48 hours in a zone",
        "Own its whole family",
    ]


def test_rarer_species_ask_for_fewer_obtentions():
    obtain = [
        c.objective.target for c in generic_challenges(CHARIZARD) if c.id.startswith("obtain")
    ]
    assert obtain == list(balance.CHALLENGE_OBTAIN_TIERS["very_rare"])


def test_levels_start_from_the_arrival_level():
    assert level_targets(1) == [15, 30]
    assert level_targets(36) == [50, 65]  # 46 and 61, rounded up to 5
    assert level_targets(95) == [100, 100]  # never above level 100


def test_challenges_only_count_their_own_species():
    first = generic_challenges(PIDGEY)[0]
    assert first.objective.key == "dex:pidgey:obtain-1"
    assert first.objective.filters == {"species": "pidgey"}
    family = next(c for c in generic_challenges(CHARIZARD) if c.id == "family")
    assert family.objective.event == FAMILY
    assert family.objective.filters == {"family": "charmander"}


def test_a_species_file_adds_and_skips_challenges():
    custom = {
        "add": [{"id": "shiny", "event": "obtained", "filters": {"shiny": True}, "target": 1}],
        "skip": ["work"],
    }
    validate_custom(custom)
    challenges = challenges_for(PIDGEY, custom)
    assert "work" not in ids(challenges)
    shiny = challenges[-1]
    assert (shiny.id, shiny.text) == ("shiny", "Obtain a shiny one once")
    # The species is added to its filters: another species' shiny doesn't count
    event = Event(OBTAINED, details={"species": "rattata", "shiny": True})
    assert apply([shiny.objective], {}, [event]) == ({}, [])


def test_zone_challenges_name_their_zone():
    custom = {
        "add": [{"id": "orchard", "event": "worked", "filters": {"zone": "orchard"}, "target": 24}]
    }
    assert challenges_for(PIDGEY, custom)[-1].text == "Work 24 hours in the Orchard"


@pytest.mark.parametrize(
    "custom",
    [
        [],  # not an object
        {"remove": ["work"]},  # unknown key
        {"add": [{"event": "obtained", "target": 1}]},  # no id
        {"add": [{"id": "x", "event": "fainted", "target": 1}]},  # unknown event
        {"add": [{"id": "x", "event": "obtained", "target": 0}]},  # target below 1
        {"add": [{"id": "x", "event": "level", "target": 50, "filters": {"zone": "meadow"}}]},
        {"add": [{"id": "x", "event": "worked", "target": 5, "filters": {"zone": "moon"}}]},
        {"skip": [3]},
    ],
)
def test_malformed_custom_challenges_are_rejected(custom):
    with pytest.raises(ChallengeError):
        validate_custom(custom)


def test_skipping_or_doubling_a_challenge_that_does_not_exist_fails():
    with pytest.raises(ChallengeError, match="to skip"):
        challenges_for(PIDGEY, {"skip": ["fly"]})
    with pytest.raises(ChallengeError, match="two challenges"):
        challenges_for(PIDGEY, {"add": [{"id": "work", "event": "worked", "target": 5}]})


def test_stages():
    assert stage(owned=False, completed=0, total=10) == 0
    assert stage(owned=True, completed=0, total=10) == 1
    assert stage(owned=True, completed=balance.STAGE_2_CHALLENGES, total=10) == 2
    assert stage(owned=True, completed=10, total=10) == 3


def test_rarer_species_give_more_research_points():
    assert challenge_points("common") < challenge_points("rare") < challenge_points("legendary")
