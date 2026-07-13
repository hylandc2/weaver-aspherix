"""Layer 0 run tests: case writer, launch argv, binary resolution, and launch()."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
from asx_util import normalize
from test_render import BASIC_PARAMS, GOLDEN

from weaver.aspherix.run import build_launch_argv, launch, resolve_aspherix_bin, resolve_mpi_bin, write_case


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never read the machine's real launcher env vars in tests."""
    monkeypatch.delenv("ASPHERIX_BIN", raising=False)
    monkeypatch.delenv("ASPHERIX_MPI_BIN", raising=False)


# Step 5: write_case writes a file whose content matches the golden.
def test_write_case_roundtrips_golden(tmp_path: Path) -> None:
    case_path = write_case(BASIC_PARAMS, tmp_path)
    assert case_path == tmp_path / "case.asx"
    assert case_path.exists()
    assert normalize(case_path.read_text()) == normalize(GOLDEN.read_text())


def test_write_case_custom_filename(tmp_path: Path) -> None:
    case_path = write_case(BASIC_PARAMS, tmp_path / "runs", filename="drop.asx")
    assert case_path == tmp_path / "runs" / "drop.asx"
    assert case_path.exists()


# Step 6: build_launch_argv builds the argv without executing anything.
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
    assert "ok" in (tmp_path / "aspherix.log").read_text()


def test_launch_captures_stderr_and_returncode(tmp_path: Path) -> None:
    proc = launch([sys.executable, "-c", "import sys; sys.stderr.write('boom'); sys.exit(3)"], cwd=tmp_path)
    assert proc.returncode == 3
    assert "boom" in (tmp_path / "aspherix.log").read_text()
