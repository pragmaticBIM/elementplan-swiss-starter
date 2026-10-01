"""Shared extruded-product helpers used by slab / covering / space vignettes."""

from __future__ import annotations

import math
from typing import Sequence

import ifcopenshell
import numpy as np
from ifcopenshell.api.geometry import assign_representation, edit_object_placement
from ifcopenshell.api.root import create_entity
from ifcopenshell.api.spatial import assign_container


def translation_matrix(x: float = 0.0, y: float = 0.0, z: float = 0.0) -> np.ndarray:
    matrix = np.eye(4, dtype=np.float64)
    matrix[0, 3] = x
    matrix[1, 3] = y
    matrix[2, 3] = z
    return matrix


def axis_placement_matrix(
    origin: Sequence[float],
    *,
    local_x: Sequence[float] = (1.0, 0.0, 0.0),
    local_z: Sequence[float] = (0.0, 0.0, 1.0),
) -> np.ndarray:
    """Build a 4×4 placement from origin and local X/Z axes."""
    ox, oy, oz = (float(v) for v in origin)
    x_axis = np.array(local_x, dtype=np.float64)
    x_axis /= np.linalg.norm(x_axis)
    z_axis = np.array(local_z, dtype=np.float64)
    z_axis /= np.linalg.norm(z_axis)
    y_axis = np.cross(z_axis, x_axis)
    y_axis /= np.linalg.norm(y_axis)
    x_axis = np.cross(y_axis, z_axis)

    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, 0] = x_axis
    matrix[:3, 1] = y_axis
    matrix[:3, 2] = z_axis
    matrix[:3, 3] = (ox, oy, oz)
    return matrix


def _axis2placement3d(
    ifc_file: ifcopenshell.file,
    origin: Sequence[float] = (0.0, 0.0, 0.0),
    *,
    axis: Sequence[float] = (0.0, 0.0, 1.0),
    ref_direction: Sequence[float] = (1.0, 0.0, 0.0),
) -> ifcopenshell.entity_instance:
    return ifc_file.create_entity(
        "IfcAxis2Placement3D",
        Location=ifc_file.create_entity(
            "IfcCartesianPoint", Coordinates=(float(origin[0]), float(origin[1]), float(origin[2]))
        ),
        Axis=ifc_file.create_entity(
            "IfcDirection", DirectionRatios=(float(axis[0]), float(axis[1]), float(axis[2]))
        ),
        RefDirection=ifc_file.create_entity(
            "IfcDirection",
            DirectionRatios=(
                float(ref_direction[0]),
                float(ref_direction[1]),
                float(ref_direction[2]),
            ),
        ),
    )


def _closed_polyline_2d(
    ifc_file: ifcopenshell.file,
    polyline: Sequence[Sequence[float]],
) -> ifcopenshell.entity_instance:
    """IfcPolyline with explicit closing vertex (viewer-friendly closed loop)."""
    pts = [(float(p[0]), float(p[1]), 0.0) for p in polyline]
    if len(pts) < 3:
        raise ValueError("polyline needs at least 3 points")
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    points = [
        ifc_file.create_entity("IfcCartesianPoint", Coordinates=coord) for coord in pts
    ]
    return ifc_file.create_entity("IfcPolyline", Points=points)


def create_extruded_area_solid(
    ifc_file: ifcopenshell.file,
    polyline: Sequence[Sequence[float]],
    depth: float,
    *,
    origin: Sequence[float] = (0.0, 0.0, 0.0),
) -> ifcopenshell.entity_instance:
    """Build a complete IfcExtrudedAreaSolid with Position, closed profile, +Z extrude.

    All lengths are in project length units (metres).
    """
    if depth <= 0:
        raise ValueError("extrusion depth must be positive")
    profile = ifc_file.create_entity(
        "IfcArbitraryClosedProfileDef",
        ProfileType="AREA",
        ProfileName=None,
        OuterCurve=_closed_polyline_2d(ifc_file, polyline),
    )
    return ifc_file.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=profile,
        Position=_axis2placement3d(ifc_file, origin),
        ExtrudedDirection=ifc_file.create_entity(
            "IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)
        ),
        Depth=float(depth),
    )


def create_tapered_extruded_solid(
    ifc_file: ifcopenshell.file,
    *,
    length: float,
    fall_length: float,
    thickness_start: float,
    thickness_end: float,
) -> ifcopenshell.entity_instance:
    """Trapezoid wedge: fall along local +X, height local +Y, extrude local +Z.

    Used for Gefälledämmung (IfcCovering ROOFING) with linear fall.
    """
    if min(length, fall_length, thickness_start, thickness_end) <= 0:
        raise ValueError("tapered solid dimensions must be positive")
    profile = ifc_file.create_entity(
        "IfcArbitraryClosedProfileDef",
        ProfileType="AREA",
        ProfileName=None,
        OuterCurve=_closed_polyline_2d(
            ifc_file,
            [
                (0.0, 0.0),
                (fall_length, 0.0),
                (fall_length, thickness_end),
                (0.0, thickness_start),
            ],
        ),
    )
    return ifc_file.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=profile,
        Position=_axis2placement3d(ifc_file),
        ExtrudedDirection=ifc_file.create_entity(
            "IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)
        ),
        Depth=float(length),
    )


def create_cylinder_solid(
    ifc_file: ifcopenshell.file,
    *,
    radius: float,
    height: float,
    origin: Sequence[float] = (0.0, 0.0, 0.0),
    segments: int = 16,
) -> ifcopenshell.entity_instance:
    """Vertical IfcExtrudedAreaSolid cylinder (+Z) with circular polyline profile."""
    if radius <= 0 or height <= 0:
        raise ValueError("cylinder radius and height must be positive")
    if segments < 8:
        raise ValueError("cylinder needs at least 8 segments")
    polyline = [
        (radius * math.cos(2.0 * math.pi * i / segments),
         radius * math.sin(2.0 * math.pi * i / segments))
        for i in range(segments)
    ]
    return create_extruded_area_solid(ifc_file, polyline, height, origin=origin)


def create_sphere_brep(
    ifc_file: ifcopenshell.file,
    *,
    radius: float,
    center: Sequence[float] = (0.0, 0.0, 0.0),
    n_u: int = 12,
    n_v: int = 8,
) -> ifcopenshell.entity_instance:
    """Approximate sphere as IfcFacetedBrep (UV grid, outward faces)."""
    if radius <= 0:
        raise ValueError("sphere radius must be positive")
    if n_u < 6 or n_v < 4:
        raise ValueError("sphere needs n_u>=6 and n_v>=4")

    cx, cy, cz = (float(center[0]), float(center[1]), float(center[2]))
    vertices: list[tuple[float, float, float]] = []
    # poles + latitude rings (excluding poles)
    vertices.append((cx, cy, cz + radius))  # north pole = 0
    for v in range(1, n_v):
        phi = math.pi * v / n_v
        sin_phi = math.sin(phi)
        cos_phi = math.cos(phi)
        for u in range(n_u):
            theta = 2.0 * math.pi * u / n_u
            vertices.append(
                (
                    cx + radius * sin_phi * math.cos(theta),
                    cy + radius * sin_phi * math.sin(theta),
                    cz + radius * cos_phi,
                )
            )
    vertices.append((cx, cy, cz - radius))  # south pole
    south = len(vertices) - 1

    faces: list[tuple[int, ...]] = []
    # top cap: pole → ring 1
    for u in range(n_u):
        a = 1 + u
        b = 1 + (u + 1) % n_u
        faces.append((0, a, b))
    # middle quads
    for v in range(n_v - 2):
        row = 1 + v * n_u
        next_row = 1 + (v + 1) * n_u
        for u in range(n_u):
            a = row + u
            b = row + (u + 1) % n_u
            c = next_row + (u + 1) % n_u
            d = next_row + u
            faces.append((a, d, c, b))
    # bottom cap
    bottom_row = 1 + (n_v - 2) * n_u
    for u in range(n_u):
        a = bottom_row + u
        b = bottom_row + (u + 1) % n_u
        faces.append((south, b, a))

    return create_faceted_brep(ifc_file, vertices, faces)


def create_body_representation(
    ifc_file: ifcopenshell.file,
    body_context: ifcopenshell.entity_instance,
    solid: ifcopenshell.entity_instance | Sequence[ifcopenshell.entity_instance],
) -> ifcopenshell.entity_instance:
    items = list(solid) if isinstance(solid, (list, tuple)) else [solid]
    return ifc_file.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=body_context,
        RepresentationIdentifier="Body",
        RepresentationType="SweptSolid",
        Items=items,
    )


def create_faceted_brep(
    ifc_file: ifcopenshell.file,
    vertices: Sequence[Sequence[float]],
    faces: Sequence[Sequence[int]],
) -> ifcopenshell.entity_instance:
    """Build an IfcFacetedBrep from vertex coords and face index loops.

    Face winding should be outward-facing for reliable tessellation.
    """
    points = [
        ifc_file.create_entity(
            "IfcCartesianPoint",
            Coordinates=(float(v[0]), float(v[1]), float(v[2])),
        )
        for v in vertices
    ]

    face_entities: list[ifcopenshell.entity_instance] = []
    for idxs in faces:
        if len(idxs) < 3:
            raise ValueError("each face needs at least 3 vertices")
        poly = ifc_file.create_entity(
            "IfcPolyLoop",
            Polygon=[points[int(i)] for i in idxs],
        )
        bound = ifc_file.create_entity(
            "IfcFaceOuterBound", Bound=poly, Orientation=True
        )
        face_entities.append(ifc_file.create_entity("IfcFace", Bounds=[bound]))

    shell = ifc_file.create_entity("IfcClosedShell", CfsFaces=face_entities)
    return ifc_file.create_entity("IfcFacetedBrep", Outer=shell)


def create_brep_body_representation(
    ifc_file: ifcopenshell.file,
    body_context: ifcopenshell.entity_instance,
    solid: ifcopenshell.entity_instance | Sequence[ifcopenshell.entity_instance],
) -> ifcopenshell.entity_instance:
    items = list(solid) if isinstance(solid, (list, tuple)) else [solid]
    return ifc_file.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=body_context,
        RepresentationIdentifier="Body",
        RepresentationType="Brep",
        Items=items,
    )


def add_extruded_product(
    ifc_file: ifcopenshell.file,
    *,
    ifc_class: str,
    name: str,
    body_context: ifcopenshell.entity_instance,
    storey: ifcopenshell.entity_instance,
    polyline: Sequence[Sequence[float]],
    thickness: float,
    z_bottom: float = 0.0,
    predefined_type: str | None = None,
) -> ifcopenshell.entity_instance:
    """Create a storey-contained product with a horizontal extruded Body.

    Extrusion runs +Z for ``thickness`` metres from ``z_bottom``.
    """
    product = create_entity(
        ifc_file,
        ifc_class=ifc_class,
        name=name,
        predefined_type=predefined_type,
    )
    assign_container(ifc_file, relating_structure=storey, products=[product])
    edit_object_placement(
        ifc_file,
        product=product,
        matrix=translation_matrix(z=z_bottom),
    )
    solid = create_extruded_area_solid(
        ifc_file,
        [(float(p[0]), float(p[1])) for p in polyline],
        float(thickness),
    )
    representation = create_body_representation(ifc_file, body_context, solid)
    assign_representation(ifc_file, product=product, representation=representation)
    return product


def bounds_2d(
    polyline: Sequence[Sequence[float]],
) -> tuple[float, float, float, float]:
    xs = [float(p[0]) for p in polyline]
    ys = [float(p[1]) for p in polyline]
    return min(xs), min(ys), max(xs), max(ys)


def rect_polyline(
    x0: float, y0: float, x1: float, y1: float
) -> list[tuple[float, float]]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
