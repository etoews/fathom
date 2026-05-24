"""Per-video processing pipeline: sample, score, cluster into Events, export.

Composes the primitives in `fathom.ffmpeg`, `fathom.analyser`,
`fathom.events`, `fathom.exiftool`, and `fathom.state` to deliver one
end-to-end behaviour: take a video, produce up to `max_events` JPGs
alongside it with EXIF copied from the source.

Selection: one Frame per Event, up to `max_events` Events per video ranked
by best-Frame Score (see CONTEXT.md / ADR-0001).

Failure semantics: any `ExtractionError` raised during sampling, decoding,
exporting, or metadata copying propagates out without writing to SQLite.
SQLite writes happen only after all failable steps succeed, so a video that
crashed mid-process leaves no row behind for #6's resume logic to falsely
skip on the next run.
"""

import logging
import shutil
import sqlite3
import tempfile
from pathlib import Path

import cv2

from fathom import exiftool, ffmpeg, state
from fathom.analyser import FrameAnalyser, FrameAnalysis
from fathom.events import ScoredFrame, select_top_events
from fathom.exceptions import ExtractionError

logger = logging.getLogger(__name__)


def process_video(
    video: Path,
    scan_root: Path,
    conn: sqlite3.Connection,
    analyser: FrameAnalyser,
    *,
    rate_fps: float,
    max_events: int,
    min_score: float,
) -> int:
    """Process one video end-to-end. Returns the number of JPGs exported."""
    rel = str(video.relative_to(scan_root))

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # All failable work happens before any SQLite writes.
        sampled = ffmpeg.sample_frames(video, rate_fps, tmp)
        if not sampled:
            raise ExtractionError(f"no frames sampled from {video}")

        scored: list[ScoredFrame[Path]] = []
        analyses: list[tuple[float, FrameAnalysis]] = []
        for i, frame_path in enumerate(sampled, start=1):
            timestamp = ffmpeg.timestamp_for_index(i, rate_fps)
            image = cv2.imread(str(frame_path))
            if image is None:
                logger.warning("Could not decode %s; skipping", frame_path)
                continue
            analysis = analyser.analyse(image)
            analyses.append((timestamp, analysis))
            scored.append(
                ScoredFrame(timestamp=timestamp, score=analysis.score, payload=frame_path)
            )

        chosen = select_top_events(
            scored,
            min_score=min_score,
            max_events=max_events,
        )

        # Remove any prior exports for this video, then write the new ones.
        for old in video.parent.glob(f"{video.stem}_*.jpg"):
            old.unlink()
        for rank, frame in enumerate(chosen, start=1):
            dest = video.with_name(f"{video.stem}_{rank:02d}.jpg")
            shutil.copy(frame.payload, dest)
            exiftool.copy_metadata(video, dest)

        # Only now, with all failable work done, commit to SQLite.
        video_id = state.record_video(conn, rel)
        state.clear_frames_for_video(conn, video_id)
        for timestamp, analysis in analyses:
            state.record_frame(conn, video_id, timestamp, analysis)

        logger.debug(
            "%s: sampled %d, exported %d (events)",
            rel,
            len(scored),
            len(chosen),
        )
        return len(chosen)
