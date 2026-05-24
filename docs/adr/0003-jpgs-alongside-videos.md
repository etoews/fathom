# JPGs alongside videos; `.fathom/` at scan root

Exported JPGs land in the same folder as the source video (`/dives/2024/ningaloo/IMG_1234.mp4` → `/dives/2024/ningaloo/IMG_1234_01.jpg`). SQLite state lives at `<scan-root>/.fathom/state.db`; soft-deleted Exports go to `<scan-root>/.fathom/.trash/<relative-path>/`. The scan tree gets written into.

The two alternatives considered were a separate mirror tree (`fathom process /dives /fathom-out`) and an encapsulated `/dives/.fathom/frames/` tree. Both keep the original folder pristine, but both add friction for the actual export use case: dragging the JPGs into a photo library (Photos, Lightroom, Immich) for keeps. A hidden `.fathom/frames/` is invisible to those tools; a separate output tree means maintaining `--input` / `--output` arg discipline forever. Mixing JPGs with MP4s in the source folder is the cost we pay for the JPGs being where the user naturally looks for them.

## Consequences

- The scanner must filter by extension when listing videos, otherwise it'll see its own JPG output.
- `fathom clean` (purges stale SQLite rows for missing videos) does not touch JPGs on disk. If the user moves a folder, the JPGs come along; SQLite rows go stale until cleaned.
- Source video trees must be writable. Read-only NAS / external drives are not supported in v1.
- The single `.fathom/` at the scan root means `fathom process /dives/2024-australia` and `fathom process /dives` use *different* state databases. Same data, two views. Acceptable for personal use; would be a problem for any multi-user shared-archive scenario (out of scope).
