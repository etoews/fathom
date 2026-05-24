"""Event clustering and selection.

An Event is a contiguous span of Frames in the same video that all clear the
Score floor and whose timestamps are within `EVENT_GAP_SECONDS` of each other.
The pipeline picks the highest-scoring Frame from each Event, then takes up
to `max_events` Events per video ranked by their best Frame's Score.

See CONTEXT.md (Event) and ADR-0001 for the rationale.
"""

from collections.abc import Iterable
from dataclasses import dataclass

EVENT_GAP_SECONDS = 2.0


@dataclass(frozen=True)
class ScoredFrame[T]:
    """A timestamped, scored Frame carrying an opaque payload.

    The payload lets selection logic stay generic — the pipeline uses
    `Path` (the on-disk JPG of a sampled frame), tests use small primitives.
    """

    timestamp: float
    score: float
    payload: T


def cluster_into_events[T](
    frames: Iterable[ScoredFrame[T]],
    event_gap_seconds: float = EVENT_GAP_SECONDS,
) -> list[list[ScoredFrame[T]]]:
    """Group frames into Events by time-adjacency.

    Frames are sorted by timestamp; consecutive frames within
    `event_gap_seconds` of each other are placed in the same Event, otherwise
    a new Event starts. Returns a list of Events (each a non-empty list of
    `ScoredFrame`).
    """
    sorted_frames = sorted(frames, key=lambda f: f.timestamp)
    if not sorted_frames:
        return []

    events: list[list[ScoredFrame[T]]] = [[sorted_frames[0]]]
    for frame in sorted_frames[1:]:
        last = events[-1][-1]
        if frame.timestamp - last.timestamp < event_gap_seconds:
            events[-1].append(frame)
        else:
            events.append([frame])
    return events


def select_top_events[T](
    frames: Iterable[ScoredFrame[T]],
    *,
    min_score: float,
    max_events: int,
    event_gap_seconds: float = EVENT_GAP_SECONDS,
) -> list[ScoredFrame[T]]:
    """Filter, cluster, pick best per Event, return up to `max_events`.

    Order of the returned list is by best-frame Score descending, so callers
    can name them `_01.jpg`, `_02.jpg`, ... in rank order.
    """
    eligible = [f for f in frames if f.score >= min_score]
    events = cluster_into_events(eligible, event_gap_seconds)
    bests = [max(event, key=lambda f: f.score) for event in events]
    bests.sort(key=lambda f: f.score, reverse=True)
    return bests[:max_events]
