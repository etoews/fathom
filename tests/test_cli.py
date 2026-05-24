"""Integration tests for the CLI `process` command."""

from pathlib import Path

from typer.testing import CliRunner

from fathom.cli import app
from fathom.state import list_videos, open_db

runner = CliRunner()


def test_process_creates_jpgs_for_each_video(scan_root_with_videos: Path) -> None:
    result = runner.invoke(app, ["process", str(scan_root_with_videos)])
    assert result.exit_code == 0, result.output

    videos = [v for v in scan_root_with_videos.glob("*.mp4") if v.name != "corrupt.mp4"]
    for video in videos:
        expected_jpg = video.with_name(f"{video.stem}_01.jpg")
        assert expected_jpg.is_file(), f"Missing {expected_jpg}"
        assert expected_jpg.read_bytes()[:3] == b"\xff\xd8\xff"


def test_process_creates_state_db(scan_root_with_videos: Path) -> None:
    runner.invoke(app, ["process", str(scan_root_with_videos)])
    state_db = scan_root_with_videos / ".fathom" / "state.db"
    assert state_db.is_file()


def test_process_records_each_video_in_sqlite(scan_root_with_videos: Path) -> None:
    runner.invoke(app, ["process", str(scan_root_with_videos)])
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

    runner.invoke(app, ["process", str(scan_root_with_videos)])
    conn = open_db(scan_root_with_videos)
    try:
        paths = {v.relative_path for v in list_videos(conn)}
    finally:
        conn.close()
    assert not any(p.startswith(".secret/") for p in paths)


def test_process_handles_nested_videos(scan_root_with_nested_videos: Path) -> None:
    result = runner.invoke(app, ["process", str(scan_root_with_nested_videos)])
    assert result.exit_code == 0
    nested_jpg = scan_root_with_nested_videos / "trip" / "day1" / "fish-swim-by_01.jpg"
    assert nested_jpg.is_file()


def test_serve_refuses_when_state_db_missing(tmp_path: Path) -> None:
    result = runner.invoke(app, ["serve", str(tmp_path)])
    assert result.exit_code == 1
    assert "No state DB" in result.output or "No state DB" in (result.stderr or "")
