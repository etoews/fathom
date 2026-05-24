"""SQLite state management.

The state DB lives at `<scan-root>/.fathom/state.db`. v1 schema is two tables:

- `videos`  — one row per processed video file
- `frames`  — one row per sampled frame with the Frame analyser's output
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fathom.analyser import FrameAnalysis

STATE_DIR_NAME = ".fathom"
STATE_DB_NAME = "state.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    relative_path TEXT UNIQUE NOT NULL,
    processed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS frames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    timestamp REAL NOT NULL,
    score REAL NOT NULL,
    sharpness REAL,
    edges REAL,
    colour REAL,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_frames_video_id ON frames(video_id);
"""


@dataclass(frozen=True)
class VideoRow:
    """A row from the `videos` table."""

    id: int
    relative_path: str
    processed_at: str


@dataclass(frozen=True)
class FrameRow:
    """A row from the `frames` table."""

    id: int
    video_id: int
    timestamp: float
    score: float
    sharpness: float | None
    edges: float | None
    colour: float | None
    metadata: dict[str, Any] | None


def state_dir(scan_root: Path) -> Path:
    """Path to the `.fathom/` directory under `scan_root`."""
    return scan_root / STATE_DIR_NAME


def state_db_path(scan_root: Path) -> Path:
    """Path to the SQLite state DB file under `scan_root`."""
    return state_dir(scan_root) / STATE_DB_NAME


def open_db(scan_root: Path) -> sqlite3.Connection:
    """Open (creating if needed) the SQLite state DB.

    Creates the `.fathom/` directory, applies the schema, and enables WAL
    mode plus foreign-key enforcement.
    """
    state_dir(scan_root).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(state_db_path(scan_root))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    return conn


def record_video(conn: sqlite3.Connection, relative_path: str) -> int:
    """Upsert a video row by `relative_path`, returning its id."""
    now = datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute(
        "INSERT OR IGNORE INTO videos (relative_path, processed_at) VALUES (?, ?)",
        (relative_path, now),
    )
    conn.commit()
    row = conn.execute("SELECT id FROM videos WHERE relative_path = ?", (relative_path,)).fetchone()
    return int(row["id"])


def list_videos(conn: sqlite3.Connection) -> list[VideoRow]:
    """Return all rows from `videos`, sorted by `relative_path`."""
    rows = conn.execute(
        "SELECT id, relative_path, processed_at FROM videos ORDER BY relative_path"
    ).fetchall()
    return [
        VideoRow(
            id=int(r["id"]),
            relative_path=str(r["relative_path"]),
            processed_at=str(r["processed_at"]),
        )
        for r in rows
    ]


def clear_frames_for_video(conn: sqlite3.Connection, video_id: int) -> int:
    """Delete all frame rows belonging to a video. Returns rows affected."""
    cur = conn.execute("DELETE FROM frames WHERE video_id = ?", (video_id,))
    conn.commit()
    return cur.rowcount


def record_frame(
    conn: sqlite3.Connection,
    video_id: int,
    timestamp: float,
    analysis: FrameAnalysis,
) -> int:
    """Insert a frame row with the analyser's output. Returns the new id.

    The composite Score goes in `score`. Heuristic component breakdown
    (sharpness/edges/colour) populates the dedicated columns when present.
    Anything else from the analyser is serialised into `metadata` (JSON).
    """
    components = analysis.components
    metadata_json = json.dumps(analysis.metadata) if analysis.metadata else None
    cur = conn.execute(
        (
            "INSERT INTO frames"
            " (video_id, timestamp, score, sharpness, edges, colour, metadata)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)"
        ),
        (
            video_id,
            timestamp,
            analysis.score,
            components.get("sharpness"),
            components.get("edges"),
            components.get("colour"),
            metadata_json,
        ),
    )
    conn.commit()
    if cur.lastrowid is None:
        raise RuntimeError("frame insert returned no lastrowid")
    return int(cur.lastrowid)


def list_frames_for_video(conn: sqlite3.Connection, video_id: int) -> list[FrameRow]:
    """Return all frame rows for a video, ordered by timestamp."""
    rows = conn.execute(
        (
            "SELECT id, video_id, timestamp, score, sharpness, edges, colour, metadata"
            " FROM frames WHERE video_id = ? ORDER BY timestamp"
        ),
        (video_id,),
    ).fetchall()
    return [
        FrameRow(
            id=int(r["id"]),
            video_id=int(r["video_id"]),
            timestamp=float(r["timestamp"]),
            score=float(r["score"]),
            sharpness=None if r["sharpness"] is None else float(r["sharpness"]),
            edges=None if r["edges"] is None else float(r["edges"]),
            colour=None if r["colour"] is None else float(r["colour"]),
            metadata=json.loads(r["metadata"]) if r["metadata"] else None,
        )
        for r in rows
    ]
