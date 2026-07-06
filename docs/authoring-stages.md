# Authoring Compiler Stages — `stages.py`

A **StepBuilder** is what the compiler resolves from the `ref` string in operator JSON
(e.g. `"weaver.foo.stages:build_foo_stage"`). Create `src/weaver/foo/stages.py`
(substituting your leaf name for `foo`) from the reference builders below; a stage whose
work is a whole coordinated run also gets `src/weaver/foo/orchestrators.py` (see
"External orchestrators"). Re-export your primary builder from
`src/weaver/foo/__init__.py` ([AUTHORING_GUIDE.md](AUTHORING_GUIDE.md) §5) — `ref`
resolution imports the dotted module path directly, so the re-export is curation, not a
requirement. How a study repo declares the `ref` — and what happens when it is wrong —
is covered in [AUTHORING_GUIDE.md](AUTHORING_GUIDE.md) §8; the JSON node shapes live in
[study-json-reference.md](study-json-reference.md); the stage tests live in
[authoring-tests.md](authoring-tests.md).

---

## The StepBuilder contract

- **Type / signature:** a `StepBuilder` is
  `Callable[[Workspace, ProjectNode, StageNode], Operator]`. Your function takes exactly
  `(workspace, project, stage)` and returns an `Operator`.
- **Return idiom:** return `Operate(stage.name, _do, output_field=stage.name)`, where
  `_do(state: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]` returns
  `{stage.name: result}`. **Do not write to `state` directly — return a dict.** An
  `Orchestrate` step with `output_field=stage.name` satisfies the same contract — see
  "External orchestrators".
- **Runtime `state` keys:**
  - `state["db"]` → a `weaver.utils.database.Database` instance.
  - `state[<prior_stage_name>]` → the output of an upstream stage (the keys upstream
    `_do`s returned). In a subset run (`run_stages(..., stages=[...])`) an unselected
    upstream's key is **absent** — the built-ins reload from persisted artifacts in that
    case, so guard with `state.get(...)` if your stage supports subset runs.
- **Runtime `ctx` keys:**
  - `ctx["repo_root"]` → `str`, the study repo root.
  - `ctx["artifact_dir"]` → `str`, the artifact directory.
- **Blessed import line** (top-level only — never reach into `weaver.compile.execute` /
  `.resolve` / other submodules):
  ```python
  from weaver.compile import (
      StepBuilder, Workspace, ProjectNode, StageNode,
      build_project, build_runtime_model, build_design_registry,
      lower_objectives, lower_override_registry, lower_ga_params, LowerError,
  )
  ```
- **Lazy imports:** keep domain/heavy imports inside `_do`. At module level, import only
  the blessed `weaver.compile` surface plus the weaver-core classes and helpers used to
  *build* the returned operator (`weaver.base.operator.Operator`,
  `weaver.operators.operate.Operate`, `weaver.operators.orchestrate.Orchestrate`,
  `weaver.operators.registry.MergeRegistry`, `weaver.utils.database.database_registry`,
  …) — exactly as the built-in builders do.

---

## `build_project`: non-table vs. table-producing stages

**`build_project(workspace, project, stage)`** yields the resolved project
(`.system.name`, `.model.name`, `.seed`, `.registry`, …). It raises a located
`LowerError` unless **all** of the following hold:

- the stage **binds a single `model`**;
- the stage's **orchestrator is declared**;
- **`sampler`** — a **top-level** orchestrator param, *not* inside `population` —
  names a known sampler. It **defaults to `"lhs"`**, the only built-in;
- the orchestrator's **`population` block** carries **`count`**, a **required** int
  `>= 1` (bools are rejected), and optionally **`seed`**, an int defaulting to `0`
  (bools rejected).

Illustrative orchestrator params (shapes are pinned in
[study-json-reference.md](study-json-reference.md)):

```json
{ "name": "pop", "op": "populate", "sampler": "lhs", "population": { "count": 100, "seed": 7 } }
```

- A **non-table stage** (the reference `build_foo_stage` below) must **not** call
  `build_project` — it binds no model and needs no population block, and calling it for
  such a stage raises `LowerError`.
- **Only call `build_project` from a table-producing stage** whose JSON binds a real
  `model` and whose orchestrator carries a valid `population` block.

A **table-producing stage** must also set `produces_table: true` in its operator JSON
and write the `{system}__{model}__{seed}` table — the next section covers who reads it,
and the table-producing variant below covers how to write it.

---

## Consuming upstream output: state vs. tables

Two distinct mechanisms — do not conflate them:

- **State dataflow — the stage-level `"from"` list.** The compiler folds every stage
  over one shared state; each stage's `_do` returns `{stage.name: result}`, which lands
  in state — so a later stage reads an earlier one's **in-memory output** as
  `state[<stage name>]`. The project JSON's stage-level `"from": [...]` declares that
  edge: validate errors if a listed name is not an **earlier** stage, and your builder
  can read the list as `stage.from_`. The state key appears whether or not it is listed —
  `"from"` is the declared, checked dependency, not the transport.
- **Table consumption — the downstream orchestrator param `source.from_stage`.** A stage
  that reads the actual **DB table** (as the built-in `preprocess` does) names its
  producer in its *orchestrator's* params: `"source": {"from_stage": "<stage name>"}`.
  The compiler gates this: the named stage's operator must be **table-producing** — its
  `ref` one of the built-ins `weaver.core:populate` / `weaver.core:run`, **or** the
  operator declares `produces_table: true`. Anything else is a located `LowerError`. The
  table read is `{system}__{model}__{seed}`, computed from the **upstream** stage node —
  which is why a table-producing stage must bind a model and satisfy `build_project`.

---

## `ref` caution: built-in refs are symbolic, yours is an import path

`weaver.core:populate` and `weaver.core:run` are **symbolic keys** in the compiler's
built-in builder table — there is **no `weaver.core` module**; do not model your `ref`
on them. An external `ref` must be a **real dotted import path**
(`weaver.foo.stages:build_foo_stage`): the compiler converts the colon to a dot and
imports it. External refs are imported at **validate time** — the ref-to-builder
resolution runs during the compiler's validate phase for every stage `op` — so a typo'd
`ref` or an uninstalled package fails early as a located `LowerError` diagnostic
(`weaver.compile.assert_valid`, or `weaver validate` where the CLI meta-package is
installed), not mid-run.

---

## Reference module — a non-table stage

The first block carries the module docstring and **every** import the module needs
(including those used by the continued blocks below).

**`src/weaver/foo/stages.py`**

```python
"""External compiler stages for weaver.foo.

A StepBuilder has signature (Workspace, ProjectNode, StageNode) -> Operator and
is resolved by the compiler from an operator JSON `ref` such as
'weaver.foo.stages:build_foo_stage'. Each builder lowers one stage to one fold
step whose `_do(state, ctx)` returns `{stage.name: result}`.

Three builders live here: build_foo_stage (non-table), build_table_source
(table-producing: ensure_table + insert), and build_orchestrated_stage
(constructs a FooSweep orchestrator from grammar params and wraps it via
Orchestrate).
"""

from __future__ import annotations

from typing import Any

from weaver.base.operator import Operator
from weaver.compile import LowerError, ProjectNode, StageNode, Workspace, build_design_registry, build_project
from weaver.foo.orchestrators import FooSweep
from weaver.operators.operate import Operate
from weaver.operators.orchestrate import Orchestrate
from weaver.operators.registry import MergeRegistry
from weaver.utils.database import database_registry

__all__ = ["build_foo_stage", "build_orchestrated_stage", "build_table_source"]


def build_foo_stage(workspace: Workspace, project: ProjectNode, stage: StageNode) -> Operator:
    """StepBuilder resolved from 'weaver.foo.stages:build_foo_stage'.

    Non-table stage: does NOT call build_project (it binds no model and needs no
    population block). Reads upstream stage outputs from `state`.
    """
    del workspace, project

    def _do(state: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        db = state["db"]  # weaver.utils.database.Database
        repo_root = ctx["repo_root"]
        artifact_dir = ctx["artifact_dir"]
        del db, repo_root, artifact_dir  # use as needed

        # Access upstream stage outputs via state[<prior_stage_name>].
        # Stage logic here.
        result = "processed"
        return {stage.name: result}

    return Operate(stage.name, _do, output_field=stage.name, info={"builder": "build_foo_stage", "stage": stage.name})
```

---

## Table-producing variant

Only write this variant if you need to produce a queryable table (and then declare
`produces_table: true` on the operator). Two facts drive its shape, both mirrored from
the built-in `Populate`:

- **`Database.insert` never creates a table.** It executes a plain `INSERT` — it only
  `ALTER`s unknown payload columns into an **existing** table. Inserting into a table
  nothing created fails at runtime, so the stage must call
  `db.ensure_table(table_name=..., registry=...)` **before** the insert loop.
- **The registry passed to `ensure_table` is the full table schema driving creation** —
  one column per Registry variable — and it **must include the database's reserved
  bookkeeping columns**: merge your design registry with `database_registry()` via
  `MergeRegistry` first (`ensure_table` rejects a registry without them). Pass the same
  merged registry to `insert`; a payload column the registry doesn't describe is added
  on the fly, but keep the registry in sync with what you write rather than leaning on
  that.

The **real, keyword-only** `Database.insert` API is
`insert(*, table_name, registry, payload, system_fields=None, status=None,
run_metadata=None)` — there is **no** `unique_by` and no positional form. Obtain the
design registry via `build_design_registry(workspace, model_name)` — it takes the
**model-name string** (e.g. `stage.model`), *not* the project/stage. This sketch shows
the shape — adapt the payload to your model's columns.

**`src/weaver/foo/stages.py`** (continued)

```python
def build_table_source(workspace: Workspace, project: ProjectNode, stage: StageNode) -> Operator:
    """Table-producing StepBuilder. Set produces_table=true in this operator's JSON.

    Writes the {system}__{model}__{seed} table a downstream orchestrator's
    source.from_stage can read. Requires stage.model bound and a valid
    orchestrator population block (build_project enforces both).
    """
    if stage.model is None:
        raise LowerError(f"table stage {stage.name!r} must bind a single 'model'")
    weaver_project = build_project(workspace, project, stage)
    design_registry = build_design_registry(workspace, stage.model)

    def _do(state: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        del ctx
        db = state["db"]
        table_name = f"{weaver_project.system.name}__{weaver_project.model.name}__{weaver_project.seed}"

        # Full table schema = problem variables + reserved bookkeeping columns.
        # insert() alone never creates a table — mirror Populate: ensure_table first.
        table_registry = MergeRegistry().do([design_registry, database_registry()], {})
        db.ensure_table(table_name=table_name, registry=table_registry)

        for i in range(10):
            db.insert(
                table_name=table_name,
                registry=table_registry,
                payload={"x": i, "y": i * 2},
            )

        return {stage.name: {"count": 10, "table": table_name}}

    return Operate(stage.name, _do, output_field=stage.name, info={"builder": "build_table_source", "model": stage.model})
```

---

## External orchestrators

A stage whose work is a whole coordinated run (a sweep, a solver loop, a training
campaign) belongs in an **Orchestrator** — weaver's second runtime citizen, next to
`Operator`.

- **The ABC** (`weaver.base.orchestrator.Orchestrator`): implement `run(...)` — the
  **single public entry point**, with whatever signature makes sense for the pipeline —
  and optionally override `check(context) -> list[str]`, the preflight returning
  human-readable failures (empty list = ready; the default is a no-op).
- **The grammar node is a param bag.** `OrchestratorNode` types only `name` + `op`;
  every other field is allowed and kept — a *validated bag of op-specific params*. **The
  compiler never instantiates an orchestrator from it.** Your builder reads the bag via
  `workspace.orchestrators[stage.orchestrator].model_extra` and constructs the
  orchestrator itself.
- **`op` mismatch is only a warning.** Validate *warns* — never errors — when the bound
  orchestrator's `op` differs from the stage `op`: first-party studies deliberately
  reuse one orchestrator across `populate` + `run` to share the seed, hence the table
  identity.
- **Validate the params yourself, loudly.** Typed checks with located `LowerError`
  messages that name the orchestrator and the param and show the rejected value —
  including rejecting bools masquerading as ints — mirroring `lower_ga_params`.
- **Wrap it via `Orchestrate`, or call `.run()` in `_do`.** `Orchestrate` is the
  universal nesting seam — an Operator holding an Orchestrator. Its real signature:
  `Orchestrate(name, orchestrator, *, output_field, run_args=(), run_kwargs=None,
  pass_context=True, expect=None, info=None)`. `run_args` / `run_kwargs` name **state
  keys** to pass positionally / by keyword to `run`; `pass_context` forwards the
  pipeline `ctx` as `context=`; `expect` type-checks the return; the result lands as
  `{output_field: result}` — so `output_field=stage.name` satisfies the StepBuilder
  contract with no `Operate` wrapper. Calling `.run()` inside your own `_do` is
  equivalent when you need to massage inputs or outputs first.
- **Subclass vs. factory — the doctrine.** A new *flavor* of an existing orchestrator is
  a **factory-configured instance**, never a subclass — weaver-opt's `Optimize` pins
  this (new optimizer flavors are factory functions returning a configured `Optimize`).
  Subclass the ABC only for a **genuinely new** orchestrator, like `FooSweep` below.

Illustrative orchestrator JSON for the sweep (the bag carries `count`):

```json
{ "name": "sweep_orch", "op": "foo_sweep", "count": 25 }
```

**`src/weaver/foo/orchestrators.py`**

```python
"""External orchestrator for weaver.foo.

FooSweep subclasses the weaver.base.orchestrator.Orchestrator ABC — the right
move ONLY for a genuinely new orchestrator. A new flavor of an existing
orchestrator (a differently-configured Optimize, CreateModel, ...) is a factory
function returning a configured instance, never a subclass.

The contract: run() is the single public entry point (any signature that makes
sense); check(context) preflights the wiring and returns human-readable failure
strings (empty list = ready).
"""

from __future__ import annotations

from typing import Any, Mapping

from weaver.base.orchestrator import Orchestrator

__all__ = ["FooSweep"]


class FooSweep(Orchestrator):
    """A minimal fixed-count sweep producing a summary dict.

    Construct once with the validated grammar params; run many times. When
    wrapped via Orchestrate (pass_context=True, the default), run() receives
    the pipeline ctx as `context` — repo_root / artifact_dir live there.
    """

    def __init__(self, *, count: int) -> None:
        self.count = count

    def run(self, *, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Sweep `count` iterations; return the summary dict the stage lands in state."""
        values = [float(i) for i in range(self.count)]
        artifact_dir = None if context is None else context.get("artifact_dir")
        return {"count": self.count, "values": values, "artifact_dir": artifact_dir}

    def check(self, context: Mapping[str, Any]) -> list[str]:
        """Preflight: mirrors the Operator.check list-of-strings contract."""
        del context
        if self.count < 1:
            return [f"FooSweep: count must be an int >= 1, got {self.count}"]
        return []
```

**`src/weaver/foo/stages.py`** (continued)

```python
def build_orchestrated_stage(workspace: Workspace, project: ProjectNode, stage: StageNode) -> Operator:
    """StepBuilder for a stage backed by an external Orchestrator (FooSweep).

    The grammar's OrchestratorNode is a validated param bag — the compiler never
    instantiates it. This builder reads the bag, validates the params with
    located LowerError messages, constructs the orchestrator, and wraps it as
    one fold step via Orchestrate.
    """
    del project
    orchestrator = workspace.orchestrators.get(stage.orchestrator)
    if orchestrator is None:
        raise LowerError(f"orchestrator {stage.orchestrator!r} (stage {stage.name!r}) is not declared")
    params = orchestrator.model_extra or {}

    count = params.get("count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise LowerError(f"orchestrator {orchestrator.name!r} count must be an int >= 1, got {count!r}")

    return Orchestrate(
        stage.name,
        FooSweep(count=count),
        output_field=stage.name,
        expect=dict,
        info={"builder": "build_orchestrated_stage", "orchestrator": stage.orchestrator, "count": count},
    )
```

Notes:

- `Orchestrate.do(state, ctx)` calls `FooSweep.run(context=ctx)` (the `pass_context`
  default) and returns `{stage.name: <summary dict>}` — the StepBuilder contract, with
  `expect=dict` guarding the return type.
- All param validation happens at **build time** (before any `_do` runs), so a bad
  orchestrator bag fails when the stage is lowered, with a message that points at the
  orchestrator by name.

---

## Growth path

`stages.py` is the one module that is legitimately **external-only**: no first-party
`weaver.*` package ships a `stages.py` — the built-in stage builders live inside
weaver-compile itself. There is therefore no first-party layout to converge toward:
`stages.py` stays a single module at any package size, and growth happens in
`operators.py` and friends ([AUTHORING_GUIDE.md](AUTHORING_GUIDE.md) §7).
