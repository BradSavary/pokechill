"""Tests of the mastery bonuses (game.mastery), applied by the zones and the candies."""

from game import balance, experience
from game.mastery import bonuses, candy_percent, is_mastered
from game.zones import ZONES, Worker, experience_per_hour, is_efficient, production_per_hour

ORCHARD = ZONES["orchard"]
PIDGEY = Worker(types=("normal", "flying"), level=10)  # not favoured in the Orchard
MASTERED_PIDGEY = Worker(types=("normal", "flying"), level=10, mastered=True)
BULBASAUR = Worker(types=("grass", "poison"), level=10)  # favoured in the Orchard


def test_a_species_is_mastered_at_its_stage_3():
    assert [is_mastered(stage) for stage in range(4)] == [False, False, False, True]


def test_a_mastered_pokemon_works_at_full_rate_in_every_zone():
    assert not is_efficient(ORCHARD, PIDGEY)
    assert is_efficient(ORCHARD, MASTERED_PIDGEY)
    # Full rate, as a favoured type would, plus its own harvest bonus
    full_rate = production_per_hour(ORCHARD, BULBASAUR)
    expected = full_rate * (100 + balance.MASTERY_YIELD_PERCENT) // 100
    assert production_per_hour(ORCHARD, MASTERED_PIDGEY) == expected


def test_the_mastery_bonuses_add_to_the_skill_tree():
    made = production_per_hour(ORCHARD, BULBASAUR)
    with_tree = production_per_hour(ORCHARD, Worker(("grass",), 10, mastered=True), 10)
    assert with_tree == made * (100 + 10 + balance.MASTERY_YIELD_PERCENT) // 100


def test_a_mastered_pokemon_earns_more_experience():
    base = experience.base_experience_per_hour(10)
    bonus = balance.XP_TYPE_BONUS_PERCENT + balance.MASTERY_XP_PERCENT
    assert experience_per_hour(ORCHARD, MASTERED_PIDGEY) == base * (100 + bonus) // 100


def test_the_candies_of_a_mastered_pokemon_give_more_experience():
    assert candy_percent(False) == 0
    assert candy_percent(True) == balance.MASTERY_CANDY_PERCENT
    plain = experience.candy_experience(10, 1)
    sweet = experience.candy_experience(10, 1, candy_percent(True))
    assert sweet == plain * (100 + balance.MASTERY_CANDY_PERCENT) // 100


def test_the_four_bonuses_are_written_from_the_balance_values():
    found = {bonus.effect: bonus.text for bonus in bonuses()}
    assert set(found) == {"affinity", "harvest", "experience", "candies"}
    assert f"{balance.MASTERY_YIELD_PERCENT} %" in found["harvest"]
    assert f"{balance.MASTERY_CANDY_PERCENT} %" in found["candies"]
