"""IfcBuildingElementProxy Umbauperimeter on the decision-model floor plan."""

from __future__ import annotations

from typing import Any

import ifcopenshell

from generators.base import assign_pset, assign_qto, create_project_shell, get_body_context
from generators.decision_volume import (
    DEFAULT_PLAN_DEPTH,
    DEFAULT_PLAN_WIDTH,
    DEFAULT_SLAB_THICKNESS,
    DEFAULT_SPLIT_X,
    DEFAULT_SPLIT_Y,
    DEFAULT_WALL_HEIGHT,
    DEFAULT_WALL_THICKNESS,
    add_closed_storey_plan,
)
from generators.parts import add_extruded_product, rect_polyline

# Aliases for older mapping imports and geometry fallbacks.
DEFAULT_BUILDING_WIDTH = DEFAULT_PLAN_WIDTH
DEFAULT_BUILDING_DEPTH = DEFAULT_PLAN_DEPTH
DEFAULT_BUILDING_HEIGHT = DEFAULT_WALL_HEIGHT
DEFAULT_YARD = 0.0
DEFAULT_PLOT_THICKNESS = DEFAULT_SLAB_THICKNESS
DEFAULT_PERIMETER_HEIGHT = 2.40

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


def _default_perimeter_box(
    *,
    wall_t: float,
    plan_d: float,
    split_x: float,
) -> tuple[float, float, float, float]:
    """Left rooms (Wohnen + Schlafen) as one project perimeter."""
    inset = 0.12
    return (
        wall_t + inset,
        wall_t + inset,
        split_x - inset,
        plan_d - wall_t - inset,
    )


def generate_umbau_perimeter(
    params: dict[str, Any],
) -> tuple[ifcopenshell.file, ifcopenshell.entity_instance]:
    """Build one Umbauperimeter volume on the closed decision-model floor plan."""
    plan_w = float(params.get("plan_width", params.get("building_width", DEFAULT_PLAN_WIDTH)))
    plan_d = float(params.get("plan_depth", params.get("building_depth", DEFAULT_PLAN_DEPTH)))
    wall_h = float(params.get("wall_height", params.get("building_height", DEFAULT_WALL_HEIGHT)))
    wall_t = float(params.get("wall_thickness", DEFAULT_WALL_THICKNESS))
    slab_t = float(params.get("slab_thickness", DEFAULT_SLAB_THICKNESS))
    split_x = float(params.get("split_x", DEFAULT_SPLIT_X))
    split_y = float(params.get("split_y", DEFAULT_SPLIT_Y))
    perimeter_h = float(params.get("perimeter_height", DEFAULT_PERIMETER_HEIGHT))

    ifc_file, _project, _site, _building, storey, body_context = create_project_shell(
        params.get("project_name") or "Umbauperimeter",
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

    if params.get("perimeter_box"):
        x0, y0, x1, y1 = (float(v) for v in params["perimeter_box"])
    else:
        x0, y0, x1, y1 = _default_perimeter_box(
            wall_t=wall_t, plan_d=plan_d, split_x=split_x
        )
    perimeter_w = x1 - x0
    perimeter_d = y1 - y0
    if min(perimeter_w, perimeter_d, perimeter_h) <= 0:
        raise ValueError("Umbauperimeter extent must be positive")

    name = params.get("name") or "P-2026-014"
    predefined_type = params.get("predefined_type") or "USERDEFINED"
    object_type = (
        params.get("object_type") or params.get("ObjectType") or "Umbauperimeter"
    )
    perimeter = add_extruded_product(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name=name,
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(x0, y0, x1, y1),
        thickness=perimeter_h,
        z_bottom=0.0,
        predefined_type=predefined_type,
    )

    quantities = dict(params.get("quantities") or {})
    qto = dict(quantities.get("Qto_BuildingElementProxyBaseQuantities") or {})
    qto["GrossVolume"] = round(perimeter_w * perimeter_d * perimeter_h, 3)
    quantities["Qto_BuildingElementProxyBaseQuantities"] = qto
    resolved = {
        "Name": name,
        "PredefinedType": predefined_type,
        "ObjectType": object_type,
        "properties": params.get("properties") or {},
        "property_datatypes": params.get("property_datatypes") or {},
        "quantities": quantities,
    }
    _apply_resolved_attributes(ifc_file, perimeter, resolved)

    return ifc_file, perimeter
