"""
Game time: hourly slots, Paris local time and per-slot random generators.

Every arrival happens on the hour. A "slot" is the UTC datetime of that full
hour (e.g. 2026-10-26 14:00:00+00:00). All slots are UTC; Paris time is only
derived to know whether it is day or night.
"""

import hashlib
import random
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from . import balance

ONE_HOUR = timedelta(hours=1)
PARIS = ZoneInfo(balance.GAME_TIMEZONE)


def floor_to_hour(moment: datetime) -> datetime:
    """The slot containing `moment`: 14:37 -> 14:00 (UTC)."""
    if moment.tzinfo is None:
        # A naive datetime has no timezone: guessing would hide bugs
        raise ValueError("Game times must be timezone-aware datetimes.")
    return moment.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def slots_after(last_slot: datetime, now: datetime) -> Iterator[datetime]:
    """
    Every slot after `last_slot` (excluded), up to the current one (included),
    in chronological order. This is what a catch-up has to replay.
    """
    slot = floor_to_hour(last_slot) + ONE_HOUR
    current = floor_to_hour(now)
    while slot <= current:
        yield slot
        slot += ONE_HOUR


def time_of_day(slot: datetime) -> str:
    """ "day" or "night", according to the hour in Paris (handles DST)."""
    hour = slot.astimezone(PARIS).hour
    is_night = hour >= balance.NIGHT_START_HOUR or hour < balance.NIGHT_END_HOUR
    return "night" if is_night else "day"


def slot_rng(player_id: int, slot: datetime) -> random.Random:
    """
    A random generator dedicated to one player and one slot.

    The seed is derived from both values with SHA-256, so the draw of a given
    hour is always the same, whenever it is computed: replaying a catch-up
    twice, or a minute later, gives exactly the same arrivals.
    """
    key = f"{player_id}:{floor_to_hour(slot).isoformat()}".encode()
    seed = int.from_bytes(hashlib.sha256(key).digest()[:8], "big")
    return random.Random(seed)
