"""IfcSpace Vorsatzschale — bathroom lining gap between structural and facing wall."""

from __future__ import annotations

from typing import Any

import ifcopenshell

from generators.base import create_project_shell, get_body_context
from generators.parts import add_extruded_product, rect_polyline
from generators.slab import add_slab
from generators.space import (
    FLOOR_SLAB_THICKNESS,
    WALL_THICKNESS,
    _create_space_entity,
    _shoelace_area,
)
from generators.wall import add_wall

# Metres — Installationsvorsatzschale in a wet room.
DEFAULT_ROOM_WIDTH = 2.20
DEFAULT_ROOM_DEPTH = 1.20
DEFAULT_GAP = 0.20  # clear usable Vorsatzschale depth
DEFAULT_FACING_THICKNESS = 0.07
DEFAULT_HEIGHT = 2.50


def _add_schematic_toilet(
    ifc_file: ifcopenshell.file,
    *,
    body_context: ifcopenshell.entity_instance,
    storey: ifcopenshell.entity_instance,
    center_x: float,
    wall_face_y: float,
    z_floor: float,
) -> None:
    """Simple cistern + bowl proxies in front of the facing wall (+Y, camera side)."""
    cistern_w, cistern_d, cistern_h = 0.50, 0.16, 0.85
    bowl_w, bowl_d, bowl_h = 0.36, 0.52, 0.40
    seat_h = 0.05

    # Cistern flush to facing-wall face; bowl projects into the room (+Y).
    cx0 = center_x - cistern_w * 0.5
    cx1 = center_x + cistern_w * 0.5
    cistern = add_extruded_product(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name="WC-Spuelkasten",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(cx0, wall_face_y, cx1, wall_face_y + cistern_d),
        thickness=cistern_h,
        z_bottom=z_floor,
        predefined_type="USERDEFINED",
    )
    cistern.ObjectType = "Toilet"

    bx0 = center_x - bowl_w * 0.5
    bx1 = center_x + bowl_w * 0.5
    by0 = wall_face_y + cistern_d
    by1 = by0 + bowl_d
    bowl = add_extruded_product(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name="WC-Schuessel",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(bx0, by0, bx1, by1),
        thickness=bowl_h,
        z_bottom=z_floor,
        predefined_type="USERDEFINED",
    )
    bowl.ObjectType = "Toilet"

    seat = add_extruded_product(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name="WC-Sitz",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(bx0, by0, bx1, by1 - 0.04),
        thickness=seat_h,
        z_bottom=z_floor + bowl_h,
        predefined_type="USERDEFINED",
    )
    seat.ObjectType = "Toilet"


def generate_vorsatzschale(
    params: dict[str, Any] | None = None,
) -> tuple[ifcopenshell.file, ifcopenshell.entity_instance]:
    """Build slab + structural wall + facing wall + clear Vorsatzschale + toilet.

    Layout (Y grows toward the camera / bathroom)::

        [structural wall]          ← far side (−Y)
        [Vorsatzschale 20 cm]      ← accent IfcSpace (clear usable volume)
        [facing wall 7 cm]         ← thin lining board
        [bathroom + schematic WC]  ← toilet against facing wall (+Y, near camera)

    Typical params:
      - width / room_width, room_depth, height
      - gap (default 0.20), facing_thickness (default 0.07)
      - name / predefined_type / object_type / quantities / properties
    """
    params = dict(params or {})

    width = float(params.get("width", params.get("room_width", DEFAULT_ROOM_WIDTH)))
    room_depth = float(params.get("room_depth", DEFAULT_ROOM_DEPTH))
    height = float(params.get("height", DEFAULT_HEIGHT))
    gap = float(params.get("gap", DEFAULT_GAP))
    facing_t = float(
        params.get("facing_thickness", DEFAULT_FACING_THICKNESS)
    )
    wall_t = float(params.get("wall_thickness", WALL_THICKNESS))
    slab_t = float(params.get("slab_thickness", FLOOR_SLAB_THICKNESS))

    if min(width, room_depth, height, gap, facing_t, wall_t, slab_t) <= 0:
        raise ValueError("all Vorsatzschale vignette dimensions must be positive")

    # Plan: structural wall at −Y (far), bathroom / WC at +Y (near isometric camera).
    y_wall0 = 0.0
    y_wall1 = wall_t
    y_gap0 = y_wall1
    y_gap1 = y_gap0 + gap
    y_facing0 = y_gap1
    y_facing1 = y_facing0 + facing_t
    y_room0 = y_facing1
    y_room1 = y_room0 + room_depth

    name = params.get("name") or "VS-01"
    predefined_type = params.get("predefined_type") or "USERDEFINED"
    object_type = params.get("object_type") or params.get("ObjectType") or "Vorsatzschale"

    ifc_file = params.get("ifc_file")
    storey = params.get("storey")
    body_context = params.get("body_context")
    if ifc_file is None or storey is None:
        shell_name = params.get("project_name") or name
        ifc_file, _project, _site, _building, storey, body_context = create_project_shell(
            name=f"Catalog — {shell_name}"
        )
    elif body_context is None:
        body_context = get_body_context(ifc_file)

    gap_poly = rect_polyline(0.0, y_gap0, width, y_gap1)
    area = _shoelace_area(gap_poly)
    quantities = dict(params.get("quantities") or {})
    quantities.setdefault("GrossFloorArea", round(area, 2))
    quantities.setdefault("NetFloorArea", round(area, 2))
    quantities.setdefault("GrossVolume", round(area * height, 2))
    quantities.setdefault("Height", height)

    space = _create_space_entity(
        ifc_file,
        storey=storey,
        body_context=body_context,
        name=str(name),
        long_name=params.get("long_name"),
        predefined_type=str(predefined_type),
        polyline=gap_poly,
        height=height,
        quantities=quantities,
        properties=params.get("properties") or {},
        properties_datatypes=params.get("property_datatypes") or {},
        object_type=str(object_type),
    )

    if params.get("with_context", True):
        z_slab_top = 0.0
        z_slab = z_slab_top - slab_t
        wall_height = height - z_slab_top

        slab_footprint = rect_polyline(0.0, y_wall0, width, y_room1)
        add_slab(
            ifc_file,
            name="Bad-Bodenplatte",
            body_context=body_context,
            storey=storey,
            polyline=slab_footprint,
            thickness=slab_t,
            z_bottom=z_slab,
            predefined_type="FLOOR",
        )

        # Structural wall far side (thickness toward +Y into the gap).
        add_wall(
            ifc_file,
            name="Tragwand",
            body_context=body_context,
            storey=storey,
            origin=(0.0, y_wall0, z_slab_top),
            length=width,
            height=wall_height,
            thickness=wall_t,
            direction_xy=(1.0, 0.0),
            predefined_type="SOLIDWALL",
        )

        # Facing shell / lining board (thickness toward +Y into the bathroom).
        add_wall(
            ifc_file,
            name="Vorsatzschale-Bekleidung",
            body_context=body_context,
            storey=storey,
            origin=(0.0, y_facing0, z_slab_top),
            length=width,
            height=wall_height,
            thickness=facing_t,
            direction_xy=(1.0, 0.0),
            predefined_type="PARTITIONING",
        )

        _add_schematic_toilet(
            ifc_file,
            body_context=body_context,
            storey=storey,
            center_x=width * 0.5,
            wall_face_y=y_facing1,
            z_floor=z_slab_top,
        )

    return ifc_file, space
