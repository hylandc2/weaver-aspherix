# Authoring Model-Step Functions — `physics.py`

A **simulate model** is how a study repo declares executable per-row physics: a JSON node at
`system/models/<name>.json` whose `steps` the compiler lowers into an executable runtime
Model (`weaver.compile`'s `build_runtime_model`). Each step is a plain Python function —
and a step `ref` may point **into your installed package**
(`"weaver.foo.physics:efficiency"`). That is the external hook this guide covers: create
`src/weaver/foo/physics.py` (substituting your leaf name for `foo`) shipping reusable step
functions, using the reference module below.

Do **not** add physics functions to the `__init__.py` re-export surface
([AUTHORING_GUIDE.md](AUTHORING_GUIDE.md) §5) — they are consumed by dotted `ref` string
only, never imported through the curated surface.

---

## The simulate model and its sibling module

A simulate model node carries the shared model keys (`name`, `kind: "simulate"`,
`implements`, `consumes`, `produces`, `description`) plus four of its own:

- **`module`** — the filename of a sibling `.py` next to the JSON (e.g. `"m.py"`).
- **`phases`** — declared phase names (`{"name": ..., "description": ...}` entries).
- **`domains`** — model-local column declarations (e.g. artifact outputs); these join the
  study's resolvable column pool alongside `system/variables/`.
- **`steps`** — the ordered row-step list; each step is
  `{"op": ..., "produces": ..., "ref": ..., "params": {...}, "phase": ...}` (`ref`,
  `params`, and `phase` optional).

**Module loading:** the compiler **path-loads** the sibling `.py` from the model JSON's own
directory (`importlib` `spec_from_file_location` — not a `sys.path` import). The study repo
owns its local physics; **nothing needs installing for bare refs**. The module is loaded
before any step lowers, so `module` must name an existing sibling file even when every step
`ref` is dotted — a missing/undeclared module is a `LowerError`.

---

## Step-ref resolution — the external hook

The effective ref is **`step.ref`, defaulting to `step.produces` when omitted**. It resolves
in one of two ways:

- **Bare name** (no dot, no colon) — resolved as an **attribute of the sibling module**. A
  missing or non-callable attribute is a `LowerError`.
- **Contains a dot or colon** — resolved as a **normal import** of a dotted path: the colon
  is normalized to a dot, so `"weaver.foo.physics:efficiency"` and
  `"weaver.foo.physics.efficiency"` are equivalent. This is how a study runs **your
  installed package's function** as a model step.

Unlike an operator `ref` (which must match the `package:attr` shape), a step `ref` has **no
shape constraint** — bare local names are legal here by design.

**Failure modes:** the compiler's validate phase lowers every simulate model, so a bad bare
ref or `$param` surfaces as a located diagnostic (`model 'm' ... does not lower: ...`)
pointing at the model JSON. A **dotted ref that fails to import** raises the raw
`ModuleNotFoundError`/`AttributeError` instead — your package must be installed in the
study's environment before validate runs.

---

## The 3-arg step contract

Every step function has the same signature:

```
fn(row, ctx, params) -> Mapping[str, Any]
```

The compiler bridges it to the 2-arg operator callable (`do_fn(row, ctx)`) in a closure that
binds `params` at lowering time. Because the bridged callable takes two arguments, it is
always dispatched as the **full-form** operator callable
([authoring-operators.md](authoring-operators.md)) — so a step function must **always return
a Mapping**; a bare scalar raises `TypeError`. What the Mapping must contain depends on the
step `op`:

- **`construct`** — lowers to `Operate`. The mapping is merged into the row **as-is**; the
  keyset is *not* validated, so a construct step may thread free-form interim state
  alongside (or instead of) its named column.
- **`evaluate`** — lowers to `Evaluate`. The keyset must equal **exactly**
  `{step.produces}`.
- **`observe`** — lowers to `Observe`. Return the mapping keyed by the **unprefixed**
  `produces` name; when the step declares a `phase`, the bridge relabels every key to
  `<phase>_<key>` and the operator's column becomes `<phase>_<produces>`. The keyset rule is
  otherwise the same exact-match as `Evaluate`.

`row` is the accumulating row state (the `consumes` columns plus everything earlier steps
produced); `ctx` is the runtime context. `params` is a plain dict of already-resolved
values — see below.

---

## Step params

The step's `params` block is resolved **once, at lowering** — the function receives plain
values, never `$` strings:

- **Literals** (numbers, strings, lists, nested objects) pass through unchanged.
- A string value starting with **`$`** (e.g. `"$k"`) resolves to the **declared value** of
  that variable in `system/variables/` — a constant bound at lowering time, not a per-row
  column read.
- An unknown `$name` is a `LowerError` (surfaced as a validate diagnostic).

---

## StepOp dispatch and validation

| step `op` | lowers to | runtime column | return-keyset rule |
|---|---|---|---|
| `construct` | `Operate` | `produces` (declarative only) | any Mapping, merged as-is |
| `evaluate` | `Evaluate` | `produces` | exactly `{produces}` |
| `observe` | `Observe` | `<phase>_<produces>` if `phase` set, else `produces` | exactly `{produces}` (bridge relabels phased keys) |
| `constrain` | *reserved* | — | parses, but lowering raises `LowerError` |

Validation rules that bind your model JSON (all surfaced as located diagnostics):

- **Produces coverage:** every name in the model's declared `produces` must be produced by
  some step — matched against the step's runtime column, so a phased observe counts as
  `<phase>_<produces>`. Steps *may* also produce undeclared interim columns (the construct
  idiom); only the declared direction is checked.
- **Column resolution:** every `consumes`/`produces` name must be a declared column —
  `system/variables/` or some model's `domains` block. `consumes` becomes the runtime
  Model's input registry.
- **Lowering:** the whole model must lower — module loads, every ref and `$param` resolves.

---

## Reference module

Two worked step functions: `assemble_case` (a `construct` step) and `efficiency` (an
`evaluate` step producing the `efficiency` column).

**`src/weaver/foo/physics.py`**

```python
"""Model-step physics for weaver.foo — functions a study's simulate model binds via dotted step refs.

Every function follows the compiler's 3-arg row-step contract: ``fn(row, ctx, params) ->
Mapping[str, Any]``. The compiler bridges each to a 2-arg operator ``do_fn(row, ctx)`` at
lowering time, with ``params`` bound from the step JSON (``$name`` values already resolved).
A construct step's mapping is merged into the row as-is; an evaluate/observe step's keyset
must equal its produced column exactly.
"""

from __future__ import annotations

from typing import Any, Mapping

__all__ = ["assemble_case", "efficiency"]


def assemble_case(row: Mapping[str, Any], ctx: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
    """construct:case — assemble the interim case description later steps consume.

    Lowers to Operate: the returned mapping is merged into the row as-is (the keyset is
    NOT validated), so a construct step may thread free-form interim state.
    """
    del ctx
    return {"case": {"x": float(row["x"]), "gain": float(params.get("gain", 1.0))}}


def efficiency(row: Mapping[str, Any], ctx: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
    """evaluate:efficiency — efficiency = k * x, keyed exactly by the produced column.

    Lowers to Evaluate: the returned keyset must equal ``{"efficiency"}`` exactly.
    """
    del ctx
    return {"efficiency": float(row["x"]) * float(params["k"])}
```

---

## Wiring it from a study

A simulate model mixing both resolution modes — one bare sibling-module step, one dotted
step running your installed package. (Illustrative; the canonical minimal study fixture
lives in [study-json-reference.md](study-json-reference.md).)

```json
{
  "name": "foo_sim",
  "kind": "simulate",
  "implements": "demo",
  "module": "foo_sim.py",
  "consumes": ["x", "k"],
  "produces": ["efficiency"],
  "steps": [
    {"op": "construct", "produces": "case", "ref": "assemble_case"},
    {"op": "evaluate", "produces": "efficiency", "ref": "weaver.foo.physics:efficiency", "params": {"k": "$k"}}
  ]
}
```

The sibling `foo_sim.py` owns the bare step — study-local, nothing to install:

```python
"""Study-local physics for foo_sim, path-loaded by the compiler from this JSON's directory."""

from __future__ import annotations

from typing import Any, Mapping


def assemble_case(row: Mapping[str, Any], ctx: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
    """construct:case — study-owned interim state threaded to later steps."""
    del ctx, params
    return {"case": {"x": float(row["x"])}}
```

Notes:

- `"ref": "assemble_case"` is bare → sibling-module attribute. Omitting `ref` entirely would
  default to the `produces` name (here it would look up `case` instead).
- The `construct` step's `case` is interim state, deliberately **not** in the declared
  `produces`; the declared `efficiency` **is** covered by a step, as validation requires.
- Every produced **physical** column (`efficiency` here) must be declared as a study
  variable with a **resolvable `units` string** (`"None"` for dimensionless) — see the units
  section of [study-json-reference.md](study-json-reference.md).
- The `Operate` / `Evaluate` / `Observe` categories these steps lower into are documented in
  [authoring-operators.md](authoring-operators.md).
