"""SQLite state management.

The state DB lives at `<scan-root>/.fathom/state.db`. v1 schema has a single
`videos` table; later issues add `frames` (per-frame scores) and may add
others.
"""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

STATE_DIR_NAME = ".fathom"
STATE_DB_NAME = "state.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    relative_path TEXT UNIQUE NOT NULL,
    processed_at TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class VideoRow:
    """A row from the `videos` table."""

    id: int
    relative_path: str
    processed_at: str


def state_dir(scan_root: Path) -> Path:
    """Path to the `.fathom/` directory under `scan_root`."""
    return scan_root / STATE_DIR_NAME


def state_db_path(scan_root: Path) -> Path:
    """Path to the SQLite state DB file under `scan_root`."""
    return state_dir(scan_root) / STATE_DB_NAME


def open_db(scan_root: Path) -> sqlite3.Connection:
    """Open (creating if needed) the SQLite state DB.

    Creates the `.fathom/` directory and applies the schema. WAL mode enabled
    so future `serve` can read concurrently while `process` writes.
    """
    state_dir(scan_root).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(state_db_path(scan_root))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(_SCHEMA)
    return conn


def record_video(conn: sqlite3.Connection, relative_path: str) -> int:
    """Upsert a video row by `relative_path`, returning its id.

    If the path is already recorded, returns the existing id without modifying
    the row. v1 semantics; re-run skip logic and `--force` arrive in issue #6.
    """
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
