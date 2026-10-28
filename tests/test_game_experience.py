"""Tests of the experience curves (the games' growth rates)."""

import pytest

from game.experience import CURVES, MAX_LEVEL, add_experience, level_for, total_experience


@pytest.mark.parametrize(
    ("curve", "level_50", "level_100"),
    [
        # Values of the games (Bulbapedia, "Experience" page)
        ("fast", 100_000, 800_000),
        ("medium", 125_000, 1_000_000),
        ("medium-slow", 117_360, 1_059_860),
        ("slow", 156_250, 1_250_000),
    ],
)
def test_curves_match_the_games(curve, level_50, level_100):
    assert total_experience(curve, 1) == 0
    assert total_experience(curve, 50) == level_50
    assert total_experience(curve, 100) == level_100


def test_medium_slow_starts_at_zero_despite_its_formula():
    # The formula gives -54 at level 1; the games start everyone at 0
    assert total_experience("medium-slow", 1) == 0
    assert total_experience("medium-slow", 2) == 9


@pytest.mark.parametrize("curve", CURVES)
def test_each_level_costs_more_experience(curve):
    totals = [total_experience(curve, level) for level in range(1, MAX_LEVEL + 1)]
    assert totals == sorted(totals)
    assert len(set(totals)) == len(totals)


@pytest.mark.parametrize("curve", CURVES)
def test_level_for_is_the_reverse_of_total_experience(curve):
    for level in range(2, MAX_LEVEL + 1):
        needed = total_experience(curve, level)
        assert level_for(curve, needed) == level
        assert level_for(curve, needed - 1) == level - 1  # one point short


def test_level_is_capped_at_100():
    assert level_for("fast", 10**9) == MAX_LEVEL


def test_bad_inputs_fail_loudly():
    with pytest.raises(ValueError):
        total_experience("erratic", 10)  # not used by Kanto species: not supported
    with pytest.raises(ValueError):
        total_experience("medium", 0)
    with pytest.raises(ValueError):
        total_experience("medium", 101)


def test_add_experience_levels_up_and_keeps_the_rest():
    # Medium curve: level 10 = 1000, level 11 = 1331, level 12 = 1728
    assert add_experience("medium", 10, 0, 200) == (10, 200)
    assert add_experience("medium", 10, 200, 200) == (11, 69)  # 1400 - 1331
    assert add_experience("medium", 10, 0, 800) == (12, 72)  # two levels at once


def test_add_experience_stops_at_level_100():
    assert add_experience("fast", 99, 0, 10**9) == (100, 0)
    assert add_experience("fast", 100, 0, 5000) == (100, 0)
