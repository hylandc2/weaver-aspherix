# Authoring Operator Factories — `operators.py`

Weaver's operator doctrine has two clauses. Know which one you are in:

1. **Same `do()` shape → a factory.** New behavior that fits an existing category's
   `do()` signature is a **factory function** returning a configured instance of that
   category (`Operate` / `Evaluate` / `Constrain` / `Observe`) with a closure capturing
   its parameterization. **This is the template default** — everything in this file.
2. **A genuinely new `do()` signature → a new category.** A new category is a direct
   subclass of the base `weaver.base.Operator` whose built-in behaviors are still
   factories — classmethod constructors (weaver-ml's `Fit.standard`,
   `Audit.permutation`) or one-per-module preset functions (weaver-analyze's `Show` /
   `Tell` plots). This is **rare and deliberate**: those packages subclass `Operator`
   directly, **never** an existing category.

Either way: **never subclass an existing category (`Operate` / `Evaluate` /
`Constrain` / `Observe`) for new behavior.** If your callable fits a category's shape,
write a factory. If it truly doesn't, you are designing a new category — a package-level
decision, not an `operators.py` entry.

Create `src/weaver/foo/operators.py` (substituting your leaf name for `foo`), using the
reference module below as the starting point. Re-export your public factories from
`src/weaver/foo/__init__.py` ([AUTHORING_GUIDE.md](AUTHORING_GUIDE.md) §5) and add them
to the name list in `tests/test_imports.py` ([authoring-tests.md](authoring-tests.md)).

---

## The four category contracts

- **`Operate` — `do_fn(state, ctx) -> Mapping[str, Any]`, strictly two positional
  arguments** (no arity detection). `do()` returns the callable's mapping **as-is** —
  any keys, including none; the only enforcement is that the result is a `Mapping`.
  `output_field` is **declarative metadata only** — it names the column this step is
  expected to produce for static coverage checks and is *not* validated against the
  returned keyset.

- **`Evaluate` — two callable shapes, auto-detected by arity:**
  - **Full form `fn(row, context) -> Mapping[str, Any]`** — exactly two positional
    parameters. The returned keyset must equal the declared output variables
    **exactly**; a mismatch raises `ValueError` naming the missing/extra keys.
  - **Calculator short form `fn(row) -> scalar`** — exactly one positional parameter.
    The scalar is wrapped as `{output_field: scalar}` and is **not** keyset-validated.
    Pair it with `output_field` (single output only).

  **Arity is the contract switch.** A `do_fn` with a single positional parameter
  silently becomes a calculator — if you meant the full form and dropped `context`,
  nothing warns you; the keyset validation you expected simply never runs.

  Declare outputs with **exactly one** of `output_field=` (single, `str`) or
  `output_fields=` (multi, `tuple[str, ...]`) — neither or both raises `ValueError`.
  Set `field_deps` to the input columns the callable reads.

- **`Constrain` — `check=` is a constructor parameter**, a callable
  `(row) -> Optional[Violation]` invoked via `Constrain.do(row)`: return a `Violation`
  on failure, `None` on pass. **Do not confuse it with the `.check` attribute** — that
  is the inherited `Operator.check(context) -> list[str]` setup-verification API (a
  different thing; see the signature/check section below). `requires` lists the row
  fields the rule reads; `do()` returns `None` (skip) while any of them is absent.
  Two more knobs:
  - **`mode="hard" | "soft"`** (default `"hard"`). Hard: orchestrators reject the row
    on a `Violation`. Soft: orchestrators accept the row and the severity magnitude
    feeds an optimizer's penalty term. The base class carries `mode` as informational
    metadata — honoring the hard/soft split is the consuming orchestrator's job.
  - **`severity(row) -> float`** — signed magnitude, convention `<= 0` satisfied,
    `> 0` violated. When `severity_fn` is given it is used (an exception inside it is
    coerced to `1.0`); a missing `requires` field yields `0.0`; without a
    `severity_fn` the default is binary `{0.0, 1.0}` derived from `do()`.

- **`Observe` — the fourth column producer.** Semantically distinct: an Observe's
  values come from **calling something external** (a sensor, sim solver state, an ML
  inference endpoint) rather than deriving from row data — that split is what lets
  identical downstream Evaluates run against different Models (sim, ML, lab, plant).
  Mechanically it is identical to `Evaluate`: same arity detection, same exact-keyset
  rule, same `output_field`/`output_fields` resolution. When driven from a **phased**
  model step, the produced column is labeled `<phase>_<key>` — the operator
  self-labels under a `Phase`, and the compiler applies the same prefix when lowering
  a phased `observe` step.

---

## Core presets — don't reinvent them

weaver-core ships preset factories for the common cases, one per module
(`from weaver.operators.evaluate.ratio import ratio`):

- **Evaluate:** `delta` (difference), `ratio` (quotient), `in_bounds` (validity flag).
- **Constrain:** `lower_bound`, `upper_bound`, `in_set`, `integer_constraint`,
  `ref_compare`, `callable_compare`, `predicate_constraint`.

Reach for a preset before writing a factory. `my_ratio` below **intentionally
duplicates the `ratio` preset** as a worked teaching example — note the real preset
additionally returns `NaN` on a zero denominator (a queryable sentinel) where the
teaching version lets the `ZeroDivisionError` surface.

---

## Reference module

One worked factory per category: `my_solver` (`Operate`), `my_ratio` (`Evaluate`),
`my_in_range` (`Constrain`), and `my_probe` (`Observe`).

**`src/weaver/foo/operators.py`**

```python
"""Custom operator factories for weaver.foo.

Each public name is a FACTORY: it returns a configured instance of an existing
Weaver operator category (Operate / Evaluate / Constrain / Observe). Behavior
is captured in closures at call time — these are NOT subclasses.

Contracts:
  - my_solver -> Operate: do_fn(state, ctx); output_field is declarative only.
  - my_ratio -> Evaluate: full-form do_fn(row, ctx); returned keyset must equal
    {output_field} exactly.
  - my_in_range -> Constrain: check(row) -> Violation | None; severity <= 0
    satisfied, > 0 violated; mode= passes through ("hard" rejects the row,
    "soft" feeds an optimizer penalty).
  - my_probe -> Observe: full-form do_fn(row, ctx); same exact-keyset rule as
    Evaluate. A real Observe queries an external backend; this one reads a row
    field so the reference package runs anywhere.
"""

from __future__ import annotations

from typing import Any, Literal, Mapping, Optional

from weaver.operators.constrain import Constrain, Violation
from weaver.operators.evaluate import Evaluate
from weaver.operators.observe import Observe
from weaver.operators.operate import Operate

__all__ = ["my_in_range", "my_probe", "my_ratio", "my_solver"]


def my_solver(
    name: str,
    *,
    solver_class: type,
    config_dict: dict[str, Any],
) -> Operate:
    """Factory: returns a configured Operate that instantiates and runs a solver.

    do_fn(state, ctx) -> Mapping — strictly two positional arguments.
    `output_field` is declarative metadata only; Operate.do() does NOT validate
    the returned keyset against it.
    """

    def _do(state: Mapping[str, Any], context: Mapping[str, Any]) -> Mapping[str, Any]:
        # Hyperparams / registry / prior artifacts come from context.
        hyperparams = context.get("hyperparams", {})

        # Thread interim state: solver instance, sampled population, etc.
        solver = solver_class(**{**config_dict, **hyperparams})
        population = solver.sample(state.get("domain"))

        return {"solver": solver, "population": population}

    return Operate(
        name=name,
        do_fn=_do,
        output_field="solver",
        info={"factory": "my_solver", "config": config_dict},
    )


def my_ratio(
    name: str,
    *,
    numerator: str,
    denominator: str,
    output_field: str,
) -> Evaluate:
    """Factory: returns Evaluate filling output_field with row[numerator] / row[denominator].

    Full-form do_fn(row, context) -> Mapping; the returned keyset must equal
    the declared output variable EXACTLY ({output_field} here).
    """

    def _do(row: Mapping[str, Any], context: Mapping[str, Any]) -> Mapping[str, Any]:
        del context
        return {output_field: float(row[numerator]) / float(row[denominator])}

    return Evaluate(
        name=name,
        do_fn=_do,
        output_field=output_field,
        field_deps=(numerator, denominator),
        info={"fn": "my_ratio", "numerator": numerator, "denominator": denominator},
    )


def my_in_range(
    field_name: str,
    minimum: float,
    maximum: float,
    *,
    mode: Literal["hard", "soft"] = "hard",
) -> Constrain:
    """Factory: returns Constrain requiring row[field_name] in [minimum, maximum].

    The `check` callable is invoked via Constrain.do(row) -> Violation on
    failure, None on pass; `requires` auto-skips the check when field_name is
    absent from the row. `mode` passes through: "hard" (default) rejects the
    row on Violation; "soft" accepts it and the severity magnitude feeds an
    optimizer's penalty term.
    """
    name = f"in_range:{field_name}:{minimum}:{maximum}"

    def _check(row: Mapping[str, Any]) -> Optional[Violation]:
        v = float(row.get(field_name, float("nan")))
        if v < minimum or v > maximum:
            return Violation(
                constraint_name=name,
                message=f"{field_name}={v} not in [{minimum}, {maximum}]",
                field=field_name,
            )
        return None

    def _severity(row: Mapping[str, Any]) -> float:
        v = float(row.get(field_name, float("nan")))
        if v < minimum:
            return minimum - v
        if v > maximum:
            return v - maximum
        return 0.0

    return Constrain(
        name=name,
        check=_check,
        requires=frozenset({field_name}),
        severity_fn=_severity,
        mode=mode,
        info={"factory": "my_in_range", "field": field_name, "minimum": minimum, "maximum": maximum, "mode": mode},
    )


def my_probe(
    name: str,
    *,
    source_field: str,
    output_field: str,
) -> Observe:
    """Factory: returns Observe filling output_field by "reading an instrument".

    Full-form do_fn(row, context) -> Mapping; same exact-keyset rule as
    Evaluate. A production Observe callable calls something EXTERNAL — reads a
    thermocouple via ctx["case_dir"], polls solver state, hits an inference
    endpoint. This reference probe reads row[source_field] instead so the
    package imports and tests with no backend attached.
    """

    def _do(row: Mapping[str, Any], context: Mapping[str, Any]) -> Mapping[str, Any]:
        del context
        # A real probe would call out here (sensor, sim snapshot, ML client).
        return {output_field: float(row[source_field])}

    return Observe(
        name=name,
        do_fn=_do,
        output_field=output_field,
        info={"factory": "my_probe", "source_field": source_field, "output_field": output_field},
    )
```

---

## Notes on each factory

### `my_solver` (`Operate`)

- Hyperparams, registries, and prior artifacts arrive via `context`; merge them over the
  factory's captured `config_dict` when instantiating.
- Return interim state (the solver instance, the sampled population, …) in the result
  Mapping so downstream steps can use it — `Operate` is the one category that lets a
  step thread free-form state.
- `output_field="solver"` is metadata only — `Operate.do()` does **not** validate that
  the returned keyset matches it.

### `my_ratio` (`Evaluate`)

- The returned keyset must be exactly `{output_field}` — anything else raises
  `ValueError`.
- `field_deps=(numerator, denominator)` declares the input columns the evaluation reads;
  this feeds real dataflow verification (next section), not just documentation.
- Deliberately mirrors the core `ratio` preset (which also guards a zero denominator
  with `NaN`) — a worked example of the factory shape, not new capability.

### `my_in_range` (`Constrain`)

- The `check` closure returns a `Violation` (with `constraint_name`, `message`,
  `field`) on failure and `None` on pass; callers invoke it through
  `Constrain.do(row)`.
- `requires=frozenset({field_name})` makes `do()` skip (return `None`) and
  `severity()` return `0.0` while the field is absent from the row.
- `_severity` returns how far out of range the value is (`0.0` when in range) — the
  `<= 0` satisfied / `> 0` violated convention optimizers consume. If it ever raises,
  the base class coerces the result to `1.0`.
- `mode` passes straight through: `"hard"` rows are rejected on violation; `"soft"`
  rows are accepted and scored.

### `my_probe` (`Observe`)

- Same construction and validation rules as `Evaluate` — full-form callable, exact
  keyset. The difference is the semantic contract: a real probe's value comes from an
  external call, not from row math. Keep the reference version row-fed so tests run
  without hardware; put the backend call where the comment marks it.
- Under a `Phase` (or a phased model step), the produced column becomes
  `<phase>_<output_field>` automatically — declare the *unprefixed* name; the phase
  labeling is applied for you.

---

## `signature()` and `check()`: declare inputs truthfully

Every operator inherits two introspection APIs from `weaver.base.Operator`, and each
category implements them as **one-line read-models over the constructor fields you
already pass** — `field_deps` (`Evaluate`), `requires` (`Constrain`),
`output_field` / `output_fields` (`Operate` / `Evaluate` / `Observe`):

- `signature() -> Signature(requires, produces)` — the context-free "what do I read /
  write" declaration.
- `check(context) -> list[str]` — the contextual "am I satisfied here" preflight; the
  default reports each `signature().requires` name missing from `context["registry"]`
  (and defers — returns `[]` — when no registry is in the context).

These feed real machinery — three consumers today:

1. **Dataflow verification.** `check_dataflow` (in `weaver.orchestrators.pipeline`)
   walks a pipeline's steps **in fold order**: every name a step `requires` must be
   present in the seed columns or `produces`-d by an earlier step, and each failure is
   reported before anything runs. Wiring and ordering bugs surface here — but only for
   inputs you declared.
2. **Populate preflight.** The `Populate` orchestrator calls `op.check(ctx)` on the
   sampler and every design-time `Evaluate` / `Constrain` and **hard-fails**
   (`ValueError` listing every message) before sampling a single row.
3. **Static contract coverage.** `check_output_coverage` (in `weaver.config.loader`)
   unions the outputs each step *declares* — `output_variables` on
   `Evaluate` / `Observe`, `output_field` on `Operate` — and reports every
   System-required metric no step claims to produce.

Guidance for your factories:

- **Fill the constructor fields truthfully.** An `Evaluate` with empty `field_deps`
  that actually reads row columns is invisible to `check_dataflow`; a `Constrain`
  missing a `requires` entry runs against rows that aren't ready.
- **Do not override `signature()` or `check()` in a factory.** The categories derive
  both from the fields you pass; overriding them forks the declaration from the
  behavior.
- **Prefer `Evaluate` over `Operate` when the inputs are named row columns.**
  `Operate.signature()` declares no `requires` (its reads are free-form interim
  state), so `check_dataflow` cannot verify an `Operate`'s inputs — only its declared
  `output_field` joins the walk. Reserve `Operate` for genuinely free-form state
  threading.

---

## Reachability: where these operators actually run

Writing a factory does not wire it into a study. Know the seams — and which of them
are live:

- **Design-time `Evaluate` / `Constrain` / `Repair` are unwired in the compiler
  path.** `build_project` (in `weaver.compile`) hardcodes
  `DesignOperators(evaluates=(), constraints=(), repair_chain=None)` — a study JSON
  cannot route your evaluates or constraints into populate today. Your factories run
  where *you* place them: as simulate-model steps
  ([authoring-models.md](authoring-models.md)) or inside your own stage builder
  ([authoring-stages.md](authoring-stages.md)).
- **`emits=` / `emit_variables` / `compose_registry` is a dormant seam.**
  `compose_registry` is public in `weaver.config.loader` and can fold operator-emitted
  `Variable` specs into the runtime registry — but no production caller passes
  operators; the compiler composes the registry from the System and Model manifests
  only. Consequence: **declare every column your operators produce in the study's
  `system/variables/` JSON** ([study-json-reference.md](study-json-reference.md)).
  An undeclared column is computed and then **silently dropped** — the `Run`
  write-back keeps only columns whose names are in the composed registry.
- **`Sample` is grammar-closed.** The compiler's sampler table knows exactly one name,
  `"lhs"`; any other `sampler` value in an orchestrator block raises `LowerError`. A
  custom `Sample` is constructible only inside your own stage builder — there is no
  registration hook to teach the grammar a new name.
- **`Repair` is the one category *designed* for subclassing** (it is abstract; each
  concrete repair is a distinct mutation algorithm, addressable by dotted class path)
  — **but it has zero production callers today**: the compiler wires
  `repair_chain=None`. Don't author repairs expecting the study grammar to run them.
