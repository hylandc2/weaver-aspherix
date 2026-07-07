"""Test helper: normalise .asx text to its semantic command lines.

The shipped basic.asx has cosmetic alignment spaces (`single 0.1 0   0`) and blank
lines / comments between blocks. `normalize` strips those so generated output is
compared on meaning (the ordered command lines), not byte-for-byte spelling.
"""

from __future__ import annotations

import re


def normalize(text: str) -> list[str]:
    """Return the non-blank, non-comment command lines with runs of whitespace collapsed."""
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(re.sub(r"\s+", " ", line))
    return lines
