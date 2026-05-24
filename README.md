# fathom

Pulls the best frames from scuba diving videos using cheap heuristics, exports them as JPGs with metadata preserved, and gives you a local web UI to review and prune the results.

## Prereqs

```sh
brew install ffmpeg exiftool
```

## Quick start

```sh
uv sync
uv run fathom process /path/to/videos
uv run fathom serve /path/to/videos
```

Open http://localhost:8000.

- See [CONTEXT.md](CONTEXT.md) for the project's domain vocabulary.
- See [docs/adr/](docs/adr/) for architectural decisions.
