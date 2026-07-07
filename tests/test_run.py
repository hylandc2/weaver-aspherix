"""Layer 0 run tests: case writer + dry-run launcher."""

from __future__ import annotations

from pathlib import Path

from asx_util import normalize
from test_render import BASIC_PARAMS, GOLDEN

from weaver.aspherix.run import build_launch_argv, write_case


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


# Step 6: build_launch_argv returns the mpirun argv (dry run — nothing executed).
def test_build_launch_argv_default() -> None:
    argv = build_launch_argv(Path("/some/dir/case.asx"))
    assert argv == ["mpirun", "-np", "4", "aspherix", "-in", "case.asx"]


def test_build_launch_argv_nprocs() -> None:
    argv = build_launch_argv(Path("case.asx"), nprocs=8)
    assert argv == ["mpirun", "-np", "8", "aspherix", "-in", "case.asx"]
