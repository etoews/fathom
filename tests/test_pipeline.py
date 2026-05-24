"""Tests for the per-video processing pipeline.

Integration tests that exercise event clustering via the real ffmpeg + OpenCV
chain. The detailed unit-level event-clustering tests live in test_events.py.
"""

import shutil
from pathlib import Path

import numpy as np
import pytest

from fathom.analyser import FrameAnalyser, FrameAnalysis, HeuristicAnalyser
from fathom.exceptions import ExtractionError
from fathom.pipeline import process_video
from fathom.state import list_frames_for_video, list_videos, open_db


class _ConstantAnalyser:
    """Test double returning the same Score for every frame."""

    name = "constant"

    def __init__(self, score: float = 0.5) -> None:
        self._score = score

    def analyse(self, frame: np.ndarray) -> FrameAnalysis:
        return FrameAnalysis(score=self._score, components={"sharpness": self._score})


class _AlternatingAnalyser:
    """Returns 0.9 for the first frame of every cycle, 0.1 for the next `gap`.

    Used to manufacture multiple Events from a single video by introducing
    gaps in eligibility (frames scoring below the floor).
    """

    name = "alternating"

    def __init__(self, gap: int) -> None:
        self._gap = gap
        self._calls = 0

    def analyse(self, frame: np.ndarray) -> FrameAnalysis:
        position = self._calls % (1 + self._gap)
        score = 0.9 if position == 0 else 0.1
        self._calls += 1
        return FrameAnalysis(score=score, components={"sharpness": score})


def test_process_video_creates_jpgs_and_records_frames(scan_root_with_videos: Path) -> None:
    video = scan_root_with_videos / "fish-swim-by.mp4"
    conn = open_db(scan_root_with_videos)
    try:
        count = process_video(
            video,
            scan_root_with_videos,
            conn,
            HeuristicAnalyser(),
            rate_fps=3.0,
            max_events=6,
            min_score=0.0,
        )
        videos = list_videos(conn)
        frames = list_frames_for_video(conn, videos[0].id)
    finally:
        conn.close()

    assert 1 <= count <= 6
    exports = sorted(scan_root_with_videos.glob(f"{video.stem}_*.jpg"))
    assert len(exports) == count
    expected_names = [f"{video.stem}_{i:02d}.jpg" for i in range(1, count + 1)]
    assert [p.name for p in exports] == expected_names

    assert len(videos) == 1
    assert len(frames) > 0
    for frame in frames:
        assert 0.0 <= frame.score <= 1.0


def test_continuous_high_scores_collapse_into_single_event(
    scan_root_with_videos: Path,
) -> None:
    """Acceptance: a burst where every sampled frame clears the floor -> 1 Event -> 1 export.

    At 3fps consecutive frames are 0.333s apart, well within the 2s event-gap
    threshold, so a video whose every frame scores above the floor clusters
    into exactly one Event.
    """
    video = scan_root_with_videos / "fish-swim-by.mp4"
    conn = open_db(scan_root_with_videos)
    try:
        count = process_video(
            video,
            scan_root_with_videos,
            conn,
            _ConstantAnalyser(score=0.7),
            rate_fps=3.0,
            max_events=6,
            min_score=0.5,
        )
    finally:
        conn.close()

    assert count == 1


def test_video_row_recorded_even_when_zero_frames_export(
    scan_root_with_videos: Path,
) -> None:
    """Acceptance: a video whose frames never clear the floor still writes a video row.

    This is what lets the re-run skip logic in #6 know we already processed it.
    """
    video = scan_root_with_videos / "empty-water.mp4"
    conn = open_db(scan_root_with_videos)
    try:
        count = process_video(
            video,
            scan_root_with_videos,
            conn,
            _ConstantAnalyser(score=0.1),
            rate_fps=3.0,
            max_events=6,
            min_score=0.9,
        )
        videos = list_videos(conn)
    finally:
        conn.close()

    assert count == 0
    assert not list(scan_root_with_videos.glob(f"{video.stem}_*.jpg"))
    # Despite 0 exports, the video must be recorded so re-runs can skip it.
    assert any(v.relative_path == video.name for v in videos)


def test_eligibility_gaps_produce_multiple_events(scan_root_with_videos: Path) -> None:
    """Acceptance: a video with separated eligibility windows produces multiple Events.

    Alternating analyser with gap=10 makes one frame eligible every 11 sampled
    frames. At 3fps that's a ~3.67s gap between eligible frames — beyond the
    2s event-gap threshold — so each eligible frame becomes its own Event.
    """
    video = scan_root_with_videos / "fish-swim-by.mp4"
    conn = open_db(scan_root_with_videos)
    try:
        count = process_video(
            video,
            scan_root_with_videos,
            conn,
            _AlternatingAnalyser(gap=10),
            rate_fps=3.0,
            max_events=6,
            min_score=0.5,
        )
    finally:
        conn.close()

    assert count >= 2, "expected multiple Events from gap-injected eligibility"


def test_max_events_caps_exports_when_many_events_available(
    scan_root_with_videos: Path,
) -> None:
    """Acceptance: with more Events than the cap, exports are capped at max_events."""
    video = scan_root_with_videos / "multiple-events.mp4"
    conn = open_db(scan_root_with_videos)
    try:
        count = process_video(
            video,
            scan_root_with_videos,
            conn,
            _AlternatingAnalyser(gap=10),
            rate_fps=3.0,
            max_events=3,
            min_score=0.5,
        )
    finally:
        conn.close()

    assert count <= 3


def test_rerun_replaces_prior_exports(scan_root_with_videos: Path) -> None:
    video = scan_root_with_videos / "fish-swim-by.mp4"
    stale = video.with_name(f"{video.stem}_99.jpg")
    stale.write_bytes(b"\xff\xd8\xff" + b"stale")

    conn = open_db(scan_root_with_videos)
    try:
        count = process_video(
            video,
            scan_root_with_videos,
            conn,
            HeuristicAnalyser(),
            rate_fps=3.0,
            max_events=6,
            min_score=0.0,
        )
    finally:
        conn.close()

    assert not stale.exists()
    exports = sorted(scan_root_with_videos.glob(f"{video.stem}_*.jpg"))
    assert len(exports) == count


def test_process_video_protocol_acceptance(scan_root_with_videos: Path) -> None:
    """The pipeline accepts any FrameAnalyser-protocol-compatible object."""
    fake = _ConstantAnalyser(score=0.7)
    assert isinstance(fake, FrameAnalyser)


def test_process_video_raises_for_corrupt(scan_root_with_videos: Path, fixtures_dir: Path) -> None:
    shutil.copy(fixtures_dir / "corrupt.mp4", scan_root_with_videos)
    video = scan_root_with_videos / "corrupt.mp4"

    conn = open_db(scan_root_with_videos)
    try:
        with pytest.raises(ExtractionError):
            process_video(
                video,
                scan_root_with_videos,
                conn,
                HeuristicAnalyser(),
                rate_fps=3.0,
                max_events=6,
                min_score=0.0,
            )
    finally:
        conn.close()
