# Generalized Aspherix wrapper for Weaver — implementation plan

**Status:** approved; amended 2026-07-14 after a claim-by-claim verification review (40 claims checked against the four repos + vendor install). **Date:** 2026-07-14.
**Approach:** Deck-as-Template (the study owns a real `.asx`; the wrapper owns zero Aspherix vocabulary).

---

## 0. Orientation — where everything lives

This plan spans **three sibling repos** plus a vendor install. All paths are on this machine.

| What | Path | Role |
|---|---|---|
| **Weaver** (the framework) | `C:\Users\hylandc2\Workspaces\Weaver` | Monorepo: `packages/weaver-{core,compile,ml,opt,analyze}`. **Read-only for this build — do not change it.** |
| **weaver-aspherix** (this repo) | `C:\Users\hylandc2\Workspaces\weaver-aspherix` | The DEM wrapper being rewritten. |
| **aspherix-study** | `C:\Users\hylandc2\Workspaces\aspherix-study` | The study repo. Its `walled_box` project really ran Aspherix 6.5.1 on 2026-07-12. |
| **flywheel** | `C:\Users\hylandc2\Workspaces\flywheel` | The **reference study**. Its wiring is what we copy. Read it first. |
| **system-template** | `C:\Users\hylandc2\Workspaces\system-template` | The copy-me skeleton `aspherix-study` was made from. |
| **Aspherix 6.5.1** (vendor) | `C:\Users\aschrader1\DCS-Computing\Aspherix-6.5.1` | Another user's profile — **readable, never run sims in-place**. Ships **183 example `.asx` decks** under `examples\` and the full command reference at `documentation\solver\Section_commands_aspherix.html`. |

### Files worth reading before writing code
- `Weaver/packages/weaver-compile/src/weaver/compile/lower.py` — `_resolve_callable`:196-204, `_resolve_params`:207-218, `_wrap`:221-231, `_lower_step`:234-244. **This is the seam.**
- `Weaver/packages/weaver-core/src/weaver/orchestrators/run.py` — `_evaluate_row`:26-64, `Run.run`:114-275.
- `flywheel/system/models/spindown.{json,py}` and `flywheel/projects/sim_opt.json` — the pattern being copied.
- `aspherix-study/artifacts/walled_box/case.asx` — the deck Aspherix **actually consumed**. Seed the template from this. (`artifacts/` is gitignored, so it exists only locally.)

### Environment (machine-specific, deliberately not committed)
- `ASPHERIX_BIN` → `C:\Users\aschrader1\DCS-Computing\Aspherix-6.5.1\bin\aspherix.exe`
- `ASPHERIX_MPI_BIN` → `C:\Program Files\Microsoft MPI\Bin\mpiexec.exe` (only needed for `nprocs > 1`)
- License is **RLM cloud** (`share\aspherix\Dayton-ls61.rlmcloud.com.lic`) — runs need outbound TCP 5053/5151 to `ls61.rlmcloud.com`. Verified working 2026-07-12.

---

## 1. Context — why we're doing this

`weaver-aspherix` today renders a `.asx` from a hardcoded 10-block Python vocabulary and launches Aspherix. It works, but it has two structural ceilings that make it useless for the actual goal (sweeping/optimizing DEM cases):

**1. The case cannot vary per design point.** `stages.py:47-59` reads the case from an orchestrator's param bag at *lower* time and freezes it into `AspherixRun`. Sampled values live in exactly one place — **the DB row** — and exactly one kind of code sees it: a **model step**, called as `fn(row, ctx, params)` (`lower.py:221-231`). An `Orchestrate` fold step never reads the row. So: no sweeps, no surrogate, no optimization — the entire reason to put DEM in Weaver. The 2026-07-12 run simulated three spheres and **recorded nothing**: no `.db`, no rows.

> ⚠️ **The `$var` escape you'd reach for is a trap.** `_resolve_params` (`lower.py:207-218`) injects a variable's *statically declared* `value` at compile time, **top-level keys only, no recursion**. For a swept variable declared `"value": [0.15, 0.75]` it substitutes **the list itself**. There is no path from a sample to an orchestrator param bag, and there never can be one.

**2. The vocabulary covers ~7% of real Aspherix.** Measured against the 183 vendor decks:

| command | decks | current renderer |
|---|---|---|
| `enable_gravity` | 137/183 | ✗ |
| `particle_distribution` | 139/183 | ✗ |
| `insertion` | 131/183 | ✗ |
| `region` | 107/183 | ✗ |
| `write_restart` | 100/183 | ✗ |
| `mesh_module` (motion/servo) | 73/183 | ✗ |
| `material_interaction_properties` (per-*pair*) | 50/183 | ✗ |
| **`create_particles`** — the renderer's *only* particle mechanism | **13/183** | ✓ |

27 decks run multiple `simulate` phases (202 `simulate` calls total); `assemble` emits exactly one, always last. **Three-quarters of real decks can't even turn gravity on.** This is not raisable by adding block renderers — you'd be reimplementing Aspherix.

Also: **nothing stages a mesh** (this package's own `aspherix/run.py:30-35` — `write_case` — is `mkdir` + `write_text`; the `meshes/plate.stl` in the test fixture exists in no repo — that golden has never been executed), and **nothing reads Aspherix output back**.

### The fix
The study owns a **real `.asx` deck** with `{{name}}` holes. `weaver-aspherix` becomes render → stage assets → launch → observe, wired as **model steps** of a `simulate` model bound to the built-in `weaver.core:run`. The wrapper owns **zero** Aspherix vocabulary — so the ceiling disappears permanently, and a new Aspherix keyword is a text edit in a study, not a package release.

**Outcome:** `uv run weaver run walled_box` sweeps N design points through real Aspherix, each with its own rendered deck and case dir, landing real KPIs in SQLite. Because `weaver.core:run` is already in `_TABLE_OPS` (`execute.py:158`), `preprocess → train → optimize → analyze` chain off it for free, exactly as in flywheel.

### Scope decisions (agreed with the user — respect these)
1. **Zero Weaver core changes.** Ride the existing seam. Deferred core work → §4.
2. **Readback = the timeseries CSV only.** No VTK reader this build.
3. **Categorical design variables: deferred.**
4. **Preload/restart (settle-then-vary): not this build.** The eventual target is a **Weaver-general PhaseLoop**; see §4.2.

---

## 2. `weaver-aspherix` — the package

**Layering rule:** `errors / template / assets / solver / results` import **zero weaver**. `steps.py` + `preflight.py` are the only weaver-aware files. Net ≈ **+240 LOC** after deleting 245.

### Delete
`render.py` (127), `stages.py` (63), `orchestrators/run.py` (80), `operators/build.py` (37), and both sub-package `__init__.py`s (`aspherix/__init__.py` itself stays — it exports `bind`). Drop `weaver-compile` from `pyproject.toml` dependencies **and** `[tool.uv.sources]` (`stages.py` is its only `src/` importer; `tests/test_stages.py` also imports it and is deleted in the same change — keep the dep-drop and the test-delete coupled). Regenerate `uv.lock` after the drop. Keep the PEP-420 namespace layout (`packages = ["src/weaver"]`, **no** `src/weaver/__init__.py`) — that's what lets `weaver.aspherix` co-exist with `weaver.core`.

### New / rewritten modules

| File | ~LOC | Contents |
|---|---|---|
| `errors.py` | 10 | `AsxError(RuntimeError)` |
| `template.py` | 50 | `render(text, ns)`, `placeholders(text)`, `token(v)` |
| `assets.py` | 40 | `stage(study_root, patterns, dest) -> list[Path]` |
| `solver.py` | 75 | the 4 kept launch fns + `timeout_s` (renamed from `run.py`) |
| `results.py` | 75 | `read_timeseries(path)`, `reduce(values, how)` |
| `preflight.py` | 90 | `check_model(module_file, study_root, *, on_error)` |
| `steps.py` | 130 | `bind(__file__) -> (run_case, observe, observe_bytes)` — **the per-row seam** |

#### `errors.py`
`AsxError(RuntimeError)` — **not** `LowerError`. The wrapper must not depend on weaver-compile. `RuntimeError` also preserves the 4 ported tests (`pytest.raises(RuntimeError, match="ASPHERIX_BIN")`). The validate-time need is met by the `on_error=` inversion in §3.

#### `template.py` — why `{{name}}`
Proven by the real deck, not theory: `case.asx:6` is `materials {m1}` — **literal single braces**, so `str.format` raises `KeyError: 'm1'`. And Aspherix's own variable syntax is `${var}`, so `string.Template` collides. `{{name}}` touches neither — and it's Jinja's delimiter, so swapping in Jinja later is a drop-in, not a rewrite. **Do not use Jinja on day 1**; this is a 5-line `re.sub`.

- `token()`: **`bool` must RAISE, checked *before* `int`** (`bool` is an `int` subclass; `str(True)` → `"True"` and `int(True)` → `1` are both silently wrong in a deck). `float` → `f"{v:.10g}"`, and **raise on non-finite**. `None` raises. `str` passes through **verbatim** (numeric formatting applies to numbers only; categoricals remain deferred). Any other type raises.
- `render()` must use a **function** replacement in `re.sub`, never a string one — a string repl re-interprets backslashes, so a Windows path in the namespace becomes `C:<TAB>mp\x`.
- Raise on `placeholders(text) - set(ns)`. Do **not** raise on unused `ns` keys (the row always carries extras).

#### `assets.py`
Reject absolute patterns and `..`. Glob from the study root. **Empty match → `AsxError` naming the pattern** (never silently stage nothing). `shutil.copy2` **preserving the repo-relative subpath** (`dest / src.relative_to(study_root)`), so `mesh id p file decks/meshes/plate.stl` resolves identically by hand from the study root *and* under Weaver (cwd = case dir). `copy2`, not hardlink — a hardlink means editing the source STL retroactively mutates every archived run.

#### `solver.py`
`resolve_aspherix_bin`, `resolve_mpi_bin`, `build_launch_argv` carry over **verbatim** — the launch contract (cwd = case dir; argv = `[bin, "-in", case_path.name]`; MPI wrapper only when `nprocs > 1`) is already correct. Three fixes/additions to `launch`:
- Pass `encoding="utf-8", errors="replace"`. Bare `text=True` decodes with the **locale** codec (cp1252 here) — one non-ASCII byte in the solver log would `UnicodeDecodeError` and fail a row for a cosmetic reason.
- **Write the log before re-raising on `TimeoutExpired`.** Today you'd get a killed process and no log.
- **Enforce a timeout.** `run_case` threads the `timeout_s` step param (default **600** — 10× the observed ~60 s walled_box run) into `launch(timeout=...)`, so a hung/diverged solver cannot stall the sequential sweep forever.

#### `results.py`
⚠️ **`simulation_data_aspherix.csv` is WHITESPACE-delimited despite the extension.** `sep=','` returns one column. This is the #1 parsing landmine. Split on any whitespace, take column names from the **header row**, **never index positionally**. Stdlib only (no pandas) — keeps the wrapper's sole dependency `weaver-core`.

Real header from the 2026-07-12 run:
```
          Time     Step    Atoms         KinEng            rke             Cu  Elapsed        CPULeft          T/CPU         Volume
             0        0        3   0.0078539816              0              0        0              0              0          0.001
```

`reduce` supports `last|first|min|max|mean|sum|delta` and **raises on a non-finite result** (see R4).

#### `preflight.py` — the highest-value file
Runs at model-module **import** time, which is inside `build_runtime_model` — so a failure becomes a **located `weaver validate` Diagnostic** instead of burning N solver launches. Checks:
1. Each step's `params["produces"] == step["produces"]` — the drift guard. Without it, a typo means `Observe`'s exact-keyset check fails on **every** row, after N solver launches.
2. The deck exists at `study_root / params["deck"]`.
3. `placeholders(deck) ⊆ consumes ∪ non-control params` (control keys: `produces`, `deck`, `assets`, `nprocs`, `timeout_s`, `file`, `column`, `reduce`).
3b. A non-control param key colliding with a consumed variable name is an error (the row must stay the single source of truth for schema columns).
4. **Every consumed placeholder is a variable `Populate` will actually fill** — mirroring `Physical.is_ranged` (`variable.py:253-271`), `Physical.fixed_value` (`:290-314`) and `latin_hypercube._sample`. This turns the silent-NULL categorical trap into a validate-time error.

#### `steps.py` — the per-row seam
```python
def bind(module_file, *, on_error=AsxError) -> tuple[Step, Step, Step]:
    """Resolve the study root from this file; preflight the sibling manifest.

    Returns (run_case, observe, observe_bytes)."""
```

- **Namespace = allowlist off `ctx["registry"]`, not a blocklist of reserved DB columns:**
  ```python
  ns = {n: row[n] for n in ctx["registry"].names if row.get(n) is not None}
  ```
  `registry.names` is *exactly* the schema columns, so this excludes all 9 non-schema columns (7 named in `_RESERVED_COLUMNS`, `database.py:39-47`, plus `valid`/`artifact_dir` injected by `Run` at `run.py:185-187`) with **no hardcoded list to drift**, and drops not-yet-produced outputs. That last part matters: an output column is `None` at construct time, so `{{final_kinetic_energy}}` correctly **raises** rather than rendering the literal string `"None"`.

- **Merge non-control step params into the render namespace.** `$`-params resolve into the step's `params` dict (`_resolve_params`, `lower.py:207-218`) — they never reach the row or the registry, so `{{n_timesteps}}` is fillable *only* from `params`. The namespace `run_case` renders from is `row-allowlist ∪ (params minus the control keys listed in preflight check 3)`; preflight check 3b rejects a collision with a schema column at validate time. Without this merge every row fails at render with an unresolved placeholder.

- **`bind(__file__)` is unavoidable and correct.** The per-row ctx is `{registry, build_state, artifact_dir, run_id, row_id}` — **no `repo_root`**. But `SimulateModel.module` is *mandatory* when a model has steps (`lower.py:183-184`) and is path-loaded from an absolute path. So the shim's `__file__` is the **only** study-root anchor a row-step gets. The wart is the mechanism. Resolve the root by walking up for the `system/` + `projects/` markers, **not** `parents[2]`. (Do **not** reuse weaver's `repo_root()` — it checks `packages/` + `tests/` and returns the *monorepo* root, `helpers.py:30-40`; this walk-up is deliberately new code.)

- `run_case` writes the deck into `ctx["artifact_dir"]` **directly** (no subdir), so the DB's `artifact_dir` column points straight at the case dir. It returns a `Domain` whose `info` surfaces `warnings_aspherix.txt` — a non-empty one is the difference between "the sweep ran" and "the sweep ran and every row silently fell back to a default contact model". The Domain itself never reaches the DB (`Run`'s scalar filter drops it — that's the §4.2 wall); the *recorded* warnings signal is the `warnings_bytes` output column via `observe_bytes` (§3).

- **Both steps take `produces` as an ordinary param.** `_wrap` never tells a callable its own output name, and `Observe` hard-checks the returned keyset. A reusable step shipped in an installed package must be told its output name.

- ⚠️ **`nprocs` is a step param (default 1) — never a variable, and no env override.** It isn't physics; as a registry entry it becomes an LHS/GA dimension and a preprocess feature. Worse, MPI domain decomposition perturbs the KPI at round-off — a design knob that silently changes the answer. (An env override was considered and rejected for the same reason: a stray shell variable would silently change every KPI and break Gate 2's byte-identity. §7's one-off MPI probe is a temporary `nprocs: 4` edit in the model json.)

### Tests
- **Delete:** all 19 in `test_render.py` (golden/line-offset, pinned to the block renderers), all 7 in `test_stages.py`, `tests/asx_util.py`, `tests/fixtures/basic.asx`, `tests/fixtures/walled_box.asx`, `tests/fixtures/study/**`.
- **Keep:** the launch-contract tests in `test_run.py` (14 total) → rename to `test_solver.py` (argv contract, binary/MPI resolution, cwd contract, log capture), **dropping the `write_case`/`assemble` tests** — that code is deleted with `render.py`. Keep the `_clean_env` autouse fixture. Add a timeout test (asserts both the kill and the written log).
- **Port:** the 4 execute-path tests from `test_operators.py` → `test_steps.py`: argv + `cwd == case dir`; nonzero exit → error; missing binary names `ASPHERIX_BIN`; `nprocs>1` without MPI names `ASPHERIX_MPI_BIN`.
- **New:** `test_template.py`, `test_assets.py`, `test_results.py`, `test_preflight.py`, `test_steps.py`, and the keystone:

> **`test_wiring.py`** — build `System`/`Model`/`Registry`/`Project` by hand, wrap the step fns in real `Operate`/`Observe` **exactly as `_lower_step` does** (replicate `_wrap` in 3 lines — the closures are 3-arg; handed raw to `Observe` they'd be invoked full-form as `fn(row, context)` and raise `TypeError`), stub `launch` to write a synthetic CSV, then run **real `Populate` + real `Run`** against a tmp SQLite. Proves the whole seam with no Aspherix and no *real* study repo — a tmp study dir with a minimal deck + model manifest is still required (`bind` preflights; `run_case` reads the deck). The hand-built `Registry` must reproduce `compose_registry` membership exactly (required outputs ∪ consumes, **no** `$`-params). This is the regression net for every gate below.

---

## 3. `aspherix-study` — the migration

Today it has **no `system/variables/*.json` and no `system/models/*.json`** — no column schema, no model. That's exactly why it can't sample, can't build a table, and can't read anything back. The migration is mostly additive.

**Delete:** `system/operators/aspherix.json`, `system/orchestrators/aspherix_run.json` (the 44-line DEM case embedded in a Weaver config).

**Add `decks/walled_box.asx`** — a **new top-level `decks/` dir**.

> ⚠️ **Not `assets/`.** `aspherix-study/.gitignore:3` is `**/assets/`, so a deck there would **never be committed**. (`**/artifacts/` is line 2 — that's why the 2026-07-12 outputs are local-only.)

Seed it **verbatim** from `artifacts/walled_box/case.asx` and introduce 4 tokens:

| token | kind | value |
|---|---|---|
| `coefficientRestitution {{coefficient_restitution}}` | swept | `[0.2, 0.9]` |
| `velocity ±{{impact_speed}}` (×3 lines) | swept | `[1.0, 4.0]` |
| `radius {{particle_radius}}` | fixed | `0.005` |
| `simulate time_steps {{n_timesteps}}` | `$`-param constant | `2000` |

Ranges are chosen so every row has **exactly one wall impact** inside the 0.02 s run (`t_contact = 0.015/v < 0.02` ⇒ `v > 0.75`; and the rebound at `e·v` never reaches the far wall — worst corner `e=0.9, v=4`: rebound 3.6 m/s × ≤0.01625 s ≈ 0.059 m < ~0.08 m available; confirm against the actual deck geometry at Gate 2).

**Add** `system/variables/{design,outputs,parameters}.json` (outputs include `final_kinetic_energy` *and* `warnings_bytes`, type int), `system/models/aspherix_dem.json` (`kind: "simulate"`, `module: "aspherix_dem.py"`, three steps):

1. `construct` → `run_case`, params `{produces: "case_domain", deck: "decks/walled_box.asx", nprocs: 1, timeout_s: 600, n_timesteps: "$n_timesteps"}`
2. `observe` → `observe`, params `{produces: "final_kinetic_energy", file: "simulation_data_aspherix.csv", column: "KinEng", reduce: "last"}` — the deck never names the CSV; it is an Aspherix **default** written to the case root, so the study must supply the filename (the wrapper stays vocabulary-free)
3. `observe` → `observe_bytes`, params `{produces: "warnings_bytes", file: "warnings_aspherix.txt"}` — persists the per-row solver-warnings signal (size in bytes, 0 if absent) as a queryable column

**Add** `system/orchestrators/populate_8.json`, shaped like flywheel's `populate_400.json`: `{sampler: "lhs", population: {count: 8, seed: 7}}`. This replaces the deleted `aspherix_run.json` — without it, validate fails on "unknown orchestrator". **Seed 7 is what makes the table `walled_box__aspherix_dem__7`** (the suffix is `project.seed`, `run.py:177`); `count: 8` is the sweep size Gates 3–4 assume.

And the shim — the study's **entire** Python surface:

```python
"""Aspherix row-steps bound to this study root; see aspherix_dem.json."""
from weaver.aspherix import bind
from weaver.compile.lower import LowerError

run_case, observe, observe_bytes = bind(__file__, on_error=LowerError)
```

> The `on_error=LowerError` **inversion** is what makes a bad deck a `weaver validate` Diagnostic: `validate.py:257-260` catches **only** `LowerError`. The *study* supplies the class (it already has weaver-compile via the CLI); the wrapper stays weaver-compile-free. Anything else raised from the module escapes as a raw traceback.

**Rewrite** `system/walled_box.system.json` → `required_outputs: ["final_kinetic_energy", "warnings_bytes"]` (required, not optional — optional outputs get no column), and `projects/walled_box.json` → `populate` + `run` stages **sharing one orchestrator** (`populate_8`; flywheel's exact trick, `sim_opt.json:8-9`) so both derive the same table `walled_box__aspherix_dem__7`. Costs one tolerated validate warning (`validate.py:171-172`).

**Copy verbatim from flywheel:** `system/operators/{populate,run}.json`. Their refs are weaver-core built-ins. The `run` operator must be **named `run`** — `validate.py:212` keys the System-contract coverage check off the operator *name*. **weaver-aspherix contributes no operator node at all** — that's the proof the design is right.

> ⚠️ **Every KPI must be a `required_output`.** `compose_registry` (`config/loader.py:59-61`) never merges `system.optional_variables`, so an `optional_output` gets **no column** and is never written. Confirmed end-to-end.

---

## 4. Deliverable: `docs/DEFERRED-WEAVER-CHANGES.md`

Write this file as part of the build. It captures the Weaver core work the **full** scope needs, so it's recoverable once the sweep works. Each item with file:line, a proposed fix, and a test.

### 4.1 Priority order
1. **`Run` is strictly sequential.** `_step_run` (`execute.py:61-70`) never passes `workers`. `Run` *supports* `workers>1` (`run.py:228-252`) but hard-rejects a pre-built compiler model there (`run.py:159-163` — the lowered `do_fn`s are unpicklable closures). Fine for 8 rows; 400 × 60 s is 6.7 h. Fix: a thread-pool path (Aspherix is subprocess-bound and releases the GIL), or make the lowered Model picklable. **Biggest practical win.**
2. **A `Domain` cannot outlive a row — the PhaseLoop wall.** See §4.2.
3. **`optional_outputs` is dead** (`loader.py:59-61`).
4. **Categoricals are silently NULL.** A declared categorical lands in **neither** `Registry.ranged` nor `.fixed` — no error, just a NULL column. weaver-ml already ships a `uniform_categorical` sampler whose *predicate* works verbatim on a core `Registry` — but it is **not** registered in the compiler's `_SAMPLERS` (`lower.py:46` — `lhs` only), so it's unreachable from the grammar without wiring. ⚠️ Fixing the sampler **without** weaver-opt's `DesignCodec` still breaks the GA *silently*, but the mechanism is: `DesignCodec.names` is ranged-numeric-only (`codec.py:56-70`), so a categorical is **dropped from the GA design space** (silently un-optimized). The `row_to_x` `float()` crash path surfaces *loudly* at gen-0 seeding (`adapters.py:180`); the bare-`except` swallow (`_INFEASIBLE = 1e6`) guards `model.run` inside `_ModelProblem._evaluate` (`adapters.py:100-119`), not the codec.
5. `Optimize` shares one `artifact_dir` across all GA candidates (`opt/optimize.py:96-100`) — the first thing that breaks when `optimize` is wired.
6. Fixed `type:"int"` variables arrive in the row as **floats**; `Populate` re-inserts on re-run; `failed` rows never retry (nor do rows stuck at `running` after a crash); `validate()` catches only `LowerError`.
7. **Fresh-clone breakage (verified still broken):** `Weaver/.gitignore:76` ignores `**/schemas/*.schema.json` while weaver-compile's pyproject force-includes that dir — the schema files are untracked+ignored (`git check-ignore` confirms), so a fresh clone fails `uv sync`. Durable fix = un-ignore + commit the schemas.

### 4.2 The preload / settle-then-vary mechanic (the user's stated target)

**Weaver already sketched this and never wired it.** `Phase` and `Stepper` are real, fully-tested operators; only `Stepper` is truly unconstructed (`Phase` *is* built in production by `wrap_phases`, `loader.py:361` — but that is the per-phase **observer** wrapper, a different mechanic from the Stepper-based domain-advance PhaseLoop needs). `stepper/__init__.py` says outright: *"the per-phase wiring is not built yet… a standalone, test-covered seam **awaiting the PhaseLoop work**"* — and it **names Aspherix** as an intended stepping backend. There's also a reserved-but-unused `phases_json` DB column (`database.py:46`).

**The wall is one filter:** `run.py:53-55` keeps only `{k: v for k, v in out.items() if k in registry.names and _is_db_scalar(v)}`. A `Domain` is neither, so **an artifact cannot outlive a row**. Persisting `domain.value` into its (already-created) TEXT column is the ~3-line change that unlocks everything downstream.

**The Aspherix side is a green light.** The vendor ships exactly this pattern in `examples\gui\Project_Hopper_Emptying\{Filling,Emptying}\input.asx`. Deck 2 is:
```
particle_shape sphere
read file ../Filling/restart/restart.latest
<... everything else re-declared from scratch ...>
```
- **Freely variable post-restart:** friction, restitution, Young's/Poisson, rolling friction, contact models, gravity, meshes + mesh motion, walls, regions, insertion/deletion, timestep, neighbor skin, all output settings.
- **Baked into the restart:** particle positions/velocities/radii/ids, and tangential contact history.
- **Must be held identical:** `particle_shape`, `simulation_domain`, units — and wall/mesh **IDs** (contact history is keyed to them; the real VTP carries arrays literally named `history_wx0`…).
- Treat **`density` as prefix-time only** (it's per-particle in the restart).
- Pass `reset_timestep yes` so every variant's output tree starts at step 0 and is comparable.
- The restart file is **portable and `-np`-agnostic** (though only bit-exact at matching `-np`). Copy it into N run dirs and resume N times.

---

## 5. Verification gates (in build order — each falsifiable)

**Gate 0 — wrapper, hermetic.** `uv run ruff check && uv run pyright && uv run pytest`. `test_wiring.py` yields `{complete: 3, failed: 1}` with **3 distinct** KPI values, and the failed row does not stop the others.

**Gate 1 — `weaver validate` clean.** In `aspherix-study`: exit 0, zero errors, and the shared-orchestrator op-mismatch warning **present** (don't assert an exact warning count — it's advisory output and future advisories would break the gate spuriously). Then falsify three ways and confirm each is a *located Diagnostic*, not a traceback and not a burned sweep — revert after each:
- misspell a deck token → `does not lower: … unresolved placeholder(s)`
- break a step's `params.produces` → drift error
- declare `coefficient_restitution` as `["low","high"]` → categorical-NULL error

**Gate 2 — deck fidelity: one real Aspherix run, no Weaver.** Hand-substitute the tokens to the original values (`e=0.4, v=2, r=0.005, n=2000`). Exit 0; `warnings_aspherix.txt` is **0 bytes**; `log_aspherix.txt` echoes `simulate time_steps 2000` (proves the parser reached the last line); last-row `KinEng` is **`0.0012529523`** — byte-identical to the 2026-07-12 run. If byte-identity fails on two back-to-back *identical* runs (solver nondeterminism), relax the assertion to rel-tol ≤ 1e-6 and record which held.

> ⚠️ **The deck that actually ran is CRLF** (verified: 30 CRLF, 0 bare LF). LF is the right default (deterministic, git-friendly) but is **unverified against this Windows binary**. This gate is the check; the fallback is one character (`newline="\n"` → `newline=""`). Same for `#` comments — the original ran comment-free.

**Gate 3 — end-to-end differential, no Aspherix.** Point `ASPHERIX_BIN` at a stub that records argv + cwd and writes a synthetic CSV. `weaver run walled_box` →
- 8 case dirs under `artifacts/walled_box/runs/<run_id>/<row_id>/`, each with a `case.asx`
- `diff` of row-0 vs row-1 `case.asx` changes **exactly the 4 token-bearing lines and nothing else** — in particular `materials {m1}` is byte-identical (**the literal-brace proof**)
- 8 rows `complete` with 8 **distinct** `final_kinetic_energy`
- the stub's recorded cwd == the case dir; argv == `[<bin>, "-in", "case.asx"]`

**Gate 4 — the real sweep + a deliberately-broken row.** Nuke `artifacts/walled_box/`. Poison one row: `weaver run walled_box --stages populate`, then against the study DB `UPDATE walled_box__aspherix_dem__7 SET coefficient_restitution = NULL WHERE row_id = (<any one row>)`, then `--stages run`. The namespace allowlist drops NULLs, so render raises unresolved-placeholder — the row fails **deterministically at render, burning no solver launch**. Then:
- `{complete: 7, failed: 1}` — **the sweep survives the failure**
- all 7 complete rows have `valid = 1` and a non-empty `post/` + `simulation_data_aspherix.csv`
- all 7 complete rows have `warnings_bytes = 0`
- **the analytic oracle holds for every complete row:**
  > `final_KE ≈ 1.96350e-3 · (e·v)²`, from 3 spheres of `m = 2500·(4/3)π(0.005)³ = 1.309e-3 kg`.
  > Verified against the recorded run: predicted initial KE `7.854e-3` matches the recorded `0.0078539816` **to 8 significant figures**; predicted final `1.2566e-3` vs recorded `1.2530e-3` = **0.29% error**. Assert `< 3%`.

  This makes the sweep self-checking **against physics**, not merely against itself.

**Gate 5 — the mesh, which has never once worked.** Add a hand-written 2-triangle ASCII `decks/meshes/plate.stl`, an `"assets": ["decks/meshes/*.stl"]` glob, and a `mesh` line in the deck. Prove (with the stub binary):
- the `.stl` lands at `<case_dir>/decks/meshes/plate.stl`
- `filecmp.cmp(src, dst, shallow=False)` is `True` (proves `copy2`, not a truncated re-write)
- the deck's relative path resolves to that exact file from cwd
- **the negative:** a glob matching nothing (`*.obj`) **fails the row loudly**, naming the pattern. Never silently stage nothing.

Then with the real binary: exit 0, and `log_aspherix.txt` echoes the `mesh` line.

---

## 6. Key risks

| | Risk | Mitigation |
|---|---|---|
| R1 | `**/assets/` is gitignored — a deck there is never committed | new top-level `decks/` |
| R2 | The proven deck is **CRLF**; LF unverified on this binary | Gate 2; one-character fallback |
| R3 | `simulation_data_aspherix.csv` is whitespace-, not comma-delimited | `line.split()`, parse the header, never index positionally |
| R4 | A diverged run writes `nan`, which passes `_is_db_scalar`; `Run`'s validity check is `is None` → **row persisted `valid=1`** | `reduce()` raises on non-finite |
| R5 | `re.sub` string-repl eats backslashes | function repl |
| R6 | `Populate` double-inserts on a full re-run (16 rows, 8 duplicated) | nuke `artifacts/walled_box/` between runs, or `--stages run` |
| R7 | `subprocess` locale (cp1252) decoding fails a row cosmetically | `encoding="utf-8", errors="replace"` |
| R8 | The shim imports ~2× per `weaver run` (`assert_valid` then `_step_run`) | keep `bind()` cheap; never put expensive work in it |
| R9 | `failed` rows never retry (`Run` selects `status='pending'`) | manual `UPDATE … SET status='pending'` |

**Housekeeping:** regenerate `uv.lock` after the weaver-compile drop; add the new vocabulary (aspherix, asx, nprocs, mpiexec, KinEng, restitution, …) to both repos' `cspell.json`; commit `docs/` (this plan + `DEFERRED-WEAVER-CHANGES.md`). There is no CI — Gate 0 is manual.

---

## 7. Cheap, worth doing before any future VTK work

Re-run `walled_box` once with `nprocs: 4` (a temporary edit in `aspherix_dem.json`) and list `post/dump_particle_1000/`. That single command **empirically settles the MPI multi-piece filename convention**, which any future VTK reader depends on. Note the **serial** 2026-07-12 run already emits 8 pieces per step (`_1_0.._7_0.vtp` + `_8_0.vtu`) — piece-concatenation is mandatory even at np=1; the probe settles only how the pieces multiply under `-np`. (Also: an extra `aspherix.log` sits at the case root beside `log_aspherix.txt`.)

The safe reader contract (for when it's built): read `post/aspherix_simulation.pvd` → the `.vtm` → resolve blocks **by `name`** (`"Particles"`, `"Meshes"`) → **concatenate every piece**. Never glob `*.vtp`; never hardcode the `_7_0` leaf index (it shifts with the number of meshes, and under `-np 8` a naive glob silently reads 1/8 of the particles). The vendor's own ParaView plugin (`share\ParaView\aspherix\aspherix_particle_filter.py`) is the de facto spec — it iterates and appends every piece.
