"""results.py: whitespace-delimited parse and reduce (incl. the non-finite guard)."""

from __future__ import annotations

from pathlib import Path

import pytest

from weaver.aspherix.errors import AsxError
from weaver.aspherix.results import read_timeseries, reduce

# Real header + rows from the 2026-07-12 walled_box run (whitespace, despite .csv).
REAL_SAMPLE = """\
          Time     Step    Atoms         KinEng            rke             Cu  Elapsed        CPULeft          T/CPU         Volume
             0        0        3   0.0078539816              0              0        0              0              0          0.001
          0.02     2000        3   0.0012529523              0      18933.537     2000              0     0.06311179          0.001
"""

# Real excerpt from the 2026-07-21 narrow_channel run: one header per `simulate`
# command in the same file, and the column set widens after `output_settings`.
MULTI_BLOCK_SAMPLE = """\
          Time     Step    Atoms         KinEng             Cu
             0        0        0              0              0
         5e-06        1     1200  1.3640497e-12      97723.054
          Time     Step    Atoms         KinEng            rke             Cu ts_check.rayleigh ts_check.hertz  Elapsed        CPULeft          T/CPU         Volume     channel.fx     channel.fy     channel.fz       wedge.fx       wedge.fy       wedge.fz
         5e-06        1     1200  1.3640497e-12              0              0                 0              0        0              0              0          0.024              0              0              0              0              0              0
         0.005     1000     1200  5.4507441e-06              0       21073986        0.05736843    0.012420181      999      5.6399552    0.087808274          0.024              0              0              0              0              0              0
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "simulation_data_aspherix.csv"
    path.write_text(text)
    return path


def test_read_timeseries_real_sample(tmp_path: Path) -> None:
    series = read_timeseries(_write(tmp_path, REAL_SAMPLE))
    assert set(series) == {"Time", "Step", "Atoms", "KinEng", "rke", "Cu", "Elapsed", "CPULeft", "T/CPU", "Volume"}
    assert series["KinEng"] == [0.0078539816, 0.0012529523]
    assert series["Step"] == [0.0, 2000.0]


def test_read_timeseries_multi_block_merges_by_name(tmp_path: Path) -> None:
    series = read_timeseries(_write(tmp_path, MULTI_BLOCK_SAMPLE))
    assert series["KinEng"] == [0.0, 1.3640497e-12, 1.3640497e-12, 5.4507441e-06]
    assert series["Atoms"] == [0.0, 1200.0, 1200.0, 1200.0]
    assert series["rke"] == [0.0, 0.0]  # only present after output_settings
    assert series["wedge.fz"] == [0.0, 0.0]


def test_read_timeseries_data_before_header_raises(tmp_path: Path) -> None:
    with pytest.raises(AsxError, match="before any header"):
        read_timeseries(_write(tmp_path, "1 2 3\na b c\n"))


def test_read_timeseries_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(AsxError, match="not found"):
        read_timeseries(tmp_path / "nope.csv")


def test_read_timeseries_empty_raises(tmp_path: Path) -> None:
    with pytest.raises(AsxError, match="empty"):
        read_timeseries(_write(tmp_path, "\n\n"))


def test_read_timeseries_ragged_row_raises(tmp_path: Path) -> None:
    with pytest.raises(AsxError, match="expected 3 columns"):
        read_timeseries(_write(tmp_path, "a b c\n1 2\n"))


def test_read_timeseries_non_numeric_raises(tmp_path: Path) -> None:
    with pytest.raises(AsxError, match="not numeric"):
        read_timeseries(_write(tmp_path, "a b\n1 x\n"))


def test_read_timeseries_duplicate_columns_raise(tmp_path: Path) -> None:
    with pytest.raises(AsxError, match="duplicate"):
        read_timeseries(_write(tmp_path, "a a\n1 2\n"))


def test_reduce_vocabulary() -> None:
    xs = [4.0, 1.0, 3.0]
    assert reduce(xs, "last") == 3.0
    assert reduce(xs, "first") == 4.0
    assert reduce(xs, "min") == 1.0
    assert reduce(xs, "max") == 4.0
    assert reduce(xs, "mean") == pytest.approx(8.0 / 3.0)
    assert reduce(xs, "sum") == 8.0
    assert reduce(xs, "delta") == -1.0  # last - first


def test_reduce_unknown_raises() -> None:
    with pytest.raises(AsxError, match="unknown reduce"):
        reduce([1.0], "median")


def test_reduce_empty_raises() -> None:
    with pytest.raises(AsxError, match="empty"):
        reduce([], "last")


def test_reduce_nonfinite_raises() -> None:
    # A diverged run writes nan; nan passes _is_db_scalar and the is-None validity
    # check, so the row would persist valid=1 — reduce must be the guard (R4).
    with pytest.raises(AsxError, match="non-finite"):
        reduce([1.0, float("nan")], "last")
    with pytest.raises(AsxError, match="non-finite"):
        reduce([1.0, float("inf")], "sum")
