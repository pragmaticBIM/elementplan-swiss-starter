"""IfcFurniture catalog generators for loose and built-in furniture."""

from __future__ import annotations

from typing import Any, Sequence

import ifcopenshell
from ifcopenshell.api.geometry import assign_representation, edit_object_placement
from ifcopenshell.api.root import create_entity
from ifcopenshell.api.spatial import assign_container

from generators.base import assign_pset, assign_qto, create_project_shell, get_body_context
from generators.parts import (
    create_body_representation,
    create_extruded_area_solid,
    rect_polyline,
    translation_matrix,
)
from generators.slab import add_slab
from generators.wall import add_wall

# Metres — interior corner vignette; furniture toward the camera (+X/+Y).
DEFAULT_ROOM_WIDTH = 4.0
DEFAULT_ROOM_DEPTH = 3.5
DEFAULT_WALL_HEIGHT = 2.80
DEFAULT_WALL_THICKNESS = 0.20
DEFAULT_SLAB_THICKNESS = 0.30

DEFAULT_TABLE_WIDTH = 1.40
DEFAULT_TABLE_DEPTH = 0.80
DEFAULT_TABLE_HEIGHT = 0.75
DEFAULT_TABLE_TOP = 0.05
DEFAULT_TABLE_LEG = 0.06

DEFAULT_CHAIR_WIDTH = 0.45
DEFAULT_CHAIR_DEPTH = 0.45
DEFAULT_CHAIR_SEAT_HEIGHT = 0.45
DEFAULT_CHAIR_SEAT_THICKNESS = 0.05
DEFAULT_CHAIR_BACK_HEIGHT = 0.40
DEFAULT_CHAIR_BACK_THICKNESS = 0.05
DEFAULT_CHAIR_CLEARANCE = 0.15  # gap between chair front and table edge

DEFAULT_KITCHEN_TALL_WIDTH = 0.60
DEFAULT_KITCHEN_UNIT_WIDTH = 0.60
DEFAULT_KITCHEN_DEPTH = 0.60
DEFAULT_KITCHEN_TALL_HEIGHT = 2.20
DEFAULT_KITCHEN_BASE_HEIGHT = 0.86
DEFAULT_KITCHEN_WALL_HEIGHT = 0.72
DEFAULT_KITCHEN_WALL_BOTTOM = 1.42
DEFAULT_KITCHEN_WORKTOP_THICKNESS = 0.04

_ENTITY_FIELD_MAP = (
    "Name",
    "LongName",
    "Description",
    "PredefinedType",
    "ObjectType",
    "Phase",
)


def _apply_resolved_attributes(
    ifc_file: ifcopenshell.file,
    product: ifcopenshell.entity_instance,
    resolved: dict[str, Any] | None,
) -> None:
    if not resolved:
        return
    for field in _ENTITY_FIELD_MAP:
        if field in resolved and hasattr(product, field):
            setattr(product, field, resolved[field])
    property_datatypes = resolved.get("property_datatypes") or {}
    for pset_name, props in (resolved.get("properties") or {}).items():
        assign_pset(
            ifc_file,
            product,
            pset_name,
            props,
            datatypes=property_datatypes.get(pset_name),
        )
    for qto_name, quantities in (resolved.get("quantities") or {}).items():
        assign_qto(ifc_file, product, qto_name, quantities)


def _box_solid(
    ifc_file: ifcopenshell.file,
    *,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    z0: float,
    height: float,
) -> ifcopenshell.entity_instance:
    return create_extruded_area_solid(
        ifc_file,
        [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
        height,
        origin=(0.0, 0.0, z0),
    )


def _add_furniture(
    ifc_file: ifcopenshell.file,
    *,
    name: str,
    predefined_type: str,
    object_type: str | None = None,
    body_context: ifcopenshell.entity_instance,
    storey: ifcopenshell.entity_instance,
    solids: Sequence[ifcopenshell.entity_instance],
) -> ifcopenshell.entity_instance:
    product = create_entity(
        ifc_file,
        ifc_class="IfcFurniture",
        name=name,
        predefined_type=predefined_type,
    )
    if object_type is not None:
        product.ObjectType = object_type
    assign_container(ifc_file, relating_structure=storey, products=[product])
    edit_object_placement(ifc_file, product=product, matrix=translation_matrix())
    representation = create_body_representation(ifc_file, body_context, list(solids))
    assign_representation(ifc_file, product=product, representation=representation)
    return product


def _table_solids(
    ifc_file: ifcopenshell.file,
    *,
    x0: float,
    y0: float,
    width: float,
    depth: float,
    height: float,
    top_t: float,
    leg: float,
) -> list[ifcopenshell.entity_instance]:
    x1, y1 = x0 + width, y0 + depth
    z_top = height - top_t
    solids = [
        _box_solid(ifc_file, x0=x0, y0=y0, x1=x1, y1=y1, z0=z_top, height=top_t),
    ]
    # Four corner legs under the top
    insets = (
        (x0, y0),
        (x1 - leg, y0),
        (x0, y1 - leg),
        (x1 - leg, y1 - leg),
    )
    for lx, ly in insets:
        solids.append(
            _box_solid(
                ifc_file,
                x0=lx,
                y0=ly,
                x1=lx + leg,
                y1=ly + leg,
                z0=0.0,
                height=z_top,
            )
        )
    return solids


def _chair_solids(
    ifc_file: ifcopenshell.file,
    *,
    x0: float,
    y0: float,
    width: float,
    depth: float,
    seat_h: float,
    seat_t: float,
    back_h: float,
    back_t: float,
) -> list[ifcopenshell.entity_instance]:
    x1, y1 = x0 + width, y0 + depth
    z_seat = seat_h - seat_t
    # Seat + four short legs + backrest on the +Y side (away from the table),
    # so the chair faces the table.
    solids = [
        _box_solid(ifc_file, x0=x0, y0=y0, x1=x1, y1=y1, z0=z_seat, height=seat_t),
        _box_solid(
            ifc_file,
            x0=x0,
            y0=y1 - back_t,
            x1=x1,
            y1=y1,
            z0=seat_h,
            height=back_h,
        ),
    ]
    leg = min(0.05, width * 0.12, depth * 0.12)
    for lx, ly in (
        (x0, y0),
        (x1 - leg, y0),
        (x0, y1 - leg),
        (x1 - leg, y1 - leg),
    ):
        solids.append(
            _box_solid(
                ifc_file,
                x0=lx,
                y0=ly,
                x1=lx + leg,
                y1=ly + leg,
                z0=0.0,
                height=z_seat,
            )
        )
    return solids


def generate_furniture(
    params: dict[str, Any] | None = None,
) -> tuple[ifcopenshell.file, list[ifcopenshell.entity_instance]]:
    """Build slab + back wall with schematic orange table and chair in front.

    Layout (top view): wall along Y=0 (away from camera); table then chair toward
    +Y so both face the default isometric eye at (+X,+Y,+Z).

    ``params`` keys:
    - room / wall / slab geometry overrides
    - table_* / chair_* geometry overrides
    - ``name`` / ``predefined_type`` for the table (YAML defaults)
    - ``chair_name`` / ``chair_predefined_type`` for the chair
    - ``properties`` / ``property_datatypes`` / ``quantities`` (YAML-resolved on table)

    Returns ``(ifc_file, [table, chair])``.
    """
    params = dict(params or {})

    room_w = float(params.get("room_width", DEFAULT_ROOM_WIDTH))
    room_d = float(params.get("room_depth", DEFAULT_ROOM_DEPTH))
    wall_h = float(params.get("wall_height", DEFAULT_WALL_HEIGHT))
    wall_t = float(params.get("wall_thickness", DEFAULT_WALL_THICKNESS))
    slab_t = float(params.get("slab_thickness", DEFAULT_SLAB_THICKNESS))

    table_w = float(params.get("table_width", DEFAULT_TABLE_WIDTH))
    table_d = float(params.get("table_depth", DEFAULT_TABLE_DEPTH))
    table_h = float(params.get("table_height", DEFAULT_TABLE_HEIGHT))
    table_top = float(params.get("table_top_thickness", DEFAULT_TABLE_TOP))
    table_leg = float(params.get("table_leg", DEFAULT_TABLE_LEG))

    chair_w = float(params.get("chair_width", DEFAULT_CHAIR_WIDTH))
    chair_d = float(params.get("chair_depth", DEFAULT_CHAIR_DEPTH))
    chair_seat_h = float(params.get("chair_seat_height", DEFAULT_CHAIR_SEAT_HEIGHT))
    chair_seat_t = float(params.get("chair_seat_thickness", DEFAULT_CHAIR_SEAT_THICKNESS))
    chair_back_h = float(params.get("chair_back_height", DEFAULT_CHAIR_BACK_HEIGHT))
    chair_back_t = float(params.get("chair_back_thickness", DEFAULT_CHAIR_BACK_THICKNESS))
    chair_clear = float(params.get("chair_clearance", DEFAULT_CHAIR_CLEARANCE))

    if min(room_w, room_d, wall_h, wall_t, slab_t, table_w, table_d, table_h) <= 0:
        raise ValueError("all furniture vignette dimensions must be positive")
    if table_top >= table_h or chair_seat_t >= chair_seat_h:
        raise ValueError("furniture top/seat thickness must be less than overall height")

    table_name = params.get("name") or "Tisch-01"
    table_type = params.get("predefined_type") or "TABLE"
    chair_name = params.get("chair_name") or "Stuhl-01"
    chair_type = params.get("chair_predefined_type") or "CHAIR"

    # Table centred on X, mid-room; chair in front toward +Y (camera).
    table_x0 = (room_w - table_w) * 0.5
    table_y0 = room_d * 0.38
    chair_x0 = table_x0 + (table_w - chair_w) * 0.5
    chair_y0 = table_y0 + table_d + chair_clear
    if chair_y0 + chair_d > room_d - 0.05:
        raise ValueError("chair does not fit in front of the table within the room")

    ifc_file, _project, _site, _building, storey, body_context = create_project_shell(
        params.get("project_name") or table_name,
        storey_name="EG",
    )
    body_context = get_body_context(ifc_file) or body_context

    z_slab = -slab_t
    # Floor plate under the room (slab top at z=0)
    add_slab(
        ifc_file,
        name="Bodenplatte",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(0.0, 0.0, room_w, room_d),
        thickness=slab_t,
        z_bottom=z_slab,
        predefined_type="FLOOR",
    )

    # Back wall along Y=0 (away from camera); thickness grows into the room (+Y)
    add_wall(
        ifc_file,
        name="Wand",
        body_context=body_context,
        storey=storey,
        origin=(0.0, 0.0, 0.0),
        length=room_w,
        height=wall_h,
        thickness=wall_t,
        direction_xy=(1.0, 0.0),
        predefined_type="PARTITIONING",
    )

    table = _add_furniture(
        ifc_file,
        name=table_name,
        predefined_type=table_type,
        body_context=body_context,
        storey=storey,
        solids=_table_solids(
            ifc_file,
            x0=table_x0,
            y0=table_y0,
            width=table_w,
            depth=table_d,
            height=table_h,
            top_t=table_top,
            leg=table_leg,
        ),
    )

    chair = _add_furniture(
        ifc_file,
        name=chair_name,
        predefined_type=chair_type,
        body_context=body_context,
        storey=storey,
        solids=_chair_solids(
            ifc_file,
            x0=chair_x0,
            y0=chair_y0,
            width=chair_w,
            depth=chair_d,
            seat_h=chair_seat_h,
            seat_t=chair_seat_t,
            back_h=chair_back_h,
            back_t=chair_back_t,
        ),
    )

    resolved = {
        "Name": table_name,
        "PredefinedType": table_type,
        "properties": params.get("properties") or {},
        "property_datatypes": params.get("property_datatypes") or {},
        "quantities": params.get("quantities") or {},
    }
    _apply_resolved_attributes(ifc_file, table, resolved)

    chair_resolved = {
        "Name": chair_name,
        "PredefinedType": chair_type,
    }
    _apply_resolved_attributes(ifc_file, chair, chair_resolved)

    return ifc_file, [table, chair]


def generate_built_in_furniture(
    params: dict[str, Any] | None = None,
) -> tuple[ifcopenshell.file, list[ifcopenshell.entity_instance]]:
    """Build a deliberately rough kitchen line from separate furniture blocks."""
    params = dict(params or {})

    room_w = float(params.get("room_width", DEFAULT_ROOM_WIDTH))
    room_d = float(params.get("room_depth", DEFAULT_ROOM_DEPTH))
    wall_h = float(params.get("wall_height", DEFAULT_WALL_HEIGHT))
    wall_t = float(params.get("wall_thickness", DEFAULT_WALL_THICKNESS))
    slab_t = float(params.get("slab_thickness", DEFAULT_SLAB_THICKNESS))
    tall_w = float(params.get("tall_width", DEFAULT_KITCHEN_TALL_WIDTH))
    unit_w = float(params.get("unit_width", DEFAULT_KITCHEN_UNIT_WIDTH))
    kitchen_d = float(params.get("kitchen_depth", DEFAULT_KITCHEN_DEPTH))
    tall_h = float(params.get("tall_height", DEFAULT_KITCHEN_TALL_HEIGHT))
    base_h = float(params.get("base_height", DEFAULT_KITCHEN_BASE_HEIGHT))
    upper_h = float(params.get("wall_unit_height", DEFAULT_KITCHEN_WALL_HEIGHT))
    upper_z = float(params.get("wall_unit_bottom", DEFAULT_KITCHEN_WALL_BOTTOM))
    worktop_t = float(
        params.get("worktop_thickness", DEFAULT_KITCHEN_WORKTOP_THICKNESS)
    )

    dimensions = (
        room_w,
        room_d,
        wall_h,
        wall_t,
        slab_t,
        tall_w,
        unit_w,
        kitchen_d,
        tall_h,
        base_h,
        upper_h,
        upper_z,
        worktop_t,
    )
    if min(dimensions) <= 0:
        raise ValueError("all built-in furniture vignette dimensions must be positive")
    line_width = tall_w + 3.0 * unit_w
    if line_width > room_w - 0.40:
        raise ValueError("kitchen line does not fit within the room width")
    if kitchen_d > room_d - wall_t:
        raise ValueError("kitchen depth does not fit within the room")
    if upper_z + upper_h > wall_h:
        raise ValueError("wall units exceed the wall height")

    project_name = str(params.get("project_name") or "Einbaumoebel-Kueche")
    predefined_type = str(params.get("predefined_type") or "USERDEFINED")
    object_type = str(params.get("object_type") or "Einbaumöbel")
    ifc_file, _project, _site, _building, storey, body_context = create_project_shell(
        project_name,
        storey_name="EG",
    )
    body_context = get_body_context(ifc_file) or body_context

    add_slab(
        ifc_file,
        name="Bodenplatte",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(0.0, 0.0, room_w, room_d),
        thickness=slab_t,
        z_bottom=-slab_t,
        predefined_type="FLOOR",
    )
    add_wall(
        ifc_file,
        name="Wand",
        body_context=body_context,
        storey=storey,
        origin=(0.0, 0.0, 0.0),
        length=room_w,
        height=wall_h,
        thickness=wall_t,
        direction_xy=(1.0, 0.0),
        predefined_type="PARTITIONING",
    )

    x0 = (room_w - line_width) * 0.5
    y0 = wall_t
    specs = [
        (
            "Hochschrank-01",
            [
                _box_solid(
                    ifc_file,
                    x0=x0,
                    y0=y0,
                    x1=x0 + tall_w,
                    y1=y0 + kitchen_d,
                    z0=0.0,
                    height=tall_h,
                )
            ],
        ),
    ]
    base_start = x0 + tall_w
    for index, label in enumerate(("Spüle", "Arbeitsfläche", "Kochfeld")):
        bx0 = base_start + index * unit_w
        specs.append(
            (
                f"Unterschrank-{label}",
                [
                    _box_solid(
                        ifc_file,
                        x0=bx0,
                        y0=y0,
                        x1=bx0 + unit_w,
                        y1=y0 + kitchen_d,
                        z0=0.0,
                        height=base_h,
                    )
                ],
            )
        )

    specs.append(
        (
            "Arbeitsplatte-01",
            [
                _box_solid(
                    ifc_file,
                    x0=base_start,
                    y0=y0,
                    x1=base_start + 3.0 * unit_w,
                    y1=y0 + kitchen_d,
                    z0=base_h,
                    height=worktop_t,
                )
            ],
        )
    )
    for index in range(3):
        ux0 = base_start + index * unit_w
        specs.append(
            (
                f"Oberschrank-{index + 1:02d}",
                [
                    _box_solid(
                        ifc_file,
                        x0=ux0,
                        y0=y0,
                        x1=ux0 + unit_w,
                        y1=y0 + kitchen_d * 0.58,
                        z0=upper_z,
                        height=upper_h,
                    )
                ],
            )
        )

    resolved = {
        "PredefinedType": predefined_type,
        "ObjectType": object_type,
        "properties": params.get("properties") or {},
        "property_datatypes": params.get("property_datatypes") or {},
        "quantities": params.get("quantities") or {},
    }
    products: list[ifcopenshell.entity_instance] = []
    for name, solids in specs:
        product = _add_furniture(
            ifc_file,
            name=name,
            predefined_type=predefined_type,
            object_type=object_type,
            body_context=body_context,
            storey=storey,
            solids=solids,
        )
        _apply_resolved_attributes(ifc_file, product, {**resolved, "Name": name})
        products.append(product)

    return ifc_file, products
