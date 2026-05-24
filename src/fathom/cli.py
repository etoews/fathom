"""Typer CLI entry point.

Two commands: `process` (the extraction pipeline) and `serve` (the review
server). They share the SQLite state at `<scan-root>/.fathom/state.db`.
"""

import logging
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from fathom import _logging, scanner, state
from fathom.analyser import available_analysers, get_analyser
from fathom.exceptions import ExtractionError
from fathom.pipeline import process_video
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
    analyser_name: Annotated[
        str,
        typer.Option(
            "--analyser",
            help="Frame analyser to use.",
        ),
    ] = "heuristic",
    max_events: Annotated[
        int,
        typer.Option(
            "--max-events",
            min=1,
            help="Maximum JPGs to export per video.",
        ),
    ] = 6,
    min_score: Annotated[
        float,
        typer.Option(
            "--min-score",
            min=0.0,
            max=1.0,
            help="Drop frames whose composite Score falls below this floor.",
        ),
    ] = 0.3,
    rate: Annotated[
        float,
        typer.Option(
            "--rate",
            min=0.1,
            help="Frame sampling rate (frames per second).",
        ),
    ] = 3.0,
) -> None:
    """Sample frames, score them, export the top JPGs alongside each video."""
    _logging.configure()
    scan_root = scan_root.resolve()
    logger.info("Scanning %s", scan_root)

    try:
        analyser = get_analyser(analyser_name)
    except ValueError as e:
        typer.echo(str(e), err=True)
        available = ", ".join(available_analysers())
        typer.echo(f"Available analysers: {available}", err=True)
        raise typer.Exit(2) from None

    conn = state.open_db(scan_root)
    try:
        processed = 0
        failed = 0
        total_exports = 0
        for video in scanner.find_videos(scan_root):
            rel = str(video.relative_to(scan_root))
            try:
                exported = process_video(
                    video,
                    scan_root,
                    conn,
                    analyser,
                    rate_fps=rate,
                    max_events=max_events,
                    min_score=min_score,
                )
                processed += 1
                total_exports += exported
                logger.info("Processed %s (%d exported)", rel, exported)
            except ExtractionError as e:
                failed += 1
                logger.error("Failed on %s: %s", rel, e)
        logger.info(
            "Processed %d videos, %d exports, %d failed",
            processed,
            total_exports,
            failed,
        )
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
