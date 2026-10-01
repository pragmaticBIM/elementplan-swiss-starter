"""Generate survey reference points (Bezugspunkte) as inverted pyramid markers."""

from __future__ import annotations

from typing import Any, Sequence

import ifcopenshell
from ifcopenshell.api.georeference import add_georeferencing, edit_georeferencing
from ifcopenshell.api.geometry import assign_representation, edit_object_placement
from ifcopenshell.api.root import create_entity
from ifcopenshell.api.spatial import assign_container

from generators.base import (
    assign_pset,
    create_project_shell,
    get_body_context,
)
from generators.parts import (
    create_body_representation,
    create_extruded_area_solid,
    rect_polyline,
    translation_matrix,
)

# Marker defaults (metres) — tip at survey point, base above
DEFAULT_MARKER_HEIGHT = 1.50
DEFAULT_MARKER_HALF_BASE = 0.40

# Geographic centre of Switzerland (Älggi-Alp) in LV95 / LHN95
DEFAULT_ORIGIN_LV95 = {
    "easting": 2660156.235,
    "northing": 1183629.331,
    "height": 1645.0,
}


def _inverted_pyramid_solid(
    ifc_file: ifcopenshell.file,
    *,
    height: float,
    half_base: float,
) -> ifcopenshell.entity_instance:
    """Closed faceted solid: tip at local (0,0,0), square base at z=height."""
    h = float(height)
    s = float(half_base)
    if h <= 0 or s <= 0:
        raise ValueError("marker height and half_base must be positive")

    # Apex then base corners (CCW when viewed from above)
    coords = [
        (0.0, 0.0, 0.0),
        (-s, -s, h),
        (s, -s, h),
        (s, s, h),
        (-s, s, h),
    ]
    points = [
        ifc_file.create_entity("IfcCartesianPoint", Coordinates=c) for c in coords
    ]

    def face(*idxs: int) -> ifcopenshell.entity_instance:
        poly = ifc_file.create_entity(
            "IfcPolyLoop",
            Polygon=[points[i] for i in idxs],
        )
        bound = ifc_file.create_entity(
            "IfcFaceOuterBound", Bound=poly, Orientation=True
        )
        return ifc_file.create_entity("IfcFace", Bounds=[bound])

    # Side faces + base on top; CCW from outside so normals point outward
    # (inverted winding lit the accent brown instead of catalog orange).
    faces = [
        face(0, 2, 1),
        face(0, 3, 2),
        face(0, 4, 3),
        face(0, 1, 4),
        face(1, 2, 3, 4),
    ]
    shell = ifc_file.create_entity("IfcClosedShell", CfsFaces=faces)
    return ifc_file.create_entity(
        "IfcFacetedBrep",
        Outer=shell,
    )


def _create_pyramid_body_representation(
    ifc_file: ifcopenshell.file,
    body_context: ifcopenshell.entity_instance,
    solid: ifcopenshell.entity_instance,
) -> ifcopenshell.entity_instance:
    return ifc_file.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=body_context,
        RepresentationIdentifier="Body",
        RepresentationType="Brep",
        Items=[solid],
    )


def _add_ground_context(
    ifc_file: ifcopenshell.file,
    *,
    storey: ifcopenshell.entity_instance,
    body_context: ifcopenshell.entity_instance,
    points: Sequence[dict[str, Any]],
    padding: float = 8.0,
) -> ifcopenshell.entity_instance:
    """Thin ground slab under the markers for isometric scale."""
    xs = [float(p["x"]) for p in points]
    ys = [float(p["y"]) for p in points]
    x0, x1 = min(xs) - padding, max(xs) + padding
    y0, y1 = min(ys) - padding, max(ys) + padding
    thickness = 0.15
    product = create_entity(
        ifc_file,
        ifc_class="IfcSlab",
        name="Ground",
        predefined_type="FLOOR",
    )
    assign_container(ifc_file, relating_structure=storey, products=[product])
    edit_object_placement(
        ifc_file,
        product=product,
        matrix=translation_matrix(z=-thickness),
    )
    solid = create_extruded_area_solid(
        ifc_file, rect_polyline(x0, y0, x1, y1), thickness
    )
    representation = create_body_representation(ifc_file, body_context, solid)
    assign_representation(ifc_file, product=product, representation=representation)
    return product


def add_reference_point(
    ifc_file: ifcopenshell.file,
    *,
    site: ifcopenshell.entity_instance,
    body_context: ifcopenshell.entity_instance,
    name: str,
    reference: str | None = None,
    x: float = 0.0,
    y: float = 0.0,
    z: float = 0.0,
    marker_height: float = DEFAULT_MARKER_HEIGHT,
    marker_half_base: float = DEFAULT_MARKER_HALF_BASE,
) -> ifcopenshell.entity_instance:
    """Create one IfcBuildingElementProxy Bezugspunkt at local engineering coords."""
    proxy = create_entity(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name=str(name),
        predefined_type="USERDEFINED",
    )
    proxy.ObjectType = "Bezugspunkt"
    assign_container(ifc_file, relating_structure=site, products=[proxy])
    edit_object_placement(
        ifc_file,
        product=proxy,
        matrix=translation_matrix(float(x), float(y), float(z)),
    )
    solid = _inverted_pyramid_solid(
        ifc_file, height=marker_height, half_base=marker_half_base
    )
    representation = _create_pyramid_body_representation(
        ifc_file, body_context, solid
    )
    assign_representation(ifc_file, product=proxy, representation=representation)
    if reference is not None:
        assign_pset(
            ifc_file,
            proxy,
            "Pset_BuildingElementProxyCommon",
            {"Reference": str(reference)},
            datatypes={"Reference": "IfcIdentifier"},
        )
    return proxy


def apply_lv95_georeferencing(
    ifc_file: ifcopenshell.file,
    *,
    easting: float,
    northing: float,
    height: float,
) -> None:
    """Bind local engineering origin (0,0,0) to CH1903+ / LV95 (EPSG:2056)."""
    add_georeferencing(ifc_file, name="EPSG:2056")
    edit_georeferencing(
        ifc_file,
        projected_crs={
            "Name": "EPSG:2056",
            "Description": "CH1903+ / LV95",
            "GeodeticDatum": "CH1903+",
            "VerticalDatum": "LN02",
            "MapProjection": "Swiss Oblique Mercator",
            "MapZone": "LV95",
        },
        coordinate_operation={
            "Eastings": float(easting),
            "Northings": float(northing),
            "OrthogonalHeight": float(height),
            "XAxisAbscissa": 1.0,
            "XAxisOrdinate": 0.0,
            "Scale": 1.0,
        },
    )


def generate_reference_points(
    params: dict[str, Any],
) -> tuple[ifcopenshell.file, list[ifcopenshell.entity_instance]]:
    """Create ≥3 survey reference points as inverted pyramids, georeferenced to LV95.

    Required params:
      - points: list of {name, x, y, z?, Reference?} (at least 3)

    Optional params:
      - origin_lv95: {easting, northing, height} for local (0,0,0)
      - marker_height, marker_half_base
      - with_context (bool, default True): thin ground slab

    Returns ``(ifc_file, list_of_proxy_entities)``.
    """
    points = params.get("points") or []
    if len(points) < 3:
        raise ValueError("at least three reference points are required")

    origin = dict(DEFAULT_ORIGIN_LV95)
    origin.update(params.get("origin_lv95") or {})

    ifc_file, _project, site, _building, storey, body_context = create_project_shell(
        name=params.get("project_name") or "Catalog — Bezugspunkte"
    )
    apply_lv95_georeferencing(
        ifc_file,
        easting=float(origin["easting"]),
        northing=float(origin["northing"]),
        height=float(origin["height"]),
    )

    # Place site/building/storey at engineering origin (map conversion carries LV95)
    for product in (site, _building, storey):
        edit_object_placement(ifc_file, product=product)

    marker_height = float(params.get("marker_height") or DEFAULT_MARKER_HEIGHT)
    marker_half_base = float(
        params.get("marker_half_base") or DEFAULT_MARKER_HALF_BASE
    )

    if params.get("with_context", True):
        _add_ground_context(
            ifc_file,
            storey=storey,
            body_context=body_context or get_body_context(ifc_file),
            points=points,
        )

    proxies: list[ifcopenshell.entity_instance] = []
    for pt in points:
        proxies.append(
            add_reference_point(
                ifc_file,
                site=site,
                body_context=body_context,
                name=str(pt.get("name") or pt.get("Name") or "BP"),
                reference=pt.get("Reference") or pt.get("reference"),
                x=float(pt.get("x", 0.0)),
                y=float(pt.get("y", 0.0)),
                z=float(pt.get("z", 0.0)),
                marker_height=marker_height,
                marker_half_base=marker_half_base,
            )
        )

    return ifc_file, proxies
