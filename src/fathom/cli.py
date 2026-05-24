"""Typer CLI entry point.

Two commands: `process` (the extraction pipeline) and `serve` (the review
server). They share the SQLite state at `<scan-root>/.fathom/state.db`.
"""

import contextlib
import logging
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
)

from fathom import _logging, exiftool, scanner, state
from fathom.analyser import available_analysers, get_analyser
from fathom.exceptions import ExtractionError
from fathom.pipeline import process_video
from fathom.server import create_app

logger = logging.getLogger(__name__)

app = typer.Typer(
    no_args_is_help=True,
    help="Pull the best frames from scuba diving videos.",
)

trash_app = typer.Typer(
    no_args_is_help=True,
    help="Manage the .fathom/.trash/ folder.",
)
app.add_typer(trash_app, name="trash")


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
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Reprocess videos even if they're already in the SQLite state.",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Emit DEBUG-level logging.",
        ),
    ] = False,
) -> None:
    """Sample frames, score them, export the top JPGs alongside each video."""
    _logging.configure(level="DEBUG" if verbose else "INFO")
    scan_root = scan_root.resolve()
    logger.info("Scanning %s", scan_root)

    if not exiftool.is_available():
        typer.echo(
            "exiftool not found on PATH. Install with: brew install exiftool",
            err=True,
        )
        raise typer.Exit(2)

    try:
        analyser = get_analyser(analyser_name)
    except ValueError as e:
        typer.echo(str(e), err=True)
        available = ", ".join(available_analysers())
        typer.echo(f"Available analysers: {available}", err=True)
        raise typer.Exit(2) from None

    console = Console(stderr=True)
    conn = state.open_db(scan_root)
    try:
        already_processed = {v.relative_path for v in state.list_videos(conn)}
        all_videos = list(scanner.find_videos(scan_root))
        to_process = [
            v for v in all_videos if force or str(v.relative_to(scan_root)) not in already_processed
        ]
        skipped = len(all_videos) - len(to_process)
        if skipped:
            logger.info("Skipping %d already-processed video(s); --force to override", skipped)

        processed = 0
        total_exports = 0
        failures: list[tuple[str, str]] = []

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=False,
        ) as progress:
            task = progress.add_task("Processing", total=len(to_process))
            for video in to_process:
                rel = str(video.relative_to(scan_root))
                progress.update(task, description=rel)
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
                except ExtractionError as e:
                    failures.append((rel, str(e)))
                    logger.error("Failed on %s: %s", rel, e)
                progress.update(task, advance=1)

        console.print(
            f"Processed {processed} video(s), {total_exports} export(s), "
            f"{len(failures)} failure(s), {skipped} skipped"
        )
        if failures:
            console.print("Failures:", style="bold red")
            for rel, err in failures:
                console.print(f"  {rel}: {err}", style="red")
            raise typer.Exit(1)
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


@trash_app.command("empty")
def trash_empty(
    scan_root: Annotated[
        Path,
        typer.Argument(
            help="The scan root whose .fathom/.trash/ should be emptied.",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ],
) -> None:
    """Permanently delete the contents of <scan-root>/.fathom/.trash/."""
    scan_root = scan_root.resolve()
    trash_dir = state.state_dir(scan_root) / ".trash"

    if not trash_dir.is_dir():
        typer.echo("Trash is already empty.")
        return

    files = [p for p in trash_dir.rglob("*") if p.is_file()]
    if not files:
        typer.echo("Trash is already empty.")
        return

    typer.echo(f"{len(files)} file(s) under {trash_dir}:")
    for f in files:
        typer.echo(f"  {f.relative_to(trash_dir)}")
    if not typer.confirm("Permanently delete all of these?", default=False):
        typer.echo("Aborted; trash left intact.")
        return

    for f in files:
        f.unlink()
    # Remove now-empty subdirectories.
    for sub in sorted(
        (p for p in trash_dir.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        with contextlib.suppress(OSError):
            sub.rmdir()
    typer.echo(f"Removed {len(files)} file(s).")


@app.command()
def clean(
    scan_root: Annotated[
        Path,
        typer.Argument(
            help="The scan root whose SQLite to prune.",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ],
) -> None:
    """Remove SQLite rows for videos that no longer exist on disk.

    Does NOT delete any JPGs or video files — only prunes the state DB.
    """
    scan_root = scan_root.resolve()
    db_path = state.state_db_path(scan_root)
    if not db_path.exists():
        typer.echo(f"No state DB at {db_path}; nothing to clean.")
        return

    conn = state.open_db(scan_root)
    try:
        all_videos = state.list_videos(conn)
        stale = [v for v in all_videos if not (scan_root / v.relative_path).exists()]
        if not stale:
            typer.echo(f"No stale rows ({len(all_videos)} video row(s) all have files on disk).")
            return

        typer.echo(f"{len(stale)} stale row(s):")
        for v in stale:
            typer.echo(f"  {v.relative_path}")
        if not typer.confirm(
            "Remove these rows (and their frames) from the state DB?", default=False
        ):
            typer.echo("Aborted; SQLite left intact.")
            return

        removed = state.delete_videos(conn, [v.id for v in stale])
        typer.echo(f"Removed {removed} video row(s).")
    finally:
        conn.close()
