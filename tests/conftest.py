"""Shared pytest fixtures.

The committed test videos live at `tests/fixtures/videos/`. Tests that don't
need real video content use synthetic files in `tmp_path`. Tests that do need
real content copy from the fixtures dir into `tmp_path` to keep each test
isolated.
"""

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "videos"


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to the committed fixture videos directory."""
    return FIXTURES_DIR


@pytest.fixture
def scan_root_with_videos(tmp_path: Path) -> Iterator[Path]:
    """A scan root populated with the real fixture videos (excluding corrupt)."""
    for video in FIXTURES_DIR.glob("*.mp4"):
        if video.name == "corrupt.mp4":
            continue
        shutil.copy(video, tmp_path)
    yield tmp_path


@pytest.fixture
def scan_root_with_nested_videos(tmp_path: Path) -> Iterator[Path]:
    """A scan root with one video nested two folders deep."""
    nested = tmp_path / "trip" / "day1"
    nested.mkdir(parents=True)
    shutil.copy(FIXTURES_DIR / "fish-swim-by.mp4", nested)
    yield tmp_path
