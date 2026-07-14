"""assets.py: staging contract — relative-subpath copy2, loud empty matches."""

from __future__ import annotations

import filecmp
from pathlib import Path

import pytest

from weaver.aspherix.assets import stage
from weaver.aspherix.errors import AsxError


@pytest.fixture()
def study(tmp_path: Path) -> Path:
    root = tmp_path / "study"
    (root / "decks" / "meshes").mkdir(parents=True)
    (root / "decks" / "meshes" / "plate.stl").write_text("solid plate\nendsolid plate\n")
    (root / "decks" / "meshes" / "wall.stl").write_text("solid wall\nendsolid wall\n")
    return root


def test_stage_preserves_relative_subpath(study: Path, tmp_path: Path) -> None:
    dest = tmp_path / "case"
    staged = stage(study, ["decks/meshes/*.stl"], dest)
    assert sorted(p.name for p in staged) == ["plate.stl", "wall.stl"]
    target = dest / "decks" / "meshes" / "plate.stl"
    assert target.is_file()
    assert filecmp.cmp(study / "decks" / "meshes" / "plate.stl", target, shallow=False)


def test_stage_empty_match_raises_naming_pattern(study: Path, tmp_path: Path) -> None:
    with pytest.raises(AsxError, match=r"\*\.obj"):
        stage(study, ["decks/meshes/*.obj"], tmp_path / "case")


def test_stage_absolute_pattern_raises(study: Path, tmp_path: Path) -> None:
    with pytest.raises(AsxError, match="relative"):
        stage(study, [str(study / "decks" / "meshes" / "plate.stl")], tmp_path / "case")


def test_stage_parent_escape_raises(study: Path, tmp_path: Path) -> None:
    with pytest.raises(AsxError, match=r"\.\."):
        stage(study, ["../outside/*.stl"], tmp_path / "case")


def test_stage_multiple_patterns(study: Path, tmp_path: Path) -> None:
    (study / "decks" / "box.cfg").write_text("cfg")
    staged = stage(study, ["decks/meshes/plate.stl", "decks/*.cfg"], tmp_path / "case")
    assert [p.name for p in staged] == ["plate.stl", "box.cfg"]


def test_stage_directories_do_not_count_as_matches(study: Path, tmp_path: Path) -> None:
    # 'decks/*' matches the meshes/ dir; only files count, and files exist via box.cfg.
    with pytest.raises(AsxError, match="matched nothing"):
        stage(study, ["decks/m*"], tmp_path / "case")
