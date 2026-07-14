"""solver.py: launch argv, binary resolution, cwd/log contract, timeout."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from weaver.aspherix.solver import build_launch_argv, launch, resolve_aspherix_bin, resolve_mpi_bin


# build_launch_argv builds the argv without executing anything.
def test_build_launch_argv_default() -> None:
    argv = build_launch_argv(Path("/some/dir/case.asx"))
    assert argv == ["mpiexec", "-np", "4", "aspherix", "-in", "case.asx"]


def test_build_launch_argv_nprocs() -> None:
    argv = build_launch_argv(Path("case.asx"), nprocs=8)
    assert argv == ["mpiexec", "-np", "8", "aspherix", "-in", "case.asx"]


def test_build_launch_argv_serial_skips_mpi() -> None:
    argv = build_launch_argv(Path("case.asx"), nprocs=1)
    assert argv == ["aspherix", "-in", "case.asx"]


def test_build_launch_argv_overrides() -> None:
    argv = build_launch_argv(Path("case.asx"), nprocs=2, binary="X:/tools/aspherix.exe", mpi_bin="X:/mpi/mpiexec.exe")
    assert argv == ["X:/mpi/mpiexec.exe", "-np", "2", "X:/tools/aspherix.exe", "-in", "case.asx"]


# Binary resolution: env var wins, PATH is the fallback, None when neither.
def test_resolve_aspherix_bin_env_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASPHERIX_BIN", "X:/tools/aspherix.exe")
    assert resolve_aspherix_bin() == "X:/tools/aspherix.exe"


def test_resolve_aspherix_bin_path_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "X:/on/path/aspherix" if name == "aspherix" else None)
    assert resolve_aspherix_bin() == "X:/on/path/aspherix"


def test_resolve_aspherix_bin_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert resolve_aspherix_bin() is None


def test_resolve_mpi_bin_env_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASPHERIX_MPI_BIN", "X:/mpi/mpiexec.exe")
    assert resolve_mpi_bin() == "X:/mpi/mpiexec.exe"


def test_resolve_mpi_bin_prefers_mpiexec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: f"X:/on/path/{name}" if name in ("mpiexec", "mpirun") else None)
    assert resolve_mpi_bin() == "X:/on/path/mpiexec"


def test_resolve_mpi_bin_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert resolve_mpi_bin() is None


# launch(): real subprocess (python itself), cwd honoured, output captured to the log.
def test_launch_runs_and_writes_log(tmp_path: Path) -> None:
    proc = launch([sys.executable, "-c", "print('ok')"], cwd=tmp_path)
    assert proc.returncode == 0
    assert "ok" in (tmp_path / "aspherix.log").read_text(encoding="utf-8")


def test_launch_captures_stderr_and_returncode(tmp_path: Path) -> None:
    proc = launch([sys.executable, "-c", "import sys; sys.stderr.write('boom'); sys.exit(3)"], cwd=tmp_path)
    assert proc.returncode == 3
    assert "boom" in (tmp_path / "aspherix.log").read_text(encoding="utf-8")


def test_launch_non_utf8_output_does_not_fail(tmp_path: Path) -> None:
    # Bare text=True would decode with the locale codec (cp1252) and could raise;
    # utf-8 + errors="replace" must swallow arbitrary bytes.
    proc = launch(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'caf\\xe9 \\xff')"],
        cwd=tmp_path,
    )
    assert proc.returncode == 0
    assert "caf" in (tmp_path / "aspherix.log").read_text(encoding="utf-8")


def test_launch_timeout_kills_and_still_writes_log(tmp_path: Path) -> None:
    with pytest.raises(subprocess.TimeoutExpired):
        launch(
            [sys.executable, "-c", "import time; print('started', flush=True); time.sleep(30)"],
            cwd=tmp_path, timeout=1.0,
        )
    log = (tmp_path / "aspherix.log").read_text(encoding="utf-8")
    assert "timeout" in log
    assert "killed after" in log
