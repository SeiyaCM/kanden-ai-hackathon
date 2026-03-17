"""
Generate OpenFOAM case directories from Jinja2 templates and parameter grid.

Reads the parameter grid from room_config.py, renders templates, and produces
one complete OpenFOAM case directory per simulation case.
"""

import os
import shutil
import json
import math

from jinja2 import Environment, FileSystemLoader

from room_config import generate_parameter_grid, save_case_list


# Default output path (override with OUTPUT_BASE env var for cluster)
DEFAULT_OUTPUT_BASE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "data", "cfd_cases"
)


def compute_template_vars(case):
    """Convert a SimulationCase into template variables for Jinja2."""
    room = case.room
    ac = case.ac
    vent = case.ventilation
    window = case.window
    furniture = case.furniture

    # Normalize AC direction vector
    dx, dy, dz = ac.direction
    mag = math.sqrt(dx**2 + dy**2 + dz**2)
    ac_vx = ac.speed * dx / mag
    ac_vy = ac.speed * dy / mag
    ac_vz = ac.speed * dz / mag

    # Temperature in Kelvin
    ac_temp_k = ac.temperature + 273.15
    ambient_temp_k = case.ambient_temp + 273.15
    t_ref = 293.15  # 20 degrees C reference

    # Window inflow speed (natural ventilation when open)
    window_inflow_speed = -0.5 if window.is_open else 0.0

    # Ventilation outlet speed from rate and area
    vent_area = vent.size[0] * vent.size[1]  # m^2
    vent_speed = vent.rate / vent_area if vent_area > 0 and vent.rate > 0 else 0.0

    # Heat flux from furniture/humans (simplified)
    total_heat = sum(h.heat_output for h in furniture.humans)
    # Approximate heat flux over furniture surface area
    furniture_heat_flux = 0.0
    if furniture.humans:
        # rough surface area of all human cylinders
        total_surface = sum(
            2 * math.pi * h.radius * h.height for h in furniture.humans
        )
        if total_surface > 0:
            furniture_heat_flux = total_heat / total_surface

    # CO2 sources for controlDict
    co2_sources = []
    for i, human in enumerate(furniture.humans):
        # Convert L/s to volume fraction source rate
        # CO2 rate in L/s -> m^3/s -> ppm increase per cell volume
        co2_rate_m3s = human.co2_rate * 1e-3  # L/s -> m^3/s
        co2_sources.append({
            "index": i,
            "rate": co2_rate_m3s,
            "position": human.position,
        })

    # Mesh resolution for ~50K cells
    # Room: 6x5x2.7 -> cell size ~0.15m -> 40x33x18 = 23760
    # Increase z resolution: 40x33x38 = 50160
    nx = 40
    ny = 33
    nz = 38

    return {
        # Room
        "room_lx": room.length,
        "room_ly": room.width,
        "room_lz": room.height,
        # Mesh
        "nx": nx,
        "ny": ny,
        "nz": nz,
        # AC
        "ac_vx": f"{ac_vx:.4f}",
        "ac_vy": f"{ac_vy:.4f}",
        "ac_vz": f"{ac_vz:.4f}",
        "ac_temp_k": f"{ac_temp_k:.2f}",
        # Ventilation
        "vent_speed": f"{vent_speed:.4f}",
        # Window
        "window_open": window.is_open,
        "window_inflow_speed": f"{window_inflow_speed:.4f}",
        # Temperature
        "ambient_temp_k": f"{ambient_temp_k:.2f}",
        "t_ref": f"{t_ref:.2f}",
        "furniture_heat_flux": f"{furniture_heat_flux:.4f}",
        # CO2
        "co2_sources": co2_sources,
        # Layout
        "layout_id": furniture.layout_id,
    }


def render_case(case, template_dir, output_dir):
    """Render all templates for a single case and write to output directory."""
    env = Environment(
        loader=FileSystemLoader(template_dir),
        keep_trailing_newline=True,
    )
    template_vars = compute_template_vars(case)

    case_dir = os.path.join(output_dir, case.case_id)

    for subdir in ["0", "constant", "system"]:
        src_subdir = os.path.join(template_dir, subdir)
        dst_subdir = os.path.join(case_dir, subdir)
        os.makedirs(dst_subdir, exist_ok=True)

        if not os.path.isdir(src_subdir):
            continue

        for filename in os.listdir(src_subdir):
            src_path = os.path.join(src_subdir, filename)
            if not os.path.isfile(src_path):
                continue

            if filename.endswith(".j2"):
                # Render Jinja2 template
                template = env.get_template(f"{subdir}/{filename}")
                rendered = template.render(**template_vars)
                output_name = filename[:-3]  # strip .j2
                with open(os.path.join(dst_subdir, output_name), "w",
                          newline="\n") as f:
                    f.write(rendered)
            else:
                # Copy static file as-is
                shutil.copy2(src_path, os.path.join(dst_subdir, filename))

    # Write case parameters JSON
    with open(os.path.join(case_dir, "case_params.json"), "w",
              newline="\n") as f:
        json.dump(case.to_dict(), f, indent=2, ensure_ascii=False)


def main():
    output_base = os.environ.get("OUTPUT_BASE", DEFAULT_OUTPUT_BASE)
    output_base = os.path.abspath(output_base)

    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

    print(f"Template directory: {template_dir}")
    print(f"Output directory:   {output_base}")

    cases = generate_parameter_grid()
    print(f"Generating {len(cases)} OpenFOAM cases...")

    for i, case in enumerate(cases):
        render_case(case, template_dir, output_base)
        if (i + 1) % 50 == 0:
            print(f"  Generated {i + 1}/{len(cases)} cases")

    # Save case list
    save_case_list(cases, output_base)

    print(f"\nDone. {len(cases)} cases generated in: {output_base}")
    print(f"Case list: {os.path.join(output_base, 'case_list.txt')}")


if __name__ == "__main__":
    main()
