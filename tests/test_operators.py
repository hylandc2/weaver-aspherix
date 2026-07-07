"""Layer 1 unit tests: the build_case operator factory and the AspherixRun orchestrator."""

from __future__ import annotations

from pathlib import Path

from asx_util import normalize
from test_render import BASIC_PARAMS, GOLDEN

from weaver.aspherix.operators import build_case
from weaver.aspherix.orchestrators import AspherixRun
from weaver.operators.operate import Operate
from weaver.base.orchestrator import Orchestrator


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
    assert summary["argv"] == ["mpirun", "-np", "8", "aspherix", "-in", "case.asx"]
    assert normalize(Path(summary["case"]).read_text()) == normalize(GOLDEN.read_text())


def test_aspherix_run_check_rejects_bad_nprocs() -> None:
    assert AspherixRun(case=BASIC_PARAMS, nprocs=4).check({}) == []
    assert AspherixRun(case=BASIC_PARAMS, nprocs=0).check({}) != []
    assert AspherixRun(case=BASIC_PARAMS, nprocs=True).check({}) != []  # bool is not a valid int here
