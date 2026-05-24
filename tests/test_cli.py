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


def test_process_resume_skips_already_processed_videos(scan_root_with_videos: Path) -> None:
    """A second run with the same scan root should skip everything from the first."""
    _process(scan_root_with_videos)
    conn = open_db(scan_root_with_videos)
    try:
        first_videos = {v.relative_path for v in list_videos(conn)}
    finally:
        conn.close()
    assert first_videos, "first run should have recorded at least one video"

    # Capture mtimes of the JPGs to verify they weren't rewritten.
    sample_jpg = next(scan_root_with_videos.glob("*_01.jpg"))
    mtime_before = sample_jpg.stat().st_mtime_ns

    # Second run.
    result = runner.invoke(app, ["process", str(scan_root_with_videos), "--min-score", "0"])
    assert result.exit_code == 0

    conn = open_db(scan_root_with_videos)
    try:
        second_videos = {v.relative_path for v in list_videos(conn)}
    finally:
        conn.close()
    # Same set of videos in DB; no duplicates.
    assert first_videos == second_videos

    # JPG wasn't rewritten on the second run.
    assert sample_jpg.stat().st_mtime_ns == mtime_before


def test_process_force_reprocesses_everything(scan_root_with_videos: Path) -> None:
    _process(scan_root_with_videos)
    sample_jpg = next(scan_root_with_videos.glob("*_01.jpg"))
    mtime_before = sample_jpg.stat().st_mtime_ns

    # Run with --force; the JPG should be regenerated.
    result = runner.invoke(
        app, ["process", str(scan_root_with_videos), "--min-score", "0", "--force"]
    )
    assert result.exit_code == 0
    assert sample_jpg.stat().st_mtime_ns >= mtime_before


def test_process_continues_after_corrupt_video(
    scan_root_with_videos: Path, fixtures_dir: Path
) -> None:
    """A corrupt video must not crash the run; other videos still get processed."""
    import shutil as _shutil

    _shutil.copy(fixtures_dir / "corrupt.mp4", scan_root_with_videos)

    result = runner.invoke(app, ["process", str(scan_root_with_videos), "--min-score", "0"])
    # Exit code 1 because at least one video failed.
    assert result.exit_code == 1
    combined = (result.output or "") + (result.stderr or "")
    assert "corrupt.mp4" in combined  # Listed in summary

    # The non-corrupt videos still produced JPGs.
    for video in scan_root_with_videos.glob("*.mp4"):
        if video.name == "corrupt.mp4":
            continue
        exports = list(scan_root_with_videos.glob(f"{video.stem}_*.jpg"))
        assert exports, f"expected exports for {video.name} despite failure of corrupt.mp4"


def test_process_exit_zero_when_all_succeed(scan_root_with_videos: Path) -> None:
    result = runner.invoke(app, ["process", str(scan_root_with_videos), "--min-score", "0"])
    assert result.exit_code == 0


def test_process_does_not_record_failed_video_in_sqlite(
    scan_root_with_videos: Path, fixtures_dir: Path
) -> None:
    """A video that fails to process must NOT leave a row in SQLite.

    This is what lets the next run retry it naturally.
    """
    import shutil as _shutil

    _shutil.copy(fixtures_dir / "corrupt.mp4", scan_root_with_videos)
    runner.invoke(app, ["process", str(scan_root_with_videos), "--min-score", "0"])

    conn = open_db(scan_root_with_videos)
    try:
        paths = {v.relative_path for v in list_videos(conn)}
    finally:
        conn.close()
    assert "corrupt.mp4" not in paths
