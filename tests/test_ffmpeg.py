"""Tests for the ffmpeg subprocess wrappers."""

from pathlib import Path

import pytest

from fathom.exceptions import ExtractionError
from fathom.ffmpeg import extract_frame, get_duration


def test_get_duration_of_real_video(fixtures_dir: Path) -> None:
    duration = get_duration(fixtures_dir / "fish-swim-by.mp4")
    assert duration > 0
    assert duration < 600  # generous sanity bound


def test_get_duration_of_corrupt_video_raises(fixtures_dir: Path) -> None:
    with pytest.raises(ExtractionError):
        get_duration(fixtures_dir / "corrupt.mp4")


def test_get_duration_of_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ExtractionError):
        get_duration(tmp_path / "does-not-exist.mp4")


def test_extract_frame_writes_jpg(fixtures_dir: Path, tmp_path: Path) -> None:
    output = tmp_path / "frame.jpg"
    extract_frame(fixtures_dir / "fish-swim-by.mp4", 1.0, output)

    assert output.is_file()
    assert output.stat().st_size > 0
    # JPG magic bytes
    assert output.read_bytes()[:3] == b"\xff\xd8\xff"


def test_extract_frame_from_corrupt_raises(fixtures_dir: Path, tmp_path: Path) -> None:
    with pytest.raises(ExtractionError):
        extract_frame(fixtures_dir / "corrupt.mp4", 0.5, tmp_path / "out.jpg")


def test_extract_frame_overwrites_existing(fixtures_dir: Path, tmp_path: Path) -> None:
    output = tmp_path / "frame.jpg"
    output.write_bytes(b"stale content")
    extract_frame(fixtures_dir / "fish-swim-by.mp4", 1.0, output)
    assert output.read_bytes()[:3] == b"\xff\xd8\xff"
