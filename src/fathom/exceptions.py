"""Project-specific exception hierarchy.

All exceptions raised by fathom code inherit from `FathomError`. Callers catch
the base for "anything from us" or specific subclasses for targeted handling.
"""


class FathomError(Exception):
    """Base class for all fathom exceptions."""


class ScanError(FathomError):
    """Raised when scanning the filesystem fails in a recoverable way."""


class ExtractionError(FathomError):
    """Raised when ffmpeg or ffprobe cannot read or extract from a video."""


class StateError(FathomError):
    """Raised when SQLite state operations fail."""
