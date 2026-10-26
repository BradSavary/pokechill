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


def test_valid_tree_passes_validation():
    validate({"all": [AT_NIGHT, {"not": {"any": [BY_DAY]}}]})


@pytest.mark.parametrize(
    "tree",
    [
        {"weather": "rain"},  # unknown condition
        {"time_of_day": "evening"},  # unknown value
        {"time_of_day": "day", "not": BY_DAY},  # two keys in one node
        {"all": AT_NIGHT},  # "all" expects a list
        {"all": [{"any": [{"weather": "rain"}]}]},  # error deep in the tree
        "night",  # not an object at all
    ],
)
def test_invalid_trees_are_rejected(tree):
    with pytest.raises(ConditionError):
        validate(tree)


def test_evaluating_an_unknown_condition_fails_loudly():
    with pytest.raises(ConditionError):
        evaluate({"weather": "rain"}, DAY)
