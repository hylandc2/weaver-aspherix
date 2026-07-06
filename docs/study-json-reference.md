# Study JSON Reference — the six-node grammar and the minimal study repo

This is the reference for the **study / consumer repo side** of an external package: the
JSON grammar `weaver.compile` parses, the complete minimal study that wires `weaver-foo`
in, the units rules, the validation diagnostics you will actually see, and the seams that
are **closed** (do not build against them). How the package side is authored is covered in
[AUTHORING_GUIDE.md](AUTHORING_GUIDE.md) (wiring: §8) and
[authoring-stages.md](authoring-stages.md).

The study files in §2 are defined **once, here**. The test suite copies them verbatim
under `tests/fixtures/study/` ([authoring-tests.md](authoring-tests.md)) — do not fork or
redefine them elsewhere.

---

## 1. Study repo layout — the `Workspace.scan` contract

`Workspace.scan(root)` reads a study repo into four name-unique registries plus the System
contract and the project spines:

```
<study root>/
├── system/
│   ├── <name>.system.json        ← EXACTLY ONE (the System contract)
│   ├── variables/*.json          ← {name: descriptor} maps
│   ├── operators/*.json          ← one operator per file
│   ├── orchestrators/*.json      ← one orchestrator per file
│   └── models/*.json  (+ .py)    ← one model per file; simulate models path-load a sibling module
└── projects/*.json               ← one project per file
```

- **`system/` is required.** A missing `system/` directory raises `ResolveError`.
- **Exactly one `system/*.system.json`.** Zero or several raise `ResolveError`.
- **The four subtrees are optional.** A missing `variables/` / `operators/` /
  `orchestrators/` / `models/` subtree (or `projects/`) just yields an empty registry.
- **Names come from the JSON, not the filename.** Operators, orchestrators, models, and
  projects are keyed by their `"name"` field; variables are keyed by the object keys of
  each variables file. A simulate model's `module` resolves **relative to its own JSON
  file** (so `"module": "m.py"` means a sibling of `m.json`).
- **Names are unique per registry.** A duplicate variable / operator / orchestrator /
  model / project name — even across files — raises `ResolveError`.

Scanning also parses every file (§3); a file that fails schema validation raises
`ParseError` with the file path and the offending field path (§5).

---

## 2. The complete minimal study

A two-stage study: `populate` samples the design space with the built-in
`weaver.core:populate`, then `process` runs the external `weaver.foo.stages:build_foo_stage`.
The simulate model `m` mixes a **sibling-module step** (`compute_y` in `m.py`) with a
**dotted external step** (`weaver.foo.physics:efficiency`) so both ref forms are exercised.
It is a minimal adaptation of the compiler's own walking-skeleton fixture study.

**`system/demo.system.json`**

```json
{
  "name": "demo",
  "description": "minimal study repo wiring the weaver-foo external package",
  "required_outputs": ["y"],
  "optional_outputs": ["efficiency"]
}
```

**`system/variables/vars.json`**

```json
{
  "x": {"type": "float", "role": "input", "value": [0.0, 1.0], "units": "None", "description": "ranged design input"},
  "k": {"kind": "parameter", "type": "float", "role": "input", "produced_by": "constant", "value": 2.0, "units": "None", "description": "fixed gain, referenced by $k"},
  "y": {"type": "float", "role": "output", "produced_by": "evaluated", "units": "None", "description": "y = k * x"},
  "efficiency": {"type": "float", "role": "output", "produced_by": "evaluated", "units": "None", "description": "efficiency column, computed by weaver.foo.physics:efficiency"}
}
```

**`system/models/m.json`**

```json
{
  "name": "m",
  "kind": "simulate",
  "implements": "demo",
  "module": "m.py",
  "consumes": ["x", "k"],
  "produces": ["y", "efficiency"],
  "steps": [
    {"op": "evaluate", "produces": "y", "ref": "compute_y", "params": {"k": "$k"}},
    {"op": "evaluate", "produces": "efficiency", "ref": "weaver.foo.physics:efficiency", "params": {"k": "$k"}}
  ]
}
```

**`system/models/m.py`**

```python
"""Model-step module for the demo study, path-loaded via m.json's "module": "m.py".

Step functions use the compiler's 3-arg contract: fn(row, ctx, params) -> Mapping.
"""

from __future__ import annotations

from typing import Any, Mapping


def compute_y(row: Mapping[str, Any], ctx: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
    """evaluate:y — multiply the sampled input x by the $k parameter."""
    del ctx
    return {"y": float(row["x"]) * float(params["k"])}
```

**`system/operators/populate.json`**

```json
{"name": "populate", "kind": "sample", "reads": ["registry.inputs"], "writes": ["population"], "ref": "weaver.core:populate", "description": "sample the design space"}
```

**`system/operators/foo.json`**

```json
{
  "name": "foo",
  "kind": "operate",
  "reads": ["upstream_data"],
  "writes": ["downstream_data"],
  "ref": "weaver.foo.stages:build_foo_stage",
  "produces_table": false,
  "description": "custom stage from the external weaver-foo package"
}
```

**`system/orchestrators/pop.json`**

```json
{"name": "pop", "op": "populate", "sampler": "lhs", "population": {"count": 8, "seed": 3}}
```

**`system/orchestrators/foo_orch.json`**

```json
{"name": "foo_orch", "op": "foo", "custom_param": "value"}
```

**`projects/demo.json`**

```json
{
  "name": "demo",
  "system": "demo",
  "stages": [
    {"name": "populate", "op": "populate", "orchestrator": "pop", "model": "m"},
    {"name": "process", "op": "foo", "orchestrator": "foo_orch", "from": ["populate"]}
  ]
}
```

**Expected validation outcomes** (verified against the compiler):

- **With `weaver-foo` installed** in the same environment: `validate(workspace)` returns
  **zero diagnostics** — the study is fully clean.
- **Without it**, every failure names `weaver.foo`, which is exactly what proves the
  wiring points at your package. The two failures take *different forms*: the `process`
  stage's operator `ref` surfaces as a **located error diagnostic** (`operator 'foo' ref
  'weaver.foo.stages:build_foo_stage' has no step builder — external resolution failed:
  No module named 'weaver.foo' …`), but the model's dotted step ref is **not** wrapped —
  the validate ref-resolution pass reuses the model lowering, and an unimportable dotted
  step ref escapes `validate()` as a raw `ModuleNotFoundError` instead of joining the
  diagnostics list. Either way, installing the package is the fix.

Notes:

- `process` binds **no** `model` — valid because `build_foo_stage` is a non-table stage
  that never calls `build_project` ([authoring-stages.md](authoring-stages.md)).
- `from: ["populate"]` may only name an **earlier** stage in the same project.
- Coverage holds by construction: `m.produces` covers the System's `required_outputs`,
  and both steps' `produces` account for everything `m` declares it produces.

---

## 3. The six-node grammar

**Closed by default: unknown keys are parse errors.** Every node rejects keys outside its
schema (Pydantic `extra="forbid"`) — a typo like `"orchestraor"` fails at parse time with
the field path. Exactly three nodes are **open** (`extra="allow"`): **OrchestratorNode**
(the op-specific param bag), and the two reserved kinds **`variable kind: "unit"`** and
**`model kind: "import"`** (accepted, shape not yet pinned down).

### System — `system/<name>.system.json`

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | str | yes | must match each project's `system` and each model's `implements` |
| `description` | str | no | |
| `required_outputs` | list[str] | yes | column names a `run`-stage model must produce |
| `optional_outputs` | list[str] | no | |

### Variable — `system/variables/*.json`

Each file is a `{name: descriptor}` **map**. A descriptor with no `kind` defaults to
`physical`. The union discriminates on `kind`:

| Kind | Fields | Notes |
|---|---|---|
| `physical` | `type` (required), `role`, `produced_by`, `value`, `units` (str, default `"None"`), `shape`, `description`, `info` | a measured/derived quantity; `units` is dimension-checked (§4) |
| `parameter` | `type` (required), `role`, `produced_by` (default `constant`), `value`, `units` (default `"None"`), `shape`, `description`, `info` | a fixed knob; referenceable from step `params` as `"$name"` |
| `domain` | `role`, `produced_by`, `value` (str path, default `""`), `description`, `info` | a runtime artifact (dataset, trained state); carries no units |
| `unit` | `description`, `info`, + open | **reserved-but-live for the dimensional pass**: declare `dimensions` / `symbol` to add a named unit (§4) |

### Operator — `system/operators/*.json`

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | str | yes | what a stage's `op` names |
| `kind` | enum | yes | vocabulary label (all 10 values below); **dispatch is ref-authoritative**, not kind-driven |
| `reads` / `writes` | list[str] | no | declarative documentation |
| `ref` | str \| null | no | must match `^[\w.]+:[\w.]+$` — `package.module:attr`; selects a built-in step builder or an external `StepBuilder` import |
| `produces_table` | bool | no (false) | **gate**: an orchestrator `source.from_stage` may only name a stage whose operator is the built-in populate/run or sets `produces_table: true` |
| `description` | str | no | |

### Orchestrator — `system/orchestrators/*.json`

Only `name` and `op` are schema'd; **everything else is an open param bag** the bound
stage builder reads (`model_extra`). The built-in populate reads `sampler` +
`population {count >= 1, seed}`; your own builder defines (and must validate) its own params.

### Model — `system/models/*.json`

Shared base fields: `name`, `implements` (must equal the System name if set), `consumes`,
`produces` (both column lists), `description`. Then per kind:

| Kind | Fields | Notes |
|---|---|---|
| `simulate` | `module`, `phases` `[{name, description}]`, `domains` `{name: domain descriptor}`, `steps` | `module` is a sibling `.py`, **path-loaded** (no install) |
| `predict` | `backend`, `hyperparameters` `{name: {type, value}}`, `scaling` `{feature_scaler, target_scaler}`, `tune`, `n_iter`, `domains` | `backend` is a **closed set** (§6) |
| `ensemble` | `members` (required), `aggregation` (default `"mean"`), `size` | members must be declared models; declared `produces` must be covered by the members' union |
| `import` | open | **reserved** — accepted, not lowered |

A simulate **step** (`extra="forbid"`): `op` (`construct` / `observe` / `evaluate`;
`constrain` is reserved), `produces` (the output column), `ref`, `params`, `phase`. Ref
resolution is hybrid: a ref containing `:` or `.` imports as a dotted path
(`weaver.foo.physics:efficiency`); a bare name is an attribute of the model's `module`.
A `"$name"` param value resolves to that declared variable's `value` at lowering time.
A phased `observe` step writes the column `<phase>_<produces>`. Every declared `produces`
of the model must be produced by some step.

### Project — `projects/*.json`

`name`, `label`, `description`, `system` (must equal the repo's System name), `stages`.

### Stage (inside a project's `stages` list)

| Field | Type | Notes |
|---|---|---|
| `name` | str | keys the stage's output in shared state; later stages read `state[<name>]` |
| `op` | str | names a declared operator |
| `orchestrator` | str | names a declared orchestrator (its `op` should match the stage's — mismatch is a *warning*) |
| `model` / `models` | str / list[str] | **at most one of the two keys** — setting both is a parse error |
| `requires` | list[str] | columns the bound models' `produces` union must cover |
| `objectives` | list of `{metric, direction}` | `direction`: `min` (default) \| `max`; `metric` must be a declared column |
| `overrides` | dict[str, str] | `{target_column: value_variable}`; both must be declared columns, dimensions must match (§4) |
| `from` | list[str] | upstream stage names — must be **earlier** stages in the same project |

### Enum values (closed sets — anything else is a parse error)

| Enum | Values |
|---|---|
| VariableKind | `physical`, `domain`, `parameter`, `unit` (reserved) |
| VarType | `float`, `int`, `str`, `bool`, `list` |
| Role | `input`, `output` |
| ProducedBy | `sampled`, `constant`, `calculated`, `observed`, `evaluated` |
| OperatorKind | `sample`, `run`, `preprocess`, `create_model`, `optimize`, `analyze`, `operate`, `observe`, `evaluate`, `constrain` |
| StepOp | `construct`, `observe`, `evaluate`, `constrain` (reserved) |
| ModelKind | `simulate`, `predict`, `ensemble`, `import` (reserved) |
| ScalerKind | `minmax`, `zscore`, `none` |
| ObjectiveDirection | `min`, `max` |

---

## 4. Units and the dimensional pass

**Every `physical` / `parameter` variable's `units` string must resolve to a dimension
vector, or validation errors on that variable.** The pass builds a unit registry from
three sources: the seven SI base units (`K`, `m`, `s`, `kg`, `A`, `cd`, `mol`, plus
`_unitless`), the common composites (`N`, `Pa`, `J`, `W`, `m_per_s`, `m_per_s_sq`), and
the study's own `kind: "unit"` variable declarations. The strings `"None"`,
`"_unitless"`, and `""` resolve to the dimensionless zero vector — so an un-unitted study
(like §2) is clean. Produced physical columns follow the same rule: a resolvable units
name or `"None"`.

Declaring your own named unit (illustrative — not part of the fixture study):

```json
{
  "rpm": {"kind": "unit", "dimensions": {"time": -1}, "symbol": "rpm", "description": "rotation rate"},
  "omega": {"type": "float", "role": "input", "value": [0.0, 100.0], "units": "rpm", "description": "rotation speed"}
}
```

`dimensions` maps the seven SI base dimensions (`length`, `time`, `mass`, `temperature`,
`current`, `luminosity`, `quantity`) to integer exponents.

**Overrides must be dimensionally consistent.** A stage override `{target: value}` may
only substitute a same-dimensioned quantity — pinning a `1/time` knob with a `length`
constant is a located error (`override 'omega' <- 'length_knob' is dimensionally
inconsistent ({'time': -1} vs {'length': 1})`).

**Runtime-emitted variables bypass this pass** — the pass only sees `system/variables/`
declarations, so columns your operators emit at runtime are never dimension-checked; see
the dormant emits seam in [authoring-operators.md](authoring-operators.md).

---

## 5. Validation and diagnostics

The error taxonomy (`weaver.compile`):

| Type | Meaning |
|---|---|
| `CompileError` | base class for every compiler error |
| `ParseError` | one file failed schema validation; carries the `file` and each problem's field path (e.g. `stages.1.objectives.0.direction`) |
| `ResolveError` | the repo is structurally invalid: missing `system/`, not exactly one `*.system.json`, duplicate names |
| `LowerError` | a resolved stage/model cannot be lowered: dangling ref, missing/invalid orchestrator param, unknown sampler/backend |
| `Diagnostic` | one located finding — `message`, `file`, `where`, `severity` (`"error"` \| `"warning"`) |
| `SemanticError` | raised by `assert_valid` when any **error**-severity diagnostic exists; its message is the full source-mapped report |

`validate(workspace)` runs every semantic pass and returns **all** diagnostics (errors
and warnings); `assert_valid(workspace)` raises `SemanticError` if any error-severity
diagnostic exists.

Diagnostics an external-package author actually hits:

| Diagnostic | Trigger |
|---|---|
| unknown operator / orchestrator / model | a stage's `op` / `orchestrator` / `model(s)` names nothing declared |
| **external ref import failure — at validate time, not run time** | an operator `ref` outside the built-in table fails to import (package not installed, typo'd path); reported per stage |
| `'from' references … not an earlier stage` | `from` names a later or undeclared stage |
| coverage | the bound models' `produces` union does not cover the stage's `requires`; or a `run` stage's model does not produce the System's `required_outputs` |
| units | unresolvable `units` string; dimensionally inconsistent override (§4) |
| orchestrator/op mismatch (*warning*) | the bound orchestrator declares a different `op` than the stage — advisory, because reusing one orchestrator across populate+run shares the seed and hence the table identity |

**One caveat:** a simulate model's *dotted step ref* to an uninstalled package is not
wrapped into a diagnostic — it escapes `validate()` as a raw `ModuleNotFoundError` from
the ref-resolution pass (§2). Treat any failure naming your package, in either form, as
"install the package in this environment".

**How to run validation.** A package that depends only on `weaver-core` +
`weaver-compile` gets **no CLI** — validate is a library phase:

```python
from pathlib import Path

from weaver.compile import Workspace, assert_valid, validate

workspace = Workspace.scan(Path("/path/to/study"))
for diagnostic in validate(workspace):
    print(diagnostic.format())
assert_valid(workspace)  # raises SemanticError on any error diagnostic
```

Installing the **`weaver` meta-package** (the `weaver-dist` distribution, which pulls in
every first-party package) additionally provides the console commands — run them **from
the study repo root** (they scan the current directory):

```bash
weaver validate                      # prints diagnostics; exit 1 on errors, else "grammar OK"
weaver run demo --stages populate    # validate gate, then execute the named stages
```

---

## 6. Closed seams — do not copy these expecting extension points

Two grammar keys look pluggable but are **closed sets** resolved from hardcoded tables in
the lowering phase. Do not model your own extension points on them; the one open seam for
external code is the operator `ref` → `StepBuilder` path (and the dotted model-step ref)
— see the reachability section of [authoring-operators.md](authoring-operators.md).

- **Predict-model `backend` is closed: `rf`, `svr`, `nn`.** Each maps to a recipe that a
  hardcoded `import weaver.ml` attaches at lowering time (`rf` → `RFRegressor`, `svr` →
  `SVRegressor`, `nn` → `NNRegressor`). Any other value raises `LowerError` (`… has no
  recipe`). There is **no grammar path to an external recipe** — an external ML backend
  cannot be reached through `kind: "predict"`.
- **Samplers are closed: `lhs` only.** The populate orchestrator's `sampler` key selects
  from a one-entry table (Latin hypercube); any other value raises `LowerError`
  (`unknown sampler …`). External samplers are unreachable through the grammar.
