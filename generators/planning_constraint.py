"""IfcBuildingElementProxy Rahmenbedingungen — site + building + constraint volumes."""

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

# Metres — building mass + flood zone, railway corridor, flight corridor
DEFAULT_PLOT_THICKNESS = 0.20
DEFAULT_BUILDING_WIDTH = 8.0
DEFAULT_BUILDING_DEPTH = 6.0
DEFAULT_BUILDING_HEIGHT = 7.0
DEFAULT_YARD = 4.0
DEFAULT_FLOOD_HEIGHT = 1.5
DEFAULT_RAIL_WIDTH = 3.0
DEFAULT_RAIL_HEIGHT = 4.0
DEFAULT_FLIGHT_HEIGHT = 14.0
DEFAULT_FLIGHT_WIDTH = 10.0
DEFAULT_FLIGHT_DEPTH = 6.0

_ENTITY_FIELD_MAP = ("Name", "LongName", "Description", "PredefinedType", "ObjectType", "Phase")

_DEFAULT_CONSTRAINT_NAMES: tuple[str, ...] = (
    "Überschwemmungsgebiet",
    "Eisenbahnkorridor",
    "Flugschneise",
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


def _shoelace_area(polyline: Sequence[Sequence[float]]) -> float:
    pts = [(float(p[0]), float(p[1])) for p in polyline]
    if pts[0] != pts[-1]:
        pts = pts + [pts[0]]
    area = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        area += x0 * y1 - x1 * y0
    return abs(area) * 0.5


def _add_extruded_on_site(
    ifc_file: ifcopenshell.file,
    *,
    ifc_class: str,
    name: str,
    body_context: ifcopenshell.entity_instance,
    site: ifcopenshell.entity_instance,
    polyline: Sequence[Sequence[float]],
    thickness: float,
    z_bottom: float = 0.0,
    predefined_type: str | None = None,
) -> ifcopenshell.entity_instance:
    product = create_entity(
        ifc_file,
        ifc_class=ifc_class,
        name=name,
        predefined_type=predefined_type,
    )
    assign_container(ifc_file, relating_structure=site, products=[product])
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


def generate_planning_constraint(
    params: dict[str, Any],
) -> tuple[ifcopenshell.file, list[ifcopenshell.entity_instance]]:
    """Build Rahmenbedingung proxies + opaque building on a shared plot.

    Layout: flood zone over the front yard (low), railway corridor along the
    left edge, flight corridor as a tall volume above/behind the building.

    Returns ``(ifc_file, constraint_proxies)``.
    """
    building_w = float(params.get("building_width", DEFAULT_BUILDING_WIDTH))
    building_d = float(params.get("building_depth", DEFAULT_BUILDING_DEPTH))
    building_h = float(params.get("building_height", DEFAULT_BUILDING_HEIGHT))
    yard = float(params.get("yard", DEFAULT_YARD))
    flood_h = float(params.get("flood_height", DEFAULT_FLOOD_HEIGHT))
    rail_w = float(params.get("rail_width", DEFAULT_RAIL_WIDTH))
    rail_h = float(params.get("rail_height", DEFAULT_RAIL_HEIGHT))
    flight_h = float(params.get("flight_height", DEFAULT_FLIGHT_HEIGHT))
    flight_w = float(params.get("flight_width", DEFAULT_FLIGHT_WIDTH))
    flight_d = float(params.get("flight_depth", DEFAULT_FLIGHT_DEPTH))
    plot_t = float(params.get("plot_thickness", DEFAULT_PLOT_THICKNESS))

    names = list(params.get("constraint_names") or _DEFAULT_CONSTRAINT_NAMES)
    while len(names) < 3:
        names.append(_DEFAULT_CONSTRAINT_NAMES[len(names)])

    object_type = params.get("object_type") or "Rahmenbedingung"
    predefined_type = params.get("predefined_type") or "USERDEFINED"

    x0 = -rail_w - 1.0
    x1 = building_w + yard
    y0 = -yard
    y1 = building_d + flight_d * 0.3
    plot_w = x1 - x0
    plot_d = y1 - y0

    project_name = params.get("project_name") or "Rahmenbedingung"
    ifc_file, _project, site, _building, storey, body_context = create_project_shell(
        project_name
    )
    _ = storey
    body_context = get_body_context(ifc_file) or body_context

    plot_poly = rect_polyline(x0, y0, x1, y1)
    solid = create_extruded_area_solid(ifc_file, plot_poly, plot_t)
    representation = create_body_representation(ifc_file, body_context, solid)
    edit_object_placement(
        ifc_file,
        product=site,
        matrix=translation_matrix(z=-plot_t),
    )
    assign_representation(ifc_file, product=site, representation=representation)

    building_poly = rect_polyline(0.0, 0.0, building_w, building_d)
    _add_extruded_on_site(
        ifc_file,
        ifc_class="IfcSlab",
        name="Gebäudevolumen",
        body_context=body_context,
        site=site,
        polyline=building_poly,
        thickness=building_h,
        z_bottom=0.0,
        predefined_type="FLOOR",
    )

    proxies: list[ifcopenshell.entity_instance] = []

    # 1) Flood zone — low volume over front yard + part of building footprint
    flood_poly = rect_polyline(0.0, y0, building_w + yard * 0.5, yard + building_d * 0.35)
    flood = _add_extruded_on_site(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name=names[0],
        body_context=body_context,
        site=site,
        polyline=flood_poly,
        thickness=flood_h,
        z_bottom=0.0,
        predefined_type=predefined_type,
    )
    flood.ObjectType = object_type
    proxies.append(flood)

    # 2) Railway corridor — strip along left side
    rail_poly = rect_polyline(x0, y0, x0 + rail_w, y1)
    rail = _add_extruded_on_site(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name=names[1],
        body_context=body_context,
        site=site,
        polyline=rail_poly,
        thickness=rail_h,
        z_bottom=0.0,
        predefined_type=predefined_type,
    )
    rail.ObjectType = object_type
    proxies.append(rail)

    # 3) Flight corridor — tall volume overlapping building top / rear
    fx0 = building_w * 0.15
    fy0 = building_d * 0.4
    flight_poly = rect_polyline(fx0, fy0, fx0 + flight_w, fy0 + flight_d)
    flight = _add_extruded_on_site(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name=names[2],
        body_context=body_context,
        site=site,
        polyline=flight_poly,
        thickness=flight_h,
        z_bottom=building_h * 0.35,
        predefined_type=predefined_type,
    )
    flight.ObjectType = object_type
    proxies.append(flight)

    shared = {
        "PredefinedType": predefined_type,
        "ObjectType": object_type,
        "properties": params.get("properties") or {},
        "property_datatypes": params.get("property_datatypes") or {},
        "quantities": params.get("quantities") or {},
    }
    polys = [flood_poly, rail_poly, flight_poly]
    heights = [flood_h, rail_h, flight_h]
    for index, proxy in enumerate(proxies):
        attrs = dict(shared)
        attrs["Name"] = names[index]
        area = _shoelace_area(polys[index])
        quantities = dict(attrs.get("quantities") or {})
        qto = dict(quantities.get("Qto_BuildingElementProxyBaseQuantities") or {})
        qto["GrossVolume"] = round(area * heights[index], 3)
        quantities["Qto_BuildingElementProxyBaseQuantities"] = qto
        attrs["quantities"] = quantities
        _apply_resolved_attributes(ifc_file, proxy, attrs)

    return ifc_file, proxies
