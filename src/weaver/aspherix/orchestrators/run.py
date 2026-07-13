"""External orchestrator for weaver.aspherix (Layer 1).

AspherixRun subclasses the weaver.base.orchestrator.Orchestrator ABC — the right
move for a genuinely new orchestrator (it is not a flavor of an existing one). It
owns the whole run: assemble the case into a .asx (Layer 0 renderers), write it to
the pipeline's artifact dir, and launch Aspherix.

Dry-run by default: without `execute=True` it returns the argv it *would* run and
touches nothing but the .asx. With `execute=True` it resolves the binary from the
environment (ASPHERIX_BIN / PATH; ASPHERIX_MPI_BIN for nprocs > 1), runs it with
the case directory as the working directory (aspherix-dem-guide.md §7: paths are
resolved relative to the working directory), and raises on nonzero exit.

Construct once with the validated case + nprocs; run() takes the pipeline context
(carrying artifact_dir) — the same shape Orchestrate forwards via pass_context.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional

from weaver.aspherix.run import build_launch_argv, launch, resolve_aspherix_bin, resolve_mpi_bin, write_case
from weaver.base.orchestrator import Orchestrator

__all__ = ["AspherixRun"]


class AspherixRun(Orchestrator):
    """Assemble a case into a .asx, write it, and launch Aspherix (dry-run by default)."""

    def __init__(self, *, case: Mapping[str, Any], nprocs: int = 4, execute: bool = False) -> None:
        self.case = case
        self.nprocs = nprocs
        self.execute = execute

    def run(self, *, context: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
        """Write `<artifact_dir>/case.asx`, then launch Aspherix (or dry-run the argv)."""
        if context is None or "artifact_dir" not in context:
            raise ValueError("AspherixRun.run requires context['artifact_dir']")
        case_path = write_case(self.case, Path(context["artifact_dir"]))

        if not self.execute:
            argv = build_launch_argv(case_path, nprocs=self.nprocs)
            return {"case": str(case_path), "argv": argv, "nprocs": self.nprocs, "launched": False}

        binary = resolve_aspherix_bin()
        if binary is None:
            raise RuntimeError("AspherixRun: execute is true but no Aspherix binary found — set ASPHERIX_BIN to the full aspherix path or put 'aspherix' on PATH")
        if self.nprocs > 1:
            mpi_bin = resolve_mpi_bin()
            if mpi_bin is None:
                raise RuntimeError("AspherixRun: nprocs > 1 but no MPI launcher found — set ASPHERIX_MPI_BIN or put mpiexec/mpirun on PATH")
            argv = build_launch_argv(case_path, nprocs=self.nprocs, binary=binary, mpi_bin=mpi_bin)
        else:
            argv = build_launch_argv(case_path, nprocs=1, binary=binary)

        proc = launch(argv, cwd=case_path.parent)
        log_path = case_path.parent / "aspherix.log"
        if proc.returncode != 0:
            tail = "\n".join((proc.stdout.splitlines() + proc.stderr.splitlines())[-20:])
            raise RuntimeError(f"AspherixRun: aspherix exited {proc.returncode}; log: {log_path}\n{tail}")
        return {"case": str(case_path), "argv": argv, "nprocs": self.nprocs, "launched": True, "returncode": proc.returncode, "log": str(log_path)}

    def check(self, context: Mapping[str, Any]) -> list[str]:
        """Preflight: nprocs sanity plus, when executing, binary/MPI resolution.

        The fold path never calls check() — the hard gate is the RuntimeError in
        run(); this mirrors it for unit-testable preflight.
        """
        del context
        failures: list[str] = []
        if not isinstance(self.nprocs, int) or isinstance(self.nprocs, bool) or self.nprocs < 1:
            failures.append(f"AspherixRun: nprocs must be an int >= 1, got {self.nprocs!r}")
        if self.execute:
            if resolve_aspherix_bin() is None:
                failures.append("AspherixRun: execute is true but no Aspherix binary found (ASPHERIX_BIN / PATH)")
            if isinstance(self.nprocs, int) and self.nprocs > 1 and resolve_mpi_bin() is None:
                failures.append("AspherixRun: nprocs > 1 but no MPI launcher found (ASPHERIX_MPI_BIN / PATH)")
        return failures
