"""Tests of hourly arrivals: eligibility, weighted draw and catch-up."""

import ast
import random
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from game import balance
from game.arrivals import (
    NATURES,
    Lure,
    SpeciesRule,
    catch_up,
    draw_arrival,
    eligible_species,
    lure_of,
)
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


def share_of(slug, rules, context, lure=None, draws=3000):
    """Share of `slug` among seeded draws (deterministic: never fails randomly)."""
    picked = [draw_arrival(rules, context, random.Random(i), lure).slug for i in range(draws)]
    return Counter(picked)[slug] / draws


def test_a_lure_is_one_point_of_chance_per_unit_up_to_the_cap():
    assert lure_of(("apricorn", 13)) == Lure(frozenset({"grass", "bug"}), 0.13)
    assert lure_of(("apricorn", 80)).chance == balance.FEEDER_MAX_UNITS / 100


def test_a_lure_raises_the_chance_of_its_types():
    # Two common species: 50/50 without a lure
    assert abs(share_of("caterpie", [RATTATA, CATERPIE], NOON) - 0.5) < 0.03
    # 13 apricorns: +13 points for Grass and Bug, Caterpie comes 63 % of the time
    lure = lure_of(("apricorn", 13))
    assert abs(share_of("caterpie", [RATTATA, CATERPIE], NOON, lure) - 0.63) < 0.03
    # 50 apricorns: +50 points, Caterpie every time
    assert share_of("caterpie", [RATTATA, CATERPIE], NOON, lure_of(("apricorn", 50))) == 1


def test_a_lure_changes_nothing_if_all_or_none_have_its_types():
    lure = lure_of(("apricorn", 30))
    assert share_of("rattata", [RATTATA], NOON, lure) == 1  # nothing Grass or Bug can come
    # Only lured species: the usual draw between them
    assert share_of("caterpie", [CATERPIE], NOON, lure) == 1


def test_the_first_arrival_eats_the_whole_first_slot():
    feeder = [("apricorn", 13), ("berry", 5)]
    one = catch_up(1, [RATTATA], START, START + timedelta(hours=1), free_places=8, feeder=feeder)
    assert one.feeder == [("berry", 5)]  # the second slot waits for the next arrival
    two = catch_up(1, [RATTATA], START, START + timedelta(hours=2), free_places=8, feeder=feeder)
    assert two.feeder == []


def test_nobody_eats_when_the_welcome_area_is_full():
    feeder = [("berry", 5)]
    result = catch_up(1, [RATTATA], START, START + timedelta(hours=5), free_places=0, feeder=feeder)
    assert result.arrivals == []
    assert result.feeder == [("berry", 5)]


def test_conditions_see_the_ranch_during_the_catch_up():
    # Nidoran♂ only comes if the player owns a Nidoran♀
    nidoran_m = SpeciesRule("nidoran-m", "common", {"owns": "nidoran-f"})
    window = (START, START + timedelta(hours=3))
    assert catch_up(1, [nidoran_m], *window, free_places=8).arrivals == []
    owned = catch_up(1, [nidoran_m], *window, free_places=8, owned=frozenset({"nidoran-f"}))
    assert len(owned.arrivals) == 3


def test_catch_up_with_a_feeder_does_not_depend_on_when_it_runs():
    # The slots left after the first visit carry on into the second one
    rules = [RATTATA, CATERPIE, PIKACHU]
    feeder = [("apricorn", 40), ("apricorn", 20), ("berry", 10)]
    middle, end = START + timedelta(hours=2), START + timedelta(hours=10)
    at_once = catch_up(5, rules, START, end, free_places=99, feeder=feeder)
    first = catch_up(5, rules, START, middle, free_places=99, feeder=feeder)
    second = catch_up(5, rules, first.last_slot, end, free_places=99, feeder=first.feeder)
    assert at_once.arrivals == first.arrivals + second.arrivals
    assert at_once.feeder == second.feeder == []


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
