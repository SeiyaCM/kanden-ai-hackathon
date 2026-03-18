"""
Generate simplified STL geometry files for furniture using numpy-stl.

Creates:
- Desk: rectangular box (1.2m x 0.6m x 0.75m)
- Human: simplified cylinder approximation (radius 0.2m, height 1.2m)

STL files are generated per layout and used by snappyHexMesh for mesh refinement.
"""

import os
import math
import numpy as np
from stl import mesh

from room_config import LAYOUTS


def create_box(center, size):
    """Create a box (rectangular prism) STL mesh.

    Args:
        center: (cx, cy, cz) center of the box base (z=0 is floor).
        size: (sx, sy, sz) dimensions.

    Returns:
        stl.mesh.Mesh object.
    """
    cx, cy, cz = center
    sx, sy, sz = size

    x0 = cx - sx / 2
    x1 = cx + sx / 2
    y0 = cy - sy / 2
    y1 = cy + sy / 2
    z0 = cz
    z1 = cz + sz

    # 8 vertices
    vertices = np.array([
        [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],  # bottom
        [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1],  # top
    ])

    # 12 triangles (2 per face)
    faces = np.array([
        [0, 3, 1], [1, 3, 2],  # bottom
        [4, 5, 7], [5, 6, 7],  # top
        [0, 1, 5], [0, 5, 4],  # front (y=y0)
        [2, 3, 7], [2, 7, 6],  # back  (y=y1)
        [0, 4, 7], [0, 7, 3],  # left  (x=x0)
        [1, 2, 6], [1, 6, 5],  # right (x=x1)
    ])

    box = mesh.Mesh(np.zeros(faces.shape[0], dtype=mesh.Mesh.dtype))
    for i, f in enumerate(faces):
        for j in range(3):
            box.vectors[i][j] = vertices[f[j]]

    return box


def create_cylinder(center, radius, height, n_segments=16):
    """Create a simplified cylinder STL mesh.

    Args:
        center: (cx, cy, cz) center of the cylinder base.
        radius: cylinder radius.
        height: cylinder height.
        n_segments: number of segments for the circular cross-section.

    Returns:
        stl.mesh.Mesh object.
    """
    cx, cy, cz = center
    angles = np.linspace(0, 2 * math.pi, n_segments, endpoint=False)

    # Circle vertices at bottom and top
    bottom_center = np.array([cx, cy, cz])
    top_center = np.array([cx, cy, cz + height])

    bottom_ring = np.array([
        [cx + radius * math.cos(a), cy + radius * math.sin(a), cz]
        for a in angles
    ])
    top_ring = np.array([
        [cx + radius * math.cos(a), cy + radius * math.sin(a), cz + height]
        for a in angles
    ])

    # Triangles: bottom cap + top cap + side quads (2 tri each)
    n_faces = n_segments * 4  # bottom + top + 2*sides
    cyl = mesh.Mesh(np.zeros(n_faces, dtype=mesh.Mesh.dtype))

    idx = 0
    for i in range(n_segments):
        j = (i + 1) % n_segments

        # Bottom cap
        cyl.vectors[idx] = [bottom_center, bottom_ring[j], bottom_ring[i]]
        idx += 1

        # Top cap
        cyl.vectors[idx] = [top_center, top_ring[i], top_ring[j]]
        idx += 1

        # Side quad (2 triangles)
        cyl.vectors[idx] = [bottom_ring[i], bottom_ring[j], top_ring[j]]
        idx += 1
        cyl.vectors[idx] = [bottom_ring[i], top_ring[j], top_ring[i]]
        idx += 1

    return cyl


def generate_layout_stl(layout_id, output_dir):
    """Generate STL files for a given furniture layout.

    Produces a single combined STL file per layout.
    """
    layout = LAYOUTS[layout_id]()
    meshes = []

    # Generate desk boxes
    for desk in layout.desks:
        cx, cy, _ = desk.position
        box = create_box(
            center=(cx, cy, 0.0),
            size=desk.size,
        )
        meshes.append(box)

    # Generate human cylinders
    for human in layout.humans:
        cx, cy, _ = human.position
        cyl = create_cylinder(
            center=(cx, cy, 0.0),
            radius=human.radius,
            height=human.height,
        )
        meshes.append(cyl)

    # Combine all meshes
    combined = mesh.Mesh(np.concatenate([m.data for m in meshes]))

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"furniture_layout_{layout_id}.stl")
    combined.save(output_path)
    print(f"Generated: {output_path} ({len(combined.data)} triangles)")

    return output_path


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    stl_dir = os.path.join(script_dir, "stl")

    for layout_id in LAYOUTS:
        generate_layout_stl(layout_id, stl_dir)

    print(f"\nAll STL files generated in: {stl_dir}")


if __name__ == "__main__":
    main()
