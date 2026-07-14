"""The per-row seam: ``bind(__file__) -> (run_case, observe, observe_bytes)``.

The per-row ctx (``{registry, build_state, artifact_dir, run_id, row_id}``)
carries no study root, and ``SimulateModel.module`` is path-loaded from an
absolute path — so the study shim's ``__file__`` is the only root anchor a
row-step gets. ``bind`` resolves the root, preflights the sibling manifest
(raising ``on_error`` so a study gets validate-time Diagnostics), and returns
the three step closures the model JSON references by name.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Mapping

from weaver.base.variable import Domain

from weaver.aspherix.assets import stage
from weaver.aspherix.errors import AsxError
from weaver.aspherix.preflight import CONTROL_KEYS, check_model
from weaver.aspherix.results import read_timeseries, reduce
from weaver.aspherix.solver import build_launch_argv, launch, resolve_aspherix_bin, resolve_mpi_bin
from weaver.aspherix.template import render

__all__ = ["Step", "bind"]

Step = Callable[[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]], dict[str, Any]]


def _study_root(module_path: Path) -> Path:
    """Walk up from the module for the ``system/`` + ``projects/`` study markers."""
    for ancestor in module_path.parents:
        if (ancestor / "system").is_dir() and (ancestor / "projects").is_dir():
            return ancestor
    raise AsxError(f"no study root (a dir containing system/ and projects/) above {module_path}")


def _required(params: Mapping[str, Any], key: str) -> Any:
    value = params.get(key)
    if value is None:
        raise AsxError(f"step param {key!r} is required")
    return value


def _int_param(params: Mapping[str, Any], key: str, default: int) -> int:
    value = params.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise AsxError(f"step param {key!r} must be an int >= 1, got {value!r}")
    return value


def _namespace(row: Mapping[str, Any], ctx: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
    """Render namespace = schema-column allowlist off the row + non-control params.

    ``registry.names`` is exactly the schema columns, so reserved DB columns are
    excluded with no hardcoded list, and a not-yet-produced output (None at
    construct time) is dropped — its placeholder raises instead of rendering
    ``"None"``. ``$``-params resolve into ``params`` (never the row), so
    non-control params are merged on top; a collision with a schema column
    raises (preflight also rejects it at validate time).
    """
    names = ctx["registry"].names
    ns: dict[str, Any] = {n: row[n] for n in names if row.get(n) is not None}
    for key, value in params.items():
        if key in CONTROL_KEYS:
            continue
        if key in names:
            raise AsxError(f"step param {key!r} collides with a schema column")
        ns[key] = value
    return ns


def _argv(case_path: Path, nprocs: int) -> list[str]:
    binary = resolve_aspherix_bin()
    if binary is None:
        raise AsxError("no Aspherix binary found — set ASPHERIX_BIN to the full aspherix path or put 'aspherix' on PATH")
    if nprocs > 1:
        mpi_bin = resolve_mpi_bin()
        if mpi_bin is None:
            raise AsxError("nprocs > 1 but no MPI launcher found — set ASPHERIX_MPI_BIN or put mpiexec/mpirun on PATH")
        return build_launch_argv(case_path, nprocs=nprocs, binary=binary, mpi_bin=mpi_bin)
    return build_launch_argv(case_path, nprocs=1, binary=binary)


def bind(module_file: str | os.PathLike[str], *, on_error: type[Exception] = AsxError) -> tuple[Step, Step, Step]:
    """Resolve the study root from ``module_file``; preflight the sibling manifest.

    Returns ``(run_case, observe, observe_bytes)``. Kept cheap on purpose — the
    shim executes ~2x per ``weaver run`` (validate, then the run stage).
    """
    module_path = Path(module_file).resolve()
    study_root = _study_root(module_path)
    check_model(module_path, study_root, on_error=on_error)

    def run_case(row: Mapping[str, Any], ctx: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        """construct — render the deck for this row, stage assets, launch Aspherix."""
        produces = str(_required(params, "produces"))
        deck_path = study_root / str(_required(params, "deck"))
        if not deck_path.is_file():
            raise AsxError(f"deck not found: {deck_path}")
        nprocs = _int_param(params, "nprocs", 1)
        timeout_s = float(params.get("timeout_s", 600.0))

        case_dir = Path(ctx["artifact_dir"])
        case_dir.mkdir(parents=True, exist_ok=True)
        text = render(deck_path.read_text(encoding="utf-8"), _namespace(row, ctx, params))
        case_path = case_dir / "case.asx"
        case_path.write_text(text, encoding="utf-8", newline="\n")

        patterns = params.get("assets") or []
        if patterns:
            stage(study_root, patterns, case_dir)

        argv = _argv(case_path, nprocs)
        proc = launch(argv, cwd=case_dir, timeout=timeout_s)
        log_path = case_dir / "aspherix.log"
        if proc.returncode != 0:
            tail = "\n".join((proc.stdout.splitlines() + proc.stderr.splitlines())[-20:])
            raise AsxError(f"aspherix exited {proc.returncode}; log: {log_path}\n{tail}")

        warnings_path = case_dir / "warnings_aspherix.txt"
        return {
            produces: Domain(
                name=produces, role="output", value=str(case_dir),
                info={
                    "format": "aspherix-case",
                    "warnings": str(warnings_path),
                    "warnings_bytes": warnings_path.stat().st_size if warnings_path.is_file() else 0,
                },
            )
        }

    def observe(row: Mapping[str, Any], ctx: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        """observe — reduce one column of the solver's timeseries file to a KPI."""
        produces = str(_required(params, "produces"))
        column = str(_required(params, "column"))
        path = Path(ctx["artifact_dir"]) / str(_required(params, "file"))
        series = read_timeseries(path)
        if column not in series:
            raise AsxError(f"column {column!r} not in {path} (have: {sorted(series)})")
        return {produces: reduce(series[column], str(params.get("reduce", "last")))}

    def observe_bytes(row: Mapping[str, Any], ctx: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        """observe — the size in bytes of a per-case file (0 if absent)."""
        produces = str(_required(params, "produces"))
        path = Path(ctx["artifact_dir"]) / str(_required(params, "file"))
        return {produces: path.stat().st_size if path.is_file() else 0}

    return run_case, observe, observe_bytes
