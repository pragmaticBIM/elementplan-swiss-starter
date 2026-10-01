"""IfcBuildingElementProxy Einbringweg — centred door-sized volume in an L-corridor."""

from __future__ import annotations

from typing import Any, Sequence

import ifcopenshell

from generators.base import assign_pset, assign_qto, create_project_shell, get_body_context
from generators.parts import add_extruded_product
from generators.space import DOOR_HEIGHT, FLOOR_SLAB_THICKNESS, WALL_THICKNESS
from generators.wall import add_opening_filling, add_opening_in_wall, add_wall

# Metres — 2.5 m clear corridor; transport path matches the partition door.
DEFAULT_CORRIDOR_WIDTH = 2.50
DEFAULT_LEG_A = 7.00  # along +Y (door end)
DEFAULT_LEG_B = 6.50  # along +X (side leg)
DEFAULT_WALL_HEIGHT = 2.80
DEFAULT_DOOR_WIDTH = 2.00
DEFAULT_PATH_WIDTH = DEFAULT_DOOR_WIDTH
DEFAULT_PATH_HEIGHT = DOOR_HEIGHT
DEFAULT_COLUMN_SIZE = 0.40
DEFAULT_SLAB_PADDING = 0.30
# Path continues past the door / open side-end so the volume reads longer.
DEFAULT_PATH_OVERSHOOT = 0.80

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


def _l_polyline(
    outer_a: float,
    outer_b: float,
    width: float,
) -> list[tuple[float, float]]:
    """L footprint: vertical leg along +Y to ``outer_a``, horizontal along +X to ``outer_b``."""
    w = float(width)
    return [
        (0.0, 0.0),
        (float(outer_b), 0.0),
        (float(outer_b), w),
        (w, w),
        (w, float(outer_a)),
        (0.0, float(outer_a)),
    ]


def _shoelace_area(polyline: Sequence[Sequence[float]]) -> float:
    pts = [(float(p[0]), float(p[1])) for p in polyline]
    if pts[0] != pts[-1]:
        pts = pts + [pts[0]]
    area = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        area += x0 * y1 - x1 * y0
    return abs(area) * 0.5


def generate_installation_path(
    params: dict[str, Any] | None = None,
) -> tuple[ifcopenshell.file, ifcopenshell.entity_instance]:
    """Build an L-corridor with a centred, door-sized Einbringweg.

    The corridor is bounded by outer backdrop walls (−X / −Y) and an inner
    L-shaped wall at the reentrant corner. A door partition spans the long
    corridor leg near the bend; both corridor ends remain open.

    Layout (plan, +Y toward the isometric camera)::

        [open toward camera]        ← no end walls; path overshoots
        [left][door partition][inner wall]
        [       clear bend      ]
        [bottom][path → +X][inner wall]

    ``params`` keys:
    - ``corridor_width`` / ``path_width`` / ``path_height`` / ``path_overshoot``
    - ``leg_a`` / ``leg_b`` / ``door_width``
    - ``name`` / ``predefined_type`` / ``object_type``
    - ``properties`` / ``property_datatypes`` / ``quantities``

    Returns ``(ifc_file, installation_path_proxy)``.
    """
    params = dict(params or {})

    cw = float(params.get("corridor_width", DEFAULT_CORRIDOR_WIDTH))
    leg_a = float(params.get("leg_a", DEFAULT_LEG_A))
    leg_b = float(params.get("leg_b", DEFAULT_LEG_B))
    overshoot = float(params.get("path_overshoot", DEFAULT_PATH_OVERSHOOT))
    wall_t = float(params.get("wall_thickness", WALL_THICKNESS))
    wall_h = float(params.get("wall_height", DEFAULT_WALL_HEIGHT))
    slab_t = float(params.get("slab_thickness", FLOOR_SLAB_THICKNESS))
    pad = float(params.get("slab_padding", DEFAULT_SLAB_PADDING))
    door_w = float(params.get("door_width", DEFAULT_DOOR_WIDTH))
    door_h = float(params.get("door_height", DOOR_HEIGHT))
    pw = float(params.get("path_width", door_w))
    ph = float(params.get("path_height", door_h))

    if min(cw, pw, ph, leg_a, leg_b, wall_t, wall_h, slab_t, door_w, door_h) <= 0:
        raise ValueError("all installation-path vignette dimensions must be positive")
    if overshoot < 0:
        raise ValueError("path_overshoot must be non-negative")
    if pw >= cw:
        raise ValueError("path_width must be narrower than corridor_width")
    if door_w >= cw or door_h >= wall_h:
        raise ValueError("door must fit in the corridor partition")
    name = params.get("name") or "EW-01"
    predefined_type = params.get("predefined_type") or "USERDEFINED"
    object_type = params.get("object_type") or params.get("ObjectType") or "Einbringweg"

    # Centre the path on the partition-door opening, leaving equal clearance to
    # both corridor walls. Extend beyond the open corridor ends.
    path_a = leg_a + overshoot
    path_b = leg_b + overshoot
    path_offset = (cw - pw) * 0.5
    path_poly = [
        (x + path_offset, y + path_offset)
        for x, y in _l_polyline(
            path_a - path_offset,
            path_b - path_offset,
            pw,
        )
    ]

    # Slab covers corridor + path overshoot.
    slab_a = max(leg_a, path_a) + pad
    slab_b = max(leg_b, path_b) + pad
    slab_poly = _l_polyline(slab_a, slab_b, cw + 2.0 * pad)
    slab_poly = [(x - pad, y - pad) for x, y in slab_poly]

    ifc_file, _project, _site, _building, storey, body_context = create_project_shell(
        params.get("project_name") or name,
        storey_name="EG",
    )
    body_context = get_body_context(ifc_file) or body_context

    z_slab = 0.0
    z_top = slab_t

    add_extruded_product(
        ifc_file,
        ifc_class="IfcSlab",
        name="Bodenplatte",
        body_context=body_context,
        storey=storey,
        polyline=slab_poly,
        thickness=slab_t,
        z_bottom=z_slab,
        predefined_type="FLOOR",
    )

    # --- Walls: outer backdrop plus the marked inner L; corridor ends stay open. ---
    # Outer left (−X): direction +Y → local thickness −X (outside corridor).
    left_origin = (0.0, 0.0, z_top)
    add_wall(
        ifc_file,
        name="Flur-Wand-Links",
        body_context=body_context,
        storey=storey,
        origin=left_origin,
        length=leg_a,
        height=wall_h,
        thickness=wall_t,
        direction_xy=(0.0, 1.0),
        predefined_type="SOLIDWALL",
    )
    # Outer bottom (−Y): origin below corridor so thickness fills y∈[−t, 0].
    add_wall(
        ifc_file,
        name="Flur-Wand-Unten",
        body_context=body_context,
        storey=storey,
        origin=(0.0, -wall_t, z_top),
        length=leg_b,
        height=wall_h,
        thickness=wall_t,
        direction_xy=(1.0, 0.0),
        predefined_type="SOLIDWALL",
    )

    # Inner L at the reentrant corridor boundary. Butt the two legs together
    # without overlapping at the corner.
    inner_vertical_length = leg_a - cw - wall_t
    inner_horizontal_length = leg_b - cw
    if inner_vertical_length <= 0 or inner_horizontal_length <= 0:
        raise ValueError("corridor legs are too short for the inner walls")
    inner_long_origin = (cw, leg_a, z_top)
    add_wall(
        ifc_file,
        name="Flur-Wand-Innen-Laengs",
        body_context=body_context,
        storey=storey,
        origin=inner_long_origin,
        length=inner_vertical_length,
        height=wall_h,
        thickness=wall_t,
        direction_xy=(0.0, -1.0),
        predefined_type="SOLIDWALL",
    )
    inner_cross_origin = (cw, cw, z_top)
    add_wall(
        ifc_file,
        name="Flur-Wand-Innen-Quer",
        body_context=body_context,
        storey=storey,
        origin=inner_cross_origin,
        length=inner_horizontal_length,
        height=wall_h,
        thickness=wall_t,
        direction_xy=(1.0, 0.0),
        predefined_type="SOLIDWALL",
    )

    # Partition across the long corridor leg, close to the bend. Its door clear
    # width and height also define the transparent transport-path cross-section.
    partition_y = cw + 0.65
    partition_origin = (0.0, partition_y, z_top)
    partition = add_wall(
        ifc_file,
        body_context=body_context,
        storey=storey,
        name="Flur-Trennwand",
        origin=partition_origin,
        length=cw,
        height=wall_h,
        thickness=wall_t,
        direction_xy=(1.0, 0.0),
        predefined_type="SOLIDWALL",
    )
    partition_door_along = (cw - door_w) * 0.5
    partition_opening = add_opening_in_wall(
        ifc_file,
        host=partition,
        name="Flur-Trenntueröffnung",
        body_context=body_context,
        along=partition_door_along,
        sill=0.0,
        clear_width=door_w,
        clear_height=door_h,
        wall_thickness=wall_t,
        wall_origin=partition_origin,
        direction_xy=(1.0, 0.0),
    )
    add_opening_filling(
        ifc_file,
        opening=partition_opening,
        name="Flur-Trenntuer",
        body_context=body_context,
        storey=storey,
        along=partition_door_along,
        sill=0.0,
        clear_width=door_w,
        clear_height=door_h,
        wall_thickness=wall_t,
        wall_origin=partition_origin,
        direction_xy=(1.0, 0.0),
        ifc_class="IfcDoor",
        predefined_type="DOOR",
    )

    path = add_extruded_product(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name=name,
        body_context=body_context,
        storey=storey,
        polyline=path_poly,
        thickness=ph,
        z_bottom=z_top,
        predefined_type=predefined_type,
    )

    footprint = _shoelace_area(path_poly)
    volumes = dict(params.get("quantities") or {})
    qto = dict(volumes.get("Qto_BuildingElementProxyBaseQuantities") or {})
    qto["GrossVolume"] = round(footprint * ph, 3)
    volumes["Qto_BuildingElementProxyBaseQuantities"] = qto

    resolved = {
        "Name": name,
        "PredefinedType": predefined_type,
        "ObjectType": object_type,
        "Description": "Einbringweg im L-förmigen Flur",
        "properties": params.get("properties") or {},
        "property_datatypes": params.get("property_datatypes") or {},
        "quantities": volumes,
    }
    _apply_resolved_attributes(ifc_file, path, resolved)

    return ifc_file, path
