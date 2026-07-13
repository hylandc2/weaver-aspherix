"""Pure .asx block renderers for weaver.aspherix (Layer 0).

Each function takes a param mapping and returns the text for one input-script
block; `assemble` concatenates the blocks in the order Aspherix requires
(aspherix-dem-guide.md §6). These are plain functions with NO Weaver and NO
Aspherix dependency, so the .asx text generation can be built and tested in
isolation before being wrapped in Weaver operator / orchestrator shapes.

Design note — numbers are carried as strings. An .asx script is a text format
where the exact token spelling matters (`5e6`, not `5000000.0`), so params hold
the literal tokens and renderers interpolate them verbatim. When these params
later feed a Weaver registry or a calibration sweep they will want to be real
floats; that conversion is a Layer 1 concern, deliberately not made here.
"""

from __future__ import annotations

from typing import Any, Mapping

__all__ = [
    "assemble",
    "contact_block",
    "init_block",
    "materials_block",
    "mesh_block",
    "neighbor_block",
    "output_block",
    "particles_block",
    "run_block",
    "timestep_block",
    "walls_block",
]


def _triple(values: tuple[str, str, str]) -> str:
    """Render an (x, y, z) tuple as the parenthesised `(x, y, z)` .asx form."""
    return f"({values[0]}, {values[1]}, {values[2]})"


def init_block(params: Mapping[str, Any]) -> str:
    """particle_shape + simulation_domain."""
    domain = params["domain"]
    return f"particle_shape {params['shape']}\nsimulation_domain low {_triple(domain['low'])} high {_triple(domain['high'])}"


def neighbor_block(params: Mapping[str, Any]) -> str:
    """neighbor_list skin_size .. stencil_check .."""
    neighbor = params["neighbor_list"]
    return f"neighbor_list skin_size {neighbor['skin_size']} stencil_check {neighbor['stencil_check']}"


def materials_block(params: Mapping[str, Any]) -> str:
    """materials {..} + material_properties (props emitted in declared order)."""
    material = params["material"]
    mat_id = material["id"]
    props = " ".join(f"{key} {value}" for key, value in material["properties"].items())
    return f"materials {{{mat_id}}}\nmaterial_properties {mat_id} {props}"


def contact_block(params: Mapping[str, Any]) -> str:
    """particle_contact_model + wall_contact_model (same model, per §6)."""
    contact = params["contact"]
    model = f"normal {contact['normal']} tangential {contact['tangential']}"
    return f"particle_contact_model {model}\nwall_contact_model {model}"


def timestep_block(params: Mapping[str, Any]) -> str:
    """simulation_timestep."""
    return f"simulation_timestep {params['timestep']}"


def walls_block(params: Mapping[str, Any]) -> str:
    """One primitive_wall plane per entry."""
    return "\n".join(f"primitive_wall id {wall['id']} material {wall['material']} type plane normal_axis {wall['axis']} offset {wall['offset']}" for wall in params["walls"])


def particles_block(params: Mapping[str, Any]) -> str:
    """particle_template + one create_particles line per particle."""
    particles = params["particles"]
    template_id = particles["template_id"]
    lines = [f"particle_template id {template_id} material {particles['material']} radius {particles['radius']}"]
    for particle in particles["create"]:
        pos = particle["pos"]
        vel = particle["velocity"]
        lines.append(f"create_particles {template_id} single {pos[0]} {pos[1]} {pos[2]} velocity {vel[0]} {vel[1]} {vel[2]}")
    return "\n".join(lines)


def mesh_block(params: Mapping[str, Any]) -> str:
    """mesh id .. file .. material .. translate .."""
    mesh = params["mesh"]
    return f"mesh id {mesh['id']} file {mesh['file']} material {mesh['material']} translate {_triple(mesh['translate'])}"


def output_block(params: Mapping[str, Any]) -> str:
    """write cadences + output_settings."""
    output = params["output"]
    return f"write_output_timestep {output['write_output_timestep']}\nwrite_to_terminal_timestep {output['write_to_terminal_timestep']}\noutput_settings"


def run_block(params: Mapping[str, Any]) -> str:
    """simulate time <T> or simulate time_steps <N> (exactly one)."""
    run = params["run"]
    if ("time" in run) == ("time_steps" in run):
        raise ValueError("run block needs exactly one of 'time' or 'time_steps'")
    return f"simulate time {run['time']}" if "time" in run else f"simulate time_steps {run['time_steps']}"


def assemble(params: Mapping[str, Any]) -> str:
    """Concatenate the blocks in the order Aspherix requires (§6).

    neighbor_list, walls, and mesh are optional — their blocks are skipped when
    the key is absent, so a mesh-walled case and a primitive-walled case both
    assemble from the same vocabulary.
    """
    blocks = [init_block(params)]
    if "neighbor_list" in params:
        blocks.append(neighbor_block(params))
    blocks += [materials_block(params), contact_block(params), timestep_block(params)]
    if "walls" in params:
        blocks.append(walls_block(params))
    blocks.append(particles_block(params))
    if "mesh" in params:
        blocks.append(mesh_block(params))
    blocks += [output_block(params), run_block(params)]
    return "\n\n".join(blocks) + "\n"
