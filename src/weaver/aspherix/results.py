"""Read Aspherix's timeseries file and reduce a column to one KPI (no weaver imports).

``simulation_data_aspherix.csv`` is WHITESPACE-delimited despite the extension —
``sep=','`` would return one column. Split on any whitespace, take column names
from the header row, never index positionally. Stdlib only.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable, Sequence

from weaver.aspherix.errors import AsxError

__all__ = ["read_timeseries", "reduce"]

_REDUCERS: dict[str, Callable[[Sequence[float]], float]] = {
    "last": lambda xs: xs[-1],
    "first": lambda xs: xs[0],
    "min": min,
    "max": max,
    "mean": lambda xs: sum(xs) / len(xs),
    "sum": sum,
    "delta": lambda xs: xs[-1] - xs[0],
}


def read_timeseries(path: Path) -> dict[str, list[float]]:
    """Parse the whitespace-delimited timeseries at ``path`` into ``{column: values}``."""
    if not path.is_file():
        raise AsxError(f"timeseries file not found: {path}")
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise AsxError(f"timeseries file is empty: {path}")
    header = lines[0].split()
    if len(set(header)) != len(header):
        raise AsxError(f"duplicate column names in {path}: {header}")
    columns: dict[str, list[float]] = {name: [] for name in header}
    for lineno, line in enumerate(lines[1:], start=2):
        cells = line.split()
        if len(cells) != len(header):
            raise AsxError(f"{path}:{lineno}: expected {len(header)} columns, got {len(cells)}")
        for name, cell in zip(header, cells):
            try:
                columns[name].append(float(cell))
            except ValueError as exc:
                raise AsxError(f"{path}:{lineno}: column {name!r} is not numeric: {cell!r}") from exc
    return columns


def reduce(values: Sequence[float], how: str) -> float:
    """Reduce a series to one float; raise on a non-finite result (a diverged run
    writes ``nan``, which would otherwise persist as a ``valid=1`` row).

    ``delta`` is defined as ``last - first``.
    """
    fn = _REDUCERS.get(how)
    if fn is None:
        raise AsxError(f"unknown reduce {how!r}; known: {sorted(_REDUCERS)}")
    if not values:
        raise AsxError(f"cannot reduce {how!r} over an empty series")
    out = float(fn(values))
    if not math.isfinite(out):
        raise AsxError(f"reduce {how!r} produced a non-finite value: {out!r}")
    return out
