"""Tests for the Frame analyser module."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from fathom import ffmpeg
from fathom.analyser import (
    DEFAULT_WEIGHTS,
    FrameAnalyser,
    FrameAnalysis,
    HeuristicAnalyser,
    available_analysers,
    get_analyser,
)


def _solid_colour(
    h: int = 720, w: int = 1280, bgr: tuple[int, int, int] = (200, 100, 50)
) -> np.ndarray:
    return np.full((h, w, 3), bgr, dtype=np.uint8)


def _random_noise(h: int = 720, w: int = 1280, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)


def test_score_is_in_unit_interval() -> None:
    analyser = HeuristicAnalyser()
    for frame in (_solid_colour(), _random_noise(), _solid_colour(bgr=(0, 0, 0))):
        analysis = analyser.analyse(frame)
        assert 0.0 <= analysis.score <= 1.0


def test_components_are_in_unit_interval() -> None:
    analyser = HeuristicAnalyser()
    analysis = analyser.analyse(_random_noise())
    for axis in ("sharpness", "edges", "colour"):
        assert axis in analysis.components
        assert 0.0 <= analysis.components[axis] <= 1.0


def test_score_is_weighted_sum_of_components() -> None:
    analyser = HeuristicAnalyser()
    analysis = analyser.analyse(_random_noise())
    expected = sum(DEFAULT_WEIGHTS[k] * v for k, v in analysis.components.items())
    assert analysis.score == pytest.approx(expected)


def test_solid_colour_scores_lower_than_noise() -> None:
    """Empty/uniform frames should score lower than textured ones — the heuristic's whole point."""
    analyser = HeuristicAnalyser()
    solid_score = analyser.analyse(_solid_colour()).score
    noise_score = analyser.analyse(_random_noise()).score
    assert solid_score < noise_score


def test_available_analysers_contains_heuristic() -> None:
    assert "heuristic" in available_analysers()


def test_get_analyser_returns_heuristic() -> None:
    analyser = get_analyser("heuristic")
    assert isinstance(analyser, HeuristicAnalyser)


def test_get_analyser_rejects_unknown_name() -> None:
    with pytest.raises(ValueError, match="Unknown analyser"):
        get_analyser("not-a-real-analyser")


def test_heuristic_satisfies_protocol() -> None:
    assert isinstance(HeuristicAnalyser(), FrameAnalyser)


class _FakeAnalyser:
    """Test double: returns a constant Score for every frame."""

    name = "fake"

    def __init__(self, score: float = 0.5) -> None:
        self._score = score

    def analyse(self, frame: np.ndarray) -> FrameAnalysis:
        return FrameAnalysis(score=self._score, components={"sharpness": self._score})


def test_fake_satisfies_protocol() -> None:
    assert isinstance(_FakeAnalyser(), FrameAnalyser)


def test_empty_water_scores_lower_than_fish_swim_by(fixtures_dir: Path, tmp_path: Path) -> None:
    """Real-fixture comparison: a clip with subject content should score higher."""
    analyser = HeuristicAnalyser()
    fish_max = _max_score_for_fixture(
        fixtures_dir / "fish-swim-by.mp4", tmp_path / "fish", analyser
    )
    empty_max = _max_score_for_fixture(
        fixtures_dir / "empty-water.mp4", tmp_path / "empty", analyser
    )
    assert fish_max > empty_max, (
        f"fish-swim-by max ({fish_max:.3f}) should exceed empty-water max ({empty_max:.3f})"
    )


def _max_score_for_fixture(video: Path, workdir: Path, analyser: HeuristicAnalyser) -> float:
    """Sample the video and return the maximum composite Score across all frames."""
    workdir.mkdir(parents=True, exist_ok=True)
    frames = ffmpeg.sample_frames(video, 3.0, workdir)
    assert frames, f"no frames sampled from {video}"
    best = 0.0
    for frame_path in frames:
        image = cv2.imread(str(frame_path))
        if image is None:
            continue
        best = max(best, analyser.analyse(image).score)
    return best
