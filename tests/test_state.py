"""Tests for the SQLite state module."""

from pathlib import Path

from fathom.analyser import FrameAnalysis
from fathom.state import (
    clear_frames_for_video,
    list_frames_for_video,
    list_videos,
    open_db,
    record_frame,
    record_video,
    state_db_path,
    state_dir,
)


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


def _heuristic_analysis(score: float) -> FrameAnalysis:
    return FrameAnalysis(
        score=score,
        components={"sharpness": score, "edges": score * 0.5, "colour": score * 0.25},
    )


def test_record_frame_stores_score_and_components(tmp_path: Path) -> None:
    conn = open_db(tmp_path)
    try:
        video_id = record_video(conn, "v.mp4")
        record_frame(conn, video_id, timestamp=0.0, analysis=_heuristic_analysis(0.8))
        frames = list_frames_for_video(conn, video_id)
    finally:
        conn.close()

    assert len(frames) == 1
    frame = frames[0]
    assert frame.score == 0.8
    assert frame.sharpness == 0.8
    assert frame.edges == 0.4
    assert frame.colour == 0.2
    assert frame.timestamp == 0.0
    assert frame.metadata is None


def test_record_frame_persists_metadata_as_json(tmp_path: Path) -> None:
    conn = open_db(tmp_path)
    try:
        video_id = record_video(conn, "v.mp4")
        analysis = FrameAnalysis(score=0.5, metadata={"k": "v", "n": 42})
        record_frame(conn, video_id, timestamp=1.5, analysis=analysis)
        frames = list_frames_for_video(conn, video_id)
    finally:
        conn.close()

    assert frames[0].metadata == {"k": "v", "n": 42}


def test_list_frames_for_video_sorted_by_timestamp(tmp_path: Path) -> None:
    conn = open_db(tmp_path)
    try:
        video_id = record_video(conn, "v.mp4")
        record_frame(conn, video_id, timestamp=2.0, analysis=_heuristic_analysis(0.5))
        record_frame(conn, video_id, timestamp=0.5, analysis=_heuristic_analysis(0.5))
        record_frame(conn, video_id, timestamp=1.0, analysis=_heuristic_analysis(0.5))
        frames = list_frames_for_video(conn, video_id)
    finally:
        conn.close()

    assert [f.timestamp for f in frames] == [0.5, 1.0, 2.0]


def test_clear_frames_for_video_removes_only_that_videos_frames(tmp_path: Path) -> None:
    conn = open_db(tmp_path)
    try:
        vid_a = record_video(conn, "a.mp4")
        vid_b = record_video(conn, "b.mp4")
        record_frame(conn, vid_a, 0.0, _heuristic_analysis(0.5))
        record_frame(conn, vid_a, 1.0, _heuristic_analysis(0.5))
        record_frame(conn, vid_b, 0.0, _heuristic_analysis(0.5))

        removed = clear_frames_for_video(conn, vid_a)
        assert removed == 2
        assert list_frames_for_video(conn, vid_a) == []
        assert len(list_frames_for_video(conn, vid_b)) == 1
    finally:
        conn.close()
