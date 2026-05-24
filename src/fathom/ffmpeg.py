"""Subprocess wrappers for ffmpeg and ffprobe.

Kept deliberately thin so the pipeline can compose these primitives without
inheriting unrelated behaviour.
"""

import subprocess
from pathlib import Path

from fathom.exceptions import ExtractionError


def get_duration(video: Path) -> float:
    """Return the video's duration in seconds via ffprobe.

    Raises:
        ExtractionError: If ffprobe fails or returns no duration.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(video),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise ExtractionError(f"ffprobe failed on {video}: {e.stderr.strip()}") from e

    stdout = result.stdout.strip()
    if not stdout:
        raise ExtractionError(f"ffprobe returned no duration for {video}")
    try:
        return float(stdout)
    except ValueError as e:
        raise ExtractionError(
            f"ffprobe returned non-numeric duration for {video}: {stdout!r}"
        ) from e


def extract_frame(
    video: Path,
    timestamp_seconds: float,
    output: Path,
    quality: int = 2,
) -> None:
    """Extract a single JPG frame from the video at the given timestamp.

    Args:
        video: Source video file.
        timestamp_seconds: Position within the video to grab.
        output: Destination JPG path. Overwritten if it exists.
        quality: ffmpeg `-q:v` value (1=best, 31=worst). 2 ~ JPEG q92.

    Raises:
        ExtractionError: If ffmpeg fails.
    """
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-ss",
                str(timestamp_seconds),
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-q:v",
                str(quality),
                str(output),
            ],
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="replace").strip()
        raise ExtractionError(f"ffmpeg failed on {video} at {timestamp_seconds}s: {stderr}") from e


def sample_frames(
    video: Path,
    rate_fps: float,
    output_dir: Path,
    quality: int = 2,
) -> list[Path]:
    """Sample frames from `video` at `rate_fps` into `output_dir`.

    Files are written as `frame_NNNNNN.jpg` (zero-padded, 1-indexed) in
    timestamp order. The timestamp of frame N (1-indexed) is approximately
    `(N - 1) / rate_fps` seconds.

    Returns the list of created JPG paths in timestamp order.

    Raises:
        ExtractionError: If ffmpeg fails.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(output_dir / "frame_%06d.jpg")
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(video),
                "-vf",
                f"fps={rate_fps}",
                "-q:v",
                str(quality),
                pattern,
            ],
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="replace").strip()
        raise ExtractionError(f"ffmpeg fps sampling failed on {video}: {stderr}") from e

    return sorted(output_dir.glob("frame_*.jpg"))


def timestamp_for_index(index: int, rate_fps: float) -> float:
    """Approximate timestamp (seconds) of the Nth sampled frame at `rate_fps`."""
    return (index - 1) / rate_fps
