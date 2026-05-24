"""Tests for the FastAPI review server."""

from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from fathom.cli import app
from fathom.server import create_app

cli_runner = CliRunner()


def _process(scan_root: Path) -> None:
    result = cli_runner.invoke(app, ["process", str(scan_root), "--min-score", "0"])
    assert result.exit_code == 0, result.output


def test_index_returns_200_after_processing(scan_root_with_videos: Path) -> None:
    _process(scan_root_with_videos)
    with TestClient(create_app(scan_root_with_videos)) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")


def test_index_contains_each_video_name(scan_root_with_videos: Path) -> None:
    _process(scan_root_with_videos)
    with TestClient(create_app(scan_root_with_videos)) as client:
        body = client.get("/").text
    for video in scan_root_with_videos.glob("*.mp4"):
        if video.name == "corrupt.mp4":
            continue
        assert video.name in body, f"Expected {video.name} in rendered page"


def test_index_renders_img_tags_for_jpgs(scan_root_with_videos: Path) -> None:
    _process(scan_root_with_videos)
    with TestClient(create_app(scan_root_with_videos)) as client:
        body = client.get("/").text
    assert "<img" in body
    assert "/jpg/" in body


def test_jpg_endpoint_serves_existing_jpg(scan_root_with_videos: Path) -> None:
    _process(scan_root_with_videos)
    sample_jpg = next(scan_root_with_videos.glob("*_01.jpg"))
    rel = sample_jpg.relative_to(scan_root_with_videos)
    with TestClient(create_app(scan_root_with_videos)) as client:
        response = client.get(f"/jpg/{rel}")
        assert response.status_code == 200
        assert response.content[:3] == b"\xff\xd8\xff"


def test_jpg_endpoint_404_for_missing(scan_root_with_videos: Path) -> None:
    _process(scan_root_with_videos)
    with TestClient(create_app(scan_root_with_videos)) as client:
        response = client.get("/jpg/does-not-exist.jpg")
        assert response.status_code == 404


def test_jpg_endpoint_rejects_traversal(scan_root_with_videos: Path) -> None:
    _process(scan_root_with_videos)
    with TestClient(create_app(scan_root_with_videos)) as client:
        # Path traversal attempts should not resolve outside scan_root
        response = client.get("/jpg/../../../etc/passwd")
        assert response.status_code in (400, 404)


def test_jpg_endpoint_rejects_non_jpg(scan_root_with_videos: Path) -> None:
    _process(scan_root_with_videos)
    sample_video = next(scan_root_with_videos.glob("*.mp4"))
    rel = sample_video.relative_to(scan_root_with_videos)
    with TestClient(create_app(scan_root_with_videos)) as client:
        response = client.get(f"/jpg/{rel}")
        assert response.status_code == 404


def test_nested_folder_renders_as_section(scan_root_with_nested_videos: Path) -> None:
    _process(scan_root_with_nested_videos)
    with TestClient(create_app(scan_root_with_nested_videos)) as client:
        body = client.get("/").text
    # The nested folder path should appear in the page as a section header
    assert "trip/day1" in body


def test_index_renders_trash_button_per_image(scan_root_with_videos: Path) -> None:
    _process(scan_root_with_videos)
    with TestClient(create_app(scan_root_with_videos)) as client:
        body = client.get("/").text
    assert 'class="trash-btn"' in body
    assert "/api/exports" in body  # JS calls this endpoint


def test_delete_export_moves_jpg_to_trash(scan_root_with_videos: Path) -> None:
    _process(scan_root_with_videos)
    sample_jpg = next(scan_root_with_videos.glob("*_01.jpg"))
    rel = sample_jpg.relative_to(scan_root_with_videos)

    with TestClient(create_app(scan_root_with_videos)) as client:
        response = client.delete(f"/api/exports?path={rel}")
        assert response.status_code == 204

    assert not sample_jpg.exists()
    trash_dest = scan_root_with_videos / ".fathom" / ".trash" / rel
    assert trash_dest.is_file()
    # Magic bytes survived the move.
    assert trash_dest.read_bytes()[:3] == b"\xff\xd8\xff"


def test_delete_export_preserves_relative_path_for_nested(
    scan_root_with_nested_videos: Path,
) -> None:
    _process(scan_root_with_nested_videos)
    sample_jpg = next((scan_root_with_nested_videos / "trip" / "day1").glob("fish-swim-by_01.jpg"))
    rel = sample_jpg.relative_to(scan_root_with_nested_videos)

    with TestClient(create_app(scan_root_with_nested_videos)) as client:
        response = client.delete(f"/api/exports?path={rel}")
        assert response.status_code == 204

    expected = (
        scan_root_with_nested_videos / ".fathom" / ".trash" / "trip" / "day1" / sample_jpg.name
    )
    assert expected.is_file()


def test_delete_export_404_for_missing_jpg(scan_root_with_videos: Path) -> None:
    _process(scan_root_with_videos)
    with TestClient(create_app(scan_root_with_videos)) as client:
        response = client.delete("/api/exports?path=nonexistent.jpg")
        assert response.status_code == 404


def test_delete_export_rejects_path_traversal(scan_root_with_videos: Path) -> None:
    _process(scan_root_with_videos)
    with TestClient(create_app(scan_root_with_videos)) as client:
        response = client.delete("/api/exports?path=../../../etc/passwd.jpg")
    # 400 expected (path resolves outside scan root). Not 404 because we check
    # the path before checking existence.
    assert response.status_code == 400


def test_delete_export_rejects_non_jpg(scan_root_with_videos: Path) -> None:
    _process(scan_root_with_videos)
    sample_video = next(scan_root_with_videos.glob("*.mp4"))
    rel = sample_video.relative_to(scan_root_with_videos)
    with TestClient(create_app(scan_root_with_videos)) as client:
        response = client.delete(f"/api/exports?path={rel}")
    assert response.status_code == 400
    # And the video must still exist on disk.
    assert sample_video.is_file()


def test_delete_export_refuses_to_delete_from_trash(scan_root_with_videos: Path) -> None:
    _process(scan_root_with_videos)
    sample_jpg = next(scan_root_with_videos.glob("*_01.jpg"))
    rel = sample_jpg.relative_to(scan_root_with_videos)

    # First, trash a file.
    with TestClient(create_app(scan_root_with_videos)) as client:
        first = client.delete(f"/api/exports?path={rel}")
        assert first.status_code == 204
        # Now attempt to delete the trashed file again via .fathom/.trash/ path.
        trash_rel = Path(".fathom") / ".trash" / rel
        second = client.delete(f"/api/exports?path={trash_rel}")
    assert second.status_code == 400


def test_delete_export_failure_does_not_remove_file(scan_root_with_videos: Path) -> None:
    """If the move fails, the original JPG should still exist on disk."""
    _process(scan_root_with_videos)
    sample_jpg = next(scan_root_with_videos.glob("*_01.jpg"))
    with TestClient(create_app(scan_root_with_videos)) as client:
        # A path that resolves outside the scan root → 400, no filesystem change.
        client.delete("/api/exports?path=../escape.jpg")
    assert sample_jpg.exists()
