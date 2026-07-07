# weaver-aspherix

An external Weaver package that wraps the **Aspherix® DEM solver**: operator
factories (`weaver.aspherix.operators`), a compiler stage (`weaver.aspherix.stages`),
and an external orchestrator (`weaver.aspherix.orchestrators`) that assemble an
Aspherix input script (`.asx`) from config and drive the run. It installs under the
shared `weaver.` PEP 420 namespace and requires no changes to weaver-core or
weaver-compile.

The package layers deliberately:

- **Pure `.asx` text** (`render.py`, `run.py`) — block renderers + assembler + a
  case writer and dry-run `mpirun` launcher. No Weaver, no Aspherix needed to test.
- **Weaver shapes** (`operators.py`, `orchestrators.py`, `stages.py`) — `build_case`
  (an `Operate` factory), `AspherixRun` (an `Orchestrator`), and `build_aspherix_stage`
  (the `StepBuilder` the compiler resolves from a study's operator JSON `ref`).

See [docs/aspherix-dem-guide.md](docs/aspherix-dem-guide.md) for the Aspherix side
(input-script language, run interface, output artifacts, and the Aspherix→Weaver
mapping).

## Author

The authoring guides carry the Weaver contracts plus a complete reference
implementation. They use the placeholder leaf name `foo` (`weaver.foo`) — read it as
`aspherix` (`weaver.aspherix`) here:

- Start here: [docs/AUTHORING_GUIDE.md](docs/AUTHORING_GUIDE.md)
- Operator factories (`operators.py`): [docs/authoring-operators.md](docs/authoring-operators.md)
- Compiler stages / StepBuilders (`stages.py`) and external orchestrators (`orchestrators.py`): [docs/authoring-stages.md](docs/authoring-stages.md)
- Model-step functions (`physics.py`): [docs/authoring-models.md](docs/authoring-models.md)
- Tests (`tests/`): [docs/authoring-tests.md](docs/authoring-tests.md)
- Study-repo JSON grammar, minimal study, and the validate phase: [docs/study-json-reference.md](docs/study-json-reference.md)
- Package profile to fill in: [docs/PROFILE.md](docs/PROFILE.md)

NEVER create `src/weaver/__init__.py` — `weaver` is a PEP 420 namespace.

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
uses it. [docs/AUTHORING_GUIDE.md](docs/AUTHORING_GUIDE.md) §8 covers the JSON node
shapes, and [docs/study-json-reference.md](docs/study-json-reference.md) the
validate-phase diagnostics.
