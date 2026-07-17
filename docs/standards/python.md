# Python standards

The conventions every piece of Python in fathom follows. Distilled from the
personal machine-level Python reference (the off-repo `MAC.md` / `PROJECT.md`
notes) and narrowed to what this repo actually is: a single application with a
Typer CLI, a FastAPI review server, and an OpenCV/NumPy frame pipeline.

Where fathom already embodies a rule, this doc points at the file that does it
rather than repeating a template. Where fathom has a gap (CI, pre-commit), the
template is included so the gap can be closed without re-deriving it.

Read this before writing or changing any Python here.

## Stack

Matches `pyproject.toml`. Do not swap a tool without an ADR.

| Purpose | Tool | Notes |
|---|---|---|
| Deps and envs | **uv** | never bare `pip`; `.venv` per project |
| Lint + format | **ruff** | replaces black, isort, flake8, pyupgrade |
| Tests | **pytest** | with `pytest-cov` |
| Type check | **ty** | pre-1.0; mypy is the documented fallback |
| Logging | stdlib `logging` | never `print()` for diagnostics |
| CLI | **Typer** | plus `rich` for terminal output |
| Web | **FastAPI** + **uvicorn** | the `serve` review UI |
| Vision | **OpenCV** + **NumPy** | frame scoring |

Python 3.14, pinned in `.python-version`. `src/` layout. `pyproject.toml` is the
single source of truth. `uv.lock` is committed.

## Daily workflow

All Python runs through uv. Never run bare `pip install`; it is blocked
(`PIP_REQUIRE_VIRTUALENV=1`) and breaks the lockfile contract anyway.

```sh
uv sync                       # install locked deps after a pull
uv add <pkg>                  # runtime dep
uv add --dev <pkg>            # dev dep
uv remove <pkg>               # drop a dep
uv run fathom ...             # run the CLI inside the venv
uv run pytest                 # tests
uv run ruff check --fix       # lint + autofix
uv run ruff format            # format
uv run ty check               # type check
```

Commit `pyproject.toml`, `uv.lock`, and `.python-version`. Gitignore `.venv/`.

## Project layout

The `src/` layout is deliberate: it forces tests to import the *installed*
package, so packaging mistakes surface here rather than on a fresh machine.

- Nothing importable lives outside `src/`. No top-level `__init__.py`.
- `tests/` is not a package. No `__init__.py`; pytest discovers by path.
- Tests mirror the package: `test_scanner.py` covers `scanner.py`, and so on.
- One package per repo.

Current shape is in the README's module layout section. Keep it flat: one module
per responsibility (`scanner`, `ffmpeg`, `analyser`, `events`, `exiftool`,
`state`, `pipeline`, `server`, `cli`), pure logic separated from I/O where it
already is (`events.py` is pure; keep it that way).

## pyproject.toml

Single source of truth for metadata, build, deps, and tool config.

- **Lower-bound pins only** in `[project.dependencies]`: `rich>=15.0.0`, not
  `==`. The exact resolution is `uv.lock`'s job. Pin exactly only for a known
  incompatibility, with a one-line comment saying why.
- Dev deps live in `[dependency-groups].dev` (PEP 735). `uv add --dev` writes
  there.
- Build backend is `hatchling` with `[tool.hatch.build.targets.wheel] packages
  = ["src/fathom"]`.
- The console script is declared once: `fathom = "fathom.cli:app"`. fathom wires
  the Typer app object directly rather than a `main()` shim; that is the one
  intentional divergence from the reference template, and it is fine because
  Typer's app object is callable.

## Ruff

One tool, configured in `[tool.ruff]`. Rule selection is fixed:

```toml
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]
```

`E`/`F` real bugs, `I` import sorting, `UP` syntax modernisation, `B` bugbear,
`SIM` simplify, `RUF` ruff-specific. `line-length = 100`, `target-version =
"py314"`, double quotes.

Per-file ignore: `"tests/**" = ["S101"]` because pytest uses bare `assert`.

In CI, run `ruff format --check` (fails on unformatted code) and `ruff check`
without `--fix`. Locally, use `--fix` and `format`.

## Pytest

Config in `[tool.pytest.ini_options]`:

```toml
testpaths = ["tests"]
addopts = "-ra --strict-markers --strict-config"
filterwarnings = ["error"]
```

- `-ra` summarises every non-passing outcome.
- `--strict-markers` / `--strict-config` turn typos into errors, not silent
  no-ops.
- `filterwarnings = ["error"]` makes warnings fail the suite. Do not loosen this
  to hide a deprecation; fix the call site.

Rules:

- Naming: `test_*.py`, `Test*`, `test_*`. No deviation.
- Fixtures go in `conftest.py` at the nearest common ancestor of the tests that
  use them, not a catch-all root file.
- **Parametrise, do not loop.** A loop hides every failure after the first;
  `@pytest.mark.parametrize` reports each case.
- Structure each test Arrange / Act / Assert, separated by blank lines. More
  than one Act means split the test.
- Coverage on demand: `uv run pytest --cov=fathom --cov-report=term-missing`. No
  coverage gate in CI yet; gating too early trains tests for the metric, not the
  bug.

## ty

**Everything is typed**, `src/` and `tests/` alike. Every function and method
carries a full signature, including `-> None`. Class attributes get annotations,
not just `__init__` parameters. `uv run ty check` runs clean on every commit.

Modern syntax only, no `typing.List` / `Optional`:

```python
def select(frames: list[Frame], max_events: int) -> list[Event] | None: ...
```

- No bare `# type: ignore`; scope it: `# type: ignore[arg-type]`.
- If ty cannot handle a legitimate pattern, swap it for mypy on this repo
  (`uv remove ty && uv add --dev mypy`, replace `[tool.ty]` with `[tool.mypy]`)
  and note the swap. It is a documented escape hatch, recorded in an ADR, not a
  silent workaround.

## Docstrings

**Google style.** Document intent, not mechanics. A docstring restating the
signature is noise. Document instead:

- preconditions the caller must meet,
- what "empty" or "missing" means here,
- which exceptions are raised and when,
- non-obvious side effects (fathom's file-before-DB ordering is exactly this
  kind of thing worth stating).

Every public module, class, and function gets one. Private helpers only when the
*why* is not obvious. One-liners are fine for obvious functions. See
`src/fathom/exceptions.py` and `src/fathom/_logging.py` for the house style.

## Logging

stdlib `logging`, never `print()` for diagnostics. CLI *output* to stdout via
`typer`/`rich` is a separate channel and is fine; diagnostics go to stderr.

- Module-level logger: `logger = logging.getLogger(__name__)`. Never the root
  logger.
- The package installs a `NullHandler` in `src/fathom/__init__.py` so importing
  fathom never emits noise. The application configures logging exactly once, at
  the CLI entry, via `_logging.configure()` (see `src/fathom/_logging.py`).
- Use `%`-style lazy formatting so filtered messages cost nothing:

  ```python
  logger.debug("scored %d frames in %.2fs", len(frames), elapsed)
  ```

- `logger.exception(...)` inside an `except` block to capture the traceback.
- Never log secrets, tokens, or PII. Log identifiers, not contents.

## CLI (Typer)

The CLI is Typer, driven by the type hints already required by the ty section.
It turns those hints into arguments, options, help, and validation.

- Use `Annotated[...]` for arguments and options (the modern Typer style), as
  `src/fathom/cli.py` does.
- `no_args_is_help=True` on every `Typer(...)` so a bare invocation shows help.
- Let Typer validate paths (`exists=`, `file_okay=`, `dir_okay=`) rather than
  re-checking by hand.
- Pair with `rich` for progress and tables to stdout; keep `logging` for stderr
  diagnostics. Do not conflate the two channels.
- Any command that mutates or reprocesses (fathom's `--force`, `trash empty`)
  confirms or is explicit about scope.

## Error handling

- Raise specific exceptions from the project hierarchy in
  `src/fathom/exceptions.py` (`FathomError` base, `ScanError`,
  `ExtractionError`, `StateError`). Callers catch `FathomError` for "anything
  from us" or a subclass for targeted handling.
- **Translate third-party exceptions at the boundary.** Where fathom meets
  ffmpeg, exiftool, or SQLite, catch the library's exception and re-raise a
  `FathomError` subclass `from` the original so the traceback chain survives.
- The pipeline catches *per-video* failures, logs them, and continues; the run
  exits non-zero if any video failed. Keep that contract: one bad video never
  aborts the batch.
- `except: pass` is a bug. If you genuinely swallow, name the exception and leave
  a one-line reason. Never bare `except:`; `except Exception:` at minimum so
  `KeyboardInterrupt` still kills the process.

## Configuration and secrets

fathom has no secrets today and takes all configuration as CLI flags
(`--rate`, `--min-score`, `--max-events`, `--analyser`). That is the right shape
for a local single-user tool; do not add an env/secret layer it does not need.

If configuration ever outgrows flags:

- Build one typed config object once, at the entry point, and pass it down.
  Nothing deep in the call stack reaches into `os.environ`.
- Use `pydantic-settings` with `extra="forbid"` (a typo becomes an error) and
  `SecretStr` for any secret (masked in logs and reprs).
- `.env` is never committed; commit a `.env.example` documenting the contract.
  Production secrets come from the host, not a file.

## Dependency management

```sh
uv add opencv-python                 # runtime
uv add --dev pytest                  # dev
uv lock --upgrade-package rich       # bump one dep
uv lock --upgrade                    # bump everything
uv sync                              # apply to .venv
uv tree                              # inspect the graph
```

Commit a dependency bump as its own single-purpose change, subject like
`deps: upgrade rich to 15.1`.

## Quality gates

Two gates keep `main` green: a local pre-commit hook and CI. fathom has
**neither yet**; both are tracked in `ROADMAP.md`. Run the *same* tools in both
so nothing passes locally and fails in CI.

### Pre-commit (target)

`pre-commit` is a global uv tool, not a project dependency. Install once per
clone: `pre-commit install`.

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0            # keep in sync with the ruff dev dependency
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format

  - repo: local
    hooks:
      - id: ty
        name: ty
        entry: uv run ty check
        language: system
        types: [python]
        pass_filenames: false   # ty checks the whole project

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
      - id: check-merge-conflict
```

Pin every `rev:` and bump deliberately. Keep the `ruff-pre-commit` rev in sync
with the `ruff` dev dependency, or the hook and CI apply different rules. The
hook is a fast gate that can be skipped (`git commit -n`); CI is the enforcer.

### CI (target)

```yaml
# .github/workflows/ci.yml
name: CI
on:
  push:
    branches: [main]
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - name: Set up Python
        run: uv python install        # honours .python-version
      - name: Install dependencies
        run: uv sync --locked
      - name: Ruff lint
        run: uv run ruff check
      - name: Ruff format check
        run: uv run ruff format --check
      - name: ty type check
        run: uv run ty check
      - name: pytest
        run: uv run pytest --cov=fathom --cov-report=term-missing
```

`uv sync --locked` fails if the lockfile is stale. Note that fathom's tests
shell out to real `ffmpeg` and `exiftool`; CI must install both system tools
before the pytest step (or those tests must be marked and skipped in CI). Settle
that when the workflow lands (see `ROADMAP.md` M8).

Pin `astral-sh/setup-uv` to its current major tag and bump intentionally.

## Upgrading Python

Bump when the global default moves, when new syntax or stdlib is needed, or when
the pin nears end-of-life. One project, one commit.

1. `uv python install 3.X` if the interpreter is not already on disk.
2. `uv python pin 3.X` (rewrites `.python-version`).
3. In `pyproject.toml`: `requires-python = ">=3.X"` and `[tool.ruff]
   target-version = "py3X"`. Without the ruff bump, the `UP` autofixes in
   step 5 will not fire.
4. `rm -rf .venv && uv sync`.
5. `uv run ruff check --select UP --fix`, then review the diff.
6. Run every check: `ruff check`, `ruff format --check`, `ty check`, `pytest`.
7. Commit as a single-purpose `python: upgrade to 3.X`, bundling
   `.python-version`, `pyproject.toml`, `uv.lock`, and any edits ruff made. Keep
   feature work out of it.

fathom is an application, so it can move freely; there are no downstream
consumers to break.

## Quick reference

| Command | Purpose |
|---|---|
| `uv sync` | install locked deps into `.venv` |
| `uv sync --locked` | same, but fail if the lockfile is stale (CI) |
| `uv add <pkg>` / `uv add --dev <pkg>` | add runtime / dev dep |
| `uv remove <pkg>` | remove a dep |
| `uv lock --upgrade[-package <pkg>]` | bump all / one dep |
| `uv run fathom ...` | run the CLI in the venv |
| `uv run pytest` | tests |
| `uv run pytest --cov=fathom --cov-report=term-missing` | tests + coverage |
| `uv run ruff check --fix` | lint + autofix |
| `uv run ruff format` | format |
| `uv run ty check` | type check |
| `uv tree` | dependency graph |
| `uv python pin 3.X` | pin the project Python version |
