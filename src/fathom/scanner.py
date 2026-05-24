"""Find videos in a scan tree.

Skips hidden folders (names starting with `.`) and never follows symlinks.
"""

from collections.abc import Iterator
from pathlib import Path

VIDEO_EXTENSIONS: frozenset[str] = frozenset({".mp4", ".mov", ".mts", ".m4v"})


def find_videos(scan_root: Path) -> Iterator[Path]:
    """Yield absolute paths to videos under `scan_root`.

    Order is sorted by name within each directory for deterministic output.
    """
    yield from _walk(scan_root)


def _walk(current: Path) -> Iterator[Path]:
    try:
        entries = sorted(current.iterdir(), key=lambda p: p.name)
    except PermissionError, FileNotFoundError:
        return

    for entry in entries:
        if entry.name.startswith("."):
            continue
        if entry.is_symlink():
            continue
        if entry.is_dir():
            yield from _walk(entry)
        elif entry.suffix.lower() in VIDEO_EXTENSIONS:
            yield entry
