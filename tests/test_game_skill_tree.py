"""Tests of the skill tree: its data, costs, prerequisites, effects and budget."""

from pathlib import Path

import pytest

from game import balance
from game.challenges import challenge_points
from game.skill_tree import SkillTreeError, load, nice_round, parse
from pokedex.species_files import read_species_files

ROOT = Path(__file__).resolve().parent.parent
TREE = load(ROOT / "data" / "skill_tree.json")


def test_the_data_file_is_valid():
    # Guards the hand-edited file: a mistake fails the CI
    assert set(TREE.trees) == {"ranch", "feeder", "meadow", "orchard"}
    assert len(TREE.nodes) >= 30


def test_costs_grow_with_the_column_and_milestones_cost_more():
    base = balance.SKILL_COST_BASE["research"]
    assert TREE.cost("ranch-welcome-1") == {"research": nice_round(base)}
    later = TREE.cost("ranch-welcome-3")["research"]
    assert later > TREE.cost("ranch-welcome-2")["research"]
    # A milestone of a zone also costs research points
    assert set(TREE.cost("meadow-level-2")) == {"berry", "research"}
    assert TREE.cost("meadow-level-2")["berry"] > TREE.cost("meadow-yield-2")["berry"]


def test_prices_are_easy_to_read():
    assert nice_round(37) == 35
    assert nice_round(143) == 140
    assert nice_round(1) == 5  # never free


def test_a_node_needs_the_nodes_before_it():
    assert TREE.can_unlock("ranch-welcome-1", set())
    assert not TREE.can_unlock("ranch-research-1", set())
    assert TREE.can_unlock("ranch-research-1", {"ranch-welcome-1"})
    assert not TREE.can_unlock("ranch-welcome-1", {"ranch-welcome-1"})  # once


def test_the_feeder_tree_opens_with_the_ranch_level_2():
    assert not TREE.is_open("feeder", set())
    assert not TREE.can_unlock("feeder-units-1", set())
    assert TREE.can_unlock("feeder-units-1", {"ranch-level-2"})


def test_a_late_zone_step_waits_for_the_ranch():
    # Everything of the Meadow before its level 3, but not the Ranch level 2
    before = {node_id for node_id, node in TREE.nodes.items() if node.tree == "meadow"}
    before.discard("meadow-level-3")
    assert not TREE.can_unlock("meadow-level-3", before)
    assert TREE.can_unlock("meadow-level-3", before | {"ranch-level-2"})


def test_bonuses_add_up():
    bonuses = TREE.bonuses({"ranch-welcome-1", "ranch-welcome-2", "ranch-storage-1"})
    assert bonuses.welcome_places == 2
    # "zone": "all": every zone gets it
    assert bonuses.zone_storage_hours == {"meadow": 1, "orchard": 1}
    assert bonuses.zone_level == {"meadow": 1, "orchard": 1}  # level 1 at the start
    zone = TREE.bonuses({"meadow-yield-1", "meadow-level-2"})
    assert zone.of_zone("zone_yield_percent", "meadow") == 5
    assert zone.of_zone("zone_slots", "meadow") == 1
    assert zone.zone_level == {"meadow": 2, "orchard": 1}
    assert zone.of_zone("zone_slots", "orchard") == 0


def tree_with(**node):
    """A minimal valid file, with one node changed."""
    base = {"id": "a", "tree": "ranch", "name": "A", "col": 1, "effects": {"welcome_places": 1}}
    return {
        "trees": [{"id": "ranch", "name": "Ranch", "currencies": ["research"]}],
        "nodes": [base | node],
    }


@pytest.mark.parametrize(
    "raw",
    [
        [],  # not an object
        tree_with(effects={"fly": 1}),  # unknown effect
        tree_with(requires=["nowhere"]),  # unknown node
        tree_with(effects={"zone_slots": 1}),  # a zone effect outside a zone tree
        tree_with(col=0),  # columns start at 1
        tree_with(tree="moon"),  # unknown tree
    ],
)
def test_malformed_trees_are_rejected(raw):
    with pytest.raises(SkillTreeError):
        parse(raw)


def test_a_node_only_requires_nodes_on_its_left():
    raw = tree_with()
    raw["nodes"].append(
        {"id": "b", "tree": "ranch", "name": "B", "col": 1, "effects": {}, "requires": ["a"]}
    )
    with pytest.raises(SkillTreeError, match="not on its left"):
        parse(raw)


def test_the_nodes_fit_the_research_budget():
    # All the nodes together cost a share of what the species of the game can
    # give: 9 challenges each (8 for a species alone in its family: the pool
    # is a little overestimated) and the rewards of the stages 1 and 2
    files = read_species_files(ROOT / "data" / "species")
    pool = sum(
        9 * challenge_points(data.rarity)
        + balance.STAGE_1_RESEARCH_POINTS
        + balance.STAGE_2_RESEARCH_POINTS
        for data in files
    )
    low, high = balance.SKILL_BUDGET_SHARE
    assert low <= TREE.total_cost()["research"] / pool <= high
