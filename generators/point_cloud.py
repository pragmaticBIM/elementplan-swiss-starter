"""Catalog picture for the point-cloud model (PWO).

The white floor stays. The cube is only a cloud of dots: sparse on the faces,
tighter along the edges, densest at the corners.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import ifcopenshell
from ifcopenshell.api.geometry import assign_representation
from ifcopenshell.api.root import create_entity
from ifcopenshell.api.spatial import assign_container

from generators.base import create_project_shell, get_body_context, place_product
from generators.parts import (
    add_extruded_product,
    create_brep_body_representation,
    create_sphere_brep,
    rect_polyline,
)

POINT_NAME = "Punktwolke"
# Fine enough that face angles stay under the renderer's 15° edge threshold,
# so the spheres read as solid dots rather than black wireframe balls.
_SPHERE_U = 24
_SPHERE_V = 16
_RADIUS = 0.042


def _steps(start: float, stop: float, step: float) -> list[float]:
    values: list[float] = []
    cursor = start
    while cursor <= stop + 1e-6:
        values.append(cursor)
        cursor += step
    return values


# Cube on the floor. Bottom face is omitted; the floor is the ground.
_X0, _X1 = 3.15, 7.55
_Y0, _Y1 = 2.35, 6.75
_Z0, _Z1 = 0.18 + _RADIUS, 0.18 + _RADIUS + (_X1 - _X0)
_FACE_STEP = 0.24
_EDGE_STEP = 0.10
_EDGE_CLEAR = 0.26
_CORNER_CLEAR = 0.20
_JITTER = 0.035


def _on_face(
    points: list[tuple[float, float, float]],
    *,
    fixed: str,
    value: float,
    u0: float,
    u1: float,
    v0: float,
    v1: float,
) -> None:
    """Sparse samples on one face, kept clear of the edges."""
    for u in _steps(u0 + _EDGE_CLEAR, u1 - _EDGE_CLEAR, _FACE_STEP):
        for v in _steps(v0 + _EDGE_CLEAR, v1 - _EDGE_CLEAR, _FACE_STEP):
            if fixed == "x":
                points.append((value, u, v))
            elif fixed == "y":
                points.append((u, value, v))
            else:
                points.append((u, v, value))


def _on_edge(
    points: list[tuple[float, float, float]],
    start: tuple[float, float, float],
    end: tuple[float, float, float],
) -> None:
    """Denser samples along an edge, kept clear of the corners."""
    length = (
        (end[0] - start[0]) ** 2
        + (end[1] - start[1]) ** 2
        + (end[2] - start[2]) ** 2
    ) ** 0.5
    if length <= 2 * _CORNER_CLEAR:
        return
    count = max(int((length - 2 * _CORNER_CLEAR) / _EDGE_STEP), 1)
    for index in range(count):
        t = (_CORNER_CLEAR + (index + 0.5) * (length - 2 * _CORNER_CLEAR) / count) / length
        points.append(
            (
                start[0] + (end[0] - start[0]) * t,
                start[1] + (end[1] - start[1]) * t,
                start[2] + (end[2] - start[2]) * t,
            )
        )


def _on_corner(
    points: list[tuple[float, float, float]],
    corner: tuple[float, float, float],
    rng: random.Random,
) -> None:
    """Tight cluster. Squared random radius keeps the knot densest at the corner."""
    for _ in range(52):
        radius = rng.random() ** 2 * 0.26
        theta = rng.uniform(0.0, 6.28318530718)
        phi = rng.uniform(0.15, 2.99)
        sin_phi = math.sin(phi)
        offset = (
            sin_phi * math.cos(theta),
            sin_phi * math.sin(theta),
            math.cos(phi),
        )
        z = corner[2] + radius * offset[2]
        if z < 0.20:
            z = 0.20
        points.append((corner[0] + radius * offset[0], corner[1] + radius * offset[1], z))


def _scan_points() -> list[tuple[float, float, float]]:
    """Cube skin only: open faces, tighter edges, dense corners."""
    rng = random.Random(19)
    x0, x1, y0, y1, z0, z1 = _X0, _X1, _Y0, _Y1, _Z0, _Z1
    points: list[tuple[float, float, float]] = []
    _on_face(points, fixed="y", value=y0, u0=x0, u1=x1, v0=z0, v1=z1)
    _on_face(points, fixed="y", value=y1, u0=x0, u1=x1, v0=z0, v1=z1)
    _on_face(points, fixed="x", value=x0, u0=y0, u1=y1, v0=z0, v1=z1)
    _on_face(points, fixed="x", value=x1, u0=y0, u1=y1, v0=z0, v1=z1)
    _on_face(points, fixed="z", value=z1, u0=x0, u1=x1, v0=y0, v1=y1)

    corners = [
        (x, y, z)
        for x in (x0, x1)
        for y in (y0, y1)
        for z in (z0, z1)
    ]
    edges = []
    for y in (y0, y1):
        for z in (z0, z1):
            edges.append(((x0, y, z), (x1, y, z)))
    for x in (x0, x1):
        for z in (z0, z1):
            edges.append(((x, y0, z), (x, y1, z)))
    for x in (x0, x1):
        for y in (y0, y1):
            edges.append(((x, y, z0), (x, y, z1)))
    for start, end in edges:
        _on_edge(points, start, end)
    for corner in corners:
        _on_corner(points, corner, rng)
    jittered: list[tuple[float, float, float]] = []
    corner_budget = 8 * 52
    body = points[:-corner_budget] if len(points) > corner_budget else points
    knots = points[-corner_budget:] if len(points) > corner_budget else []
    for x, y, z in body:
        jittered.append(
            (
                x + rng.uniform(-_JITTER, _JITTER),
                y + rng.uniform(-_JITTER, _JITTER),
                max(0.20, z + rng.uniform(-_JITTER, _JITTER)),
            )
        )
    jittered.extend(knots)
    return jittered


def generate_point_cloud() -> tuple[ifcopenshell.file, ifcopenshell.entity_instance]:
    """White floor; the cube is only the amber point cloud."""
    ifc_file, _project, _site, _building, storey, body = create_project_shell(
        "Punktwolke", storey_name="EG"
    )
    body = get_body_context(ifc_file) or body
    add_extruded_product(
        ifc_file,
        ifc_class="IfcSlab",
        name="Gelände",
        body_context=body,
        storey=storey,
        polyline=rect_polyline(0.0, 0.0, 11.0, 8.8),
        thickness=0.18,
        predefined_type="BASESLAB",
    )
    solids = [
        create_sphere_brep(
            ifc_file,
            radius=_RADIUS,
            center=center,
            n_u=_SPHERE_U,
            n_v=_SPHERE_V,
        )
        for center in _scan_points()
    ]
    cloud = create_entity(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name=POINT_NAME,
        predefined_type="USERDEFINED",
    )
    assign_container(ifc_file, relating_structure=storey, products=[cloud])
    place_product(ifc_file, cloud)
    assign_representation(
        ifc_file,
        product=cloud,
        representation=create_brep_body_representation(ifc_file, body, solids),
    )
    return ifc_file, cloud


def render_point_cloud_picture(repo_root: Path | None = None) -> Path:
    """Write the catalog PNG and print TIFF used by the models chapter."""
    from render.isometric import PRINT_DPI, render_isometric
    from render.print_raster import PRINT_RESOLUTION

    root = repo_root or Path(__file__).resolve().parents[1]
    media = root / "media" / "images"
    media.mkdir(parents=True, exist_ok=True)
    ifc_file, cloud = generate_point_cloud()
    png = media / "model-point-cloud.png"
    tif = media / "model-point-cloud-print.tif"
    render_isometric(
        ifc_file,
        png,
        primary_guids=[cloud.GlobalId],
        camera_padding=1.42,
        engrave=False,
        watermark=False,
    )
    render_isometric(
        ifc_file,
        tif,
        primary_guids=[cloud.GlobalId],
        camera_padding=1.42,
        resolution=PRINT_RESOLUTION,
        engrave=False,
        watermark=False,
        dpi=PRINT_DPI,
    )
    return png


if __name__ == "__main__":
    print(render_point_cloud_picture())
