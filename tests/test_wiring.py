"""The keystone: real Populate + real Run over hand-built weaver objects, with the
bind() closures wrapped exactly as weaver-compile's ``_lower_step`` wraps them
(the 3-arg closures must be bridged to 2-arg ``do_fn``s — handed raw to Observe
they would be invoked full-form as ``fn(row, context)`` and raise TypeError).

No Aspherix binary, no real study repo: launch is stubbed to write a synthetic
timeseries derived from the *rendered deck*, so distinct rows provably produce
distinct KPIs through the whole seam — LHS sample -> SQLite -> render ->
"solve" -> readback -> DB columns. One row is NULL-poisoned to prove the sweep
survives a per-row failure (the Gate 4 mechanism).
"""

from __future__ import annotations

import re
import sqlite3
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

import pytest

from conftest import MakeStudy
from weaver.aspherix import bind
from weaver.aspherix import steps as steps_mod
from weaver.base.system import System
from weaver.base.variable import Registry
from weaver.config.loader import DesignOperators, Project, compose_registry
from weaver.operators.observe import Observe
from weaver.operators.operate import Operate
from weaver.operators.sample.latin_hypercube import latin_hypercube
from weaver.orchestrators.model import Model
from weaver.orchestrators.populate import Populate
from weaver.orchestrators.run import Run
from weaver.utils.database import ID_COLUMN, Database

INPUTS: dict[str, Any] = {
    "coefficient_restitution": {"type": "float", "role": "input", "value": [0.2, 0.9], "units": "None"},
    "impact_speed": {"type": "float", "role": "input", "value": [1.0, 4.0], "units": "None"},
    "particle_radius": {"type": "float", "role": "input", "value": 0.005, "units": "None"},
}
OUTPUTS: dict[str, Any] = {
    "final_kinetic_energy": {"type": "float", "role": "output", "produced_by": "observed", "units": "None"},
    "warnings_bytes": {"type": "int", "role": "output", "produced_by": "observed", "units": "None"},
}

CONSTRUCT_PARAMS: dict[str, Any] = {
    "produces": "case_domain", "deck": "decks/box.asx", "nprocs": 1,
    "timeout_s": 60, "n_timesteps": 2000,
}
OBSERVE_PARAMS: dict[str, Any] = {
    "produces": "final_kinetic_energy", "file": "simulation_data_aspherix.csv",
    "column": "KinEng", "reduce": "last",
}
BYTES_PARAMS: dict[str, Any] = {"produces": "warnings_bytes", "file": "warnings_aspherix.txt"}

StepFn = Callable[[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]], dict[str, Any]]


def _wrap(fn: StepFn, params: Mapping[str, Any]) -> Callable[[Any, Any], Any]:
    """Replicate weaver-compile ``_wrap``: bridge fn(row, ctx, params) -> do_fn(row, ctx)."""
    def do_fn(row: Any, context: Any) -> Any:
        return fn(row, context, params)
    return do_fn


def _fake_launch(
    argv: Sequence[str], *, cwd: Path, log_name: str = "aspherix.log",
    timeout: Optional[float] = None,
) -> "subprocess.CompletedProcess[str]":
    """Read the rendered deck, derive KinEng from its tokens, write the timeseries."""
    text = (cwd / "case.asx").read_text(encoding="utf-8")
    e_match = re.search(r"coefficientRestitution (\S+)", text)
    v_match = re.search(r"velocity (\S+)", text)
    assert e_match and v_match, "stub launch needs the rendered tokens"
    kinetic = 0.5 * 3 * 1.309e-3 * (float(e_match.group(1)) * float(v_match.group(1))) ** 2
    (cwd / "simulation_data_aspherix.csv").write_text(
        f"Time Step KinEng\n0 0 0.0078539816\n0.02 2000 {kinetic:.10g}\n", encoding="utf-8"
    )
    (cwd / log_name).write_text("stub ok", encoding="utf-8")
    return subprocess.CompletedProcess(list(argv), 0, stdout="stub ok", stderr="")


def test_populate_then_run_through_the_whole_seam(
    make_study: MakeStudy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASPHERIX_BIN", "X:/fake/aspherix.exe")
    monkeypatch.setattr(steps_mod, "launch", _fake_launch)

    study_root = make_study()
    run_case, observe, observe_bytes = bind(study_root / "system" / "models" / "aspherix_dem.py")

    # Hand-build exactly what compose_registry would: required outputs ∪ consumes,
    # NO $-params (n_timesteps lives only in step params).
    system = System.from_dict({
        "name": "walled_box", "description": "wiring test contract",
        "required_variables": OUTPUTS, "optional_variables": {},
    })
    design_model = Model.from_dict({"name": "aspherix_dem", "input_variables": INPUTS})
    registry = compose_registry(system, design_model)
    project = Project(
        name="walled_box", system=system, model=design_model, registry=registry,
        operators=DesignOperators(sampler=latin_hypercube(), evaluates=(), constraints=(), repair_chain=None),
        count=4, seed=7, database="walled_box", optimization=None, operations=(),
    )

    db = Database(tmp_path / "walled_box.db")
    summary = Populate().run(project, db)
    table = summary["table"]
    assert table == "walled_box__aspherix_dem__7"
    assert summary["count"] == 4

    # Poison one row (the Gate 4 mechanism): NULL drops out of the render
    # namespace, so that row fails at render without burning a launch.
    poisoned_id = summary["row_ids"][0]
    db.update(table_name=table, id_column=ID_COLUMN, record_id=poisoned_id,
              updates={"coefficient_restitution": None})

    # Wrap the 3-arg closures exactly as _lower_step does and run the REAL Run.
    runtime = Model(
        name="aspherix_dem",
        input_variables=Registry.from_dict(INPUTS),
        steps=(
            Operate("case_domain", _wrap(run_case, CONSTRUCT_PARAMS), output_field="case_domain"),
            Observe("final_kinetic_energy", _wrap(observe, OBSERVE_PARAMS), output_field="final_kinetic_energy"),
            Observe("warnings_bytes", _wrap(observe_bytes, BYTES_PARAMS), output_field="warnings_bytes"),
        ),
    )
    result = Run().run(project, db, model=runtime, context={"repo_root": str(study_root)})

    assert result["completed"] == 3
    assert result["failed"] == 1
    assert result["invalid"] == 0
    assert "unresolved placeholder" in " ".join(result["errors"])

    conn = sqlite3.connect(db.db_path)
    try:
        rows = conn.execute(
            f"SELECT {ID_COLUMN}, status, valid, final_kinetic_energy, warnings_bytes, artifact_dir "
            f"FROM {table}"
        ).fetchall()
    finally:
        conn.close()
    by_id = {r[0]: r for r in rows}
    assert by_id[poisoned_id][1] == "failed"

    complete = [r for r in rows if r[1] == "complete"]
    assert len(complete) == 3
    kpis = [r[3] for r in complete]
    assert len(set(kpis)) == 3, f"KPIs must be distinct per design point, got {kpis}"
    assert all(r[2] == 1 for r in complete)
    assert all(r[4] == 0 for r in complete)  # warnings_bytes recorded per row

    # Each complete row's artifact_dir is its case dir: rendered deck present,
    # literal single braces intact (the str.format-would-have-raised proof).
    for r in complete:
        case = Path(r[5]) / "case.asx"
        assert case.is_file()
        assert "materials {m1}" in case.read_text(encoding="utf-8")
