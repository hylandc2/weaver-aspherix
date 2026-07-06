1# Weaver External Package — Authoring Guide

This guide walks you through authoring an **external Weaver package** from this
template. An external package extends Weaver with new operators (factory functions),
compiler stages, and model-step functions **without editing `weaver-core` or
`weaver-compile`**. Your code installs under the shared `weaver.` PEP 420 namespace
(so it lives at `weaver.<name>.*` and imports `weaver.operators` / `weaver.compile`
like any first-party package), and a study/consumer repo wires your stage in purely
through JSON config plus a `ref` string. No fork, no patch, no upstream change is
required.

> The docs use the placeholder name `foo` (`weaver-foo`, `weaver.foo`) throughout.
> Substitute your real package name — it must **not** be a reserved name (§3).
>
> The template ships the project configuration (`pyproject.toml`, `.gitignore`) and this
> documentation; **you author the Python modules**, following the per-file guides —
> each contains a complete reference implementation:
>
> - [authoring-operators.md](authoring-operators.md) — operator factories (`operators.py`)
> - [authoring-stages.md](authoring-stages.md) — compiler stage(s) / StepBuilders (`stages.py`) and external orchestrators (`orchestrators.py`)
> - [authoring-models.md](authoring-models.md) — model-step functions (`physics.py`)
> - [authoring-tests.md](authoring-tests.md) — the test suite (`tests/`)
> - [study-json-reference.md](study-json-reference.md) — the study repo's six-node JSON grammar, a complete minimal study, and the validate phase
> - [PROFILE.md](PROFILE.md) — a package-profile skeleton you fill in, mirroring Weaver's first-party `docs/packages/` format

---

## 1. What you build

The finished package looks like this:

```
weaver-foo/
├── README.md
├── .gitignore                   ← ships with the template
├── pyproject.toml               ← ships with the template (edit name/description/sources)
├── docs/                        ← this documentation (fill in PROFILE.md)
├── src/
│   └── weaver/                  ← NO __init__.py here (PEP 420 namespace)
│       └── foo/
│           ├── __init__.py      ← the ONLY __init__.py you create under src/ (§5)
│           ├── operators.py     ← operator factories (authoring-operators.md)
│           ├── stages.py        ← compiler StepBuilder(s) (authoring-stages.md)
│           ├── orchestrators.py ← optional: external Orchestrator(s) (authoring-stages.md)
│           └── physics.py       ← optional: model-step functions (authoring-models.md)
└── tests/
    ├── __init__.py
    ├── test_operators.py        ← authoring-tests.md
    ├── test_imports.py          ← authoring-tests.md
    ├── test_stages.py           ← authoring-tests.md
    └── fixtures/
        └── study/               ← mini study repo (study-json-reference.md)
```

This flat module layout is the **seed** shape — right for a package this size, and it
grows into the same shape as `weaver-ml` when the package does (§7).

---

## 2. Quick start

1. **Pick your package name.** Replace `foo` / `weaver-foo` / `weaver.foo` throughout:
   the `name` and `description` in `pyproject.toml`, the `src/weaver/<name>/` directory
   you create, the imports in `__init__.py` and the tests, and the `ref` strings. Pick a
   leaf name that is **not** reserved (§3).

2. **Point at your Weaver source.** Weaver is **source-only — not published to PyPI** —
   so nothing can resolve `weaver-core` / `weaver-compile` until you fill this in. You
   declare each dependency twice: once in `[project].dependencies` and once in
   `[tool.uv.sources]`. Edit `pyproject.toml` to choose ONE form:

   - **Git (deployment / CI):**
     ```toml
     [tool.uv.sources]
     weaver-core = { git = "https://github.com/YOUR_ORG/weaver.git", subdirectory = "packages/weaver-core", rev = "REPLACE_WITH_SHA_OR_TAG" }
     weaver-compile = { git = "https://github.com/YOUR_ORG/weaver.git", subdirectory = "packages/weaver-compile", rev = "REPLACE_WITH_SHA_OR_TAG" }
     ```
     **Pin the `rev`.** Every Weaver package is an unpublished `0.1.0`, so the
     `>=0.1.0` floor in `[project].dependencies` pins nothing — the git rev/tag is the
     only real pin. (The same logic applies to your own third-party dependencies:
     exact-pin the fragile ones, as weaver-ml does with `scikit-learn==1.8.0`.)
   - **Local path (Weaver checked out next to this repo):**
     ```toml
     [tool.uv.sources]
     weaver-core = { path = "../weaver/packages/weaver-core", editable = true }
     weaver-compile = { path = "../weaver/packages/weaver-compile", editable = true }
     ```

   The template ships with the **git** form active and the **path** form commented out.
   Swap them per your choice.

3. **Author the package modules.** Create the skeleton (§5), then write
   `operators.py` ([authoring-operators.md](authoring-operators.md)),
   `stages.py` ([authoring-stages.md](authoring-stages.md)), optionally
   `physics.py` ([authoring-models.md](authoring-models.md)), and the tests
   ([authoring-tests.md](authoring-tests.md)).

4. **Sync and verify.** `uv sync` also installs the dev tooling (`pytest`, `ruff`,
   `pyright`) from the `[dependency-groups] dev` group.
   ```bash
   uv sync
   uv run pytest
   ```

5. **Rewrite `README.md`** to describe your package (drop the template banner) and
   **fill in [PROFILE.md](PROFILE.md)** so integrators can read your package the way
   they read a first-party one.

**Prerequisites:** Python `>=3.11` (the Weaver workspace floor; some Weaver packages
also cap at `<3.14`, so the template uses `>=3.11,<3.14` — narrow the cap only if your
own dependencies require it) and [uv](https://docs.astral.sh/uv/) on `PATH`.

---

## 3. The one rule that must not be broken

> ### 🚫 NEVER create `src/weaver/__init__.py`.
>
> `weaver` is a **PEP 420 implicit namespace package** — there is **no `__init__.py`
> anywhere on the `weaver/` directory itself** in the entire Weaver workspace. Shipping
> `src/weaver/__init__.py` is **fatal**: it converts the namespace into a regular
> package and **breaks every other `weaver.*` import** (`weaver.operators`, `weaver.compile`, …)
> wherever your package is co-installed. The only `__init__.py` you may create under
> `src/` is **inside your own leaf module directory** — `src/weaver/foo/__init__.py` —
> never one directory up.

**Reserved sub-directory names under `weaver/` (do NOT reuse — collision):**
`analyze`, `base`, `cli`, `compile`, `config`, `design_space`, `ml`, `operators`,
`opt`, `orchestrators`, `props`, `utils`.

(`cli` ships with the `weaver-dist` meta-package — see §8's note on the `weaver` CLI.)

Your leaf name must be none of these.

---

## 4. Project configuration (`pyproject.toml`, `.gitignore`)

Both files ship with the template, pre-configured to mirror the Weaver workspace tool
config. You should only need to edit the `[project]` `name` / `description` and the
`[tool.uv.sources]` block (§2). What the shipped `pyproject.toml` pins down:

- **Build:** `hatchling` backend with the mandatory wheel target
  `[tool.hatch.build.targets.wheel] packages = ["src/weaver"]` — the `src/` layout is
  the only supported layout.
- **Dependencies:** `weaver-core` and `weaver-compile`, each declared **twice** — in
  `[project].dependencies` **and** `[tool.uv.sources]` (git subdirectory with a pinned
  `rev`, or local path).
- **Dev tooling:** `[dependency-groups] dev` pins `ruff`, `pyright`, and `pytest`
  (mirroring the Weaver workspace root), so the §9 verify commands work right after
  `uv sync`.
- **Python:** `requires-python = ">=3.11,<3.14"`.
- **Lint/format:** `ruff` with line-length `180` and `src = ["src"]`.
- **Types:** `pyright` in **strict** mode over `src` and `tests`.
- **Tests:** `pytest` with `testpaths = ["tests"]` and quiet output (`addopts = "-q"`).

The shipped `.gitignore` covers Python build/cache artifacts, virtualenvs,
test/lint/type-check caches, generated data/assets/artifacts directories, environment
files, and editor/OS cruft. Extend it as needed.

---

## 5. Package skeleton (`__init__.py`)

Create `src/weaver/foo/` (your leaf name for `foo`) with **no** `__init__.py` on the
parent `src/weaver/` directory — see §3. Then create `src/weaver/foo/__init__.py`
re-exporting your public factories and builders:

**`src/weaver/foo/__init__.py`**

```python
"""weaver.foo — external Weaver package: operator factories and compiler stages."""

from weaver.foo.operators import my_in_range, my_probe, my_ratio, my_solver
from weaver.foo.stages import build_foo_stage

__all__ = [
    "my_solver",
    "my_ratio",
    "my_in_range",
    "my_probe",
    "build_foo_stage",
]
```

**The `__init__.py` policy** (this is how the first-party packages do it):

- The leaf `__init__.py` is a **small curated re-export surface** (the `weaver.opt`
  style) — a handful of names, nothing else. The compiler never imports it: `ref`
  strings import your modules directly, so this surface exists for human consumers and
  the import test only.
- **Never let the `__init__` chain pull heavy dependencies at import time.** Heavy
  imports stay lazy inside callables (§7); the first-party `weaver.ml` imports
  sklearn/TensorFlow only inside its operator functions.
- A **side-effect-only `__init__`** (the `weaver.ml` style — importing a module to
  register things onto core classes) is legitimate but rarely useful externally: the
  compiler's recipe registry is closed to external packages (see the reachability
  section of [authoring-operators.md](authoring-operators.md)). If you do it, mark the
  import with `# noqa: F401  (side effect: ...)` as ml does.
- As the package grows subpackages (§7), their `__init__.py` files stay **empty or
  docstring-only** — nodes are imported by full dotted path.

When you add or rename factories, update these re-exports and the name list in
`tests/test_imports.py` together ([authoring-tests.md](authoring-tests.md)).

---

## 6. What you author

- **Operator factories** (`operators.py`) — factory functions returning configured
  `Operate` / `Evaluate` / `Constrain` / `Observe` instances. The doctrine has two
  clauses: behavior with an **existing `do()` shape** is a factory returning a
  configured category instance (the default — never subclass a category); a
  **genuinely new `do()` signature** is a new category, i.e. a direct base-`Operator`
  subclass with classmethod factories (rare and deliberate — how `weaver-ml`'s `Fit`
  and `weaver-analyze`'s `Show`/`Tell` are built). Contracts and a complete reference
  module: [authoring-operators.md](authoring-operators.md).
- **Compiler stage(s)** (`stages.py`) — `StepBuilder` functions the compiler resolves
  from the `ref` string in operator JSON. The contract, non-table vs. table-producing
  stages, external orchestrators (`orchestrators.py`), and complete reference builders:
  [authoring-stages.md](authoring-stages.md).
- **Model-step functions** (`physics.py`, optional) — functions a study's simulate
  model can reference from its JSON `steps` via a dotted `ref`
  (`"weaver.foo.physics:efficiency"`), so your package ships reusable physics:
  [authoring-models.md](authoring-models.md).
- **Tests** (`tests/`) — unit tests for your factories, a StepBuilder test against a
  mini study fixture, plus an import test pinning the blessed `weaver.compile` surface.
  Complete reference tests: [authoring-tests.md](authoring-tests.md).
- **The study-side JSON** — your package is invoked from a study repo's six-node JSON
  grammar. The full grammar reference, a complete minimal study, and the validate
  phase: [study-json-reference.md](study-json-reference.md).
- **The package profile** ([PROFILE.md](PROFILE.md)) — fill in the §0–§6 skeleton so
  your package documents itself the way first-party packages do.

---

## 7. Growth path & house style

The flat `operators.py` / `stages.py` seed is exactly `weaver-opt`'s shape. When the
package grows (roughly: a third operator concern, or any private helper), converge on
`weaver-ml`'s shape rather than growing a fat module:

```
src/weaver/foo/
├── __init__.py          ← still the curated re-export (§5)
├── operators/
│   ├── __init__.py      ← EMPTY (or docstring-only)
│   ├── solve.py         ← one module per operator concern
│   ├── probe.py
│   └── _helpers.py      ← underscore-prefixed private helpers
├── orchestrators/
│   └── __init__.py      ← docstring-only
├── utils/
├── stages.py            ← stays a single module at any size
└── physics.py
```

- **Subpackage `__init__.py` files stay empty or docstring-only**; concrete nodes are
  imported by **full dotted path** (`from weaver.foo.operators.solve import my_solver`).
  This keeps package import side-effect-free — the same convention `weaver.ml` states
  in its `orchestrators/__init__.py`.
- **`stages.py` never splits and has no first-party analog** — built-in stage builders
  live inside `weaver-compile` itself; a `stages.py` module is the *external-only*
  seam, and the `ref` strings pointing at it should stay stable.

House style, applied by every reference module in these docs (and by the first-party
packages):

- `from __future__ import annotations` at the top of every module.
- **Absolute dotted-path imports only** — no relative imports.
- A **per-module `__all__`** naming the public surface.
- **Contract-bearing module docstrings** — state the design contract, not a summary.
- **Lazy heavy imports** inside *every* operator callable and stage `_do` — never at
  module level (ml imports TensorFlow inside its loss functions, joblib inside `do`).
- **Private helpers** are underscore-prefixed modules (`_helpers.py`), not exported.
- **`info=` metadata** on every factory-built operator, carrying the factory name and
  key parameters — downstream tooling reads it.
- Full type annotations everywhere, including tests — `pyright` runs strict over both.

---

## 8. Wiring it into a study / consumer repo

The study repo invokes your stage purely through JSON — it never imports your package in
Python.

**Prerequisite:** the three files below are added to an **existing, valid study repo**.
`Workspace.scan()` requires a `system/` directory containing **exactly one**
`<name>.system.json` contract file (it errors otherwise), and every name a project
stage references — operators, orchestrators, models — must already be declared under
`system/` or the validate phase reports unknown-reference errors. If you are starting
from nothing, copy the **complete minimal study** in
[study-json-reference.md](study-json-reference.md) and adapt it.

**`system/operators/foo.json`** — declares the operator; `ref` selects your builder;
`produces_table` declares whether it writes a queryable table:

```json
{
  "name": "foo",
  "kind": "operate",
  "ref": "weaver.foo.stages:build_foo_stage",
  "reads": ["upstream_data"],
  "writes": ["downstream_data"],
  "produces_table": false,
  "description": "custom operator from external package"
}
```

**`system/orchestrators/foo_orch.json`** — names the operator; may carry extra op-specific
params (the node allows extra fields — your StepBuilder reads them as a param bag; see
[authoring-stages.md](authoring-stages.md)). Because `build_foo_stage` is a non-table
stage that does **not** call `build_project`, this orchestrator needs **no**
`population` block:

```json
{
  "name": "foo_orch",
  "op": "foo",
  "custom_param": "value"
}
```

**`projects/demo.json`** — a stage entry referencing the operator + orchestrator; `from`
lists upstream stages whose outputs appear in `state`. The `process` stage binds **no**
`model` — valid precisely because `build_foo_stage` does not call `build_project`:

```json
{
  "name": "demo",
  "system": "demo",
  "stages": [
    {
      "name": "populate",
      "op": "populate",
      "orchestrator": "pop",
      "model": "m"
    },
    {
      "name": "process",
      "op": "foo",
      "orchestrator": "foo_orch",
      "from": ["populate"]
    }
  ]
}
```

**Resolution & failure mode:** the compiler reads `operator.ref` (`"pkg.module:builder"`),
converts the colon to a dot, and imports the builder via `importlib`. Your package must be
**installed/importable** in the study's environment. A **bad or uninstalled `ref`** (e.g.
`weaver.nonexistent:builder`) raises `LowerError`, surfaced as a diagnostic during the
compiler's validate phase — **not** at fold/execution time.

**Running validate:** a package that depends only on `weaver-core` + `weaver-compile`
has no CLI — call the validate phase as a library (`weaver.compile.validate` /
`assert_valid`), as `tests/test_stages.py` does. The **`weaver` CLI** (`weaver validate`,
`weaver run`) ships with the separate `weaver-dist` meta-package; install that in the
study's environment to run the same checks from the command line. The full diagnostic
catalog is in [study-json-reference.md](study-json-reference.md).

---

## 9. Verify

Run these from the repo root. All must pass clean (`uv sync` installs the tools from
the dev dependency group):

```bash
uv sync                      # resolves weaver-core + weaver-compile and the dev tools
uv run pytest                # tests/ green (quiet via addopts=-q)
uv run ruff check .          # no lint errors (line-length 180)
uv run ruff format --check . # formatting clean
uv run pyright               # strict mode: 0 errors
```

Expected outcome:

- `uv sync` resolves `weaver-core` and `weaver-compile` (git or path) with no errors.
- `pytest` reports all tests passing, including `test_blessed_surface_is_public`,
  `test_foo_package_imports`, and the `test_stages.py` fixture tests.
- `ruff check` / `ruff format --check` report no issues.
- `pyright` reports **0 errors** — strict mode requires full annotations, so keep
  `-> dict[str, Any]` and explicit parameter types on your `_do` functions.

---

## 10. Final checklist

- [ ] **No `src/weaver/__init__.py`** exists. The only `__init__.py` under `src/` is `src/weaver/foo/__init__.py`.
- [ ] Leaf sub-directory name is **not** reserved (`analyze, base, cli, compile, config, design_space, ml, operators, opt, orchestrators, props, utils`).
- [ ] `pyproject.toml` has `[tool.hatch.build.targets.wheel] packages = ["src/weaver"]` (src/ layout, hatchling).
- [ ] Each weaver dependency is declared **twice**: in `[project].dependencies` **and** `[tool.uv.sources]`.
- [ ] `[tool.uv.sources]` URL/path filled in **with a pinned `rev`** for the git form; `requires-python = ">=3.11,<3.14"`.
- [ ] Operators are **factory functions** returning configured `Operate`/`Evaluate`/`Constrain`/`Observe` instances; a genuinely new `do()` shape is a direct base-`Operator` subclass — **never a category subclass**.
- [ ] StepBuilder's module-level imports are limited to the blessed `weaver.compile` surface plus the operator-construction classes (`Operator`, `Operate`, …); heavy imports are lazy inside `_do`; returns `{stage.name: result}`.
- [ ] Non-table stages do **not** call `build_project`; only table-producing stages (bound `model` + orchestrator with a valid `population` block) call it, **create the table with `ensure_table` (merging `database_registry()`)**, and write via keyword-only `Database.insert(table_name=..., registry=..., payload=...)`.
- [ ] Every physical column your stages/steps produce has a resolvable `units` string (or `"None"`) declared in the study's `system/variables/` ([study-json-reference.md](study-json-reference.md)).
- [ ] `docs/PROFILE.md` is filled in (§6 Cross-package wiring at minimum).
- [ ] `uv sync` resolves; `pytest`, `ruff check`, `ruff format --check`, `pyright` all green.
