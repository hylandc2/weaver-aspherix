"""weaver.aspherix — Aspherix DEM wrapper.

Curated public surface:
  - Layer 0 (pure .asx text): assemble, write_case, build_launch_argv.
  - Layer 1 (Weaver shapes): build_case (Operate factory), AspherixRun
    (Orchestrator), build_aspherix_stage (StepBuilder resolved from operator JSON).
"""

from weaver.aspherix.operators.build import build_case
from weaver.aspherix.orchestrators.run import AspherixRun
from weaver.aspherix.render import assemble
from weaver.aspherix.run import build_launch_argv, write_case
from weaver.aspherix.stages import build_aspherix_stage

__all__ = [
    "AspherixRun",
    "assemble",
    "build_aspherix_stage",
    "build_case",
    "build_launch_argv",
    "write_case",
]
