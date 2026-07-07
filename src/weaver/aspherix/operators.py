"""Operator factories for weaver.aspherix (Layer 1).

`build_case` is a FACTORY returning a configured `Operate` (never a subclass): it
renders a case dict to .asx and writes the deck into the pipeline's artifact dir,
returning `{name: <case path>}`. This is the fine-grained "build the input deck"
seam; the whole build-and-launch run lives in the AspherixRun orchestrator
(orchestrators.py). Both share the pure Layer 0 renderers in render.py.

The `case` mapping is the same structure Layer 0 tests (render.py): nested blocks
whose numeric values are string tokens (`"5e6"`, not `5000000.0`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from weaver.aspherix.run import write_case
from weaver.operators.operate import Operate

__all__ = ["build_case"]


def build_case(name: str, *, case: Mapping[str, Any]) -> Operate:
    """Factory: an Operate that writes `case` as `<artifact_dir>/<name>.asx`.

    do_fn(state, ctx) -> Mapping — strictly two positional arguments. Reads
    ctx["artifact_dir"] for where to write; returns the written path under `name`.
    output_field is declarative metadata (Operate does not validate the keyset).
    """

    def _do(state: Mapping[str, Any], ctx: Mapping[str, Any]) -> Mapping[str, Any]:
        del state
        case_path = write_case(case, Path(ctx["artifact_dir"]), filename=f"{name}.asx")
        return {name: str(case_path)}

    return Operate(name, _do, output_field=name, info={"factory": "build_case", "particles": len(case["particles"]["create"])})
