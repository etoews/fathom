"""FastAPI app for serving the review page.

Reads from SQLite to know which videos exist, walks the filesystem to find
their corresponding exported JPGs, and renders one section per leaf folder.
"""

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from fathom import state

TEMPLATES_DIR = Path(__file__).parent / "templates"


@dataclass(frozen=True)
class VideoView:
    """View model: one video and its exported JPGs."""

    basename: str
    jpgs: list[str]


@dataclass(frozen=True)
class FolderView:
    """View model: one leaf folder and the videos in it."""

    path: str
    anchor: str
    videos: list[VideoView]


def _slugify(path: str) -> str:
    """Produce an HTML id-safe slug from a folder path."""
    return path.replace("/", "-").replace(" ", "-") or "root"


def _gather(scan_root: Path) -> list[FolderView]:
    """Build the folder/video/jpg tree from SQLite plus filesystem scan."""
    conn = state.open_db(scan_root)
    try:
        videos = state.list_videos(conn)
    finally:
        conn.close()

    by_folder: dict[str, list[VideoView]] = defaultdict(list)
    for video in videos:
        rel_path = Path(video.relative_path)
        folder = str(rel_path.parent) if str(rel_path.parent) != "." else ""
        basename = rel_path.stem

        video_dir = scan_root / rel_path.parent
        jpgs: list[str] = []
        if video_dir.is_dir():
            for jpg in sorted(video_dir.glob(f"{basename}_*.jpg")):
                jpgs.append(str(jpg.relative_to(scan_root)))

        by_folder[folder].append(VideoView(basename=rel_path.name, jpgs=jpgs))

    return [
        FolderView(
            path=folder or "(root)",
            anchor=_slugify(folder),
            videos=by_folder[folder],
        )
        for folder in sorted(by_folder)
    ]


def create_app(scan_root: Path) -> FastAPI:
    """Construct a FastAPI app rooted at `scan_root`."""
    fastapi_app = FastAPI(title="fathom")
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(),
    )
    resolved_root = scan_root.resolve()

    @fastapi_app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        folders = _gather(resolved_root)
        template = env.get_template("index.html")
        return HTMLResponse(template.render(folders=folders))

    @fastapi_app.get("/jpg/{path:path}")
    def jpg(path: str) -> FileResponse:
        target = (resolved_root / path).resolve()
        if not target.is_relative_to(resolved_root):
            raise HTTPException(status_code=400, detail="Invalid path")
        if not target.is_file() or target.suffix.lower() != ".jpg":
            raise HTTPException(status_code=404)
        return FileResponse(target)

    return fastapi_app
