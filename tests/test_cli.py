"""Integration tests for the CLI `process` command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from fathom.cli import app
from fathom.state import list_videos, open_db

runner = CliRunner()


def _process(scan_root: Path, *extra: str) -> None:
    """Run `fathom process` with the floor pinned low so tests get deterministic exports."""
    args = ["process", str(scan_root), "--min-score", "0"]
    args.extend(extra)
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output


def test_process_creates_jpgs_for_each_video(scan_root_with_videos: Path) -> None:
    _process(scan_root_with_videos)

    videos = [v for v in scan_root_with_videos.glob("*.mp4") if v.name != "corrupt.mp4"]
    for video in videos:
        exports = sorted(scan_root_with_videos.glob(f"{video.stem}_*.jpg"))
        assert 1 <= len(exports) <= 6, f"{video.name} produced {len(exports)} exports"
        for jpg in exports:
            assert jpg.read_bytes()[:3] == b"\xff\xd8\xff"


def test_process_creates_state_db(scan_root_with_videos: Path) -> None:
    _process(scan_root_with_videos)
    state_db = scan_root_with_videos / ".fathom" / "state.db"
    assert state_db.is_file()


def test_process_records_each_video_in_sqlite(scan_root_with_videos: Path) -> None:
    _process(scan_root_with_videos)
    conn = open_db(scan_root_with_videos)
    try:
        videos = list_videos(conn)
    finally:
        conn.close()
    expected = {v.name for v in scan_root_with_videos.glob("*.mp4") if v.name != "corrupt.mp4"}
    assert {v.relative_path for v in videos} == expected


def test_process_skips_hidden_folders(scan_root_with_videos: Path) -> None:
    hidden = scan_root_with_videos / ".secret"
    hidden.mkdir()
    (hidden / "secret.mp4").write_bytes(b"placeholder")

    _process(scan_root_with_videos)
    conn = open_db(scan_root_with_videos)
    try:
        paths = {v.relative_path for v in list_videos(conn)}
    finally:
        conn.close()
    assert not any(p.startswith(".secret/") for p in paths)


def test_process_handles_nested_videos(scan_root_with_nested_videos: Path) -> None:
    _process(scan_root_with_nested_videos)
    nested_exports = sorted(
        (scan_root_with_nested_videos / "trip" / "day1").glob("fish-swim-by_*.jpg")
    )
    assert nested_exports, "expected at least one export under trip/day1/"


def test_process_max_events_caps_exports(scan_root_with_videos: Path) -> None:
    _process(scan_root_with_videos, "--max-events", "2")
    videos = [v for v in scan_root_with_videos.glob("*.mp4") if v.name != "corrupt.mp4"]
    for video in videos:
        exports = list(scan_root_with_videos.glob(f"{video.stem}_*.jpg"))
        assert len(exports) <= 2, f"{video.name} produced {len(exports)} exports above cap"


def test_process_rejects_unknown_analyser(scan_root_with_videos: Path) -> None:
    result = runner.invoke(
        app,
        ["process", str(scan_root_with_videos), "--analyser", "not-real"],
    )
    assert result.exit_code != 0
    assert "Unknown analyser" in result.output or "Unknown analyser" in (result.stderr or "")


def test_process_accepts_heuristic_analyser_explicitly(scan_root_with_videos: Path) -> None:
    result = runner.invoke(
        app,
        ["process", str(scan_root_with_videos), "--analyser", "heuristic", "--min-score", "0"],
    )
    assert result.exit_code == 0, result.output


def test_serve_refuses_when_state_db_missing(tmp_path: Path) -> None:
    result = runner.invoke(app, ["serve", str(tmp_path)])
    assert result.exit_code == 1
    assert "No state DB" in result.output or "No state DB" in (result.stderr or "")


def test_process_aborts_when_exiftool_missing(
    monkeypatch: pytest.MonkeyPatch, scan_root_with_videos: Path
) -> None:
    monkeypatch.setattr("fathom.exiftool.shutil.which", lambda _name: None)
    result = runner.invoke(app, ["process", str(scan_root_with_videos), "--min-score", "0"])
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    assert "exiftool" in combined
    assert "brew install exiftool" in combined
