"""Frame analysis: takes a Frame, returns a Score (with optional richer metadata).

v1 ships one implementation: `HeuristicAnalyser` (sharpness + edge density +
colour variance). The Protocol shape supports future ML-based analysers as
sibling implementations — see ADR-0002 in docs/adr/.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import cv2
import numpy as np


@dataclass(frozen=True)
class FrameAnalysis:
    """Output of one Frame analyser call.

    `score` is the composite Score in [0, 1]. `components` holds the per-axis
    breakdown for heuristic-style analysers (so re-tuning weights doesn't need
    to re-decode video). `metadata` is a free-form dict reserved for richer
    analyser outputs (bounding boxes, category labels, ML confidences).
    """

    score: float
    components: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class FrameAnalyser(Protocol):
    """Score a single video frame.

    Implementations expose a `name` (registry key) and an `analyse(frame)`
    method. `frame` is a BGR-ordered uint8 ndarray as returned by `cv2.imread`.
    """

    name: str

    def analyse(self, frame: np.ndarray) -> FrameAnalysis: ...


# --- HeuristicAnalyser ---

# Calibration scales for normalising each component to [0, 1]. Tuned for HD
# footage; the scaling is intentionally saturating (`min(1, ratio)`) so the
# components stay in a comparable range rather than dominating each other.
_SHARPNESS_SCALE = 500.0  # Laplacian variance: ~500+ is "sharp" footage
_EDGE_SCALE = 255.0  # Canny output max value
_COLOUR_SCALE = 64.0  # HSV S-channel stddev: ~64 is a vivid scene

DEFAULT_WEIGHTS: dict[str, float] = {
    "sharpness": 0.4,
    "edges": 0.3,
    "colour": 0.3,
}


def _sharpness(frame: np.ndarray) -> float:
    grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    variance = float(cv2.Laplacian(grey, cv2.CV_64F).var())
    return min(1.0, variance / _SHARPNESS_SCALE)


def _edges(frame: np.ndarray) -> float:
    grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(grey, 100, 200)
    return min(1.0, float(edges.mean()) / _EDGE_SCALE)


def _colour(frame: np.ndarray) -> float:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    return min(1.0, float(saturation.std()) / _COLOUR_SCALE)


@dataclass(frozen=True)
class HeuristicAnalyser:
    """v1 Frame analyser: composite of sharpness + edge density + colour variance.

    Each component is normalised to [0, 1] then weighted-summed. Default
    weights live in `DEFAULT_WEIGHTS`. Component values are returned in
    `FrameAnalysis.components` so re-tuning weights (issue #6 with `--force`)
    doesn't need to re-decode video.
    """

    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    name: str = "heuristic"

    def analyse(self, frame: np.ndarray) -> FrameAnalysis:
        sharpness = _sharpness(frame)
        edges = _edges(frame)
        colour = _colour(frame)
        score = (
            self.weights["sharpness"] * sharpness
            + self.weights["edges"] * edges
            + self.weights["colour"] * colour
        )
        return FrameAnalysis(
            score=score,
            components={"sharpness": sharpness, "edges": edges, "colour": colour},
        )


# --- Registry ---

_ANALYSERS: dict[str, Callable[[], FrameAnalyser]] = {
    "heuristic": HeuristicAnalyser,
}


def available_analysers() -> list[str]:
    """Return the sorted list of registry names."""
    return sorted(_ANALYSERS)


def get_analyser(name: str) -> FrameAnalyser:
    """Look up and instantiate an analyser by registry name."""
    if name not in _ANALYSERS:
        available = ", ".join(available_analysers())
        raise ValueError(f"Unknown analyser: {name!r}. Available: {available}")
    return _ANALYSERS[name]()
