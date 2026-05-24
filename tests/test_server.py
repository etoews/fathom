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
