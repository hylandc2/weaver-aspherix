# weaver-aspherix

An external Weaver package that wraps the **Aspherix® DEM solver**: operator
factories (`weaver.aspherix.operators`), a compiler stage (`weaver.aspherix.stages`),
and an external orchestrator (`weaver.aspherix.orchestrators`) that assemble an
Aspherix input script (`.asx`) from config and drive the run. It installs under the
shared `weaver.` PEP 420 namespace and requires no changes to weaver-core or
weaver-compile.

The package layers deliberately:

- **Pure `.asx` text** (`render.py`, `run.py`) — block renderers + assembler + a
  case writer and launcher. No Weaver, no Aspherix needed to test.
- **Weaver shapes** (`operators.py`, `orchestrators.py`, `stages.py`) — `build_case`
  (an `Operate` factory), `AspherixRun` (an `Orchestrator`), and `build_aspherix_stage`
  (the `StepBuilder` the compiler resolves from a study's operator JSON `ref`).

Execution is opt-in: by default `AspherixRun` is a dry run that writes the `.asx`
and returns the argv it *would* run. Setting `"execute": true` in the study's
orchestrator JSON launches Aspherix for real, resolving the binary from the
`ASPHERIX_BIN` env var (or `aspherix` on PATH) and, for `nprocs > 1`, the MPI
launcher from `ASPHERIX_MPI_BIN` (or `mpiexec`/`mpirun` on PATH) — machine paths
never live in the committed study JSON. Serial runs (`nprocs: 1`) use no MPI
wrapper.

See [docs/aspherix-dem-guide.md](docs/aspherix-dem-guide.md) for the Aspherix side
(input-script language, run interface, output artifacts, and the Aspherix→Weaver
mapping).

## Install / sync

This package depends on `weaver-core` and `weaver-compile`, which are source-only
(not on PyPI). Their locations are declared in `pyproject.toml` under
`[tool.uv.sources]` (local path for development, or a git URL with a pinned `rev`).
Dev tooling (`pytest`, `ruff`, `pyright`) installs from the `[dependency-groups] dev`
group.

```
uv sync
```

## Verify

```
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

## Wiring into a study repo

Declare an operator JSON whose `ref` is `weaver.aspherix.stages:build_aspherix_stage`,
an orchestrator JSON naming that operator and carrying the DEM `case` (see
`tests/fixtures/study/` for a complete minimal example), and a project stage that
uses it.
