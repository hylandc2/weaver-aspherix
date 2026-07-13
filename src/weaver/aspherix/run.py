"""Case writer and launcher for weaver.aspherix (Layer 0).

`write_case` assembles a .asx from params and writes it to disk. `build_launch_argv`
returns the launch argv without executing it; `launch` runs an argv with the case
directory as the working directory — Aspherix resolves the `-in` target and mesh
paths relative to the working directory (aspherix-dem-guide.md §7).

Binary discovery is environment-driven and happens ONLY on the execute path
(never during dry-run assembly, so tests stay hermetic):

- `ASPHERIX_BIN`  — full path to the aspherix executable; falls back to `aspherix`
  on PATH.
- `ASPHERIX_MPI_BIN` — MPI launcher for nprocs > 1; falls back to `mpiexec` then
  `mpirun` on PATH. Serial runs (nprocs == 1) use no MPI wrapper at all.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from weaver.aspherix.render import assemble

__all__ = ["build_launch_argv", "launch", "resolve_aspherix_bin", "resolve_mpi_bin", "write_case"]


def write_case(params: Mapping[str, Any], out_dir: Path, *, filename: str = "case.asx") -> Path:
    """Assemble the .asx for `params` and write it to `out_dir/filename`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    case_path = out_dir / filename
    case_path.write_text(assemble(params))
    return case_path


def resolve_aspherix_bin() -> Optional[str]:
    """ASPHERIX_BIN env var (full path) wins; else PATH lookup; else None."""
    return os.environ.get("ASPHERIX_BIN") or shutil.which("aspherix")


def resolve_mpi_bin() -> Optional[str]:
    """ASPHERIX_MPI_BIN env var wins; else mpiexec (MS-MPI) then mpirun on PATH; else None."""
    return os.environ.get("ASPHERIX_MPI_BIN") or shutil.which("mpiexec") or shutil.which("mpirun")


def build_launch_argv(case_path: Path, *, nprocs: int = 4, binary: str = "aspherix", mpi_bin: str = "mpiexec") -> list[str]:
    """Build the launch argv: serial for nprocs == 1, MPI-wrapped otherwise.

    Uses `case_path.name`, not the full path, because the launch runs with the
    case directory as the working directory.
    """
    if nprocs == 1:
        return [binary, "-in", case_path.name]
    return [mpi_bin, "-np", str(nprocs), binary, "-in", case_path.name]


def launch(argv: Sequence[str], *, cwd: Path, log_name: str = "aspherix.log", timeout: Optional[float] = None) -> "subprocess.CompletedProcess[str]":
    """Run `argv` with `cwd` as the working directory, capturing output to `<cwd>/<log_name>`.

    Returns the CompletedProcess without raising on nonzero exit — the caller
    inspects `returncode` and owns the error message.
    """
    proc = subprocess.run(list(argv), cwd=cwd, capture_output=True, text=True, timeout=timeout)
    log_text = proc.stdout + (f"\n--- stderr ---\n{proc.stderr}" if proc.stderr else "")
    (cwd / log_name).write_text(log_text)
    return proc
