"""Tests for the exiftool subprocess wrapper."""

import subprocess
from pathlib import Path

import pytest

from fathom.exceptions import ExtractionError
from fathom.exiftool import EXIFTOOL_BINARY, copy_metadata, is_available
from fathom.ffmpeg import extract_frame


def _read_tag(file: Path, tag: str) -> str:
    """Return the value of `tag` from `file` via exiftool, or empty string if absent."""
    result = subprocess.run(
        [EXIFTOOL_BINARY, "-s3", f"-{tag}", str(file)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_is_available_returns_true_on_this_machine() -> None:
    # This test assumes the development environment has exiftool installed
    # (README documents it as a prereq). If you're seeing this fail, run:
    #     brew install exiftool
    assert is_available()


def test_copy_metadata_propagates_create_date(fixtures_dir: Path, tmp_path: Path) -> None:
    """The canonical case: CreateDate from a video lands on the JPG."""
    source = fixtures_dir / "known-exif.mp4"
    # Produce a real JPG (extracted from a different fixture so we know its
    # current EXIF doesn't have CreateDate). exiftool refuses to write to a
    # malformed JPEG, so we can't fake one.
    dest = tmp_path / "out.jpg"
    extract_frame(fixtures_dir / "fish-swim-by.mp4", 1.0, dest)

    expected = _read_tag(source, "CreateDate")
    assert expected, "fixture should have a CreateDate to assert on"

    copy_metadata(source, dest)

    actual = _read_tag(dest, "CreateDate")
    assert actual == expected


def test_copy_metadata_raises_when_source_missing(fixtures_dir: Path, tmp_path: Path) -> None:
    dest = tmp_path / "out.jpg"
    extract_frame(fixtures_dir / "fish-swim-by.mp4", 1.0, dest)
    with pytest.raises(ExtractionError):
        copy_metadata(tmp_path / "does-not-exist.mp4", dest)


def test_copy_metadata_raises_when_dest_missing(fixtures_dir: Path, tmp_path: Path) -> None:
    with pytest.raises(ExtractionError):
        copy_metadata(fixtures_dir / "known-exif.mp4", tmp_path / "missing.jpg")
