"""Typer CLI entry point.

Two commands: `process` (the extraction pipeline) and `serve` (the review
server). They share the SQLite state at `<scan-root>/.fathom/state.db`.
"""

import logging
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from fathom import _logging, ffmpeg, scanner, state
from fathom.exceptions import ExtractionError
from fathom.server import create_app

logger = logging.getLogger(__name__)

app = typer.Typer(
    no_args_is_help=True,
    help="Pull the best frames from scuba diving videos.",
)


@app.command()
def process(
    scan_root: Annotated[
        Path,
        typer.Argument(
            help="Folder to scan for videos.",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ],
) -> None:
    """Extract one middle frame per video into JPGs alongside each video."""
    _logging.configure()
    scan_root = scan_root.resolve()
    logger.info("Scanning %s", scan_root)

    conn = state.open_db(scan_root)
    try:
        processed = 0
        failed = 0
        for video in scanner.find_videos(scan_root):
            rel = str(video.relative_to(scan_root))
            try:
                duration = ffmpeg.get_duration(video)
                midpoint = duration / 2
                output = video.with_name(f"{video.stem}_01.jpg")
                ffmpeg.extract_frame(video, midpoint, output)
                state.record_video(conn, rel)
                processed += 1
                logger.info("Processed %s", rel)
            except ExtractionError as e:
                failed += 1
                logger.error("Failed on %s: %s", rel, e)
        logger.info("Processed %d, failed %d", processed, failed)
    finally:
        conn.close()


@app.command()
def serve(
    scan_root: Annotated[
        Path,
        typer.Argument(
            help="Folder previously processed.",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ],
    port: Annotated[int, typer.Option(help="Port to listen on.")] = 8000,
) -> None:
    """Start the review web server on localhost."""
    _logging.configure()
    scan_root = scan_root.resolve()
    db_path = state.state_db_path(scan_root)
    if not db_path.exists():
        typer.echo(
            f"No state DB at {db_path}. Run `fathom process {scan_root}` first.",
            err=True,
        )
        raise typer.Exit(1)
    fastapi_app = create_app(scan_root)
    logger.info("Serving %s on http://localhost:%d", scan_root, port)
    uvicorn.run(fastapi_app, host="127.0.0.1", port=port, log_level="info")
