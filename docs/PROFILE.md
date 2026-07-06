# weaver-foo — functionality profile

> **Fill this in.** This skeleton mirrors Weaver's first-party `docs/packages/` profile format, so an
> external package documents itself the way a first-party one does: a **pure node catalog** — every
> public node and factory, profiled as *what it is*, *what it can do*, and *briefly how it does it*.
>
> **Two rules keep profiles scannable side by side:** section numbering is **stable** (§0–§6 — never
> renumber), and a section the package has nothing for is **omitted entirely** — except §6, which every
> package fills in ([AUTHORING_GUIDE.md](AUTHORING_GUIDE.md) §10). Replace `foo` with your leaf name.

**Per-symbol entry format** (§1–§4), one entry per public symbol — private helpers get no standalone
entry; describe their role inside the **How** of the public symbol they serve:

```
### `signature(...) -> ReturnType` — <AST kind>          e.g. `Orchestrator`, `factory → Constrain`
- **Is:** one-line essence.
- **Can do:** capabilities / what it produces.
- **Inputs:** / **Fields:** table — callables get an Inputs table
  (`Input · Type · Required · Default · What it does`); config dataclasses / data carriers get a
  Fields table (`Field · Type · Default · What it controls`); orchestrators additionally get a
  runtime table of the `run(...)` (or `state` + `ctx`) keys they read.
- **How:** brief mechanism — fold in the private helpers it drives. Every claim traces to source.
- **Where:** module + symbol (file-relative link, `#L<line>` anchor if you keep lines current).
```

---

## §0 Scope

One short paragraph: what this package adds to the AST; the functionality arc (e.g. *solve → probe →
gate*); whether it introduces a new node category or only configured instances of existing ones; what
stays lazy at import time.

## §1 Variables

Schema / config dataclasses and data carriers the package introduces. Omit if none.

- [ ] `<Carrier>` — data carrier / config dataclass: …

## §2 Orchestrators

`run()` coordinators — the orderings operators can't express alone. Omit if none.

- [ ] `<Sweep>(...)` — Orchestrator: …

## §3 Operators & factories

Grouped by category (Constrain / Evaluate / Observe / Sample / Operate / Repair, plus any new
category). **Each factory states which category instance it returns.**

- [ ] `<factory>(...)` — factory → `<Category>`: …

## §4 Integration adapters

Only for packages that bridge an external library (pymoo in weaver-opt; sklearn / keras in weaver-ml).
Omit if none.

- [ ] `<Adapter>` — factory → `<external type>`: …

## §5 Utils catalog

Lighter — one line per symbol: *what + how*. Omit if none. May end with a one-line note that
underscore-prefixed private helpers exist.

- [ ] `<symbol>` — …

## §6 Cross-package wiring

**The section a study-repo integrator reads first — always fill it in.**

- **Ref strings this package exposes** — the JSON-facing surface; keep them stable across refactors:
  - [ ] Stage-builder refs (operator JSON `ref`, `pkg.module:builder` shape —
    [authoring-stages.md](authoring-stages.md)): e.g. `weaver.foo.stages:build_foo_stage`, …
  - [ ] Model-step refs (dotted step `ref` in simulate-model JSON —
    [authoring-models.md](authoring-models.md)): e.g. `weaver.foo.physics:efficiency`, …
- **Lazy heavy-dependency policy:** which heavy/domain imports stay inside callables (never at module
  level), and which callables pull them.
- **Dependency edges:**
  - [ ] Depends on weaver-core: which classes (`Operate`, `Constrain`, `Orchestrator`, …)?
  - [ ] Depends on weaver-compile: which blessed-surface names your StepBuilders import?
  - [ ] External (lazy): third-party libraries and where each loads.
  - [ ] Consumed by: downstream packages / study repos that import your modules directly.
- **Import side effects:** none expected — the leaf `__init__.py` is a curated re-export
  ([AUTHORING_GUIDE.md](AUTHORING_GUIDE.md) §5). State explicitly if importing `weaver.foo` does more.
