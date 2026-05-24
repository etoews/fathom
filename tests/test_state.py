"""Tests for the SQLite state module."""

from pathlib import Path

from fathom.state import list_videos, open_db, record_video, state_db_path, state_dir


def test_open_db_creates_directory_and_file(tmp_path: Path) -> None:
    conn = open_db(tmp_path)
    try:
        assert state_dir(tmp_path).is_dir()
        assert state_db_path(tmp_path).is_file()
    finally:
        conn.close()


def test_record_and_list_video(tmp_path: Path) -> None:
    conn = open_db(tmp_path)
    try:
        vid_id = record_video(conn, "trip/dive.mp4")
        assert vid_id > 0
        videos = list_videos(conn)
        assert len(videos) == 1
        assert videos[0].id == vid_id
        assert videos[0].relative_path == "trip/dive.mp4"
        assert videos[0].processed_at  # non-empty timestamp
    finally:
        conn.close()


def test_record_duplicate_path_is_idempotent(tmp_path: Path) -> None:
    conn = open_db(tmp_path)
    try:
        id_1 = record_video(conn, "x.mp4")
        id_2 = record_video(conn, "x.mp4")
        assert id_1 == id_2
        assert len(list_videos(conn)) == 1
    finally:
        conn.close()


def test_list_videos_empty(tmp_path: Path) -> None:
    conn = open_db(tmp_path)
    try:
        assert list_videos(conn) == []
    finally:
        conn.close()


def test_list_videos_sorted_by_relative_path(tmp_path: Path) -> None:
    conn = open_db(tmp_path)
    try:
        record_video(conn, "z.mp4")
        record_video(conn, "a.mp4")
        record_video(conn, "m.mp4")
        paths = [v.relative_path for v in list_videos(conn)]
        assert paths == ["a.mp4", "m.mp4", "z.mp4"]
    finally:
        conn.close()
