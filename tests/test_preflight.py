"""preflight.py: every check fires at bind/validate time, as the caller's error type."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from conftest import DEFAULT_DECK, DEFAULT_MANIFEST, DEFAULT_VARIABLES, MakeStudy
from weaver.aspherix.errors import AsxError
from weaver.aspherix.preflight import check_model


def _module(root: Path) -> Path:
    return root / "system" / "models" / "aspherix_dem.py"


def _manifest_with(**step0_params: Any) -> dict[str, Any]:
    manifest = copy.deepcopy(DEFAULT_MANIFEST)
    manifest["steps"][0]["params"].update(step0_params)
    return manifest


def test_default_study_passes(make_study: MakeStudy) -> None:
    root = make_study()
    check_model(_module(root), root)


def test_produces_drift_raises(make_study: MakeStudy) -> None:
    root = make_study(manifest=_manifest_with(produces="case_doman"))
    with pytest.raises(AsxError, match="produces"):
        check_model(_module(root), root)


def test_missing_deck_raises(make_study: MakeStudy) -> None:
    root = make_study(manifest=_manifest_with(deck="decks/nope.asx"))
    with pytest.raises(AsxError, match="deck not found"):
        check_model(_module(root), root)


def test_unresolved_placeholder_raises_with_name(make_study: MakeStudy) -> None:
    root = make_study(deck=DEFAULT_DECK + "coefficientFriction {{coefficient_frction}}\n")
    with pytest.raises(AsxError, match=r"unresolved placeholder\(s\).*coefficient_frction"):
        check_model(_module(root), root)


def test_categorical_consumed_token_raises(make_study: MakeStudy) -> None:
    variables = copy.deepcopy(DEFAULT_VARIABLES)
    variables["coefficient_restitution"]["value"] = ["low", "high"]
    root = make_study(variables=variables)
    with pytest.raises(AsxError, match="NULL"):
        check_model(_module(root), root)


def test_undeclared_consumed_token_raises(make_study: MakeStudy) -> None:
    variables = copy.deepcopy(DEFAULT_VARIABLES)
    del variables["impact_speed"]
    root = make_study(variables=variables)
    with pytest.raises(AsxError, match="not declared"):
        check_model(_module(root), root)


def test_param_colliding_with_consumes_raises(make_study: MakeStudy) -> None:
    root = make_study(manifest=_manifest_with(impact_speed=3.0))
    with pytest.raises(AsxError, match="collide"):
        check_model(_module(root), root)


def test_no_deck_step_raises(make_study: MakeStudy) -> None:
    manifest = copy.deepcopy(DEFAULT_MANIFEST)
    del manifest["steps"][0]["params"]["deck"]
    root = make_study(manifest=manifest)
    with pytest.raises(AsxError, match="deck"):
        check_model(_module(root), root)


def test_no_manifest_for_module_raises(make_study: MakeStudy) -> None:
    root = make_study()
    with pytest.raises(AsxError, match="no model JSON"):
        check_model(root / "system" / "models" / "other.py", root)


def test_on_error_class_is_used(make_study: MakeStudy) -> None:
    class Boom(Exception):
        pass

    root = make_study(manifest=_manifest_with(deck="decks/nope.asx"))
    with pytest.raises(Boom, match="deck not found"):
        check_model(_module(root), root, on_error=Boom)
