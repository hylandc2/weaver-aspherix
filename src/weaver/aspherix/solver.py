"""Launcher for weaver.aspherix (no weaver imports).

`build_launch_argv` returns the launch argv without executing it; `launch` runs
an argv with the case directory as the working directory — Aspherix resolves the
`-in` target and mesh paths relative to the working directory.

Binary discovery is environment-driven and happens ONLY on the execute path
(never at import, so tests stay hermetic):

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
from typing import Optional, Sequence

__all__ = ["build_launch_argv", "launch", "resolve_aspherix_bin", "resolve_mpi_bin"]


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


def _as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _write_log(cwd: Path, log_name: str, stdout: str, stderr: str, *, suffix: str = "") -> None:
    log_text = stdout + (f"\n--- stderr ---\n{stderr}" if stderr else "") + suffix
    (cwd / log_name).write_text(log_text, encoding="utf-8")


def launch(argv: Sequence[str], *, cwd: Path, log_name: str = "aspherix.log", timeout: Optional[float] = None) -> "subprocess.CompletedProcess[str]":
    """Run `argv` with `cwd` as the working directory, capturing output to `<cwd>/<log_name>`.

    Returns the CompletedProcess without raising on nonzero exit — the caller
    inspects `returncode` and owns the error message. Decodes with utf-8 +
    errors="replace" (bare text=True would use the locale codec — cp1252 here —
    and one non-ASCII byte in the solver log would fail a row cosmetically).
    On TimeoutExpired the log is written before re-raising.
    """
    try:
        proc = subprocess.run(
            list(argv), cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        _write_log(
            cwd, log_name, _as_text(exc.stdout), _as_text(exc.stderr),
            suffix=f"\n--- timeout ---\nkilled after {exc.timeout} s",
        )
        raise
    _write_log(cwd, log_name, proc.stdout, proc.stderr)
    return proc
