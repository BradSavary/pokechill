"""Tests of the condition engine (evaluation and validation of condition trees)."""

from datetime import UTC, datetime

import pytest

from game.conditions import ConditionError, GameContext, evaluate, validate

# 12:00 UTC is daytime in Paris, 23:00 UTC is night, all year round
DAY = GameContext(slot=datetime(2026, 1, 15, 12, tzinfo=UTC))
NIGHT = GameContext(slot=datetime(2026, 1, 15, 23, tzinfo=UTC))

AT_NIGHT = {"time_of_day": "night"}
BY_DAY = {"time_of_day": "day"}


def test_no_condition_means_always():
    assert evaluate(None, DAY)
    assert evaluate(None, NIGHT)


def test_time_of_day_leaf():
    assert evaluate(AT_NIGHT, NIGHT)
    assert not evaluate(AT_NIGHT, DAY)


def test_combinators():
    assert evaluate({"any": [AT_NIGHT, BY_DAY]}, DAY)
    assert not evaluate({"all": [AT_NIGHT, BY_DAY]}, DAY)
    assert evaluate({"not": AT_NIGHT}, DAY)


def test_empty_combinators():
    # An empty AND has no failing condition, an empty OR has no true one
    assert evaluate({"all": []}, DAY)
    assert not evaluate({"any": []}, DAY)


def test_nested_tree():
    tree = {"all": [{"not": BY_DAY}, {"any": [AT_NIGHT]}]}
    assert evaluate(tree, NIGHT)
    assert not evaluate(tree, DAY)


def test_ranch_leaves_look_at_the_feeder_the_collection_and_the_zones():
    ranch = GameContext(
        slot=DAY.slot,
        feeder=frozenset({"berry"}),
        owned=frozenset({"nidoran-f"}),
        workers=frozenset({("orchard", "paras")}),
    )
    assert evaluate({"feeder": "berry"}, ranch)
    assert not evaluate({"feeder": "apricorn"}, ranch)
    assert evaluate({"owns": "nidoran-f"}, ranch)
    assert not evaluate({"owns": "nidoran-m"}, ranch)
    assert evaluate({"zone_occupied": "orchard"}, ranch)
    assert not evaluate({"zone_occupied": "meadow"}, ranch)
    assert evaluate({"works_in": {"species": "paras", "zone": "orchard"}}, ranch)
    assert not evaluate({"works_in": {"species": "paras", "zone": "meadow"}}, ranch)
    assert not evaluate({"works_in": {"species": "oddish", "zone": "orchard"}}, ranch)
    # By default the ranch is empty: nothing in the feeder, nothing owned
    assert not evaluate({"feeder": "berry"}, DAY)


def test_valid_tree_passes_validation():
    validate({"all": [AT_NIGHT, {"not": {"any": [BY_DAY]}}]})
    validate({"any": [{"feeder": "apricorn"}, {"owns": "pikachu"}, {"zone_occupied": "meadow"}]})
    validate({"works_in": {"species": "paras", "zone": "orchard"}})


def test_zone_level_looks_at_the_zones_of_the_player():
    ranch = GameContext(slot=DAY.slot, zone_levels={"meadow": 2, "orchard": 1})
    assert evaluate({"zone_level": {"zone": "meadow", "level": 2}}, ranch)
    assert not evaluate({"zone_level": {"zone": "orchard", "level": 2}}, ranch)
    # A zone the player hasn't got (yet): never met
    validate({"zone_level": {"zone": "pond", "level": 1}})
    assert not evaluate({"zone_level": {"zone": "pond", "level": 1}}, ranch)


def test_planned_zones_are_valid_but_never_met():
    # The Pond is not in the game yet: Blastoise may already wait for it
    tree = {
        "any": [
            {"feeder": "pearl"},
            {"zone_occupied": "pond"},
            {"works_in": {"species": "squirtle", "zone": "pond"}},
        ]
    }
    validate(tree)
    assert not evaluate(tree, DAY)


@pytest.mark.parametrize(
    "tree",
    [
        {"weather": "rain"},  # unknown condition
        {"time_of_day": "evening"},  # unknown value
        {"time_of_day": "day", "not": BY_DAY},  # two keys in one node
        {"all": AT_NIGHT},  # "all" expects a list
        {"all": [{"any": [{"weather": "rain"}]}]},  # error deep in the tree
        {"feeder": "gold"},  # no zone makes gold, not even a planned one
        {"zone_occupied": "moon"},  # unknown zone
        {"owns": ""},  # empty species slug
        {"works_in": "paras"},  # needs a species and a zone
        {"works_in": {"species": "paras"}},  # the zone is missing
        {"works_in": {"species": "paras", "zone": "moon"}},  # unknown zone
        {"zone_level": {"zone": "meadow"}},  # the level is missing
        {"zone_level": {"zone": "meadow", "level": 0}},  # levels start at 1
        "night",  # not an object at all
    ],
)
def test_invalid_trees_are_rejected(tree):
    with pytest.raises(ConditionError):
        validate(tree)


def test_evaluating_an_unknown_condition_fails_loudly():
    with pytest.raises(ConditionError):
        evaluate({"weather": "rain"}, DAY)
