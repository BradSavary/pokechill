"""Tests of game time: slots, Paris day/night cycle and seeded generators."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from game import clock


def utc(*args):
    return datetime(*args, tzinfo=UTC)


def test_floor_to_hour_converts_to_utc():
    paris_summer = timezone(timedelta(hours=2))
    moment = datetime(2026, 7, 1, 15, 37, 12, tzinfo=paris_summer)
    assert clock.floor_to_hour(moment) == utc(2026, 7, 1, 13)


def test_naive_datetimes_are_rejected():
    with pytest.raises(ValueError):
        clock.floor_to_hour(datetime(2026, 7, 1, 15))


def test_slots_after_lists_the_hours_to_replay():
    slots = list(clock.slots_after(utc(2026, 1, 1, 10), utc(2026, 1, 1, 13, 20)))
    assert slots == [utc(2026, 1, 1, 11), utc(2026, 1, 1, 12), utc(2026, 1, 1, 13)]


def test_no_slot_to_replay_within_the_same_hour():
    assert list(clock.slots_after(utc(2026, 1, 1, 10), utc(2026, 1, 1, 10, 59))) == []


@pytest.mark.parametrize(
    ("slot", "expected"),
    [
        # Winter, Paris = UTC+1
        (utc(2026, 1, 15, 19), "day"),  # 20:00 in Paris
        (utc(2026, 1, 15, 20), "night"),  # 21:00 in Paris
        (utc(2026, 1, 15, 4), "night"),  # 05:00 in Paris
        (utc(2026, 1, 15, 5), "day"),  # 06:00 in Paris
        # Summer, Paris = UTC+2 (daylight saving time)
        (utc(2026, 7, 15, 19), "night"),  # 21:00 in Paris
        (utc(2026, 7, 15, 3), "night"),  # 05:00 in Paris
        (utc(2026, 7, 15, 4), "day"),  # 06:00 in Paris
    ],
)
def test_time_of_day_follows_paris_time(slot, expected):
    assert clock.time_of_day(slot) == expected


def test_slot_rng_is_reproducible():
    slot = utc(2026, 3, 1, 8)
    first = [clock.slot_rng(42, slot).random() for _ in range(3)]
    again = [clock.slot_rng(42, slot).random() for _ in range(3)]
    assert first == again


def test_slot_rng_ignores_minutes_within_the_slot():
    on_the_hour = clock.slot_rng(42, utc(2026, 3, 1, 8)).random()
    later = clock.slot_rng(42, utc(2026, 3, 1, 8, 45)).random()
    assert on_the_hour == later


def test_slot_rng_differs_between_players_and_slots():
    slot = utc(2026, 3, 1, 8)
    values = {
        clock.slot_rng(1, slot).random(),
        clock.slot_rng(2, slot).random(),
        clock.slot_rng(1, slot + clock.ONE_HOUR).random(),
    }
    assert len(values) == 3
