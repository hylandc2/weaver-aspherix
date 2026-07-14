"""steps.py: bind + the three closures — the execute-path contract, ported from
the old operator tests (argv/cwd, nonzero exit, ASPHERIX_BIN, ASPHERIX_MPI_BIN)
plus the render-namespace and readback behavior."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional, Sequence

import pytest

from conftest import DEFAULT_VARIABLES
from weaver.aspherix import bind
from weaver.aspherix import steps as steps_mod
from weaver.aspherix.errors import AsxError
from weaver.base.variable import Domain, Registry

CONSTRUCT_PARAMS: dict[str, Any] = {
    "produces": "case_domain", "deck": "decks/box.asx", "nprocs": 1,
    "timeout_s": 600, "n_timesteps": 2000,
}
OBSERVE_PARAMS: dict[str, Any] = {
    "produces": "final_kinetic_energy", "file": "simulation_data_aspherix.csv",
    "column": "KinEng", "reduce": "last",
}
BYTES_PARAMS: dict[str, Any] = {"produces": "warnings_bytes", "file": "warnings_aspherix.txt"}

ROW: dict[str, Any] = {
    "coefficient_restitution": 0.4, "impact_speed": 2.0, "particle_radius": 0.005,
    "final_kinetic_energy": None, "warnings_bytes": None,
    "row_id": "r0", "status": "running",  # reserved columns the allowlist must exclude
}


def _ctx(case_dir: Path) -> dict[str, Any]:
    return {
        "registry": Registry.from_dict(DEFAULT_VARIABLES),
        "build_state": dict(ROW),
        "artifact_dir": case_dir,
        "run_id": "run-test",
        "row_id": "r0",
    }


class FakeLaunch:
    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self, argv: Sequence[str], *, cwd: Path, log_name: str = "aspherix.log",
        timeout: Optional[float] = None,
    ) -> "subprocess.CompletedProcess[str]":
        self.calls.append({"argv": list(argv), "cwd": cwd, "timeout": timeout})
        (cwd / log_name).write_text("stub", encoding="utf-8")
        return subprocess.CompletedProcess(list(argv), self.returncode, stdout="ok", stderr=self.stderr)


@pytest.fixture()
def bound(study_module: Path) -> tuple[steps_mod.Step, steps_mod.Step, steps_mod.Step]:
    return bind(study_module)


def test_bind_requires_a_study_root(tmp_path: Path) -> None:
    (tmp_path / "lonely").mkdir()
    with pytest.raises(AsxError, match="study root"):
        bind(tmp_path / "lonely" / "model.py")


def test_run_case_renders_launches_and_returns_domain(
    bound: tuple[steps_mod.Step, steps_mod.Step, steps_mod.Step], tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_case, _, _ = bound
    monkeypatch.setenv("ASPHERIX_BIN", "X:/fake/aspherix.exe")
    fake = FakeLaunch()
    monkeypatch.setattr(steps_mod, "launch", fake)
    case_dir = tmp_path / "row0"

    out = run_case(ROW, _ctx(case_dir), CONSTRUCT_PARAMS)

    assert fake.calls[0]["argv"] == ["X:/fake/aspherix.exe", "-in", "case.asx"]
    assert fake.calls[0]["cwd"] == case_dir
    assert fake.calls[0]["timeout"] == 600.0
    text = (case_dir / "case.asx").read_text(encoding="utf-8")
    assert "coefficientRestitution 0.4" in text
    assert "velocity 2" in text
    assert "radius 0.005" in text
    assert "time_steps 2000" in text  # the $-param merged from step params
    assert "materials {m1}" in text  # literal single braces untouched
    domain = out["case_domain"]
    assert isinstance(domain, Domain)
    assert domain.value == str(case_dir)
    assert domain.info["warnings_bytes"] == 0


def test_run_case_nonzero_exit_raises(
    bound: tuple[steps_mod.Step, steps_mod.Step, steps_mod.Step], tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_case, _, _ = bound
    monkeypatch.setenv("ASPHERIX_BIN", "X:/fake/aspherix.exe")
    monkeypatch.setattr(steps_mod, "launch", FakeLaunch(returncode=1, stderr="license failure"))
    with pytest.raises(RuntimeError, match="exited 1") as excinfo:
        run_case(ROW, _ctx(tmp_path / "row0"), CONSTRUCT_PARAMS)
    assert "license failure" in str(excinfo.value)


def test_run_case_unresolvable_binary_names_env_var(
    bound: tuple[steps_mod.Step, steps_mod.Step, steps_mod.Step], tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_case, _, _ = bound
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="ASPHERIX_BIN"):
        run_case(ROW, _ctx(tmp_path / "row0"), CONSTRUCT_PARAMS)


def test_run_case_unresolvable_mpi_names_env_var(
    bound: tuple[steps_mod.Step, steps_mod.Step, steps_mod.Step], tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_case, _, _ = bound
    monkeypatch.setenv("ASPHERIX_BIN", "X:/fake/aspherix.exe")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="ASPHERIX_MPI_BIN"):
        run_case(ROW, _ctx(tmp_path / "row0"), {**CONSTRUCT_PARAMS, "nprocs": 4})


def test_run_case_null_row_value_fails_at_render(
    bound: tuple[steps_mod.Step, steps_mod.Step, steps_mod.Step], tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The Gate 4 poison mechanism: a NULL schema value is dropped from the
    # namespace, so its placeholder raises before any solver launch.
    run_case, _, _ = bound
    monkeypatch.setenv("ASPHERIX_BIN", "X:/fake/aspherix.exe")
    fake = FakeLaunch()
    monkeypatch.setattr(steps_mod, "launch", fake)
    poisoned = {**ROW, "coefficient_restitution": None}
    with pytest.raises(AsxError, match=r"unresolved placeholder\(s\): coefficient_restitution"):
        run_case(poisoned, _ctx(tmp_path / "row0"), CONSTRUCT_PARAMS)
    assert fake.calls == []  # no launch burned


def test_run_case_param_colliding_with_schema_column_raises(
    bound: tuple[steps_mod.Step, steps_mod.Step, steps_mod.Step], tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_case, _, _ = bound
    monkeypatch.setenv("ASPHERIX_BIN", "X:/fake/aspherix.exe")
    monkeypatch.setattr(steps_mod, "launch", FakeLaunch())
    with pytest.raises(AsxError, match="collides"):
        run_case(ROW, _ctx(tmp_path / "row0"), {**CONSTRUCT_PARAMS, "impact_speed": 9.0})


def test_run_case_bad_nprocs_raises(
    bound: tuple[steps_mod.Step, steps_mod.Step, steps_mod.Step], tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_case, _, _ = bound
    monkeypatch.setenv("ASPHERIX_BIN", "X:/fake/aspherix.exe")
    for bad in (0, True):
        with pytest.raises(AsxError, match="nprocs"):
            run_case(ROW, _ctx(tmp_path / "row0"), {**CONSTRUCT_PARAMS, "nprocs": bad})


def test_observe_reduces_named_column(
    bound: tuple[steps_mod.Step, steps_mod.Step, steps_mod.Step], tmp_path: Path,
) -> None:
    _, observe, _ = bound
    case_dir = tmp_path / "row0"
    case_dir.mkdir()
    (case_dir / "simulation_data_aspherix.csv").write_text(
        "Time Step KinEng\n0 0 0.0078539816\n0.02 2000 0.0012529523\n", encoding="utf-8"
    )
    out = observe(ROW, _ctx(case_dir), OBSERVE_PARAMS)
    assert out == {"final_kinetic_energy": 0.0012529523}


def test_observe_missing_column_raises(
    bound: tuple[steps_mod.Step, steps_mod.Step, steps_mod.Step], tmp_path: Path,
) -> None:
    _, observe, _ = bound
    case_dir = tmp_path / "row0"
    case_dir.mkdir()
    (case_dir / "simulation_data_aspherix.csv").write_text("Time Step\n0 0\n", encoding="utf-8")
    with pytest.raises(AsxError, match="KinEng"):
        observe(ROW, _ctx(case_dir), OBSERVE_PARAMS)


def test_observe_bytes_reports_size_and_absent_as_zero(
    bound: tuple[steps_mod.Step, steps_mod.Step, steps_mod.Step], tmp_path: Path,
) -> None:
    _, _, observe_bytes = bound
    case_dir = tmp_path / "row0"
    case_dir.mkdir()
    assert observe_bytes(ROW, _ctx(case_dir), BYTES_PARAMS) == {"warnings_bytes": 0}
    (case_dir / "warnings_aspherix.txt").write_bytes(b"WARNING x")
    assert observe_bytes(ROW, _ctx(case_dir), BYTES_PARAMS) == {"warnings_bytes": 9}
