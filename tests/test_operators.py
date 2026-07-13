"""Layer 1 unit tests: the build_case operator factory and the AspherixRun orchestrator."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from asx_util import normalize
from test_render import BASIC_PARAMS, GOLDEN

from weaver.aspherix.operators.build import build_case
from weaver.aspherix.orchestrators import run as orch_run
from weaver.aspherix.orchestrators.run import AspherixRun
from weaver.operators.operate import Operate
from weaver.base.orchestrator import Orchestrator


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never read the machine's real launcher env vars in tests."""
    monkeypatch.delenv("ASPHERIX_BIN", raising=False)
    monkeypatch.delenv("ASPHERIX_MPI_BIN", raising=False)


# build_case is a FACTORY returning a configured Operate (not a subclass).
def test_build_case_returns_operate() -> None:
    op = build_case("deck", case=BASIC_PARAMS)
    assert isinstance(op, Operate)
    assert type(op) is Operate  # factory, never a subclass
    assert op.output_field == "deck"


def test_build_case_writes_and_returns_path(tmp_path: Path) -> None:
    op = build_case("deck", case=BASIC_PARAMS)
    result = op.do({}, {"artifact_dir": str(tmp_path), "repo_root": str(tmp_path)})
    written = Path(result["deck"])
    assert written == tmp_path / "deck.asx"
    assert normalize(written.read_text()) == normalize(GOLDEN.read_text())


# AspherixRun subclasses the Orchestrator ABC (a genuinely new orchestrator).
def test_aspherix_run_is_orchestrator() -> None:
    assert isinstance(AspherixRun(case=BASIC_PARAMS), Orchestrator)


def test_aspherix_run_assembles_and_builds_argv(tmp_path: Path) -> None:
    summary = AspherixRun(case=BASIC_PARAMS, nprocs=8).run(context={"artifact_dir": str(tmp_path)})
    assert summary["launched"] is False
    assert summary["argv"] == ["mpiexec", "-np", "8", "aspherix", "-in", "case.asx"]
    assert normalize(Path(summary["case"]).read_text()) == normalize(GOLDEN.read_text())


def test_aspherix_run_check_rejects_bad_nprocs() -> None:
    assert AspherixRun(case=BASIC_PARAMS, nprocs=4).check({}) == []
    assert AspherixRun(case=BASIC_PARAMS, nprocs=0).check({}) != []
    assert AspherixRun(case=BASIC_PARAMS, nprocs=True).check({}) != []  # bool is not a valid int here


# The execute path, without ever spawning Aspherix: launch is stubbed at its use site.
def test_aspherix_run_execute_invokes_launch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASPHERIX_BIN", "X:/fake/aspherix.exe")
    seen: dict[str, object] = {}

    def fake_launch(argv: list[str], *, cwd: Path, log_name: str = "aspherix.log", timeout: object = None) -> subprocess.CompletedProcess[str]:
        seen["argv"], seen["cwd"] = argv, cwd
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

    monkeypatch.setattr(orch_run, "launch", fake_launch)
    summary = AspherixRun(case=BASIC_PARAMS, nprocs=1, execute=True).run(context={"artifact_dir": str(tmp_path)})

    assert summary["launched"] is True
    assert summary["returncode"] == 0
    assert summary["log"] == str(tmp_path / "aspherix.log")
    assert seen["argv"] == ["X:/fake/aspherix.exe", "-in", "case.asx"]
    assert seen["cwd"] == tmp_path


def test_aspherix_run_execute_nonzero_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASPHERIX_BIN", "X:/fake/aspherix.exe")
    monkeypatch.setattr(orch_run, "launch", lambda argv, **kwargs: subprocess.CompletedProcess(argv, 1, stdout="", stderr="license failure"))

    with pytest.raises(RuntimeError, match="exited 1") as excinfo:
        AspherixRun(case=BASIC_PARAMS, nprocs=1, execute=True).run(context={"artifact_dir": str(tmp_path)})
    assert "license failure" in str(excinfo.value)


def test_aspherix_run_execute_unresolvable_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    orchestrator = AspherixRun(case=BASIC_PARAMS, nprocs=1, execute=True)

    with pytest.raises(RuntimeError, match="ASPHERIX_BIN"):
        orchestrator.run(context={"artifact_dir": str(tmp_path)})
    assert orchestrator.check({}) != []


def test_aspherix_run_execute_unresolvable_mpi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASPHERIX_BIN", "X:/fake/aspherix.exe")
    monkeypatch.setattr(shutil, "which", lambda name: None)

    with pytest.raises(RuntimeError, match="ASPHERIX_MPI_BIN"):
        AspherixRun(case=BASIC_PARAMS, nprocs=4, execute=True).run(context={"artifact_dir": str(tmp_path)})
