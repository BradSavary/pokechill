"""Tests of the default moves of a Pokémon (last four learned by level-up)."""

from game.moves import default_moves

# Bulbasaur in FireRed/LeafGreen (start of its level-up learnset)
BULBASAUR = [
    (1, "tackle"),
    (4, "growl"),
    (7, "leech-seed"),
    (10, "vine-whip"),
    (15, "poison-powder"),
    (15, "sleep-powder"),
]


def test_a_level_1_pokemon_knows_its_first_moves():
    assert default_moves(BULBASAUR, 1) == ["tackle"]


def test_moves_learned_up_to_the_level():
    assert default_moves(BULBASAUR, 9) == ["tackle", "growl", "leech-seed"]


def test_a_fifth_move_replaces_the_oldest():
    assert default_moves(BULBASAUR, 15) == [
        "leech-seed",
        "vine-whip",
        "poison-powder",
        "sleep-powder",
    ]


def test_input_order_does_not_matter():
    assert default_moves(list(reversed(BULBASAUR)), 10) == default_moves(BULBASAUR, 10)


def test_a_move_listed_twice_counts_once():
    learnset = [(1, "tackle"), (1, "growl"), (20, "tackle")]
    assert default_moves(learnset, 20) == ["growl", "tackle"]


def test_no_level_up_move():
    assert default_moves([], 50) == []
