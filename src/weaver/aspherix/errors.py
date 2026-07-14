"""Error type for the Aspherix wrapper.

``AsxError`` extends ``RuntimeError`` (not weaver-compile's ``LowerError``) so the
wrapper stays weaver-compile-free; a study that wants validate-time Diagnostics
passes ``on_error=LowerError`` into :func:`weaver.aspherix.bind`.
"""

from __future__ import annotations


class AsxError(RuntimeError):
    """A deck, staging, readback, or solver-launch problem the wrapper can name."""
