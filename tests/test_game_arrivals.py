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

PIDGEY = SpeciesRule("pidgey", "common", {"time_of_day": "day"})
RATTATA = SpeciesRule("rattata", "common")  # no condition: any time
ZUBAT = SpeciesRule("zubat", "common", {"time_of_day": "night"})
PIKACHU = SpeciesRule("pikachu", "rare")
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
