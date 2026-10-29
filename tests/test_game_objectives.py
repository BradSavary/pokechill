"""Tests of the objective engine: events feed objectives, summed or best value."""

import pytest

from game.objectives import (
    HARVESTED,
    LEVEL,
    OBTAINED,
    Event,
    Objective,
    apply,
)

OBTAIN_PIDGEY_5 = Objective("dex:pidgey:obtain-2", OBTAINED, 5, {"species": "pidgey"})
SHINY_PIDGEY = Objective("dex:pidgey:shiny", OBTAINED, 1, {"species": "pidgey", "shiny": True})
PIDGEY_LEVEL_30 = Objective("dex:pidgey:level-2", LEVEL, 30, {"species": "pidgey"})


def obtained(species, shiny=False):
    return Event(OBTAINED, details={"species": species, "shiny": shiny})


def test_a_sum_adds_up_matching_events():
    changed, completed = apply([OBTAIN_PIDGEY_5], {}, [obtained("pidgey")] * 3)
    assert changed == {OBTAIN_PIDGEY_5.key: 3}
    assert completed == []


def test_other_species_and_other_events_dont_count():
    events = [obtained("rattata"), Event(LEVEL, 30, {"species": "pidgey"})]
    assert apply([OBTAIN_PIDGEY_5], {}, events) == ({}, [])


def test_every_filter_must_match():
    _, completed = apply([SHINY_PIDGEY], {}, [obtained("pidgey")])
    assert completed == []
    _, completed = apply([SHINY_PIDGEY], {}, [obtained("pidgey", shiny=True)])
    assert completed == [SHINY_PIDGEY.key]


def test_completion_is_reported_once_and_progress_stays_at_the_target():
    changed, completed = apply(
        [OBTAIN_PIDGEY_5], {OBTAIN_PIDGEY_5.key: 4}, [obtained("pidgey")] * 3
    )
    assert changed == {OBTAIN_PIDGEY_5.key: 5}  # capped
    assert completed == [OBTAIN_PIDGEY_5.key]
    # Already done: nothing moves, nothing is completed again
    assert apply([OBTAIN_PIDGEY_5], changed, [obtained("pidgey")]) == ({}, [])


def test_a_max_keeps_the_best_value_reached():
    progress = {PIDGEY_LEVEL_30.key: 20}
    assert apply([PIDGEY_LEVEL_30], progress, [Event(LEVEL, 12, {"species": "pidgey"})]) == (
        {},
        [],
    )
    changed, completed = apply(
        [PIDGEY_LEVEL_30], progress, [Event(LEVEL, 31, {"species": "pidgey"})]
    )
    assert changed == {PIDGEY_LEVEL_30.key: 30}
    assert completed == [PIDGEY_LEVEL_30.key]


def test_resending_the_current_state_changes_nothing():
    # MAX objectives can be set up from an existing save by resending its state
    event = Event(LEVEL, 25, {"species": "pidgey"})
    changed, _ = apply([PIDGEY_LEVEL_30], {}, [event])
    assert apply([PIDGEY_LEVEL_30], changed, [event]) == ({}, [])


def test_amounts_can_be_large():
    gather = Objective("dex:pidgey:harvest", HARVESTED, 10_000, {"species": "pidgey"})
    event = Event(HARVESTED, 2_500, {"species": "pidgey", "zone": "meadow"})
    changed, _ = apply([gather], {}, [event, event])
    assert changed == {gather.key: 5_000}


def test_events_and_objectives_are_read_only():
    event = obtained("pidgey")
    with pytest.raises(TypeError):
        event.details["species"] = "rattata"
    with pytest.raises(TypeError):
        OBTAIN_PIDGEY_5.filters["species"] = "rattata"
