"""Tests of hourly arrivals: eligibility, weighted draw and catch-up."""

import ast
import random
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from game import balance
from game.arrivals import NATURES, SpeciesRule, catch_up, draw_arrival, eligible_species
from game.conditions import GameContext

START = datetime(2026, 1, 15, 0, tzinfo=UTC)
NOON = GameContext(slot=datetime(2026, 1, 15, 12, tzinfo=UTC))
MIDNIGHT = GameContext(slot=datetime(2026, 1, 15, 23, tzinfo=UTC))

PIDGEY = SpeciesRule("pidgey", "common", {"time_of_day": "day"}, ("normal", "flying"))
RATTATA = SpeciesRule("rattata", "common", types=("normal",))  # no condition: any time
ZUBAT = SpeciesRule("zubat", "common", {"time_of_day": "night"}, ("poison", "flying"))
PIKACHU = SpeciesRule("pikachu", "rare", types=("electric",))
CATERPIE = SpeciesRule("caterpie", "common", types=("bug",))
RULES = [PIDGEY, RATTATA, ZUBAT, PIKACHU]


def test_eligible_species_follow_conditions():
    assert [r.slug for r in eligible_species(RULES, NOON)] == ["pidgey", "pikachu", "rattata"]
    assert [r.slug for r in eligible_species(RULES, MIDNIGHT)] == ["pikachu", "rattata", "zubat"]


def test_no_arrival_when_nothing_is_eligible():
    assert draw_arrival([ZUBAT], NOON, random.Random(1)) is None


def test_draw_is_reproducible_and_ignores_input_order():
    first = draw_arrival(RULES, NOON, random.Random(7))
    again = draw_arrival(list(reversed(RULES)), NOON, random.Random(7))
    assert first == again
    assert first.nature in NATURES


def test_rarity_weights_shape_the_draw():
    # 3000 seeded draws: deterministic, so this test can never fail randomly
    draws = [draw_arrival([RATTATA, PIKACHU], NOON, random.Random(i)) for i in range(3000)]
    common_share = Counter(a.slug for a in draws)["rattata"] / 3000
    expected = 100 / (100 + 12)  # about 0.89
    assert abs(common_share - expected) < 0.03


def test_shiny_rate_matches_the_balance_odds():
    draws_count = 100 * balance.SHINY_ODDS  # about 100 shinies expected
    draws = [draw_arrival([RATTATA], NOON, random.Random(i)) for i in range(draws_count)]
    shinies = sum(a.is_shiny for a in draws)
    assert 70 <= shinies <= 130


def test_catch_up_replays_each_hour():
    result = catch_up(1, [RATTATA], START, START + timedelta(hours=5, minutes=30), free_places=8)
    assert [a.slot.hour for a in result.arrivals] == [1, 2, 3, 4, 5]
    assert result.last_slot == START + timedelta(hours=5)


def test_catch_up_stops_when_the_welcome_area_is_full():
    result = catch_up(1, [RATTATA], START, START + timedelta(days=3), free_places=2)
    assert len(result.arrivals) == 2
    assert result.hours_while_full == 72 - 2  # every hour after the 2 arrivals
    # Lost arrivals still count as processed: the clock moves to the current hour
    assert result.last_slot == START + timedelta(days=3)


def test_catch_up_respects_conditions_hour_by_hour():
    result = catch_up(1, [PIDGEY, ZUBAT], START, START + timedelta(hours=24), free_places=99)
    for arrival in result.arrivals:
        # In January Paris is UTC+1: day from 05:00 to 19:59 UTC
        expected = "pidgey" if 5 <= arrival.slot.hour < 20 else "zubat"
        assert arrival.slug == expected


def test_catch_up_does_not_depend_on_when_it_runs():
    # Catching up 10 hours at once or in two visits must give the same arrivals
    middle, end = START + timedelta(hours=4), START + timedelta(hours=10)
    at_once = catch_up(5, RULES, START, end, free_places=99).arrivals
    first_visit = catch_up(5, RULES, START, middle, free_places=99)
    second_visit = catch_up(5, RULES, first_visit.last_slot, end, free_places=99)
    assert at_once == first_visit.arrivals + second_visit.arrivals


def test_no_catch_up_within_the_same_hour():
    result = catch_up(1, RULES, START, START + timedelta(minutes=59), free_places=8)
    assert result.arrivals == []
    assert result.last_slot == START


def share_of(slug, rules, context, draws=3000):
    """Share of `slug` among seeded draws (deterministic: never fails randomly)."""
    picked = [draw_arrival(rules, context, random.Random(i)).slug for i in range(draws)]
    return Counter(picked)[slug] / draws


def test_the_feeder_makes_its_types_more_likely():
    # Two common species: 50/50 without feeder
    assert abs(share_of("caterpie", [RATTATA, CATERPIE], NOON) - 0.5) < 0.03
    # Apricorns attract Grass and Bug: Caterpie weighs 3 times more, 3/4 of the draws
    apricorns = GameContext(slot=NOON.slot, feeder=frozenset({"apricorn"}))
    expected = balance.FEEDER_WEIGHT_MULTIPLIER / (balance.FEEDER_WEIGHT_MULTIPLIER + 1)
    assert abs(share_of("caterpie", [RATTATA, CATERPIE], apricorns) - expected) < 0.03


def test_each_arrival_eats_from_the_feeder():
    result = catch_up(
        1, [RATTATA], START, START + timedelta(hours=3), free_places=8, feeder={"berry": 5}
    )
    assert len(result.arrivals) == 3
    assert result.feeder == {"berry": 2}


def test_the_feeder_runs_out_and_its_empty_slot_goes():
    # 2 apricorns, 4 arrivals: the bonus ends after the 2nd (an empty feeder
    # has no attracted types, see test_game_conditions), and the slot is freed
    result = catch_up(
        1, [CATERPIE], START, START + timedelta(hours=4), free_places=8, feeder={"apricorn": 2}
    )
    assert len(result.arrivals) == 4
    assert result.feeder == {}


def test_nobody_eats_when_the_welcome_area_is_full():
    result = catch_up(
        1, [RATTATA], START, START + timedelta(hours=5), free_places=0, feeder={"berry": 5}
    )
    assert result.arrivals == []
    assert result.feeder == {"berry": 5}


def test_conditions_see_the_ranch_during_the_catch_up():
    # Nidoran♂ only comes if the player owns a Nidoran♀
    nidoran_m = SpeciesRule("nidoran-m", "common", {"owns": "nidoran-f"})
    window = (START, START + timedelta(hours=3))
    assert catch_up(1, [nidoran_m], *window, free_places=8).arrivals == []
    owned = catch_up(1, [nidoran_m], *window, free_places=8, owned=frozenset({"nidoran-f"}))
    assert len(owned.arrivals) == 3


def test_catch_up_with_a_feeder_does_not_depend_on_when_it_runs():
    # The feeder left after the first visit carries on into the second one
    rules = [RATTATA, CATERPIE, PIKACHU]
    middle, end = START + timedelta(hours=4), START + timedelta(hours=10)
    at_once = catch_up(5, rules, START, end, free_places=99, feeder={"apricorn": 6})
    first = catch_up(5, rules, START, middle, free_places=99, feeder={"apricorn": 6})
    second = catch_up(5, rules, first.last_slot, end, free_places=99, feeder=first.feeder)
    assert at_once.arrivals == first.arrivals + second.arrivals
    assert at_once.feeder == second.feeder


def test_balance_covers_every_rarity():
    assert balance.RARITY_WEIGHTS.keys() == balance.CANDIES_PER_DUPLICATE.keys()


def test_game_package_never_imports_django():
    # Architecture rule: the engine stays pure Python (see game/__init__.py)
    for path in Path("game").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            assert not any(m.split(".")[0] == "django" for m in modules), path
