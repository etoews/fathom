"""Per-video processing pipeline: sample, score, cluster into Events, export.

Composes the primitives in `fathom.ffmpeg`, `fathom.analyser`,
`fathom.events`, and `fathom.state` to deliver one end-to-end behaviour:
take a video, produce up to `max_events` JPGs alongside it.

Selection (from #3 onwards): one Frame per Event, up to `max_events` Events
per video ranked by best-Frame Score. Frames below `min_score` are dropped
before clustering. See CONTEXT.md (Event) and ADR-0001.
"""

import logging
import shutil
import sqlite3
import tempfile
from pathlib import Path

import cv2

from fathom import ffmpeg, state
from fathom.analyser import FrameAnalyser
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
    """Process one video end-to-end. Returns the number of JPGs exported.

    Every sampled Frame is recorded in SQLite regardless of whether it ends
    up exported. The video row is always written, so even a video that
    exports 0 JPGs (no Frames clear the floor) leaves a record that
    re-run logic in #6 can skip on subsequent runs.

    Existing `<basename>_*.jpg` exports for this video are removed first so
    re-runs produce a clean set of outputs.
    """
    rel = str(video.relative_to(scan_root))

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        sampled = ffmpeg.sample_frames(video, rate_fps, tmp)
        if not sampled:
            raise ExtractionError(f"no frames sampled from {video}")

        video_id = state.record_video(conn, rel)
        state.clear_frames_for_video(conn, video_id)

        scored: list[ScoredFrame[Path]] = []
        for i, frame_path in enumerate(sampled, start=1):
            timestamp = ffmpeg.timestamp_for_index(i, rate_fps)
            image = cv2.imread(str(frame_path))
            if image is None:
                logger.warning("Could not decode %s; skipping", frame_path)
                continue
            analysis = analyser.analyse(image)
            state.record_frame(conn, video_id, timestamp, analysis)
            scored.append(
                ScoredFrame(timestamp=timestamp, score=analysis.score, payload=frame_path)
            )

        chosen = select_top_events(
            scored,
            min_score=min_score,
            max_events=max_events,
        )

        # Remove prior exports for this video, then write the new selection.
        for old in video.parent.glob(f"{video.stem}_*.jpg"):
            old.unlink()
        for rank, frame in enumerate(chosen, start=1):
            dest = video.with_name(f"{video.stem}_{rank:02d}.jpg")
            shutil.copy(frame.payload, dest)

        logger.debug(
            "%s: sampled %d, exported %d (events)",
            rel,
            len(scored),
            len(chosen),
        )
        return len(chosen)
