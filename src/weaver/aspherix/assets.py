"""Stage study assets (meshes etc.) into a case dir (no weaver imports).

Files are copied with their study-root-relative subpath preserved, so a deck
line like ``mesh id p file decks/meshes/plate.stl`` resolves identically by
hand from the study root and under Weaver (cwd = case dir). ``copy2``, not a
hardlink — a hardlink would let an edited source retroactively mutate every
archived run.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable

from weaver.aspherix.errors import AsxError

__all__ = ["stage"]


def stage(study_root: Path, patterns: Iterable[str], dest: Path) -> list[Path]:
    """Copy every file matching each glob ``pattern`` under ``study_root`` into ``dest``.

    A pattern that matches nothing raises (never silently stage nothing), as do
    absolute patterns and ``..`` escapes.
    """
    staged: list[Path] = []
    for pattern in patterns:
        parts = Path(pattern).parts
        if Path(pattern).is_absolute() or ".." in parts:
            raise AsxError(f"asset pattern must be study-root-relative without '..': {pattern!r}")
        files = sorted(p for p in study_root.glob(pattern) if p.is_file())
        if not files:
            raise AsxError(f"asset pattern matched nothing: {pattern!r} (under {study_root})")
        for src in files:
            out = dest / src.relative_to(study_root)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out)
            staged.append(out)
    return staged
