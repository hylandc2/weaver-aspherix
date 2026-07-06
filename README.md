# weaver-foo

Template for an external Weaver package: custom operator factories
(`weaver.foo.operators`), compiler stages (`weaver.foo.stages`), and optional
model-step functions (`weaver.foo.physics`). The package you author installs under the
shared `weaver.` PEP 420 namespace and requires no changes to weaver-core or
weaver-compile.

> **This is a template repository** for authoring external Weaver packages. It ships
> the project configuration (`pyproject.toml`, `.gitignore`) and documentation; you
> author the Python modules following the guides in [docs/](docs/). Start with
> [docs/AUTHORING_GUIDE.md](docs/AUTHORING_GUIDE.md): rename `foo` / `weaver-foo` /
> `weaver.foo` throughout to your real package name (must NOT be a reserved name — see
> the guide's §3), and fill in your Weaver source location in `pyproject.toml`.

## Author

Each guide contains the contracts plus a complete reference implementation:

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
`[tool.uv.sources]` (git URL with a pinned `rev`, or local path). Dev tooling
(`pytest`, `ruff`, `pyright`) installs from the `[dependency-groups] dev` group.

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

Declare an operator JSON whose `ref` is `weaver.foo.stages:build_foo_stage`,
an orchestrator JSON naming that operator, and a project stage that uses it.
See [docs/AUTHORING_GUIDE.md](docs/AUTHORING_GUIDE.md) §8 for the exact JSON, and
[docs/study-json-reference.md](docs/study-json-reference.md) for a complete minimal
study repo and the validate-phase diagnostics.
