# Two-step CLI workflow, not server-driven

`fathom process <scan-root>` does the heavy lifting (frame sampling, scoring, JPG export, EXIF copy). `fathom serve <scan-root>` starts a FastAPI server on localhost that reads the SQLite and renders the review page. They are completely separate processes with completely separate lifetimes.

The alternative was a single `fathom serve` that exposes a "choose folder" picker and a "process" button in the browser, streaming progress over WebSocket / SSE. We rejected it. Processing is slow (minutes to hours for a full archive) and benefits from being detachable: run overnight in a tmux session, run on a different machine over SSH, run while you're away. The server is fast and stateless and you'd want it to start instantly when you open the laptop to review. Coupling them would force a job queue, async progress streaming, and a substantially larger frontend, all significant code for a personal single-laptop tool.

SQLite is the natural handoff between the two: `process` writes per-video and per-frame rows; `serve` reads them. WAL mode allows them to run concurrently if the user wants progress visible during a long run (open the browser while `process` is still going; refresh as videos complete).

## Consequences

- A future "progress in the browser" feature is purely additive: server gains a `GET /api/progress` endpoint that queries SQLite for in-progress videos. No architectural change to `process`.
- Mismatched scan roots are a foot-gun: `fathom serve /wrong/path` will see an empty SQLite and a blank review page. Mitigation: serve refuses to start if `<scan-root>/.fathom/state.db` doesn't exist, with a hint to run `process` first.
- Test seam is clean: `process` is a pure offline pipeline (file → SQLite + JPGs); `serve` is a pure online read layer (SQLite + filesystem → HTML/JSON). Tested independently.
