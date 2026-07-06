# Authoring the Test Suite — `tests/`

Create the four test modules below plus the study fixture. They mirror Weaver's own test
patterns (`tests/operators/test_*.py`, `tests/compile/test_public_api.py`, the
`tests/compile/fixtures/study/` mini-study) and run via `uv run pytest`
(`testpaths = ["tests"]`, quiet via `addopts = "-q"` — both set in `pyproject.toml`).
The shipped pyright config runs **strict** mode over `tests/` too, so every helper and
test is fully annotated.

The suite covers three layers:

- **Factory unit tests** (`test_operators.py`) — each category's contract, exercised
  through your own factories.
- **StepBuilder tests** (`test_stages.py`) — scan the bundled mini study into a
  `Workspace`, prove it validates (which resolves your external `ref` at validate
  time), then call the builder directly.
- **Surface pinning** (`test_imports.py`) — the blessed `weaver.compile` surface and
  your package's own re-exports.

---

## `tests/__init__.py`

Weaver's test tree is package-style (`tests/__init__.py`, `tests/ml/__init__.py`, …);
mirror it so the suite moves cleanly if it ever grows subdirectories.

**`tests/__init__.py`**

```python
"""Test suite for weaver-foo."""
```

---

## `tests/test_operators.py` — factory unit tests

One test per contract claim in [authoring-operators.md](authoring-operators.md): the
`Operate` state/context threading, `Evaluate`'s exact-keyset rule plus the
calculator short form and `output_fields` multi-output, `Constrain`'s
`do()`/`severity()`/`mode` semantics, and the `Observe` probe.

**`tests/test_operators.py`**

```python
"""Unit tests for the weaver.foo operator factories.

Mirrors weaver's own tests/operators/ patterns: build the operator, exercise
do(), and probe each category's validation contract — exact keysets, arity
detection, Violation / severity / mode semantics.
"""

from __future__ import annotations

from typing import Any, Mapping

import pytest

from weaver.foo.operators import my_in_range, my_probe, my_ratio, my_solver
from weaver.operators.evaluate import Evaluate


class _StubSolver:
    """Minimal stand-in for a real solver class."""

    def __init__(self, **config: Any) -> None:
        self.config = config

    def sample(self, domain: Any) -> list[Any]:
        del domain
        return [self.config.get("size", 0)]


def test_my_solver_returns_operate() -> None:
    """The Operate threads free-form interim state (solver + population)."""
    op = my_solver("solve", solver_class=_StubSolver, config_dict={"size": 3})
    result = op.do({"domain": None}, {})
    assert isinstance(result["solver"], _StubSolver)
    assert result["population"] == [3]


def test_my_solver_merges_context_hyperparams() -> None:
    """Context hyperparams win over the factory's captured config."""
    op = my_solver("solve", solver_class=_StubSolver, config_dict={"size": 3})
    result = op.do({"domain": None}, {"hyperparams": {"size": 9}})
    assert result["population"] == [9]


def test_my_ratio_fills_output_field() -> None:
    op = my_ratio("ratio", numerator="a", denominator="b", output_field="r")
    assert op.do({"a": 6.0, "b": 3.0}, {}) == {"r": 2.0}


def test_evaluate_keyset_must_match_exactly() -> None:
    """Full-form Evaluate: a returned keyset != declared outputs raises ValueError."""

    def _wrong(row: Mapping[str, Any], ctx: Mapping[str, Any]) -> dict[str, Any]:
        del row, ctx
        return {"unexpected": 1.0}

    op = Evaluate("bad", _wrong, output_field="r")
    with pytest.raises(ValueError):
        op.do({}, {})


def test_evaluate_calculator_short_form() -> None:
    """One positional parameter -> calculator style: the scalar is wrapped, not validated."""

    def _calc(row: Mapping[str, Any]) -> float:
        return float(row["a"]) * 2.0

    op = Evaluate("double", _calc, output_field="d")
    assert op.do({"a": 2.0}, {}) == {"d": 4.0}


def test_evaluate_output_fields_multi_output() -> None:
    def _stats(row: Mapping[str, Any], ctx: Mapping[str, Any]) -> dict[str, Any]:
        del ctx
        values = [float(v) for v in row["values"]]
        return {"lo": min(values), "hi": max(values)}

    op = Evaluate("stats", _stats, output_fields=("lo", "hi"))
    assert op.do({"values": [1.0, 5.0]}, {}) == {"lo": 1.0, "hi": 5.0}


def test_my_in_range_pass_fail_and_skip() -> None:
    """do(row): None on pass, Violation on fail, None (skip) when `requires` is absent."""
    op = my_in_range("t", 0.0, 10.0)
    assert op.do({"t": 5.0}) is None
    violation = op.do({"t": 42.0})
    assert violation is not None
    assert violation.field == "t"
    assert op.do({}) is None


def test_my_in_range_severity_sign_convention() -> None:
    """severity: <= 0 satisfied, > 0 violated; 0.0 while `requires` is absent."""
    op = my_in_range("t", 0.0, 10.0)
    assert op.severity({"t": 5.0}) == 0.0
    assert op.severity({"t": 12.0}) == pytest.approx(2.0)
    assert op.severity({}) == 0.0


def test_my_in_range_soft_mode_passes_through() -> None:
    op = my_in_range("t", 0.0, 10.0, mode="soft")
    assert op.mode == "soft"


def test_my_probe_reads_source_field() -> None:
    op = my_probe("probe", source_field="raw", output_field="reading")
    assert op.do({"raw": 7}, {}) == {"reading": 7.0}
```

---

## `tests/test_stages.py` — StepBuilder tests against the study fixture

**The fixture:** copy the complete minimal study from
[study-json-reference.md](study-json-reference.md) §2 **verbatim** into
`tests/fixtures/study/`, preserving the study-relative paths (`system/demo.system.json`
→ `tests/fixtures/study/system/demo.system.json`, and so on). The study files are
defined once, there — do not fork or redefine them.

This mirrors Weaver's own convention (`tests/compile/fixtures/study/` loaded via a
module-level `STUDY` path). Because the fixture's operator `ref` and dotted model-step
`ref` both name `weaver.foo`, `assert_valid` passing **is** the proof that your
installed package resolves at validate time.

**`tests/test_stages.py`**

```python
"""StepBuilder tests against the bundled mini study fixture.

Mirrors weaver's own tests/compile pattern: scan the fixture into a Workspace,
prove it validates (external refs — the operator ref AND the dotted model-step
ref — resolve at validate time), then call the builder directly and exercise
the step it lowers to.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from weaver.compile import Workspace, assert_valid
from weaver.foo.stages import build_foo_stage

STUDY = Path(__file__).parent / "fixtures" / "study"


def test_fixture_study_validates_cleanly() -> None:
    """Zero diagnostics: the wiring points at this installed package."""
    workspace = Workspace.scan(STUDY)
    assert_valid(workspace)


def test_build_foo_stage_lowers_and_runs() -> None:
    workspace = Workspace.scan(STUDY)
    project = workspace.projects["demo"]
    stage = project.stages[1]
    assert stage.op == "foo"

    operator = build_foo_stage(workspace, project, stage)
    assert operator.name == stage.name

    state: dict[str, Any] = {"db": object(), "populate": {"rows": 8}}
    ctx: dict[str, Any] = {"repo_root": str(STUDY), "artifact_dir": str(STUDY / "artifacts")}
    assert operator.do(state, ctx) == {stage.name: "processed"}
```

---

## `tests/test_imports.py` — import & blessed-surface tests

Pins the `weaver.compile` names your package depends on, in **two tiers**, and confirms
your own public surface imports cleanly. It uses `getattr` (not direct imports) so
`ruff` does not flag `F401` unused imports.

**`tests/test_imports.py`**

```python
"""Verify the blessed weaver.compile surface is available.

Mirrors weaver's own test_public_api.py pattern, using getattr to avoid
F401 unused-import warnings.
"""

from __future__ import annotations

import weaver.compile as wc

# Tier 1: the blessed surface external packages pin against — identical to
# Weaver's own guarded contract (tests/compile/test_public_api.py).
_BLESSED_SURFACE = (
    "StepBuilder",
    "Workspace",
    "ProjectNode",
    "StageNode",
    "build_project",
    "build_runtime_model",
    "build_design_registry",
    "lower_objectives",
    "lower_override_registry",
    "lower_ga_params",
    "LowerError",
)

# Tier 2: public in weaver.compile and used by these docs/tests, but NOT part
# of the upstream-guarded contract — expect more churn here.
_COMPILE_EXPORTS_USED = (
    "validate",
    "assert_valid",
    "Diagnostic",
    "SemanticError",
)


def test_blessed_surface_is_public() -> None:
    """Verify both tiers are exported from weaver.compile."""
    for name in _BLESSED_SURFACE + _COMPILE_EXPORTS_USED:
        assert name in wc.__all__, f"{name} missing from weaver.compile.__all__"
        assert getattr(wc, name) is not None, f"{name} exported but None"


def test_foo_package_imports() -> None:
    """Verify the package's own public surface imports cleanly."""
    import weaver.foo as foo

    for name in ("my_solver", "my_ratio", "my_in_range", "my_probe", "build_foo_stage"):
        assert getattr(foo, name) is not None
```

---

## Conventions

- **One test module per source module** (`test_<module>.py`), tests named for the
  contract claim they pin — Weaver's convention throughout its `tests/` tree.
- **Package-style tests** (`tests/__init__.py` everywhere) so the tree can grow
  subdirectories mirroring `src/weaver/foo/` (`tests/operators/`, …). An eventual
  upstreaming then moves them into Weaver's root `tests/<leaf>/` unchanged.
- **When heavy dependencies arrive**, add a dependency-policy guard in the pattern of
  Weaver's `tests/ml/test_dep_policy.py` — a subprocess check that a fresh import of
  your package pulls none of them (the in-process suite would mask it):

  ```python
  _CHECK = '''
  import sys
  import weaver.foo  # noqa: F401
  assert "torch" not in sys.modules, "torch imported at package import time"
  print("DEP_OK")
  '''


  def test_import_pulls_no_heavy_deps() -> None:
      result = subprocess.run([sys.executable, "-c", _CHECK], capture_output=True, text=True, check=True)
      assert "DEP_OK" in result.stdout
  ```

---

## Keeping tests in sync

When you add or rename factories, update the name list in `test_foo_package_imports`
and the re-exports in `src/weaver/foo/__init__.py` together
([AUTHORING_GUIDE.md](AUTHORING_GUIDE.md) §5). When a stage builder's `ref` changes,
update `tests/fixtures/study/system/operators/*.json` (and the source study in
[study-json-reference.md](study-json-reference.md)) with it.
