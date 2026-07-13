"""External compiler stage for weaver.aspherix (Layer 1).

build_aspherix_stage is a StepBuilder — (Workspace, ProjectNode, StageNode) -> Operator
— the compiler resolves from an operator JSON `ref` of
'weaver.aspherix.stages:build_aspherix_stage'. It reads the case from the bound
orchestrator's open param bag (`model_extra`), validates the params with located
LowerError messages, constructs AspherixRun, and wraps it as one fold step via
Orchestrate. This is the config-driven seam: the study JSON's orchestrator carries
the whole DEM case, and this builder turns it into a run.

Non-table stage: it binds no model and does NOT call build_project.
"""

from __future__ import annotations

from typing import Any, Mapping

from weaver.aspherix.orchestrators.run import AspherixRun
from weaver.base.operator import Operator
from weaver.compile import LowerError, ProjectNode, StageNode, Workspace
from weaver.operators.orchestrate import Orchestrate

__all__ = ["build_aspherix_stage"]

# Top-level keys every case block needs — validated at build time so a malformed
# case fails when the stage is lowered, not with a KeyError mid-run. neighbor_list,
# walls, and mesh are optional (see render.assemble).
_REQUIRED_CASE_KEYS = ("shape", "domain", "material", "contact", "timestep", "particles", "output", "run")


def build_aspherix_stage(workspace: Workspace, project: ProjectNode, stage: StageNode) -> Operator:
    """StepBuilder resolved from 'weaver.aspherix.stages:build_aspherix_stage'."""
    del project
    orchestrator = workspace.orchestrators.get(stage.orchestrator)
    if orchestrator is None:
        raise LowerError(f"orchestrator {stage.orchestrator!r} (stage {stage.name!r}) is not declared")
    params: Mapping[str, Any] = orchestrator.model_extra or {}

    nprocs = params.get("nprocs", 4)
    if not isinstance(nprocs, int) or isinstance(nprocs, bool) or nprocs < 1:
        raise LowerError(f"orchestrator {orchestrator.name!r} nprocs must be an int >= 1, got {nprocs!r}")

    execute = params.get("execute", False)
    if not isinstance(execute, bool):
        raise LowerError(f"orchestrator {orchestrator.name!r} execute must be a bool, got {execute!r}")

    case = params.get("case")
    if not isinstance(case, dict):
        raise LowerError(f"orchestrator {orchestrator.name!r} must carry a 'case' object, got {case!r}")
    missing = [key for key in _REQUIRED_CASE_KEYS if key not in case]
    if missing:
        raise LowerError(f"orchestrator {orchestrator.name!r} case is missing required blocks: {missing}")
    run_cfg = case["run"]
    if not isinstance(run_cfg, dict) or (("time" in run_cfg) == ("time_steps" in run_cfg)):
        raise LowerError(f"orchestrator {orchestrator.name!r} case run block needs exactly one of 'time' or 'time_steps'")

    return Orchestrate(
        stage.name,
        AspherixRun(case=case, nprocs=nprocs, execute=execute),
        output_field=stage.name,
        expect=dict,
        info={"builder": "build_aspherix_stage", "orchestrator": stage.orchestrator, "nprocs": nprocs, "execute": execute},
    )
