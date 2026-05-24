"""Tests for `fathom trash empty` and `fathom clean`."""

from pathlib import Path

from typer.testing import CliRunner

from fathom.cli import app
from fathom.state import list_videos, open_db, record_video

runner = CliRunner()


# --- fathom trash empty ---


def test_trash_empty_when_trash_dir_missing(tmp_path: Path) -> None:
    result = runner.invoke(app, ["trash", "empty", str(tmp_path)])
    assert result.exit_code == 0
    assert "already empty" in result.output


def test_trash_empty_when_trash_dir_exists_but_empty(tmp_path: Path) -> None:
    (tmp_path / ".fathom" / ".trash").mkdir(parents=True)
    result = runner.invoke(app, ["trash", "empty", str(tmp_path)])
    assert result.exit_code == 0
    assert "already empty" in result.output


def test_trash_empty_lists_and_removes_on_yes(tmp_path: Path) -> None:
    trash = tmp_path / ".fathom" / ".trash" / "trip" / "day1"
    trash.mkdir(parents=True)
    file_a = trash / "a_01.jpg"
    file_b = trash / "a_02.jpg"
    file_a.write_bytes(b"\xff\xd8\xff" + b"a")
    file_b.write_bytes(b"\xff\xd8\xff" + b"b")

    result = runner.invoke(app, ["trash", "empty", str(tmp_path)], input="y\n")
    assert result.exit_code == 0
    assert "a_01.jpg" in result.output
    assert "Removed 2 file(s)" in result.output
    assert not file_a.exists()
    assert not file_b.exists()


def test_trash_empty_aborts_on_no(tmp_path: Path) -> None:
    trash = tmp_path / ".fathom" / ".trash"
    trash.mkdir(parents=True)
    file_a = trash / "a.jpg"
    file_a.write_bytes(b"\xff\xd8\xff" + b"a")

    result = runner.invoke(app, ["trash", "empty", str(tmp_path)], input="n\n")
    assert result.exit_code == 0
    assert "Aborted" in result.output
    assert file_a.exists(), "n should leave the trash intact"


# --- fathom clean ---


def test_clean_when_no_state_db(tmp_path: Path) -> None:
    result = runner.invoke(app, ["clean", str(tmp_path)])
    assert result.exit_code == 0
    assert "nothing to clean" in result.output


def test_clean_when_no_stale_rows(tmp_path: Path) -> None:
    # Record a video whose file actually exists.
    (tmp_path / "real.mp4").write_bytes(b"placeholder")
    conn = open_db(tmp_path)
    try:
        record_video(conn, "real.mp4")
    finally:
        conn.close()

    result = runner.invoke(app, ["clean", str(tmp_path)])
    assert result.exit_code == 0
    assert "No stale rows" in result.output


def test_clean_removes_stale_rows_on_yes(tmp_path: Path) -> None:
    # Record three videos; only one exists on disk.
    (tmp_path / "exists.mp4").write_bytes(b"placeholder")
    conn = open_db(tmp_path)
    try:
        record_video(conn, "exists.mp4")
        record_video(conn, "gone.mp4")
        record_video(conn, "trip/missing.mp4")
    finally:
        conn.close()

    result = runner.invoke(app, ["clean", str(tmp_path)], input="y\n")
    assert result.exit_code == 0
    assert "gone.mp4" in result.output
    assert "trip/missing.mp4" in result.output
    assert "Removed 2" in result.output

    conn = open_db(tmp_path)
    try:
        remaining = {v.relative_path for v in list_videos(conn)}
    finally:
        conn.close()
    assert remaining == {"exists.mp4"}


def test_clean_aborts_on_no_keeps_rows(tmp_path: Path) -> None:
    conn = open_db(tmp_path)
    try:
        record_video(conn, "gone.mp4")
    finally:
        conn.close()

    result = runner.invoke(app, ["clean", str(tmp_path)], input="n\n")
    assert result.exit_code == 0
    assert "Aborted" in result.output

    conn = open_db(tmp_path)
    try:
        remaining = {v.relative_path for v in list_videos(conn)}
    finally:
        conn.close()
    assert remaining == {"gone.mp4"}


def test_clean_does_not_touch_jpgs_on_disk(tmp_path: Path) -> None:
    """fathom clean prunes SQLite only; JPGs on disk are out of scope for it."""
    # Set up a JPG that has no corresponding video. The JPG should survive.
    (tmp_path / "orphan_01.jpg").write_bytes(b"\xff\xd8\xff" + b"jpg")
    conn = open_db(tmp_path)
    try:
        record_video(conn, "orphan.mp4")  # row points to a video that doesn't exist
    finally:
        conn.close()

    result = runner.invoke(app, ["clean", str(tmp_path)], input="y\n")
    assert result.exit_code == 0
    # The orphan JPG is still on disk.
    assert (tmp_path / "orphan_01.jpg").is_file()
