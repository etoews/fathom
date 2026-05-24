"""Per-video processing pipeline: sample, score, select, export.

Composes the primitives in `fathom.ffmpeg`, `fathom.analyser`, and
`fathom.state` to deliver one end-to-end behaviour: take a video, produce
up to N JPGs alongside it.

v2 selection (this slice): top-N by raw Score above a floor. Event-based
selection arrives in issue #3 and replaces the ranking step here.
"""

import logging
import shutil
import sqlite3
import tempfile
from pathlib import Path

import cv2

from fathom import ffmpeg, state
from fathom.analyser import FrameAnalyser
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

    The video is sampled at `rate_fps`, every sampled frame is scored by
    `analyser` and recorded in SQLite, frames below `min_score` are dropped,
    and the top `max_events` by Score are written as
    `<basename>_NN.jpg` alongside the source video (NN ranked by Score).

    Existing `<basename>_*.jpg` exports are removed first so re-runs produce
    a clean set of outputs.
    """
    rel = str(video.relative_to(scan_root))

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        sampled = ffmpeg.sample_frames(video, rate_fps, tmp)
        if not sampled:
            raise ExtractionError(f"no frames sampled from {video}")

        video_id = state.record_video(conn, rel)
        state.clear_frames_for_video(conn, video_id)

        scored: list[tuple[float, float, Path]] = []  # (timestamp, score, path)
        for i, frame_path in enumerate(sampled, start=1):
            timestamp = ffmpeg.timestamp_for_index(i, rate_fps)
            image = cv2.imread(str(frame_path))
            if image is None:
                logger.warning("Could not decode %s; skipping", frame_path)
                continue
            analysis = analyser.analyse(image)
            state.record_frame(conn, video_id, timestamp, analysis)
            scored.append((timestamp, analysis.score, frame_path))

        eligible = [t for t in scored if t[1] >= min_score]
        eligible.sort(key=lambda t: t[1], reverse=True)
        chosen = eligible[:max_events]

        # Remove any prior exports for this video, then write the new selection.
        for old in video.parent.glob(f"{video.stem}_*.jpg"):
            old.unlink()
        for rank, (_, _, frame_path) in enumerate(chosen, start=1):
            dest = video.with_name(f"{video.stem}_{rank:02d}.jpg")
            shutil.copy(frame_path, dest)

        logger.debug(
            "%s: sampled %d, eligible %d, exported %d",
            rel,
            len(scored),
            len(eligible),
            len(chosen),
        )
        return len(chosen)
