# Frame analyser as a swappable strategy

v1 ships exactly one way to score Frames: the `HeuristicAnalyser` (sharpness + edge density + colour variance at 3fps). We could have written this as a free function called directly from the processing pipeline. Instead it sits behind a `FrameAnalyser` Protocol that takes a Frame and returns a Score (plus optional richer metadata via a `metadata` field on the analyser output).

The current frame analysis approach is explicitly *one type* among many credible follow-ups. The user has signalled: tweaked heuristics with different weights, alternative heuristic mixes (e.g. motion-aware scoring that rewards inter-frame difference), and eventually ML-based analysers that produce categorised Subjects (Wildlife, Wreck, Statue, Coral). All of those should be sibling implementations selectable at runtime, not pipeline rewrites.

Cost of the abstraction today: a Protocol declaration, one small dataclass for the output, and a tiny registry/dispatch by name (`--analyser heuristic`). Cost of *not* having it later: every alternative analyser would touch the processing pipeline at every call site. The asymmetric cost is the whole justification, and the user has been explicit enough about future variants that this isn't speculative generalisation.

## Consequences

- Analyser selection is a CLI flag (`fathom process --analyser heuristic`). Default is `heuristic`. New analysers self-register and become valid choices without pipeline edits.
- The SQLite schema includes a JSON `metadata` column on each Frame row, currently empty for `HeuristicAnalyser` but available for future analysers to write per-frame detections (bbox, category, confidence) without a schema migration.
- "Subject" in CONTEXT.md is a v2+ concept tied to richer analyser outputs. v1 produces no Subjects; only Scores. The vocabulary already exists so future code can be named for what it actually does (e.g. `WildlifeMLAnalyser` produces `Subject` instances) without revisiting CONTEXT.md.
- Per-Frame component scores (the heuristic's sharpness/edges/colour breakdown) are stored alongside the composite Score so re-tuning weights with `--force` doesn't need to re-decode video.
