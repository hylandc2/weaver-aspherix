# Deferred Weaver core changes

The 2026-07-14 wrapper rewrite deliberately made **zero Weaver core changes** — it rides
the existing `simulate`-model seam. This file records the core work the *full* scope
needs, so it stays recoverable now that the sweep works. Each item: where, the fix, and
how to test it. Facts below were verified against the code on 2026-07-14.

## 1. `Run` is strictly sequential (biggest practical win)

`_step_run` (weaver-core `execute.py:61-70`) never passes `workers`, and `Run.run`
hard-rejects a pre-built compiler model with `workers > 1` (`run.py:159-163` — the
lowered `do_fn`s are unpicklable closures), while the ProcessPool path (`run.py:228-252`)
exists and works for dotted-path models. Fine for 8 rows; 400 × 60 s ≈ 6.7 h.

**Fix:** a thread-pool path for pre-built models — Aspherix is subprocess-bound and
releases the GIL — or make the lowered Model picklable (e.g. reconstruct-from-names in
the worker, as `_init_worker` already does for the dotted path).
**Test:** a `test_wiring.py`-style run (stubbed launch with a `sleep`) asserting
`workers=4` wall-clock < ½ sequential and identical row results.

## 2. A `Domain` cannot outlive a row — the PhaseLoop wall

`_evaluate_row` keeps only `{k: v for ... if k in registry.names and _is_db_scalar(v)}`
(`run.py:53-55`); a Domain is neither, so an artifact handle is dropped before the DB.
There is a reserved-but-unused `phases_json` column (`database.py:46`).

**Fix:** persist `domain.value` (a path string) into its already-created TEXT column —
a ~3-line change in `_evaluate_row` — then build the PhaseLoop on top.
**Status of the parts:** `Stepper` is real, tested, and truly unconstructed;
`Phase` *is* constructed in production, but only as the per-phase **observer** wrapper
(`wrap_phases`, `loader.py:361`) — a different mechanic from the Stepper-based
domain-advance loop. `stepper/__init__.py` names Aspherix as an intended backend.

**The Aspherix side is a green light** (vendor `examples/gui/Project_Hopper_Emptying/`
ships exactly the settle-then-vary pattern: deck 2 opens with
`read file ../Filling/restart/restart.latest`):
- Freely variable post-restart: friction, restitution, Young's/Poisson, rolling friction,
  contact models, gravity, meshes + motion, walls, regions, insertion/deletion, timestep,
  neighbor skin, all output settings.
- Baked into the restart: particle positions/velocities/radii/ids + tangential contact
  history. Treat `density` as prefix-time only (per-particle in the restart).
- Must be held identical: `particle_shape`, `simulation_domain`, units, and wall/mesh
  **IDs** (contact history is keyed to them — the VTP carries `history_wx0`… arrays).
- Pass `reset_timestep yes` so every variant's output tree starts at step 0.
- The restart is portable and `-np`-agnostic (bit-exact only at matching `-np`).

## 3. `optional_outputs` is dead

`compose_registry` (`loader.py:59-61`) merges only `system.required_variables` and
`model.input_variables`; an `optional_output` gets no column and is never written.
That is why `warnings_bytes` had to be a *required* output.
**Fix:** merge `optional_variables` too (or remove the grammar field).
**Test:** declare an optional output, run populate, assert the column exists.

## 4. Categoricals are silently NULL

A declared categorical (`value: ["low","high"]`) lands in **neither** `Registry.ranged`
nor `.fixed` (`variable.py:253-271`, `:290-314`) — no error, a NULL column. The wrapper's
preflight turns this into a validate-time Diagnostic for deck tokens, but core Populate
still accepts it silently. weaver-ml ships `uniform_categorical` whose predicate works on
a core Registry, but it is **not** in the compiler's `_SAMPLERS` (`lower.py:46` — `lhs`
only), so it is unreachable from the grammar without wiring.

⚠️ Fixing the sampler **without** weaver-opt's `DesignCodec` breaks the GA *silently* —
but the failure mode is subtler than a swallowed crash: `DesignCodec.names` is
ranged-numeric-only (`codec.py:56-70`), so a categorical is **dropped from the GA design
space** (silently un-optimized). The `row_to_x` `float()` crash path would surface loudly
at gen-0 seeding (`adapters.py:180`); the bare-`except` `_INFEASIBLE = 1e6` swallow
guards `model.run` inside `_ModelProblem._evaluate` (`adapters.py:100-119`), not the codec.

## 5. `Optimize` shares one `artifact_dir` across all GA candidates

`opt/optimize.py:96-100` narrows the artifact dir once per run; every candidate writes
into it. First thing that breaks when `optimize` is wired over `aspherix_dem` (each
candidate is a full case dir). **Fix:** per-candidate subdirs keyed by individual hash.

## 6. Smaller items

- Fixed `type:"int"` variables arrive in rows as **floats** (`fixed_value` coerces,
  `variable.py:307,310`; the int-cast in `latin_hypercube._sample` covers ranged only).
- `Populate` double-inserts on a full re-run — no dedup/upsert (`populate.py:95-104`,
  `database.py:301-304`). Mitigation today: nuke `artifacts/<project>/` or `--stages run`.
- `failed` rows never retry (`Run` selects `status='pending'`, `run.py:196`); rows stuck
  at `running` after a crash never retry either.
- `validate()` converts only `LowerError` to Diagnostics (`validate.py:257-260`); any
  other exception from a model module import is a raw traceback.
- **Fresh-clone breakage (verified still broken 2026-07-14):** `Weaver/.gitignore:76`
  ignores `**/schemas/*.schema.json` while weaver-compile's pyproject force-includes that
  dir — the schemas are untracked+ignored, so a fresh clone fails `uv sync`. Durable fix:
  un-ignore + commit the schemas.

## 7. Empirical note for any future VTK reader

The **serial** walled_box run already emits 8 pieces per step
(`post/dump_particle_<n>/` holds `_1_0.._7_0.vtp` + `_8_0.vtu`) — piece-concatenation is
mandatory even at np=1, and the leaf index shifts with the number of meshes. Read
`post/aspherix_simulation.pvd` → the `.vtm` → resolve blocks **by name** (`"Particles"`,
`"Meshes"`) → concatenate every piece; never glob `*.vtp` or hardcode a leaf index. The
vendor's own ParaView plugin (`share/ParaView/aspherix/aspherix_particle_filter.py`) is
the de facto spec. Still worth one `nprocs: 4` run to settle how pieces multiply under
`-np` (temporary edit in `aspherix_dem.json` — nprocs is deliberately param-only).
