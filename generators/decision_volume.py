"""IfcBuildingElementProxy Entscheidungskörper — several volumes on one storey."""

from __future__ import annotations

from typing import Any

import ifcopenshell

from generators.base import assign_pset, assign_qto, create_project_shell, get_body_context
from generators.parts import add_extruded_product, rect_polyline
from generators.slab import add_slab
from generators.wall import add_opening_in_wall, add_wall

# Metres — one storey, closed plan, open top so the rooms read from above.
DEFAULT_PLAN_WIDTH = 9.00
DEFAULT_PLAN_DEPTH = 6.80
DEFAULT_WALL_HEIGHT = 2.50
DEFAULT_WALL_THICKNESS = 0.16
DEFAULT_SLAB_THICKNESS = 0.28
# Interior cross: left rooms | right rooms, back rooms | front rooms.
DEFAULT_SPLIT_X = 5.20
DEFAULT_SPLIT_Y = 3.20

_ENTITY_FIELD_MAP = ("Name", "LongName", "Description", "PredefinedType", "ObjectType", "Phase")


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


def _default_volumes(
    *,
    wall_t: float,
    plan_w: float,
    plan_d: float,
    split_x: float,
    split_y: float,
) -> list[dict[str, Any]]:
    """Two decisions in different rooms: wall zone spanning to the opposite wall,
    and a superseded fit-out zone that stays clear of it.
    """
    inset = 0.20
    left0 = wall_t + inset
    left1 = split_x - inset
    right1 = plan_w - wall_t - inset
    front0 = split_y + wall_t + inset
    front1 = plan_d - wall_t - inset
    back0 = wall_t + inset
    back1 = split_y - inset
    return [
        {
            "name": "Wandfarbe",
            "reference": "E-014",
            "status": "OPEN",
            "description": "Gültigkeitsbereich der Wandfarbe im Wohnen",
            # Left exterior wall through to the opposite partition — full room width.
            "box": (left0, front0 + 0.35, left1, front1 - 0.15),
            "height": 2.20,
        },
        {
            "name": "Bodenbelag",
            "reference": "E-021",
            "status": "APPROVED",
            "description": "Gültigkeitsbereich des Bodenbelags im Schlafen",
            "box": (left0, back0, left1, back1),
            "height": 2.20,
        },
        {
            "name": "Küchenfront",
            "reference": "E-008",
            "status": "SUPERSEDED",
            "description": "Abgelöster Entscheid zur Küchenfront",
            # Against the right wall only; stops short of the partition (no overlap).
            "box": (right1 - 1.55, front0 + 0.25, right1, front1 - 0.20),
            "height": 2.05,
        },
    ]


def add_closed_storey_plan(
    ifc_file: ifcopenshell.file,
    *,
    storey: ifcopenshell.entity_instance,
    body_context: ifcopenshell.entity_instance,
    plan_w: float = DEFAULT_PLAN_WIDTH,
    plan_d: float = DEFAULT_PLAN_DEPTH,
    wall_h: float = DEFAULT_WALL_HEIGHT,
    wall_t: float = DEFAULT_WALL_THICKNESS,
    slab_t: float = DEFAULT_SLAB_THICKNESS,
    split_x: float = DEFAULT_SPLIT_X,
    split_y: float = DEFAULT_SPLIT_Y,
) -> None:
    """Closed floor plan (Wohnen, Schlafen, Küche, Bad), open top, door voids."""
    if min(plan_w, plan_d, wall_h, wall_t, slab_t) <= 0:
        raise ValueError("all storey-plan dimensions must be positive")
    if not (wall_t < split_x < plan_w - wall_t):
        raise ValueError("split_x must fall inside the plan")
    if not (wall_t < split_y < plan_d - wall_t):
        raise ValueError("split_y must fall inside the plan")

    add_slab(
        ifc_file,
        name="Geschossplatte",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(0.0, 0.0, plan_w, plan_d),
        thickness=slab_t,
        z_bottom=-slab_t,
        predefined_type="FLOOR",
    )

    # Exterior walls. Thickness grows into the plan.
    # direction (1, 0) → local thickness +Y; (-1, 0) → −Y; (0, 1) → −X; (0, −1) → +X.
    side_len = plan_d - 2.0 * wall_t
    add_wall(
        ifc_file,
        name="Aussenwand-Hinten",
        body_context=body_context,
        storey=storey,
        origin=(0.0, 0.0, 0.0),
        length=plan_w,
        height=wall_h,
        thickness=wall_t,
        direction_xy=(1.0, 0.0),
        predefined_type="SOLIDWALL",
    )
    add_wall(
        ifc_file,
        name="Aussenwand-Vorne",
        body_context=body_context,
        storey=storey,
        origin=(plan_w, plan_d, 0.0),
        length=plan_w,
        height=wall_h,
        thickness=wall_t,
        direction_xy=(-1.0, 0.0),
        predefined_type="SOLIDWALL",
    )
    add_wall(
        ifc_file,
        name="Aussenwand-Links",
        body_context=body_context,
        storey=storey,
        origin=(0.0, plan_d - wall_t, 0.0),
        length=side_len,
        height=wall_h,
        thickness=wall_t,
        direction_xy=(0.0, -1.0),
        predefined_type="SOLIDWALL",
    )
    add_wall(
        ifc_file,
        name="Aussenwand-Rechts",
        body_context=body_context,
        storey=storey,
        origin=(plan_w, wall_t, 0.0),
        length=side_len,
        height=wall_h,
        thickness=wall_t,
        direction_xy=(0.0, 1.0),
        predefined_type="SOLIDWALL",
    )

    door_w = 0.90
    door_h = 2.10
    # Cross wall between back rooms and front rooms, split at the long wall.
    # Continuous Body; door void via IfcOpeningElement (no separate lintel/jamb solids).
    left_cross_len = split_x - wall_t
    left_cross_origin = (wall_t, split_y, 0.0)
    left_cross = add_wall(
        ifc_file,
        name="Trennwand-Quer",
        body_context=body_context,
        storey=storey,
        origin=left_cross_origin,
        length=left_cross_len,
        height=wall_h,
        thickness=wall_t,
        direction_xy=(1.0, 0.0),
        predefined_type="PARTITIONING",
    )
    add_opening_in_wall(
        ifc_file,
        host=left_cross,
        name="Tuer-Schlafzimmer",
        body_context=body_context,
        along=left_cross_len * 0.42,
        sill=0.0,
        clear_width=door_w,
        clear_height=door_h,
        wall_thickness=wall_t,
        wall_origin=left_cross_origin,
        direction_xy=(1.0, 0.0),
    )
    add_wall(
        ifc_file,
        name="Trennwand-Quer-Rechts",
        body_context=body_context,
        storey=storey,
        origin=(split_x + wall_t, split_y, 0.0),
        length=plan_w - split_x - 2.0 * wall_t,
        height=wall_h,
        thickness=wall_t,
        direction_xy=(1.0, 0.0),
        predefined_type="PARTITIONING",
    )
    # Long wall between left and right rooms, split at the cross wall.
    # Door in the front half, between Wohnen and Küche.
    add_wall(
        ifc_file,
        name="Trennwand-Laengs",
        body_context=body_context,
        storey=storey,
        origin=(split_x + wall_t, wall_t, 0.0),
        length=split_y - wall_t,
        height=wall_h,
        thickness=wall_t,
        direction_xy=(0.0, 1.0),
        predefined_type="PARTITIONING",
    )
    front_long_origin = (split_x + wall_t, split_y + wall_t, 0.0)
    front_long_len = plan_d - split_y - 2.0 * wall_t
    front_long = add_wall(
        ifc_file,
        name="Trennwand-Laengs-Vorne",
        body_context=body_context,
        storey=storey,
        origin=front_long_origin,
        length=front_long_len,
        height=wall_h,
        thickness=wall_t,
        direction_xy=(0.0, 1.0),
        predefined_type="PARTITIONING",
    )
    add_opening_in_wall(
        ifc_file,
        host=front_long,
        name="Tuer-Kueche",
        body_context=body_context,
        along=0.55,
        sill=0.0,
        clear_width=door_w,
        clear_height=door_h,
        wall_thickness=wall_t,
        wall_origin=front_long_origin,
        direction_xy=(0.0, 1.0),
    )


def generate_decision_volume(
    params: dict[str, Any] | None = None,
) -> tuple[ifcopenshell.file, list[ifcopenshell.entity_instance]]:
    """Build one storey with several decision volumes in different rooms.

    Closed floor plan (Wohnen, Schlafen, Küche, Bad), no roof. Each proxy is
    the spatial extent of one decision and carries its own reference and status.
    Door openings use continuous wall Bodies with IfcOpeningElement voids so the
    lintel stays merged with the jambs.

    Returns ``(ifc_file, decision_volumes)``.
    """
    params = dict(params or {})

    plan_w = float(params.get("plan_width", DEFAULT_PLAN_WIDTH))
    plan_d = float(params.get("plan_depth", DEFAULT_PLAN_DEPTH))
    wall_h = float(params.get("wall_height", DEFAULT_WALL_HEIGHT))
    wall_t = float(params.get("wall_thickness", DEFAULT_WALL_THICKNESS))
    slab_t = float(params.get("slab_thickness", DEFAULT_SLAB_THICKNESS))
    split_x = float(params.get("split_x", DEFAULT_SPLIT_X))
    split_y = float(params.get("split_y", DEFAULT_SPLIT_Y))

    object_type = params.get("object_type") or params.get("ObjectType") or "Entscheidungskörper"
    predefined_type = params.get("predefined_type") or "USERDEFINED"
    datatypes = params.get("property_datatypes") or {}
    volumes_spec = params.get("volumes") or _default_volumes(
        wall_t=wall_t,
        plan_w=plan_w,
        plan_d=plan_d,
        split_x=split_x,
        split_y=split_y,
    )

    ifc_file, _project, _site, _building, storey, body_context = create_project_shell(
        params.get("project_name") or "Entscheidungskörper",
        storey_name="EG",
    )
    body_context = get_body_context(ifc_file) or body_context
    add_closed_storey_plan(
        ifc_file,
        storey=storey,
        body_context=body_context,
        plan_w=plan_w,
        plan_d=plan_d,
        wall_h=wall_h,
        wall_t=wall_t,
        slab_t=slab_t,
        split_x=split_x,
        split_y=split_y,
    )

    volumes: list[ifcopenshell.entity_instance] = []
    for spec in volumes_spec:
        x0, y0, x1, y1 = (float(v) for v in spec["box"])
        height = float(spec["height"])
        if min(x1 - x0, y1 - y0, height) <= 0:
            raise ValueError(f"decision volume {spec.get('name')!r} has non-positive extent")
        name = str(spec.get("name") or "Entscheid")
        volume = add_extruded_product(
            ifc_file,
            ifc_class="IfcBuildingElementProxy",
            name=name,
            body_context=body_context,
            storey=storey,
            polyline=rect_polyline(x0, y0, x1, y1),
            thickness=height,
            z_bottom=0.0,
            predefined_type=predefined_type,
        )
        props = {
            "DecisionReference": spec.get("reference") or "E-000",
            "DecisionStatus": spec.get("status") or "OPEN",
        }
        _apply_resolved_attributes(
            ifc_file,
            volume,
            {
                "Name": name,
                "PredefinedType": predefined_type,
                "ObjectType": object_type,
                "Description": spec.get("description") or "",
                "properties": {"ePset_Decision": props},
                "property_datatypes": datatypes or {"ePset_Decision": {
                    "DecisionReference": "IfcIdentifier",
                    "DecisionStatus": "IfcLabel",
                }},
                "quantities": {},
            },
        )
        volumes.append(volume)

    return ifc_file, volumes
