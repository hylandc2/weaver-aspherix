"""Shared fixtures: hermetic env and a minimal tmp study for bind()/preflight tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional

import pytest

DEFAULT_DECK = """particle_shape sphere
materials {m1}
material_properties m1 coefficientRestitution {{coefficient_restitution}} density 2500
radius {{particle_radius}}
velocity {{impact_speed}}
simulate time_steps {{n_timesteps}}
"""

DEFAULT_VARIABLES: dict[str, Any] = {
    "coefficient_restitution": {"type": "float", "role": "input", "value": [0.2, 0.9], "units": "None"},
    "impact_speed": {"type": "float", "role": "input", "value": [1.0, 4.0], "units": "None"},
    "particle_radius": {"type": "float", "role": "input", "value": 0.005, "units": "None"},
    "final_kinetic_energy": {"type": "float", "role": "output", "produced_by": "observed", "units": "None"},
    "warnings_bytes": {"type": "int", "role": "output", "produced_by": "observed", "units": "None"},
}

DEFAULT_MANIFEST: dict[str, Any] = {
    "name": "aspherix_dem",
    "kind": "simulate",
    "module": "aspherix_dem.py",
    "consumes": ["coefficient_restitution", "impact_speed", "particle_radius"],
    "produces": ["case_domain", "final_kinetic_energy", "warnings_bytes"],
    "domains": {"case_domain": {"kind": "domain", "role": "output", "produced_by": "calculated"}},
    "steps": [
        {"op": "construct", "produces": "case_domain", "ref": "run_case",
         "params": {"produces": "case_domain", "deck": "decks/box.asx", "nprocs": 1,
                    "timeout_s": 600, "n_timesteps": 2000}},
        {"op": "observe", "produces": "final_kinetic_energy", "ref": "observe",
         "params": {"produces": "final_kinetic_energy", "file": "simulation_data_aspherix.csv",
                    "column": "KinEng", "reduce": "last"}},
        {"op": "observe", "produces": "warnings_bytes", "ref": "observe_bytes",
         "params": {"produces": "warnings_bytes", "file": "warnings_aspherix.txt"}},
    ],
}

MakeStudy = Callable[..., Path]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never read the machine's real launcher env vars in tests."""
    monkeypatch.delenv("ASPHERIX_BIN", raising=False)
    monkeypatch.delenv("ASPHERIX_MPI_BIN", raising=False)


@pytest.fixture()
def make_study(tmp_path: Path) -> MakeStudy:
    """Build a minimal study tree (system/ + projects/ markers, deck, manifest)."""

    def _make(
        *,
        deck: str = DEFAULT_DECK,
        variables: Optional[dict[str, Any]] = None,
        manifest: Optional[dict[str, Any]] = None,
    ) -> Path:
        root = tmp_path / "study"
        (root / "projects").mkdir(parents=True, exist_ok=True)
        (root / "decks").mkdir(parents=True, exist_ok=True)
        (root / "system" / "variables").mkdir(parents=True, exist_ok=True)
        (root / "system" / "models").mkdir(parents=True, exist_ok=True)
        (root / "decks" / "box.asx").write_text(deck, encoding="utf-8")
        (root / "system" / "variables" / "design.json").write_text(
            json.dumps(variables if variables is not None else DEFAULT_VARIABLES), encoding="utf-8"
        )
        (root / "system" / "models" / "aspherix_dem.json").write_text(
            json.dumps(manifest if manifest is not None else DEFAULT_MANIFEST), encoding="utf-8"
        )
        return root

    return _make


@pytest.fixture()
def study_module(make_study: MakeStudy) -> Path:
    """The default study's module path (the anchor bind() resolves the root from)."""
    return make_study() / "system" / "models" / "aspherix_dem.py"
