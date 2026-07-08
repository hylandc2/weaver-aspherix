"""External orchestrator for weaver.aspherix (Layer 1).

AspherixRun subclasses the weaver.base.orchestrator.Orchestrator ABC — the right
move for a genuinely new orchestrator (it is not a flavor of an existing one). It
owns the whole run: assemble the case into a .asx (Layer 0 renderers), write it to
the pipeline's artifact dir, and build the mpirun launch argv.

The launch is a DRY RUN — this returns the argv it *would* execute. On a licensed
install, replace the marked line with
`subprocess.run(argv, cwd=case_path.parent, check=True)` and set launched=True
(aspherix-dem-guide.md §7: paths are resolved relative to the working directory).

Construct once with the validated case + nprocs; run() takes the pipeline context
(carrying artifact_dir) — the same shape Orchestrate forwards via pass_context.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional

from weaver.aspherix.run import build_launch_argv, write_case
from weaver.base.orchestrator import Orchestrator

__all__ = ["AspherixRun"]


class AspherixRun(Orchestrator):
    """Assemble a case into a .asx, write it, and build the (dry-run) mpirun argv."""

    def __init__(self, *, case: Mapping[str, Any], nprocs: int = 4) -> None:
        self.case = case
        self.nprocs = nprocs

    def run(self, *, context: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
        """Write `<artifact_dir>/case.asx` and return the launch summary (nothing executed)."""
        if context is None or "artifact_dir" not in context:
            raise ValueError("AspherixRun.run requires context['artifact_dir']")
        case_path = write_case(self.case, Path(context["artifact_dir"]))
        argv = build_launch_argv(case_path, nprocs=self.nprocs)
        # DRY RUN — on a licensed install: subprocess.run(argv, cwd=case_path.parent, check=True)
        return {"case": str(case_path), "argv": argv, "nprocs": self.nprocs, "launched": False}

    def check(self, context: Mapping[str, Any]) -> list[str]:
        """Preflight: nprocs must be a real int >= 1 (mirrors the Operator.check contract)."""
        del context
        if not isinstance(self.nprocs, int) or isinstance(self.nprocs, bool) or self.nprocs < 1:
            return [f"AspherixRun: nprocs must be an int >= 1, got {self.nprocs!r}"]
        return []
