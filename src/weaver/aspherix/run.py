"""Case writer and dry-run launcher for weaver.aspherix (Layer 0).

`write_case` assembles a .asx from params and writes it to disk. `build_launch_argv`
returns the mpirun argv WITHOUT executing it — this environment has no aspherix
binary and no license, so the launch is a dry run. On a licensed install, feed the
argv to `subprocess.run(..., cwd=case_path.parent)` — Aspherix resolves the `-in`
target and mesh paths relative to the working directory (aspherix-dem-guide.md §7).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from weaver.aspherix.render import assemble

__all__ = ["build_launch_argv", "write_case"]


def write_case(params: Mapping[str, Any], out_dir: Path, *, filename: str = "case.asx") -> Path:
    """Assemble the .asx for `params` and write it to `out_dir/filename`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    case_path = out_dir / filename
    case_path.write_text(assemble(params))
    return case_path


def build_launch_argv(case_path: Path, *, nprocs: int = 4) -> list[str]:
    """Build the `mpirun -np N aspherix -in <case>` argv (dry run — not executed).

    Uses `case_path.name`, not the full path, because the launch runs with the
    case directory as the working directory.
    """
    return ["mpirun", "-np", str(nprocs), "aspherix", "-in", case_path.name]
