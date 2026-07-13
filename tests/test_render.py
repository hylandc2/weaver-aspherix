"""Layer 0 render tests: block renderers + assembler against the shipped basic.asx.

BASIC_PARAMS is the worked example — the param dict that reproduces
tests/fixtures/basic.asx. Copy it as the starting point for a new case.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from asx_util import normalize

from weaver.aspherix.render import (
    assemble,
    contact_block,
    init_block,
    materials_block,
    mesh_block,
    neighbor_block,
    output_block,
    particles_block,
    run_block,
    timestep_block,
    walls_block,
)

GOLDEN = Path(__file__).parent / "fixtures" / "basic.asx"
WALLED_GOLDEN = Path(__file__).parent / "fixtures" / "walled_box.asx"

# The param dict that regenerates basic.asx. Numbers are strings (see render.py).
BASIC_PARAMS: dict[str, Any] = {
    "shape": "sphere",
    "domain": {"low": ("-0.1", "-0.1", "-1"), "high": ("1", "1", "1")},
    "material": {
        "id": "m1",
        "properties": {
            "youngsModulus": "5e6",
            "poissonsRatio": "0.45",
            "coefficientRestitution": "0.3",
            "coefficientFriction": "0.5",
            "density": "2500",
        },
    },
    "contact": {"normal": "hertz", "tangential": "history"},
    "timestep": "1e-5",
    "particles": {
        "template_id": "pt",
        "material": "m1",
        "radius": "0.0499",
        "create": [
            {"pos": ("0.1", "0", "0"), "velocity": ("1", "0", "0")},
            {"pos": ("0.2", "0", "0"), "velocity": ("-1", "0", "0")},
            {"pos": ("0.3", "0.3", "0"), "velocity": ("-1", "0", "0")},
        ],
    },
    "mesh": {"id": "plate", "file": "meshes/plate.stl", "material": "m1", "translate": ("0", "0", "0.05")},
    "output": {"write_output_timestep": "1e-4", "write_to_terminal_timestep": "1e-4"},
    "run": {"time": "1e-1"},
}

# A second, differently-shaped case: 2 particles, different domain / material / radius.
VARIANT_PARAMS: dict[str, Any] = {
    "shape": "sphere",
    "domain": {"low": ("0", "0", "0"), "high": ("0.5", "0.5", "0.5")},
    "material": {
        "id": "m1",
        "properties": {
            "youngsModulus": "1e7",
            "poissonsRatio": "0.3",
            "coefficientRestitution": "0.5",
            "coefficientFriction": "0.4",
            "density": "1000",
        },
    },
    "contact": {"normal": "hertz", "tangential": "history"},
    "timestep": "5e-6",
    "particles": {
        "template_id": "pt",
        "material": "m1",
        "radius": "0.01",
        "create": [
            {"pos": ("0.1", "0.1", "0.4"), "velocity": ("0", "0", "0")},
            {"pos": ("0.2", "0.2", "0.4"), "velocity": ("0", "0", "0")},
        ],
    },
    "mesh": {"id": "floor", "file": "meshes/floor.stl", "material": "m1", "translate": ("0", "0", "0")},
    "output": {"write_output_timestep": "1e-3", "write_to_terminal_timestep": "1e-3"},
    "run": {"time": "0.2"},
}

# A mesh-free case: primitive plane walls box the domain, run by step count.
# Regenerates walled_box.asx and doubles as the aspherix-study orchestrator case.
WALLED_PARAMS: dict[str, Any] = {
    "shape": "sphere",
    "domain": {"low": ("0", "0", "0"), "high": ("0.1", "0.1", "0.1")},
    "neighbor_list": {"skin_size": "0.002", "stencil_check": "no"},
    "material": {
        "id": "m1",
        "properties": {
            "youngsModulus": "5e6",
            "poissonsRatio": "0.3",
            "coefficientRestitution": "0.4",
            "coefficientFriction": "0.5",
            "density": "2500",
        },
    },
    "contact": {"normal": "hertz", "tangential": "history"},
    "timestep": "1e-5",
    "walls": [
        {"id": "wx0", "material": "m1", "axis": "x", "offset": "0"},
        {"id": "wx1", "material": "m1", "axis": "x", "offset": "0.1"},
        {"id": "wy0", "material": "m1", "axis": "y", "offset": "0"},
        {"id": "wy1", "material": "m1", "axis": "y", "offset": "0.1"},
        {"id": "wz0", "material": "m1", "axis": "z", "offset": "0"},
        {"id": "wz1", "material": "m1", "axis": "z", "offset": "0.1"},
    ],
    "particles": {
        "template_id": "pt",
        "material": "m1",
        "radius": "0.005",
        "create": [
            {"pos": ("0.02", "0.05", "0.05"), "velocity": ("-2", "0", "0")},
            {"pos": ("0.05", "0.08", "0.05"), "velocity": ("0", "2", "0")},
            {"pos": ("0.05", "0.05", "0.02"), "velocity": ("0", "0", "-2")},
        ],
    },
    "output": {"write_output_timestep": "1e-3", "write_to_terminal_timestep": "1e-3"},
    "run": {"time_steps": "2000"},
}

# The command sequence every case emits, in §6 order (create_particles repeats per particle).
EXPECTED_HEADS = [
    "particle_shape",
    "simulation_domain",
    "materials",
    "material_properties",
    "particle_contact_model",
    "wall_contact_model",
    "simulation_timestep",
    "particle_template",
    "create_particles",
    "mesh",
    "write_output_timestep",
    "write_to_terminal_timestep",
    "output_settings",
    "simulate",
]


def golden_lines() -> list[str]:
    return normalize(GOLDEN.read_text())


WALLED_HEADS = [
    "particle_shape",
    "simulation_domain",
    "neighbor_list",
    "materials",
    "material_properties",
    "particle_contact_model",
    "wall_contact_model",
    "simulation_timestep",
    "primitive_wall",
    "particle_template",
    "create_particles",
    "write_output_timestep",
    "write_to_terminal_timestep",
    "output_settings",
    "simulate",
]


def heads(text: str) -> list[str]:
    """First token of each command line, with consecutive repeats (create_particles, primitive_wall) collapsed to one."""
    result: list[str] = []
    for line in normalize(text):
        head = line.split(" ", 1)[0]
        if head in ("create_particles", "primitive_wall") and result and result[-1] == head:
            continue
        result.append(head)
    return result


# Step 1: the normalize helper is stable / idempotent.
def test_normalize_is_idempotent() -> None:
    once = golden_lines()
    assert normalize("\n".join(once)) == once


# Steps 2-3: each block renderer matches its slice of the golden file.
def test_init_block() -> None:
    assert normalize(init_block(BASIC_PARAMS)) == golden_lines()[0:2]


def test_materials_block() -> None:
    assert normalize(materials_block(BASIC_PARAMS)) == golden_lines()[2:4]


def test_contact_block() -> None:
    assert normalize(contact_block(BASIC_PARAMS)) == golden_lines()[4:6]


def test_timestep_block() -> None:
    assert normalize(timestep_block(BASIC_PARAMS)) == golden_lines()[6:7]


def test_particles_block() -> None:
    assert normalize(particles_block(BASIC_PARAMS)) == golden_lines()[7:11]


def test_mesh_block() -> None:
    assert normalize(mesh_block(BASIC_PARAMS)) == golden_lines()[11:12]


def test_output_block() -> None:
    assert normalize(output_block(BASIC_PARAMS)) == golden_lines()[12:15]


def test_run_block() -> None:
    assert normalize(run_block(BASIC_PARAMS)) == golden_lines()[15:16]


# Step 4: the whole-skeleton success criterion — assemble reproduces basic.asx.
def test_assemble_reproduces_golden() -> None:
    assert normalize(assemble(BASIC_PARAMS)) == golden_lines()


# Step 7: a second param dict proves the renderers are parameterised, not hardcoded.
def test_variant_is_parameterised() -> None:
    lines = normalize(assemble(VARIANT_PARAMS))
    assert len(lines) == 15  # one fewer particle than basic (16 lines)
    assert lines[0] == "particle_shape sphere"
    assert lines[-1] == "simulate time 0.2"
    assert sum(1 for line in lines if line.startswith("create_particles")) == 2
    assert lines[1] != golden_lines()[1]  # different simulation_domain


def test_block_order_holds_for_both_cases() -> None:
    assert heads(assemble(BASIC_PARAMS)) == EXPECTED_HEADS
    assert heads(assemble(VARIANT_PARAMS)) == EXPECTED_HEADS


# The walled (mesh-free) case: new optional blocks against the walled_box.asx golden.
def test_neighbor_block() -> None:
    assert normalize(neighbor_block(WALLED_PARAMS)) == ["neighbor_list skin_size 0.002 stencil_check no"]


def test_walls_block() -> None:
    lines = normalize(walls_block(WALLED_PARAMS))
    assert len(lines) == 6
    assert lines[0] == "primitive_wall id wx0 material m1 type plane normal_axis x offset 0"
    assert lines[-1] == "primitive_wall id wz1 material m1 type plane normal_axis z offset 0.1"


def test_run_block_time_steps() -> None:
    assert normalize(run_block(WALLED_PARAMS)) == ["simulate time_steps 2000"]


def test_run_block_rejects_both_and_neither() -> None:
    with pytest.raises(ValueError):
        run_block({"run": {}})
    with pytest.raises(ValueError):
        run_block({"run": {"time": "1e-1", "time_steps": "2000"}})


def test_assemble_skips_optional_blocks() -> None:
    basic_heads = heads(assemble(BASIC_PARAMS))
    assert "neighbor_list" not in basic_heads
    assert "primitive_wall" not in basic_heads
    assert "mesh" not in heads(assemble(WALLED_PARAMS))


def test_assemble_reproduces_walled_golden() -> None:
    assert normalize(assemble(WALLED_PARAMS)) == normalize(WALLED_GOLDEN.read_text())


def test_walled_block_order() -> None:
    assert heads(assemble(WALLED_PARAMS)) == WALLED_HEADS
