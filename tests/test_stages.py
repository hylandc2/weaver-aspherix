"""Layer 1 stage test: the study fixture validates clean, and the StepBuilder runs.

This is the config-driven seam end to end: Workspace.scan reads the JSON, validate
resolves the operator `ref` to build_aspherix_stage, and invoking the built step
writes the same .asx Layer 0 tests against.
"""

from __future__ import annotations

from pathlib import Path

from asx_util import normalize

from weaver.aspherix.stages import build_aspherix_stage
from weaver.compile import LowerError, Workspace, assert_valid, validate

STUDY = Path(__file__).parent / "fixtures" / "study"
GOLDEN = Path(__file__).parent / "fixtures" / "basic.asx"


def test_study_validates_clean() -> None:
    workspace = Workspace.scan(STUDY)
    errors = [d for d in validate(workspace) if d.severity == "error"]
    assert errors == [], [d.format() for d in errors]
    assert_valid(workspace)  # does not raise


def test_builder_writes_case_from_json(tmp_path: Path) -> None:
    workspace = Workspace.scan(STUDY)
    project = workspace.projects["demo"]
    stage = project.stages[0]

    step = build_aspherix_stage(workspace, project, stage)
    result = step.do({}, {"repo_root": str(tmp_path), "artifact_dir": str(tmp_path)})
    summary = result[stage.name]

    assert summary["launched"] is False
    assert summary["argv"] == ["mpirun", "-np", "4", "aspherix", "-in", "case.asx"]
    assert normalize(Path(summary["case"]).read_text()) == normalize(GOLDEN.read_text())


def test_builder_rejects_case_missing_blocks() -> None:
    workspace = Workspace.scan(STUDY)
    project = workspace.projects["demo"]
    stage = project.stages[0]
    # Drop a required block from the (open) orchestrator param bag.
    orchestrator = workspace.orchestrators[stage.orchestrator]
    assert orchestrator.model_extra is not None
    del orchestrator.model_extra["case"]["material"]

    try:
        build_aspherix_stage(workspace, project, stage)
    except LowerError as exc:
        assert "material" in str(exc)
    else:
        raise AssertionError("expected LowerError for a case missing a required block")
