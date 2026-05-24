"""Tests for the per-video processing pipeline."""

from pathlib import Path

import numpy as np
import pytest

from fathom.analyser import FrameAnalyser, FrameAnalysis, HeuristicAnalyser
from fathom.pipeline import process_video
from fathom.state import list_frames_for_video, list_videos, open_db


class _ConstantAnalyser:
    """Test double returning the same Score for every frame."""

    name = "constant"

    def __init__(self, score: float = 0.5) -> None:
        self._score = score

    def analyse(self, frame: np.ndarray) -> FrameAnalysis:
        return FrameAnalysis(score=self._score, components={"sharpness": self._score})


def test_process_video_creates_up_to_max_events_jpgs(scan_root_with_videos: Path) -> None:
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
    finally:
        conn.close()

    assert 1 <= count <= 6
    exports = sorted(scan_root_with_videos.glob(f"{video.stem}_*.jpg"))
    assert len(exports) == count
    expected_names = [f"{video.stem}_{i:02d}.jpg" for i in range(1, count + 1)]
    assert [p.name for p in exports] == expected_names


def test_process_video_records_frames_in_sqlite(scan_root_with_videos: Path) -> None:
    video = scan_root_with_videos / "fish-swim-by.mp4"
    conn = open_db(scan_root_with_videos)
    try:
        process_video(
            video,
            scan_root_with_videos,
            conn,
            HeuristicAnalyser(),
            rate_fps=3.0,
            max_events=6,
            min_score=0.0,
        )
        videos = list_videos(conn)
        assert len(videos) == 1
        frames = list_frames_for_video(conn, videos[0].id)
    finally:
        conn.close()

    assert len(frames) > 0
    for frame in frames:
        assert 0.0 <= frame.score <= 1.0
        assert frame.sharpness is not None
        assert frame.edges is not None
        assert frame.colour is not None


def test_process_video_zero_exports_when_floor_is_unreachable(
    scan_root_with_videos: Path,
) -> None:
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
    finally:
        conn.close()

    assert count == 0
    assert not list(scan_root_with_videos.glob(f"{video.stem}_*.jpg"))


def test_process_video_rerun_replaces_prior_exports(scan_root_with_videos: Path) -> None:
    video = scan_root_with_videos / "fish-swim-by.mp4"
    # Pre-seed a stale export that should be cleaned up on rerun.
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


def test_process_video_accepts_protocol_compatible_fake(scan_root_with_videos: Path) -> None:
    fake = _ConstantAnalyser(score=0.7)
    assert isinstance(fake, FrameAnalyser)

    video = scan_root_with_videos / "fish-swim-by.mp4"
    conn = open_db(scan_root_with_videos)
    try:
        count = process_video(
            video,
            scan_root_with_videos,
            conn,
            fake,
            rate_fps=3.0,
            max_events=6,
            min_score=0.5,
        )
    finally:
        conn.close()

    # All frames score 0.7, which exceeds the 0.5 floor, so we expect max_events=6.
    assert count == 6


def test_process_video_max_events_caps_exports(scan_root_with_videos: Path) -> None:
    video = scan_root_with_videos / "fish-swim-by.mp4"
    conn = open_db(scan_root_with_videos)
    try:
        count = process_video(
            video,
            scan_root_with_videos,
            conn,
            HeuristicAnalyser(),
            rate_fps=3.0,
            max_events=2,
            min_score=0.0,
        )
    finally:
        conn.close()

    assert count <= 2


def test_process_video_raises_for_corrupt(scan_root_with_videos: Path, fixtures_dir: Path) -> None:
    # Copy the corrupt fixture into the scan root.
    import shutil

    shutil.copy(fixtures_dir / "corrupt.mp4", scan_root_with_videos)
    video = scan_root_with_videos / "corrupt.mp4"

    from fathom.exceptions import ExtractionError

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
