"""exiftool subprocess wrapper.

Copies metadata (date/time, GPS, camera identity, codec details) from a
source video onto an exported JPG using `exiftool -tagsFromFile`. exiftool
handles the cross-format quirks (QuickTime atoms in MP4/MOV, custom DJI/GoPro
atoms, EXIF segments in JPG) so our code stays agnostic.

`exiftool` must be on PATH. CLI startup checks `is_available()` and aborts
with a `brew install exiftool` hint if not.
"""

import shutil
import subprocess
from pathlib import Path

from fathom.exceptions import ExtractionError

EXIFTOOL_BINARY = "exiftool"


def is_available() -> bool:
    """Return True if `exiftool` is on PATH."""
    return shutil.which(EXIFTOOL_BINARY) is not None


def copy_metadata(source: Path, dest: Path) -> None:
    """Copy all metadata tags from `source` (e.g. video) onto `dest` (e.g. JPG).

    Uses `exiftool -overwrite_original -tagsFromFile <source> <dest>` which
    overwrites the destination in place (no `_original` backup). The
    destination must already exist; this only writes metadata, not pixels.

    Raises:
        ExtractionError: If exiftool fails.
    """
    try:
        subprocess.run(
            [
                EXIFTOOL_BINARY,
                "-overwrite_original",
                "-tagsFromFile",
                str(source),
                str(dest),
            ],
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="replace").strip()
        raise ExtractionError(
            f"exiftool failed copying metadata from {source} to {dest}: {stderr}"
        ) from e
