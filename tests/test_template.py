"""template.py: token formatting, placeholder scan, render contract."""

from __future__ import annotations

import pytest

from weaver.aspherix.errors import AsxError
from weaver.aspherix.template import placeholders, render, token


def test_token_bool_raises_before_int() -> None:
    with pytest.raises(AsxError, match="bool"):
        token(True)
    with pytest.raises(AsxError, match="bool"):
        token(False)


def test_token_none_raises() -> None:
    with pytest.raises(AsxError, match="None"):
        token(None)


def test_token_int() -> None:
    assert token(2000) == "2000"


def test_token_float_10g() -> None:
    assert token(0.005) == "0.005"
    assert token(1.0) == "1"
    assert token(0.0012529523) == "0.0012529523"


def test_token_nonfinite_raises() -> None:
    with pytest.raises(AsxError, match="finite"):
        token(float("nan"))
    with pytest.raises(AsxError, match="finite"):
        token(float("inf"))


def test_token_str_verbatim() -> None:
    assert token("decks/meshes/plate.stl") == "decks/meshes/plate.stl"


def test_token_unsupported_type_raises() -> None:
    with pytest.raises(AsxError, match="unsupported"):
        token([1, 2])


def test_placeholders() -> None:
    assert placeholders("a {{x}} b {{y_2}} {{x}} {not_one} ${var}") == {"x", "y_2"}


def test_render_substitutes() -> None:
    assert render("v {{speed}} r {{radius}}", {"speed": 2.0, "radius": 0.005}) == "v 2 r 0.005"


def test_render_literal_single_braces_untouched() -> None:
    assert render("materials {m1}\nx {{e}}", {"e": 0.4}) == "materials {m1}\nx 0.4"


def test_render_aspherix_dollar_syntax_untouched() -> None:
    assert render("variable ${v} x {{e}}", {"e": 1}) == "variable ${v} x 1"


def test_render_missing_placeholder_raises_with_name() -> None:
    with pytest.raises(AsxError, match=r"unresolved placeholder\(s\): typo"):
        render("x {{typo}}", {"e": 1})


def test_render_unused_ns_keys_ok() -> None:
    assert render("x {{e}}", {"e": 1, "extra": 99, "row_noise": None}) == "x 1"


def test_render_windows_path_backslashes_survive() -> None:
    # A string replacement would eat these ("C:\t..." -> tab); the function repl must not.
    out = render("mesh file {{p}}", {"p": "C:\\tmp\\x\\1.stl"})
    assert out == "mesh file C:\\tmp\\x\\1.stl"


def test_render_none_value_raises() -> None:
    with pytest.raises(AsxError, match="None"):
        render("x {{e}}", {"e": None})
