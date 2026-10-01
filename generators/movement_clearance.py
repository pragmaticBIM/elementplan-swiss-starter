"""IfcBuildingElementProxy Bewegungsfläche — clearances in an accessible wet room."""

from __future__ import annotations

from typing import Any

import ifcopenshell

from generators.base import create_project_shell, get_body_context
from generators.parts import (
    add_extruded_product,
    create_extruded_area_solid,
    rect_polyline,
)
from generators.slab import add_slab
from generators.wall import add_wall

# Metres — accessible wet room from a typical Fertigbad plan.
# Interior 1.98 × 2.15; left wall 8.5 cm, back wall 5 cm. Both camera-facing
# sides stay open (front and the former door side) so fixtures and clearances
# stay visible.
DEFAULT_INTERIOR_WIDTH = 1.98
DEFAULT_INTERIOR_DEPTH = 2.15
DEFAULT_WALL_LEFT = 0.085
DEFAULT_WALL_OTHER = 0.050
DEFAULT_WALL_HEIGHT = 2.40
DEFAULT_SLAB_THICKNESS = 0.20
DEFAULT_CLEARANCE_HEIGHT = 1.50
DEFAULT_SHOWER_RECESS = 0.02
# Square Freihaltebereich; 1.20 m fits left of the original WC (cistern at x≈1.30).
DEFAULT_CLEARANCE_SIZE = 1.20
DEFAULT_WC_CENTER_X = 1.45
DEFAULT_WC_FRONT_GAP = 0.04
DEFAULT_WC_CISTERN_WIDTH = 0.48
DEFAULT_CLEARANCE_GAP = 0.01
DEFAULT_BASIN_WIDTH = 0.55
DEFAULT_BASIN_DEPTH = 0.42
DEFAULT_BASIN_HEIGHT = 0.14
DEFAULT_BASIN_RIM = 0.85
DEFAULT_BASIN_OFFSET_X = 0.08

def _add_basin(
    ifc_file: ifcopenshell.file,
    *,
    body_context: ifcopenshell.entity_instance,
    storey: ifcopenshell.entity_instance,
    x0: float,
    y_face: float,
) -> None:
    """Wall-hung basin against the back wall, projecting into the room (+Y)."""
    add_extruded_product(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name="Waschbecken",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(
            x0, y_face, x0 + DEFAULT_BASIN_WIDTH, y_face + DEFAULT_BASIN_DEPTH
        ),
        thickness=DEFAULT_BASIN_HEIGHT,
        z_bottom=DEFAULT_BASIN_RIM - DEFAULT_BASIN_HEIGHT,
        predefined_type="USERDEFINED",
    )


def _cut_shower_recess(
    slab: ifcopenshell.entity_instance,
    *,
    ifc_file: ifcopenshell.file,
    polyline: list[tuple[float, float]],
    slab_thickness: float,
    recess: float,
) -> None:
    """Cut a shallow recess into the top of the floor slab.

    The slab body stays in its local frame (extrusion from 0 to ``slab_thickness``).
    The cutter starts ``recess`` below the top face and pokes slightly above it so
    the finished floor is open over the shower.
    """
    representation = slab.Representation.Representations[0]
    first = representation.Items[0]
    cutter = create_extruded_area_solid(
        ifc_file,
        polyline,
        recess + 0.01,
        origin=(0.0, 0.0, slab_thickness - recess),
    )
    representation.Items = [
        ifc_file.create_entity(
            "IfcBooleanResult",
            Operator="DIFFERENCE",
            FirstOperand=first,
            SecondOperand=cutter,
        )
    ]
    representation.RepresentationType = "CSG"


def _add_shower(
    ifc_file: ifcopenshell.file,
    *,
    body_context: ifcopenshell.entity_instance,
    storey: ifcopenshell.entity_instance,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    recess: float,
) -> None:
    """Shower tray recessed into the floor, not raised above it."""
    add_extruded_product(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name="Dusche",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(x0, y0, x1, y1),
        thickness=recess,
        z_bottom=-recess,
        predefined_type="USERDEFINED",
    )


def _add_wc(
    ifc_file: ifcopenshell.file,
    *,
    body_context: ifcopenshell.entity_instance,
    storey: ifcopenshell.entity_instance,
    center_x: float,
    front_y: float,
) -> None:
    """Wall-hung WC near the open front; bowl projects back into the room (−Y)."""
    cistern_w, cistern_d, cistern_h = 0.48, 0.16, 0.80
    bowl_w, bowl_d, bowl_h = 0.36, 0.52, 0.40
    cx0 = center_x - cistern_w * 0.5
    cx1 = center_x + cistern_w * 0.5
    add_extruded_product(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name="WC-Spuelkasten",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(cx0, front_y - cistern_d, cx1, front_y),
        thickness=cistern_h,
        z_bottom=0.0,
        predefined_type="USERDEFINED",
    )
    bx0 = center_x - bowl_w * 0.5
    bx1 = center_x + bowl_w * 0.5
    by1 = front_y - cistern_d
    by0 = by1 - bowl_d
    add_extruded_product(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name="WC",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(bx0, by0, bx1, by1),
        thickness=bowl_h,
        z_bottom=0.0,
        predefined_type="USERDEFINED",
    )


def generate_movement_clearance(
    params: dict[str, Any] | None = None,
) -> tuple[ifcopenshell.file, list[ifcopenshell.entity_instance]]:
    """Build an accessible wet room with sanitary fixtures and one clearance.

    Back wall and left wall only; the camera-facing front and the door side
    stay open. The shower is a shallow recess in the floor. A single
    Wendefläche sits on the left clear floor, forward of the basin and left of
    the WC at the open front (furniture stays fixed; only the Freihaltebereich
    moves).

    Returns ``(ifc_file, clearances)``.
    """
    params = dict(params or {})
    inner_w = float(params.get("interior_width", DEFAULT_INTERIOR_WIDTH))
    inner_d = float(params.get("interior_depth", DEFAULT_INTERIOR_DEPTH))
    wall_left = float(params.get("wall_left", DEFAULT_WALL_LEFT))
    wall_t = float(params.get("wall_thickness", DEFAULT_WALL_OTHER))
    wall_h = float(params.get("wall_height", DEFAULT_WALL_HEIGHT))
    slab_t = float(params.get("slab_thickness", DEFAULT_SLAB_THICKNESS))
    clear_h = float(params.get("clearance_height", DEFAULT_CLEARANCE_HEIGHT))
    clear_s = float(params.get("clearance_size", DEFAULT_CLEARANCE_SIZE))
    recess = float(params.get("shower_recess", DEFAULT_SHOWER_RECESS))

    if min(inner_w, inner_d, wall_left, wall_t, wall_h, slab_t, clear_h, clear_s, recess) <= 0:
        raise ValueError("all movement-clearance dimensions must be positive")
    if recess >= slab_t:
        raise ValueError("shower recess must be shallower than the floor slab")

    # Right side stays open (no door wall), so the slab stops on that plane.
    plan_w = wall_left + inner_w
    plan_d = wall_t + inner_d
    x0 = wall_left
    x1 = wall_left + inner_w
    y0 = wall_t
    y1 = plan_d

    object_type = params.get("object_type") or params.get("ObjectType") or "Bewegungsfläche"
    predefined_type = params.get("predefined_type") or "USERDEFINED"

    # Basin on the back wall; WC on the open front. Freihaltebereich starts just
    # past the basin front and stays left of the WC (fixtures fixed).
    basin_x0 = x0 + DEFAULT_BASIN_OFFSET_X
    basin_front_y = y0 + DEFAULT_BASIN_DEPTH
    wc_center_x = x0 + float(params.get("wc_center_x", DEFAULT_WC_CENTER_X))
    wc_front_y = y1 - float(params.get("wc_front_gap", DEFAULT_WC_FRONT_GAP))
    wc_left = wc_center_x - 0.5 * DEFAULT_WC_CISTERN_WIDTH
    turn_x0 = x0
    turn_y0 = basin_front_y + DEFAULT_CLEARANCE_GAP
    turn_x1 = turn_x0 + clear_s
    turn_y1 = turn_y0 + clear_s
    if turn_x1 > wc_left - DEFAULT_CLEARANCE_GAP + 1e-9:
        raise ValueError("clearance overlaps the WC; reduce clearance_size")
    if turn_x1 > x1 + 1e-9 or turn_y1 > y1 + 1e-9:
        raise ValueError("clearance does not fit inside the wet-room interior")
    clearances_spec = params.get("clearances") or [
        ("Wendefläche", turn_x0, turn_y0, turn_x1, turn_y1),
    ]

    ifc_file, _project, _site, _building, storey, body_context = create_project_shell(
        params.get("project_name") or "Bewegungsfläche",
        storey_name="EG",
    )
    body_context = get_body_context(ifc_file) or body_context

    slab = add_slab(
        ifc_file,
        name="Bodenplatte",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(0.0, 0.0, plan_w, plan_d),
        thickness=slab_t,
        z_bottom=-slab_t,
        predefined_type="FLOOR",
    )
    shower_x0 = x0
    shower_y0 = y1 - 1.15
    shower_x1 = x0 + 1.15
    shower_y1 = y1
    _cut_shower_recess(
        slab,
        ifc_file=ifc_file,
        polyline=rect_polyline(shower_x0, shower_y0, shower_x1, shower_y1),
        slab_thickness=slab_t,
        recess=recess,
    )

    add_wall(
        ifc_file,
        name="Rueckwand",
        body_context=body_context,
        storey=storey,
        origin=(0.0, 0.0, 0.0),
        length=plan_w,
        height=wall_h,
        thickness=wall_t,
        direction_xy=(1.0, 0.0),
        predefined_type="PARTITIONING",
    )
    add_wall(
        ifc_file,
        name="Seitenwand-Links",
        body_context=body_context,
        storey=storey,
        origin=(0.0, plan_d, 0.0),
        length=inner_d,
        height=wall_h,
        thickness=wall_left,
        direction_xy=(0.0, -1.0),
        predefined_type="PARTITIONING",
    )
    _add_basin(
        ifc_file,
        body_context=body_context,
        storey=storey,
        x0=basin_x0,
        y_face=y0,
    )
    _add_shower(
        ifc_file,
        body_context=body_context,
        storey=storey,
        x0=shower_x0,
        y0=shower_y0,
        x1=shower_x1,
        y1=shower_y1,
        recess=recess,
    )
    # WC at the open front; Freihaltebereich stays left of it and forward of the basin.
    _add_wc(
        ifc_file,
        body_context=body_context,
        storey=storey,
        center_x=wc_center_x,
        front_y=wc_front_y,
    )

    clearances: list[ifcopenshell.entity_instance] = []
    for name, cx0, cy0, cx1, cy1 in clearances_spec:
        if min(cx1 - cx0, cy1 - cy0) <= 0:
            raise ValueError(f"clearance {name!r} has non-positive extent")
        proxy = add_extruded_product(
            ifc_file,
            ifc_class="IfcBuildingElementProxy",
            name=str(name),
            body_context=body_context,
            storey=storey,
            polyline=rect_polyline(cx0, cy0, cx1, cy1),
            thickness=clear_h,
            z_bottom=0.0,
            predefined_type=predefined_type,
        )
        proxy.ObjectType = object_type
        clearances.append(proxy)

    return ifc_file, clearances
