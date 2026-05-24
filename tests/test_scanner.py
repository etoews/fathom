"""Tests for the video scanner."""

from pathlib import Path

from fathom.scanner import find_videos


def test_finds_video_extensions(tmp_path: Path) -> None:
    (tmp_path / "a.mp4").touch()
    (tmp_path / "b.mov").touch()
    (tmp_path / "c.mts").touch()
    (tmp_path / "d.m4v").touch()
    (tmp_path / "e.txt").touch()
    (tmp_path / "f.jpg").touch()

    found = {p.name for p in find_videos(tmp_path)}
    assert found == {"a.mp4", "b.mov", "c.mts", "d.m4v"}


def test_recurses_into_nested_folders(tmp_path: Path) -> None:
    nested = tmp_path / "2024" / "ningaloo" / "day1"
    nested.mkdir(parents=True)
    (nested / "dive1.mp4").touch()
    (tmp_path / "top-level.mp4").touch()

    found = {p.name for p in find_videos(tmp_path)}
    assert found == {"top-level.mp4", "dive1.mp4"}


def test_skips_hidden_folders(tmp_path: Path) -> None:
    (tmp_path / "visible.mp4").touch()
    hidden = tmp_path / ".fathom"
    hidden.mkdir()
    (hidden / "hidden.mp4").touch()
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "more-hidden.mp4").touch()

    found = {p.name for p in find_videos(tmp_path)}
    assert found == {"visible.mp4"}


def test_skips_non_video_extensions(tmp_path: Path) -> None:
    (tmp_path / "video.mp4").touch()
    (tmp_path / "image.jpg").touch()
    (tmp_path / "doc.pdf").touch()
    (tmp_path / "raw.cr2").touch()

    found = {p.name for p in find_videos(tmp_path)}
    assert found == {"video.mp4"}


def test_does_not_follow_symlinks(tmp_path: Path) -> None:
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    (real_dir / "video.mp4").touch()

    link_dir = tmp_path / "link"
    link_dir.symlink_to(real_dir)

    found = {str(p.relative_to(tmp_path)) for p in find_videos(tmp_path)}
    assert "real/video.mp4" in found
    assert "link/video.mp4" not in found


def test_empty_root_yields_nothing(tmp_path: Path) -> None:
    assert list(find_videos(tmp_path)) == []


def test_extensions_are_case_insensitive(tmp_path: Path) -> None:
    (tmp_path / "upper.MP4").touch()
    (tmp_path / "mixed.MoV").touch()

    found = {p.name for p in find_videos(tmp_path)}
    assert found == {"upper.MP4", "mixed.MoV"}
