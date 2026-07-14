"""Validate-time checks for a study's Aspherix model (weaver-core-aware).

``check_model`` runs at model-module import time — which is inside
``build_runtime_model`` — so a failure raised as ``on_error`` (the study passes
weaver-compile's ``LowerError``) becomes a located ``weaver validate``
Diagnostic instead of burning N solver launches.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from weaver.base.variable import Physical, Variable

from weaver.aspherix.errors import AsxError
from weaver.aspherix.template import placeholders

__all__ = ["CONTROL_KEYS", "check_model"]

# Step-param keys the wrapper consumes itself; everything else is a deck token.
CONTROL_KEYS = frozenset({"produces", "deck", "assets", "nprocs", "timeout_s", "file", "column", "reduce"})


def _manifests(module_file: Path) -> list[tuple[Path, dict[str, Any]]]:
    """Every sibling model JSON whose ``module`` names this file."""
    found: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(module_file.parent.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("module") == module_file.name:
            found.append((path, data))
    return found


def _variable_pool(study_root: Path) -> dict[str, Any]:
    """The union of every ``system/variables/*.json`` block (``$schema`` keys dropped)."""
    pool: dict[str, Any] = {}
    for path in sorted((study_root / "system" / "variables").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            pool.update({k: v for k, v in data.items() if not k.startswith("$")})
    return pool


def _check_fillable(name: str, pool: Mapping[str, Any], where: str, on_error: type[Exception]) -> None:
    """A consumed deck token must be a variable Populate will actually fill.

    Uses the real ``Physical.is_ranged`` / ``fixed_value`` (no mirrored logic to
    drift): anything else — notably a categorical — samples to a silent NULL,
    so it fails here at validate time instead.
    """
    descriptor = pool.get(name)
    if descriptor is None:
        raise on_error(f"{where}: consumed deck token {name!r} is not declared in system/variables/")
    try:
        variable = Variable.from_dict(name, descriptor)
    except (TypeError, ValueError) as exc:
        raise on_error(f"{where}: variable {name!r} does not parse: {exc}") from exc
    if not isinstance(variable, Physical) or not (variable.is_ranged or variable.fixed_value is not None):
        raise on_error(
            f"{where}: deck token {name!r} is not a ranged or fixed numeric variable — "
            "Populate would leave its column NULL and every row would fail at render "
            "(categoricals are not supported yet)"
        )


def check_model(module_file: Path, study_root: Path, *, on_error: type[Exception] = AsxError) -> None:
    """Preflight every sibling manifest that names ``module_file`` as its module.

    Checks, in order: the produces drift guard, deck existence, placeholder
    coverage, param/schema collisions, and that every consumed deck token is a
    variable Populate will fill.
    """
    manifests = _manifests(module_file)
    if not manifests:
        raise on_error(f"no model JSON next to {module_file} declares module {module_file.name!r}")

    pool = _variable_pool(study_root)
    for manifest_path, manifest in manifests:
        where = f"model {manifest.get('name', manifest_path.stem)!r}"
        consumes = set(manifest.get("consumes") or [])
        steps = manifest.get("steps") or []

        deck_steps: list[dict[str, Any]] = []
        for step in steps:
            params = step.get("params") or {}
            if params.get("produces") != step.get("produces"):
                raise on_error(
                    f"{where} step {step.get('produces')!r}: params['produces'] is "
                    f"{params.get('produces')!r} — it must equal the step's 'produces' "
                    "(a reusable packaged step must be told its output name)"
                )
            if "deck" in params:
                deck_steps.append(step)

        if not deck_steps:
            raise on_error(f"{where}: no step carries a 'deck' param — nothing would render a case")

        for step in deck_steps:
            params = step.get("params") or {}
            deck_path = study_root / str(params["deck"])
            if not deck_path.is_file():
                raise on_error(f"{where}: deck not found: {deck_path}")

            token_params = set(params) - CONTROL_KEYS
            collisions = token_params & consumes
            if collisions:
                raise on_error(
                    f"{where}: step param(s) {sorted(collisions)} collide with consumed "
                    "variables — the row must stay the single source for schema columns"
                )

            tokens = placeholders(deck_path.read_text(encoding="utf-8"))
            missing = tokens - consumes - token_params
            if missing:
                raise on_error(
                    f"{where}: unresolved placeholder(s) in {deck_path.name}: "
                    f"{', '.join(sorted(missing))} (not in consumes or step params)"
                )

            for name in sorted(tokens & consumes):
                _check_fillable(name, pool, where, on_error)
