"""Minimal ``{{name}}`` templating for .asx decks (no weaver imports).

Why ``{{name}}``: real decks contain literal single braces (``materials {m1}``),
so ``str.format`` raises; Aspherix's own variable syntax is ``${var}``, so
``string.Template`` collides. ``{{name}}`` touches neither — and it is Jinja's
delimiter, so a later swap to Jinja is a drop-in, not a rewrite.
"""

from __future__ import annotations

import math
import re
from typing import Any, Mapping

from weaver.aspherix.errors import AsxError

__all__ = ["placeholders", "render", "token"]

_TOKEN = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}")


def token(value: Any) -> str:
    """Render one namespace value as deck text; raise on anything ambiguous.

    ``bool`` is checked before ``int`` (it is an ``int`` subclass, and both
    ``"True"`` and ``1`` are silently wrong in a deck). Non-finite floats and
    ``None`` raise rather than corrupt the deck. Strings pass through verbatim.
    """
    if isinstance(value, bool):
        raise AsxError(f"deck token cannot be a bool: {value!r}")
    if value is None:
        raise AsxError("deck token cannot be None")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise AsxError(f"deck token must be finite, got {value!r}")
        return f"{value:.10g}"
    if isinstance(value, str):
        return value
    raise AsxError(f"deck token has unsupported type {type(value).__name__}: {value!r}")


def placeholders(text: str) -> set[str]:
    """Every ``{{name}}`` in ``text``."""
    return set(_TOKEN.findall(text))


def render(text: str, ns: Mapping[str, Any]) -> str:
    """Substitute every ``{{name}}`` from ``ns``; raise on any unresolved one.

    Unused ``ns`` keys are fine (the row always carries extras). The replacement
    is a function, never a string — a string repl re-interprets backslashes, so
    a Windows path in the namespace would silently corrupt.
    """
    missing = placeholders(text) - set(ns)
    if missing:
        raise AsxError(f"unresolved placeholder(s): {', '.join(sorted(missing))}")
    return _TOKEN.sub(lambda m: token(ns[m.group(1)]), text)
