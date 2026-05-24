"""Tests for Event clustering and selection."""

from fathom.events import (
    EVENT_GAP_SECONDS,
    ScoredFrame,
    cluster_into_events,
    select_top_events,
)


def _frame(timestamp: float, score: float, label: str = "") -> ScoredFrame[str]:
    return ScoredFrame(timestamp=timestamp, score=score, payload=label or f"t={timestamp}")


def test_empty_input_yields_no_events() -> None:
    assert cluster_into_events([]) == []


def test_single_frame_yields_one_event() -> None:
    events = cluster_into_events([_frame(0.0, 0.5)])
    assert len(events) == 1
    assert len(events[0]) == 1


def test_two_frames_within_gap_form_one_event() -> None:
    events = cluster_into_events([_frame(0.0, 0.5), _frame(1.5, 0.5)])
    assert len(events) == 1
    assert len(events[0]) == 2


def test_two_frames_beyond_gap_form_two_events() -> None:
    events = cluster_into_events([_frame(0.0, 0.5), _frame(3.0, 0.5)])
    assert len(events) == 2


def test_burst_of_12_frames_within_3_seconds_collapses_to_one_event() -> None:
    """Acceptance case: 12 score-clearing frames in one 3-second burst → 1 Event."""
    frames = [_frame(i * 0.25, 0.5) for i in range(12)]  # 0.0, 0.25, ..., 2.75
    events = cluster_into_events(frames)
    assert len(events) == 1
    assert len(events[0]) == 12


def test_three_distinct_appearances_form_three_events() -> None:
    """Acceptance case: 3 distinct wildlife appearances → 3 Events."""
    frames = [
        _frame(0.0, 0.5),
        _frame(1.0, 0.5),  # event 1: 0, 1
        _frame(10.0, 0.5),
        _frame(11.0, 0.5),  # event 2: 10, 11
        _frame(20.0, 0.5),  # event 3: 20
    ]
    events = cluster_into_events(frames)
    assert len(events) == 3


def test_input_does_not_need_to_be_sorted() -> None:
    frames = [_frame(3.0, 0.5), _frame(0.0, 0.5), _frame(1.0, 0.5)]
    events = cluster_into_events(frames)
    # Sorted, the gap between 0 and 1 (1s) is within gap; between 1 and 3 (2s) is the boundary.
    # EVENT_GAP_SECONDS is 2.0 and we use strict `<`, so 2.0 should NOT merge.
    assert len(events) == 2
    assert len(events[0]) == 2  # 0.0 and 1.0
    assert len(events[1]) == 1  # 3.0


def test_select_top_events_picks_best_per_event() -> None:
    frames = [
        _frame(0.0, 0.4),
        _frame(0.5, 0.9),  # best of event 1
        _frame(1.0, 0.7),
        _frame(10.0, 0.6),  # best of event 2 (only frame)
    ]
    chosen = select_top_events(frames, min_score=0.0, max_events=10)
    assert len(chosen) == 2
    assert chosen[0].score == 0.9
    assert chosen[1].score == 0.6


def test_select_top_events_drops_frames_below_floor() -> None:
    """Acceptance case: every frame below min_score → 0 selected."""
    frames = [_frame(i * 5.0, 0.1) for i in range(5)]
    chosen = select_top_events(frames, min_score=0.5, max_events=6)
    assert chosen == []


def test_select_top_events_caps_at_max_events() -> None:
    """Acceptance case: 8 distinct appearances, max_events=6 → 6 selected."""
    frames = [_frame(i * 10.0, 0.5 + i * 0.01) for i in range(8)]
    chosen = select_top_events(frames, min_score=0.0, max_events=6)
    assert len(chosen) == 6
    # Returned in best-score order, so the highest-scoring (last in the input) comes first.
    assert chosen[0].score >= chosen[-1].score


def test_select_top_events_returns_events_ranked_by_best_score() -> None:
    """When fewer than max_events Events exist, all are returned in score-desc order."""
    frames = [
        _frame(0.0, 0.3),  # event 1, best 0.3
        _frame(10.0, 0.9),  # event 2, best 0.9
        _frame(20.0, 0.5),  # event 3, best 0.5
    ]
    chosen = select_top_events(frames, min_score=0.0, max_events=6)
    assert [f.score for f in chosen] == [0.9, 0.5, 0.3]


def test_event_gap_seconds_default_is_two_seconds() -> None:
    """Document the constant the algorithm uses."""
    assert EVENT_GAP_SECONDS == 2.0
