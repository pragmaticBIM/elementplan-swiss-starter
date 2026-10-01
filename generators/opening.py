"""IfcOpeningElement catalog generator (architectural Durchbruch / Aussparung)."""

from __future__ import annotations

from typing import Any

import ifcopenshell.util.element as element_util
from ifcopenshell.api.geometry import assign_representation, edit_object_placement
from ifcopenshell.api.root import create_entity
from ifcopenshell.api.spatial import assign_container

from generators.base import assign_pset, assign_qto, get_body_context
from generators.parts import (
    axis_placement_matrix,
    create_body_representation,
    create_extruded_area_solid,
)
from generators.wall import add_opening_in_wall

# Ventilation duct penetration near the top of the partition (metres)
DEFAULT_OPENING_WIDTH = 0.60
DEFAULT_OPENING_HEIGHT = 0.40
DEFAULT_HEADROOM = 0.15  # clear space above opening to wall top
DEFAULT_DUCT_CLEARANCE = 0.05  # gap between duct and opening reveal
DEFAULT_DUCT_OVERHANG = 1.20  # duct length beyond each wall face


def _find_partition_wall(ifc_file) -> object:
    walls = [
        wall
        for wall in ifc_file.by_type("IfcWall")
        if getattr(wall, "PredefinedType", None) == "PARTITIONING"
        or (wall.Name or "").endswith("-Partition")
    ]
    if not walls:
        raise ValueError("no partition IfcWall in vignette")
    return walls[0]


def _wall_origin_length_height(
    wall,
) -> tuple[tuple[float, float, float], float, float]:
    """Recover world origin (base), centre-line length and height from Body."""
    placement = wall.ObjectPlacement
    axis = placement.RelativePlacement
    origin = axis.Location.Coordinates
    ox, oy, oz = float(origin[0]), float(origin[1]), float(origin[2])

    length = 5.0
    height = 2.8
    for rep in wall.Representation.Representations:
        for item in rep.Items:
            if not item.is_a("IfcExtrudedAreaSolid"):
                continue
            height = float(item.Depth)
            profile = item.SweptArea
            if profile.is_a("IfcArbitraryClosedProfileDef"):
                pts = profile.OuterCurve.Points
                xs = [float(p.Coordinates[0]) for p in pts]
                length = max(xs) - min(xs)
                break
    return (ox, oy, oz), length, height


def _add_duct_through_opening(
    ifc_file,
    *,
    storey,
    body_context,
    wall_origin: tuple[float, float, float],
    wall_thickness: float,
    along: float,
    sill: float,
    clear_width: float,
    clear_height: float,
    duct_overhang: float = DEFAULT_DUCT_OVERHANG,
    duct_clearance: float = DEFAULT_DUCT_CLEARANCE,
):
    """Rectangular ventilation duct running through the wall opening (along +X).

    Partition local frame: +X along wall (world +Y), thickness toward world −X.
    Duct uses world +X as extrusion so it crosses both rooms and protrudes past
    each face.
    """
    ox, oy, oz = wall_origin
    duct_w = max(0.10, clear_width - 2.0 * duct_clearance)
    duct_h = max(0.10, clear_height - 2.0 * duct_clearance)
    total_length = wall_thickness + 2.0 * duct_overhang

    # Wall thickness grows world −X from origin; start duct on the primary-room side
    x_start = ox - wall_thickness - duct_overhang
    y_start = oy + along + (clear_width - duct_w) * 0.5
    z_start = oz + sill + (clear_height - duct_h) * 0.5

    duct = create_entity(
        ifc_file,
        ifc_class="IfcDuctSegment",
        name="LK-01",
        predefined_type="RECTANGULARDUCT",
    )
    assign_container(ifc_file, relating_structure=storey, products=[duct])
    edit_object_placement(
        ifc_file,
        product=duct,
        matrix=axis_placement_matrix(
            (x_start, y_start, z_start),
            local_x=(0.0, 1.0, 0.0),
            local_z=(1.0, 0.0, 0.0),
        ),
    )
    profile = [
        (0.0, 0.0),
        (duct_w, 0.0),
        (duct_w, duct_h),
        (0.0, duct_h),
    ]
    solid = create_extruded_area_solid(ifc_file, profile, total_length)
    representation = create_body_representation(ifc_file, body_context, solid)
    assign_representation(ifc_file, product=duct, representation=representation)
    return duct


def generate_opening(
    params: dict[str, Any],
) -> tuple:
    """Build the interior-space fabric without spaces/ceilings; cut an orange opening.

    Reuses ``generate_space`` geometry so the catalog picture matches Innenräume,
    with attributes taken from ``architecture-opening-void.yaml``. A rectangular
    ventilation duct runs through the high-level Durchbruch.
    """
    from generators.space import WALL_THICKNESS, generate_space

    space_params = dict(params.get("space_params") or {})
    if not space_params:
        raise ValueError("space_params is required (reuse the interior-space vignette)")
    space_params.setdefault("with_context", True)
    space_params["omit_primary_space"] = True
    space_params["include_neighbor_space"] = False
    space_params["include_ceiling_covering"] = False
    space_params["include_ceiling_slab"] = False
    space_params["include_floor_slab"] = False
    space_params["include_floor_covering"] = False

    ifc_file, wall = generate_space(space_params)
    if not wall.is_a("IfcWall"):
        wall = _find_partition_wall(ifc_file)

    body_context = get_body_context(ifc_file)
    wall_origin, wall_length, wall_height = _wall_origin_length_height(wall)
    storey = element_util.get_container(wall)
    if storey is None:
        raise ValueError("partition wall has no storey container")

    clear_width = float(params.get("clear_width") or DEFAULT_OPENING_WIDTH)
    clear_height = float(params.get("clear_height") or DEFAULT_OPENING_HEIGHT)
    headroom = float(params.get("headroom") or DEFAULT_HEADROOM)
    # Near the top for a ventilation canal (unless an explicit sill is given)
    if params.get("sill") is not None:
        sill = float(params["sill"])
    else:
        sill = max(0.1, wall_height - clear_height - headroom)
    along = max(0.1, (wall_length - clear_width) * 0.5)

    predefined_type = (
        params.get("predefined_type") or params.get("PredefinedType") or "OPENING"
    )
    name = params.get("name") or params.get("Name") or "D-01"

    opening = add_opening_in_wall(
        ifc_file,
        host=wall,
        name=str(name),
        body_context=body_context,
        along=along,
        sill=sill,
        clear_width=clear_width,
        clear_height=clear_height,
        wall_thickness=WALL_THICKNESS,
        wall_origin=wall_origin,
        direction_xy=(0.0, 1.0),
        predefined_type=str(predefined_type),
    )

    _add_duct_through_opening(
        ifc_file,
        storey=storey,
        body_context=body_context,
        wall_origin=wall_origin,
        wall_thickness=WALL_THICKNESS,
        along=along,
        sill=sill,
        clear_width=clear_width,
        clear_height=clear_height,
        duct_overhang=float(params.get("duct_overhang") or DEFAULT_DUCT_OVERHANG),
    )

    quantities = params.get("quantities") or {}
    for qto_name, props in quantities.items():
        assign_qto(ifc_file, opening, qto_name, props)

    property_datatypes = params.get("property_datatypes") or {}
    for pset_name, props in (params.get("properties") or {}).items():
        assign_pset(
            ifc_file,
            opening,
            pset_name,
            props,
            datatypes=property_datatypes.get(pset_name),
        )

    return ifc_file, opening
