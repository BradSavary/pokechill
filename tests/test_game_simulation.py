"""Tests of the simulated player (game.simulation), on a small catalogue of species."""

from pathlib import Path

from game.simulation import DayReport, SimSpecies, longest_wait, simulate
from game.skill_tree import load

TREE = load(Path(__file__).resolve().parent.parent / "data" / "skill_tree.json")


def species(slug, rarity, types, family, size=1, min_level=1):
    return SimSpecies(slug, rarity, min_level, types, "medium", 1, family, size)


CATALOG = [
    species("bulbasaur", "uncommon", ("grass", "poison"), "1"),
    species("charmander", "uncommon", ("fire",), "2"),
    species("squirtle", "uncommon", ("water",), "3"),
    species("pidgey", "common", ("normal", "flying"), "4"),
    species("caterpie", "common", ("bug",), "5"),
]


def test_the_simulated_player_progresses():
    reports = simulate(CATALOG, TREE, days=5)
    assert len(reports) == 5
    assert reports[-1].owned == len(CATALOG)  # every species came
    assert reports[-1].research_earned > 0
    assert reports[-1].nodes > 0  # and some nodes were bought
    assert reports[-1].research_earned >= reports[0].research_earned


def test_the_simulation_is_deterministic():
    # Same seed, same game: the settings can be compared run against run
    assert simulate(CATALOG, TREE, days=3) == simulate(CATALOG, TREE, days=3)
    assert simulate(CATALOG, TREE, days=3, seed=2) != simulate(CATALOG, TREE, days=3)


def report(day, bought):
    return DayReport(day, 0, 0, 0, 0, tuple(bought), {})


def test_the_longest_wait_between_two_unlocks():
    reports = [report(1, ["a"]), report(2, []), report(3, []), report(4, ["b"]), report(5, [])]
    assert longest_wait(reports) == 2  # days 2 and 3
    assert longest_wait([report(1, []), report(2, [])]) == 2  # nothing ever unlocked
