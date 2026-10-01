"""IfcBuildingElementProxy Baustelleneinrichtungsobjekte on a simple site + building mass."""

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

# Metres — building mass + fence, container, crane, storage area
DEFAULT_PLOT_THICKNESS = 0.20
DEFAULT_BUILDING_WIDTH = 8.0
DEFAULT_BUILDING_DEPTH = 6.0
DEFAULT_BUILDING_HEIGHT = 7.0
DEFAULT_YARD_DEPTH = 10.0
DEFAULT_YARD_SIDE = 6.0
DEFAULT_FENCE_HEIGHT = 2.0
DEFAULT_FENCE_THICKNESS = 0.15
DEFAULT_CONTAINER_WIDTH = 2.4
DEFAULT_CONTAINER_DEPTH = 6.0
DEFAULT_CONTAINER_HEIGHT = 2.6
DEFAULT_CRANE_PAD = 4.0
DEFAULT_CRANE_PAD_THICKNESS = 0.5
DEFAULT_CRANE_HEIGHT = 12.0
DEFAULT_CRANE_MAST = 0.6
DEFAULT_CRANE_JIB_LENGTH = 10.0
DEFAULT_CRANE_JIB_WIDTH = 0.5
DEFAULT_CRANE_JIB_HEIGHT = 0.5
DEFAULT_STORAGE_WIDTH = 5.0
DEFAULT_STORAGE_DEPTH = 4.0
DEFAULT_STORAGE_HEIGHT = 1.2

_ENTITY_FIELD_MAP = ("Name", "LongName", "Description", "PredefinedType", "ObjectType", "Phase")

# Default catalog Names from the Name value list (German tokens)
# Fence, container, crane (mast+jib), storage, crane foundation
_DEFAULT_LOGISTICS_NAMES: tuple[str, ...] = (
    "Zaun",
    "Container",
    "Kran",
    "Lagerfläche",
    "Kranfundament",
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
    """Create a site-contained product with a horizontal extruded Body."""
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


def generate_construction_logistics(
    params: dict[str, Any],
) -> tuple[ifcopenshell.file, list[ifcopenshell.entity_instance]]:
    """Build site logistics proxies + opaque building mass on a shared plot.

    Layout (plan): building at +Y; yard in front with fence along street edge,
    container at left, crane foundation + mast + jib at right, storage in the middle.

    Returns ``(ifc_file, logistics_proxies)`` — fence, container, foundation,
    mast, jib, storage (all IfcBuildingElementProxy except building fabric).
    """
    building_w = float(params.get("building_width", DEFAULT_BUILDING_WIDTH))
    building_d = float(params.get("building_depth", DEFAULT_BUILDING_DEPTH))
    building_h = float(params.get("building_height", DEFAULT_BUILDING_HEIGHT))
    yard_d = float(params.get("yard_depth", DEFAULT_YARD_DEPTH))
    yard_side = float(params.get("yard_side", DEFAULT_YARD_SIDE))
    fence_h = float(params.get("fence_height", DEFAULT_FENCE_HEIGHT))
    fence_t = float(params.get("fence_thickness", DEFAULT_FENCE_THICKNESS))
    cont_w = float(params.get("container_width", DEFAULT_CONTAINER_WIDTH))
    cont_d = float(params.get("container_depth", DEFAULT_CONTAINER_DEPTH))
    cont_h = float(params.get("container_height", DEFAULT_CONTAINER_HEIGHT))
    crane_pad = float(params.get("crane_pad", DEFAULT_CRANE_PAD))
    crane_pad_t = float(params.get("crane_pad_thickness", DEFAULT_CRANE_PAD_THICKNESS))
    crane_h = float(params.get("crane_height", DEFAULT_CRANE_HEIGHT))
    crane_mast = float(params.get("crane_mast", DEFAULT_CRANE_MAST))
    crane_jib_l = float(params.get("crane_jib_length", DEFAULT_CRANE_JIB_LENGTH))
    crane_jib_w = float(params.get("crane_jib_width", DEFAULT_CRANE_JIB_WIDTH))
    crane_jib_h = float(params.get("crane_jib_height", DEFAULT_CRANE_JIB_HEIGHT))
    stor_w = float(params.get("storage_width", DEFAULT_STORAGE_WIDTH))
    stor_d = float(params.get("storage_depth", DEFAULT_STORAGE_DEPTH))
    stor_h = float(params.get("storage_height", DEFAULT_STORAGE_HEIGHT))
    plot_t = float(params.get("plot_thickness", DEFAULT_PLOT_THICKNESS))

    names = list(params.get("logistics_names") or _DEFAULT_LOGISTICS_NAMES)
    while len(names) < len(_DEFAULT_LOGISTICS_NAMES):
        names.append(_DEFAULT_LOGISTICS_NAMES[len(names)])

    object_type = params.get("object_type") or "Baustelleneinricht"
    predefined_type = params.get("predefined_type") or "USERDEFINED"
    logistics_attrs = list(params.get("logistics_attrs") or [])

    x0 = -yard_side
    x1 = building_w + yard_side
    plot_w = x1 - x0
    plot_d = yard_d + building_d
    _ = plot_w

    project_name = params.get("project_name") or "Baustelleneinrichtungsobjekt"
    ifc_file, _project, site, _building, storey, body_context = create_project_shell(
        project_name
    )
    _ = storey
    body_context = get_body_context(ifc_file) or body_context

    # Plot plate on site (below Z=0)
    plot_poly = rect_polyline(x0, 0.0, x1, plot_d)
    solid = create_extruded_area_solid(ifc_file, plot_poly, plot_t)
    representation = create_body_representation(ifc_file, body_context, solid)
    edit_object_placement(
        ifc_file,
        product=site,
        matrix=translation_matrix(z=-plot_t),
    )
    assign_representation(ifc_file, product=site, representation=representation)

    # Opaque building mass as IfcSlab so it reads as fabric, not a logistics proxy
    building_poly = rect_polyline(0.0, yard_d, building_w, yard_d + building_d)
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

    fence_poly = rect_polyline(x0, 0.0, x1, fence_t)
    fence = _add_extruded_on_site(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name=names[0],
        body_context=body_context,
        site=site,
        polyline=fence_poly,
        thickness=fence_h,
        z_bottom=0.0,
        predefined_type=predefined_type,
    )
    fence.ObjectType = object_type
    proxies.append(fence)

    cont_x = x0 + 0.5
    cont_y = 1.5
    cont_poly = rect_polyline(cont_x, cont_y, cont_x + cont_w, cont_y + cont_d)
    container = _add_extruded_on_site(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name=names[1],
        body_context=body_context,
        site=site,
        polyline=cont_poly,
        thickness=cont_h,
        z_bottom=0.0,
        predefined_type=predefined_type,
    )
    container.ObjectType = object_type
    proxies.append(container)

    # Separate crane foundation (pad)
    crane_x = building_w + 0.8
    crane_y = 2.5
    pad_poly = rect_polyline(crane_x, crane_y, crane_x + crane_pad, crane_y + crane_pad)
    foundation = _add_extruded_on_site(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name=names[4],
        body_context=body_context,
        site=site,
        polyline=pad_poly,
        thickness=crane_pad_t,
        z_bottom=0.0,
        predefined_type=predefined_type,
    )
    foundation.ObjectType = object_type
    proxies.append(foundation)

    # Crane mast (vertical tower) on top of foundation
    mast_ox = crane_x + (crane_pad - crane_mast) * 0.5
    mast_oy = crane_y + (crane_pad - crane_mast) * 0.5
    mast_poly = rect_polyline(
        mast_ox, mast_oy, mast_ox + crane_mast, mast_oy + crane_mast
    )
    mast = _add_extruded_on_site(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name=names[2],
        body_context=body_context,
        site=site,
        polyline=mast_poly,
        thickness=crane_h,
        z_bottom=crane_pad_t,
        predefined_type=predefined_type,
    )
    mast.ObjectType = object_type
    proxies.append(mast)

    # Crane jib (horizontal arm) at top of mast, toward yard centre (−X)
    jib_z = crane_pad_t + crane_h - crane_jib_h
    jib_y0 = mast_oy + (crane_mast - crane_jib_w) * 0.5
    jib_poly = rect_polyline(
        mast_ox + crane_mast - crane_jib_l,
        jib_y0,
        mast_ox + crane_mast,
        jib_y0 + crane_jib_w,
    )
    jib = _add_extruded_on_site(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name=names[2],
        body_context=body_context,
        site=site,
        polyline=jib_poly,
        thickness=crane_jib_h,
        z_bottom=jib_z,
        predefined_type=predefined_type,
    )
    jib.ObjectType = object_type
    proxies.append(jib)

    stor_x = cont_x + cont_w + 1.0
    stor_y = 2.0
    stor_poly = rect_polyline(stor_x, stor_y, stor_x + stor_w, stor_y + stor_d)
    storage = _add_extruded_on_site(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name=names[3],
        body_context=body_context,
        site=site,
        polyline=stor_poly,
        thickness=stor_h,
        z_bottom=0.0,
        predefined_type=predefined_type,
    )
    storage.ObjectType = object_type
    proxies.append(storage)

    shared = {
        "PredefinedType": predefined_type,
        "ObjectType": object_type,
        "properties": params.get("properties") or {},
        "property_datatypes": params.get("property_datatypes") or {},
        "quantities": params.get("quantities") or {},
    }

    # Fence, container, storage — index 0,1,3 in logistics_names / logistics_attrs
    volume_specs: list[tuple[ifcopenshell.entity_instance, int, Sequence[Sequence[float]], float]] = [
        (fence, 0, fence_poly, fence_h),
        (container, 1, cont_poly, cont_h),
        (storage, 3, stor_poly, stor_h),
        (foundation, 4, pad_poly, crane_pad_t),
    ]
    for proxy, name_index, poly, height in volume_specs:
        attrs = dict(shared)
        attrs["Name"] = names[name_index]
        if name_index < len(logistics_attrs) and logistics_attrs[name_index]:
            attrs.update(logistics_attrs[name_index])
        area = _shoelace_area(poly)
        quantities = dict(attrs.get("quantities") or {})
        qto = dict(quantities.get("Qto_BuildingElementProxyBaseQuantities") or {})
        qto["GrossVolume"] = round(area * height, 3)
        quantities["Qto_BuildingElementProxyBaseQuantities"] = qto
        attrs["quantities"] = quantities
        _apply_resolved_attributes(ifc_file, proxy, attrs)

    crane_attrs = dict(shared)
    crane_attrs["Name"] = names[2]
    if 2 < len(logistics_attrs) and logistics_attrs[2]:
        crane_attrs.update(logistics_attrs[2])
    mast_vol = round(crane_mast * crane_mast * crane_h, 3)
    jib_vol = round(crane_jib_l * crane_jib_w * crane_jib_h, 3)
    mast_q = dict(crane_attrs.get("quantities") or {})
    mast_qto = dict(mast_q.get("Qto_BuildingElementProxyBaseQuantities") or {})
    mast_qto["GrossVolume"] = mast_vol
    mast_q["Qto_BuildingElementProxyBaseQuantities"] = mast_qto
    mast_attrs = dict(crane_attrs)
    mast_attrs["quantities"] = mast_q
    _apply_resolved_attributes(ifc_file, mast, mast_attrs)

    jib_q = dict(crane_attrs.get("quantities") or {})
    jib_qto = dict(jib_q.get("Qto_BuildingElementProxyBaseQuantities") or {})
    jib_qto["GrossVolume"] = jib_vol
    jib_q["Qto_BuildingElementProxyBaseQuantities"] = jib_qto
    jib_attrs = dict(crane_attrs)
    jib_attrs["quantities"] = jib_q
    _apply_resolved_attributes(ifc_file, jib, jib_attrs)

    return ifc_file, proxies
