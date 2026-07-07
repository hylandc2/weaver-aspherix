# weaver-aspherix — functionality profile

> A pure node catalog for the weaver-aspherix package — every public node and factory, profiled as
> *what it is*, *what it can do*, and *briefly how it does it*. Section numbering is stable (§0–§6);
> sections the package has nothing for (§1 Variables, §4 Integration adapters) are omitted.

---

## §0 Scope

weaver-aspherix wraps the **Aspherix® DEM solver** as a config-driven Weaver stage. The functionality
arc is **render → assemble → write → launch**: pure renderers turn a nested `case` mapping into an
Aspherix input-script (`.asx`), an assembler orders the blocks, a writer lands the deck in the
pipeline's artifact dir, and a launcher builds the `mpirun` command. It introduces **no new node
category** — the operator surface is a configured `Operate` (the `build_case` factory), and the run
coordinator is **one** new `Orchestrator` subclass (`AspherixRun`), wired into a stage via `Orchestrate`.
The entire `.asx` text layer is standard-library Python. **Nothing heavy loads at import time:** the
solver runs out-of-process as an `mpirun` subprocess (currently a **dry run** — the argv is built and
returned, not executed), so no domain library enters the import graph.

## §2 Orchestrators

### `AspherixRun(*, case, nprocs=4)` — `Orchestrator`
- **Is:** the run coordinator — assemble a DEM case into a `.asx`, write it, and build the `mpirun` launch.
- **Can do:** writes `<artifact_dir>/case.asx` from `case`; returns a launch summary
  `{case, argv, nprocs, launched}`; `check()` preflights `nprocs`.
- **Fields:**

  | Field | Type | Default | What it controls |
  |---|---|---|---|
  | `case` | `Mapping[str, Any]` | — | the nested DEM case blocks (numeric values are string tokens, e.g. `"5e6"`) |
  | `nprocs` | `int` | `4` | MPI process count placed in the launch argv |

- **Runtime — `run(*, context)` reads:**

  | Key | Type | What it's for |
  |---|---|---|
  | `context["artifact_dir"]` | `str` | directory the `case.asx` is written into |

- **How:** `run` calls `write_case(self.case, Path(context["artifact_dir"]))` (→ `assemble` in
  `render.py`) then `build_launch_argv(case_path, nprocs=self.nprocs)`. The launch is a **dry run** —
  the argv is returned with `launched=False`; a licensed install replaces the one marked line with
  `subprocess.run(argv, cwd=case_path.parent, check=True)`. `check` returns a one-item list when
  `nprocs` is not a real `int >= 1` (bools rejected), mirroring the `Operator.check` list-of-strings
  contract. Subclasses the ABC because it is a *genuinely new* orchestrator, not a flavor of an existing one.
- **Where:** `src/weaver/aspherix/orchestrators.py` — `AspherixRun`.

## §3 Operators & factories

### `build_case(name, *, case) -> Operate` — factory → `Operate`
- **Is:** factory returning a configured `Operate` that writes the `.asx` deck — the fine-grained
  "build the input deck" seam (build only, no launch).
- **Can do:** renders + writes `<artifact_dir>/<name>.asx`; returns `{name: <path str>}` into pipeline state.
- **Inputs:**

  | Input | Type | Required | Default | What it does |
  |---|---|---|---|---|
  | `name` | `str` | yes | — | step name; also the `output_field` and the deck filename stem (`<name>.asx`) |
  | `case` | `Mapping[str, Any]` | yes | — | the nested DEM case blocks |

- **How:** closes over `case`; the returned `Operate`'s `do_fn(state, ctx)` calls
  `write_case(case, Path(ctx["artifact_dir"]), filename=f"{name}.asx")` and returns the path under `name`.
  `output_field=name` is declarative only (`Operate` does not validate the returned keyset). A factory —
  never a category subclass.
- **Where:** `src/weaver/aspherix/operators.py` — `build_case`.

## §5 Utils catalog

The pure `.asx` text layer (`render.py`, `run.py`) — no Weaver, no Aspherix dependency, testable in
isolation:

- `assemble(params) -> str` — concatenate every block in the order Aspherix requires (DEM guide §6).
- `init_block` / `materials_block` / `contact_block` / `timestep_block` / `particles_block` /
  `mesh_block` / `output_block` / `run_block` — one pure `params -> str` renderer per `.asx` block.
- `write_case(params, out_dir, *, filename="case.asx") -> Path` — assemble + write the deck; returns its path.
- `build_launch_argv(case_path, *, nprocs=4) -> list[str]` — build `["mpirun", "-np", N, "aspherix",
  "-in", <case name>]` (dry run — returned, not executed; uses `case_path.name` since the launch runs
  with the case dir as cwd).

Private helper: `_triple` renders an `(x, y, z)` tuple as the parenthesised `.asx` form.

## §6 Cross-package wiring

**The section a study-repo integrator reads first.**

- **Ref strings this package exposes** — the JSON-facing surface; keep stable across refactors:
  - Stage-builder refs (operator JSON `ref`): **`weaver.aspherix.stages:build_aspherix_stage`** — the
    config-driven stage. Reads the DEM `case` and optional `nprocs` from the bound orchestrator's open
    param bag (`OrchestratorNode.model_extra`); validates them with located `LowerError`s (missing case
    blocks, bad `nprocs`); wraps `AspherixRun` via `Orchestrate(stage.name, ..., output_field=stage.name,
    expect=dict)`. Non-table stage — does **not** call `build_project`. A complete minimal study wiring
    it lives in `tests/fixtures/study/`.
  - Model-step refs (dotted step `ref` in simulate-model JSON): **none yet** — `physics.py` is not
    authored (reserved for reductions / quality functions per DEM guide §12).
- **Lazy heavy-dependency policy:** none required — the package is standard-library plus
  weaver-core / weaver-compile. The Aspherix solver runs **out-of-process**; when the dry-run launch is
  made live, `subprocess` is stdlib and the call sits inside `AspherixRun.run` (never at module level).
  No third-party domain library enters the import graph.
- **Dependency edges:**
  - **weaver-core:** `Operate` (`operators.py`), the `Orchestrator` ABC (`orchestrators.py`),
    `Orchestrate` + `Operator` (`stages.py`).
  - **weaver-compile (blessed surface):** `LowerError`, `ProjectNode`, `StageNode`, `Workspace`
    (`stages.py`). Does not import `build_project` (non-table stage).
  - **External (lazy):** none today; a live launch will use stdlib `subprocess` inside `AspherixRun.run`.
  - **Consumed by:** study repos wire the stage through the JSON `ref` — no Python import of this package;
    `tests/fixtures/study/` is the worked example.
- **Import side effects:** none beyond re-exports. The leaf `__init__.py` re-exports `build_case`,
  `AspherixRun`, `assemble`, `write_case`, `build_launch_argv`, and `build_aspherix_stage`; because the
  last pulls the blessed `weaver.compile` surface, `import weaver.aspherix` transitively imports
  `weaver.compile` (first-party, light). No other side effects.
