# fathom Roadmap

Build order, deliverables, and a hands-on artefact at every milestone.

For the domain model, see [CONTEXT.md](CONTEXT.md); for the decisions behind the
shape of v1, see [docs/adr/](docs/adr/). Python conventions live in
[docs/standards/python.md](docs/standards/python.md).

M0 to M7 are complete: v1 ships end-to-end, from scanning a folder of videos to
reviewing and pruning exported JPGs in the browser. Carry-forward notes live
under the most recently completed milestone.

## Contents

| Milestone | Size | Status |
|-----------|------|--------|
| [M0: Design + domain foundation](#m0-design--domain-foundation) | S | ✅ Complete |
| [M1: Skeleton end-to-end](#m1-skeleton-end-to-end) | M | ✅ Complete |
| [M2: Heuristic scoring + top-N](#m2-heuristic-scoring--top-n) | M | ✅ Complete |
| [M3: Event clustering](#m3-event-clustering) | M | ✅ Complete |
| [M4: EXIF preservation](#m4-exif-preservation) | S | ✅ Complete |
| [M5: Delete-to-trash web UI](#m5-delete-to-trash-web-ui) | M | ✅ Complete |
| [M6: Resume + failure handling](#m6-resume--failure-handling) | M | ✅ Complete |
| [M7: Trash management + docs](#m7-trash-management--docs) | S | ✅ Complete |
| [M8: Quality gates](#m8-quality-gates) | M | ⬜ Next |
| [M9: Packaging + distribution](#m9-packaging--distribution) | M | ⬜ Not started |
| [M10: Alternative analysers](#m10-alternative-analysers) | M | ⬜ Not started |
| [M11: Subject detection (v2)](#m11-subject-detection-v2) | L | ⬜ Deferred |

**Sizes:** S = a single session. M = a focused session or two, expect some
debugging. L = several sessions and a real design pass.

**Critical path:** M0 to M7 are done and were sequential. M8 (quality gates) is
the next foundation and unblocks confident work on everything after it. M9 and
M10 are independently orderable. M11 is the v2 leap and depends on the analyser
seam laid down in M2.

---

## M0: Design + domain foundation

**Deliverables**
- [x] `CONTEXT.md` glossary: Frame analyser, Score, Subject (v2+), Frame, Event,
  Scan root, Export, Trash, with an example dialogue pinning the vocabulary.
- [x] ADRs for the load-bearing decisions:
  [0001](docs/adr/0001-heuristic-frame-scoring-not-ml.md) (heuristic, not ML),
  [0002](docs/adr/0002-frame-analyser-swappable-strategy.md) (analyser as
  swappable strategy),
  [0003](docs/adr/0003-jpgs-alongside-videos.md) (JPGs alongside videos,
  `.fathom/` at scan root),
  [0004](docs/adr/0004-two-step-cli-workflow.md) (two-step CLI, not
  server-driven).
- [x] Project scaffold per [docs/standards/python.md](docs/standards/python.md):
  `src/` layout, `pyproject.toml`, `uv.lock`, `.python-version` (3.14), ruff +
  pytest + ty configured.
- [x] Public-domain test fixture videos under `tests/fixtures/videos/`
  (empty water, fish swim-by, multiple events, known EXIF, corrupt).

**Hands-on artefact**
- [x] `uv sync` resolves clean from a fresh checkout; `uv run ruff check`,
  `uv run ty check`, and `uv run pytest` all run.

---

## M1: Skeleton end-to-end

Issue #1. The tracer bullet: one frame from one video, all the way to the
browser, so every seam exists before any of them is good.

**Deliverables**
- [x] `scanner.py` walks a scan root recursively, yielding video paths
  (`.mp4`, `.mov`, `.mts`, `.m4v`), skipping hidden folders and symlinks.
- [x] `ffmpeg.py` subprocess wrappers (sample, extract, probe).
- [x] `state.py` SQLite at `<scan-root>/.fathom/state.db` (WAL mode), `videos`
  and `frames` tables.
- [x] `server.py` FastAPI app rendering the known exports from a template.
- [x] `cli.py` Typer skeleton with `process` and `serve`.

**Hands-on artefact**
- [x] `uv run fathom process <folder>` then `uv run fathom serve <folder>`; open
  http://localhost:8000 and see one extracted frame.

---

## M2: Heuristic scoring + top-N

Issue #2. Replace "grab one frame" with "grab the good ones".

**Deliverables**
- [x] `analyser.py`: `FrameAnalyser` Protocol, the `HeuristicAnalyser`
  implementation, and a name-keyed registry selected by `--analyser`
  (default `heuristic`). See ADR-0002.
- [x] `HeuristicAnalyser` scores each frame as a weighted, normalised sum of
  sharpness (Laplacian variance), edge density (Canny mean), and colour
  variance (HSV saturation stddev). See ADR-0001.
- [x] Top-N selection: keep the highest-scoring frames per video.

**Hands-on artefact**
- [x] Running against the fish swim-by fixture exports frames containing the
  fish; the empty-water fixture exports little or nothing.

---

## M3: Event clustering

Issue #3. Top-N over-samples a single long moment. Cluster instead.

**Deliverables**
- [x] `events.py` (pure, no I/O): drop frames below `--min-score` (default 0.3),
  group the survivors by time adjacency (2.0s gap) into Events, pick the
  highest-scoring Frame per Event.
- [x] Cap at `--max-events` (default 6), ranked by best-Frame Score. Six is a
  ceiling, not a target: one Event yields one Export.
- [x] Pipeline swaps top-N for event clustering; `events.py` stays pure so it is
  unit-testable without ffmpeg.

**Hands-on artefact**
- [x] The multiple-events fixture yields one Export per distinct Event, not one
  per qualifying Frame.

---

## M4: EXIF preservation

Issue #4. An exported JPG must carry the dive's date, time, and GPS.

**Deliverables**
- [x] `exiftool.py` wraps `exiftool -tagsFromFile <video> <jpg>` to propagate all
  metadata from the source video onto the Export.
- [x] Exports named `<video_basename>_NN.jpg`, written alongside the source
  video. See ADR-0003.

**Hands-on artefact**
- [x] Process the known-EXIF fixture; `exiftool <export>.jpg` shows the video's
  date/time and GPS on the JPG.

---

## M5: Delete-to-trash web UI

Issue #5. Reviewing means pruning. Deleting must be reversible.

**Deliverables**
- [x] `server.py`: one section per leaf folder, an anchor table-of-contents, Pico
  CSS, and a hover-revealed trash button per image (inline vanilla JS).
- [x] `DELETE /api/exports?path=<rel>` *moves* the JPG to
  `<scan-root>/.fathom/.trash/<rel>/`, preserving directory structure, returning
  204. Nothing is unlinked.

**Hands-on artefact**
- [x] In the browser, trash an export; it disappears from the page and reappears
  under `.fathom/.trash/` with its relative path intact.

---

## M6: Resume + failure handling

Issue #6. Real runs are interrupted and hit bad files. Make reruns cheap and
failures survivable.

**Deliverables**
- [x] Resume-by-path: reruns skip videos already in the `videos` table; `--force`
  reprocesses everything regardless of state.
- [x] All file operations complete before any SQLite write, so a video that
  crashes mid-process leaves no row and is retried naturally on the next run.
- [x] Per-video failures are caught and logged; a failure summary prints at end
  of run and later videos still process. Exit code 1 if any video failed, 0
  otherwise.
- [x] Terminal progress via `rich.Progress`.

**Hands-on artefact**
- [x] Point a run at a folder containing the corrupt fixture: it logs the
  failure, finishes the healthy videos, and exits non-zero.

---

## M7: Trash management + docs

Issue #7, plus the README expansion.

**Deliverables**
- [x] `fathom trash empty <scan-root>`: purges `.fathom/.trash/` after
  confirmation.
- [x] `fathom clean <scan-root>`: removes SQLite rows whose video file no longer
  exists; never touches JPGs.
- [x] README expanded: table of contents, prereqs (`ffmpeg`, `exiftool`, `uv`),
  architecture, and the `process` pipeline as a mermaid diagram.

**Hands-on artefact**
- [x] Trash an export, run `fathom trash empty`, confirm the prompt, and see
  `.fathom/.trash/` emptied.

### Carry-forward

- **M8**: the pytest suite shells out to real `ffmpeg` and `exiftool`. CI must
  install both system tools, or those tests must be marked and skipped there.
  Decide which when the workflow lands.
- **M8**: `docs/standards/python.md` prescribes the exact pre-commit and CI
  templates. M8 is wiring them in, not designing them.

---

## M8: Quality gates

**Next.** v1 works but nothing stops a regression on `main`. Close the gap
between "passes on my machine" and "passes for anyone".

**Deliverables**
- [ ] `.github/workflows/ci.yml` per the template in
  [docs/standards/python.md](docs/standards/python.md): `uv sync --locked`, ruff
  lint, ruff format check, ty check, pytest. System `ffmpeg` + `exiftool`
  installed in the runner (see M7 carry-forward).
- [ ] `.pre-commit-config.yaml` per the same standard: ruff (check + format), ty
  as a local system hook, the baseline pre-commit-hooks. Pin every `rev:` and
  keep the ruff rev in sync with the ruff dev dependency.
- [ ] CI runs on push to `main` and on every pull request; a red run blocks
  merge.

**Hands-on artefact**
- [ ] Open a PR that breaks formatting or a type: CI goes red before it can
  merge.
- [ ] `pre-commit run --all-files` passes clean on the current tree.

---

## M9: Packaging + distribution

**Deliverables**
- [ ] `uv tool install .` installs `fathom` as a system-wide command; verify it
  runs against a real folder outside the repo.
- [ ] Decide and document the distribution target: `uv tool install` from git is
  enough for a personal tool; only publish to PyPI if others need it. Record the
  decision (an ADR if it is load-bearing).
- [ ] Document the runtime prereqs the wheel cannot carry (`ffmpeg`, `exiftool`)
  at the install boundary, not just the dev README.

**Hands-on artefact**
- [ ] On a second machine (or a clean shell), install fathom and process a folder
  without a checkout of the repo.

---

## M10: Alternative analysers

The `FrameAnalyser` seam (ADR-0002) exists so scoring can improve without a
rewrite. This milestone exercises it for the first time with a second
implementation.

**Deliverables**
- [ ] A second analyser (candidate: motion-aware scoring that rewards subject
  movement between sampled frames), registered under a new `--analyser` name.
- [ ] Shared analyser test harness: run each registered analyser against the
  fixtures and assert the expected relative ranking, so a new analyser proves
  itself against the same bar.
- [ ] Tune or expose the `HeuristicAnalyser` weights if the comparison shows the
  defaults leave frames on the table.

**Hands-on artefact**
- [ ] `uv run fathom process <folder> --analyser motion-aware` produces a
  different, defensibly better selection on a clip where the heuristic
  under-performs.

---

## M11: Subject detection (v2)

**Deferred.** The big leap: an ML-based analyser that produces categorised
Subjects (Wildlife, and later Wreck, Statue, Coral, Plant), not just Scores. The
schema and analyser interface were shaped in v1 to accommodate this without a
redesign (CONTEXT.md; ADR-0001; ADR-0002).

**Deliverables**
- [ ] An ML-based `FrameAnalyser` that emits Subjects: a category, a confidence,
  and a bounding box per detection, alongside the Score.
- [ ] Persist Subjects in SQLite (the `frames` schema already anticipates them;
  confirm or extend).
- [ ] Web UI surfaces the Subject category and confidence per Export, and lets
  the reviewer filter by category.
- [ ] Model choice, licensing, and where inference runs (local only, per the
  single-laptop constraint) recorded in an ADR before any code.

**Hands-on artefact**
- [ ] Process a dive with a turtle and a moray; the exports are tagged
  `wildlife` with plausible confidence, and the UI can filter to just those.
