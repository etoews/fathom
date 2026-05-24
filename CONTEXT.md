# fathom

A personal tool for extracting the best frames from a folder of scuba diving videos, with a web UI for reviewing and curating the results. Runs locally on one laptop, against folders of 1-10 videos at 30s-5min each.

## Language

**Frame analyser**:
The swappable strategy that takes a Frame and produces a Score (and optionally richer metadata). v1 ships one implementation, `HeuristicAnalyser`. Future analysers (alternative heuristic mixes, motion-aware scoring, ML-based detectors) implement the same interface and slot in interchangeably. Pick the analyser via CLI flag (`--analyser`); default `heuristic`.

**Score**:
A per-Frame number in [0, 1] produced by the configured Frame analyser. The v1 `HeuristicAnalyser` computes it from sharpness + edge density + colour variance. Used to rank Frames within an Event and to rank Events against each other.

**Subject** (v2+):
A *categorised detection* produced by certain Frame analysers, typically ML-based ones. A Subject has a category (e.g. `wildlife`, `wreck`), a confidence, and a bounding box. v1's `HeuristicAnalyser` produces no Subjects; it produces only Scores. Subjects exist as a forward-looking concept so the SQLite schema and analyser interface accommodate them without redesign.
_Avoid_: Wildlife (too narrow), object (too generic), target (military-flavoured).

**Wildlife** (v2+):
The first anticipated Subject category, to be produced by a future ML-based Frame analyser detecting marine animals (fish, rays, sharks, turtles, octopuses, etc.). Sibling categories anticipated: Wreck, Statue, Coral, Plant. None implemented in v1.

**Frame**:
A single still image sampled from a video at a given timestamp. Frames are scored, then those that clear the Score floor are grouped into Events.

**Scan root**:
The directory the user passes to `fathom process` and `fathom serve`. All relative paths in the SQLite, all Exports, and the `.fathom/` directory (state, trash) are anchored to this root. The same scan root must be passed to both commands for them to see each other's output.

**Event**:
A contiguous span of Frames in the same video that all clear the Score floor. Two Frames are in the same Event if their timestamps differ by less than the event-gap threshold (default 2 seconds). The selection algorithm picks one Frame per Event (the highest-scoring), then takes up to 6 Events per video ranked by their best-Frame Score.

**Export**:
A Frame written to disk as a high-quality JPG, named `<video_basename>_NN.jpg` and placed alongside the source video. EXIF fields (date/time, GPS location, camera metadata) are copied from the source video onto the JPG.

**Trash**:
Soft-delete area at `<scan-root>/.fathom/.trash/`. When the user deletes an Export from the web UI, the file is *moved* there preserving its relative path, not unlinked. The user sweeps trash manually.

## Example dialogue

> **Dev:** When we say "find the best frames," is something actually detecting fish?
>
> **Domain expert:** Not in v1. The current Frame analyser is the `HeuristicAnalyser`: it scores every Frame on three cheap signals (sharpness, edge density, colour variance) and assumes high-scoring frames probably contain *something*: a fish, a coral head, a wreck. Empty blue water scores low because it's smooth, edgeless, and one colour. That's the whole trick.
>
> **Dev:** So we don't have Subjects in v1?
>
> **Domain expert:** Right. Subject is a v2+ concept: a categorised detection that an ML-based Frame analyser would produce. v1 produces only Scores.
>
> **Dev:** What stops me from swapping in a totally different heuristic, say motion-aware scoring?
>
> **Domain expert:** Nothing. That's another `FrameAnalyser` implementation. Write the class, register it, run with `--analyser motion-aware`. The pipeline doesn't care which one it's calling. Same with a future ML analyser that produces Wildlife Subjects: it's a sibling, not a rewrite.
>
> **Dev:** And an Event isn't a single Frame, it's a span?
>
> **Domain expert:** Right. If a turtle drifts through the shot for four seconds at 30fps, that's 120 Frames clearing the Score floor, but one Event. We export the highest-scoring Frame from that Event. If the turtle leaves and a moray appears two minutes later, that's a second Event: different Frame, different Export.
>
> **Dev:** So a 5-minute dive video with one Event yields one Export, not six?
>
> **Domain expert:** Correct. Six is a cap on Events per video, not a target. Up-to-6, never-pad.
