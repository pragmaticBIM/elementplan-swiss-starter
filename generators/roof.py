"""IfcRoof pitched-roof catalog generator with attic IfcSpace under the slopes."""

from __future__ import annotations

from math import sqrt
from typing import Any

import ifcopenshell
from ifcopenshell.api.aggregate import assign_object
from ifcopenshell.api.geometry import assign_representation, edit_object_placement
from ifcopenshell.api.root import create_entity
from ifcopenshell.api.spatial import assign_container
from ifcopenshell.util.element import get_psets

from generators.base import assign_pset, assign_qto, create_project_shell, get_body_context
from generators.parts import (
    create_brep_body_representation,
    create_faceted_brep,
    rect_polyline,
    translation_matrix,
)
from generators.slab import add_slab

# Metres — gable roof (Satteldach) over a rectangular attic space
DEFAULT_WIDTH = 6.0  # X span (eave to eave)
DEFAULT_DEPTH = 5.0  # Y along ridge
DEFAULT_EAVE_HEIGHT = 2.50
DEFAULT_RISE = 1.80  # ridge above eaves ≈ 31°
DEFAULT_ROOF_THICKNESS = 0.30
DEFAULT_FLOOR_THICKNESS = 0.30
DEFAULT_INTERMEDIATE_SLAB_ELEVATION = 2.00

_ENTITY_FIELD_MAP = ("Name", "LongName", "PredefinedType", "ObjectType", "Phase")


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


def pitched_roof_gross_area(width: float, depth: float, rise: float) -> float:
    """Two-slope planimetric roof area (both faces)."""
    half = width * 0.5
    slope_len = sqrt(half * half + rise * rise)
    return 2.0 * slope_len * depth


def attic_space_volume(
    width: float, depth: float, eave_height: float, rise: float
) -> float:
    """Prism under a gable: rectangular walls to eaves + triangular ridge prism."""
    return width * depth * eave_height + 0.5 * width * rise * depth


def _roof_half_space_solid(
    ifc_file: ifcopenshell.file,
    *,
    width: float,
    depth: float,
    eave_height: float,
    rise: float,
    z_bottom: float,
    side: str,
) -> ifcopenshell.entity_instance:
    """Half-gable volume from a horizontal floor to one roof slope."""
    w, d, h, r = float(width), float(depth), float(eave_height), float(rise)
    z0 = float(z_bottom)
    if z0 >= h:
        raise ValueError("roof-half-space floor must be below the roof eaves")
    mid = w * 0.5
    if side == "left":
        x0, x1 = 0.0, mid
        roof_z0, roof_z1 = h, h + r
    elif side == "right":
        x0, x1 = mid, w
        roof_z0, roof_z1 = h + r, h
    else:
        raise ValueError("roof-half-space side must be 'left' or 'right'")
    verts = [
        (x0, 0.0, z0),
        (x1, 0.0, z0),
        (x1, d, z0),
        (x0, d, z0),
        (x0, 0.0, roof_z0),
        (x1, 0.0, roof_z1),
        (x1, d, roof_z1),
        (x0, d, roof_z0),
    ]
    faces = [
        (0, 3, 2, 1),  # floor
        (4, 5, 6, 7),  # roof underside
        (0, 1, 5, 4),  # front
        (3, 7, 6, 2),  # back
        (0, 4, 7, 3),  # left wall
        (1, 2, 6, 5),  # right wall
    ]
    return create_faceted_brep(ifc_file, verts, faces)


def _box_space_solid(
    ifc_file: ifcopenshell.file,
    *,
    width: float,
    depth: float,
    height: float,
    y_start: float,
) -> ifcopenshell.entity_instance:
    """Closed rectangular lower-space volume."""
    w, d, h, y0 = float(width), float(depth), float(height), float(y_start)
    verts = [
        (0.0, y0, 0.0),
        (w, y0, 0.0),
        (w, d, 0.0),
        (0.0, d, 0.0),
        (0.0, y0, h),
        (w, y0, h),
        (w, d, h),
        (0.0, d, h),
    ]
    faces = [
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (3, 7, 6, 2),
        (0, 4, 7, 3),
        (1, 2, 6, 5),
    ]
    return create_faceted_brep(ifc_file, verts, faces)


def _create_space(
    ifc_file: ifcopenshell.file,
    *,
    storey: ifcopenshell.entity_instance,
    body_context: ifcopenshell.entity_instance,
    storey_z: float,
    attrs: dict[str, Any],
    solid: ifcopenshell.entity_instance,
    fallback_name: str,
    fallback_predefined_type: str,
) -> ifcopenshell.entity_instance:
    """Create one context IfcSpace and apply its resolved catalog attributes."""
    space = create_entity(
        ifc_file,
        ifc_class="IfcSpace",
        name=str(attrs.get("Name") or fallback_name),
        predefined_type=str(
            attrs.get("PredefinedType") or fallback_predefined_type
        ),
    )
    assign_object(ifc_file, relating_object=storey, products=[space])
    edit_object_placement(
        ifc_file,
        product=space,
        matrix=translation_matrix(z=storey_z),
    )
    assign_representation(
        ifc_file,
        product=space,
        representation=create_brep_body_representation(
            ifc_file, body_context, solid
        ),
    )
    _apply_resolved_attributes(ifc_file, space, attrs)
    return space


def _gable_roof_solid(
    ifc_file: ifcopenshell.file,
    *,
    width: float,
    depth: float,
    eave_height: float,
    rise: float,
    thickness: float,
) -> ifcopenshell.entity_instance:
    """Thin gable roof shell with vertical thickness (catalog sketch)."""
    w, d, h, r, t = (
        float(width),
        float(depth),
        float(eave_height),
        float(rise),
        float(thickness),
    )
    mid = w * 0.5
    # Underside (0–5) then outer top (6–11)
    verts = [
        (0.0, 0.0, h),
        (mid, 0.0, h + r),
        (w, 0.0, h),
        (w, d, h),
        (mid, d, h + r),
        (0.0, d, h),
        (0.0, 0.0, h + t),
        (mid, 0.0, h + r + t),
        (w, 0.0, h + t),
        (w, d, h + t),
        (mid, d, h + r + t),
        (0.0, d, h + t),
    ]
    faces = [
        # Underside (inward / downward)
        (0, 5, 4, 1),
        (1, 4, 3, 2),
        # Outer top
        (6, 7, 10, 11),
        (7, 8, 9, 10),
        # Front / back eaves + ridges
        (0, 1, 7, 6),
        (1, 2, 8, 7),
        (5, 11, 10, 4),
        (4, 10, 9, 3),
        # Left / right eaves
        (0, 6, 11, 5),
        (2, 3, 9, 8),
    ]
    return create_faceted_brep(ifc_file, verts, faces)


def generate_pitched_roof(
    params: dict[str, Any] | None = None,
) -> tuple[ifcopenshell.file, ifcopenshell.entity_instance]:
    """Build a gable IfcRoof with attic IfcSpace following the roof inclination.

    ``params`` keys:
    - geometry: ``width``, ``depth``, ``eave_height``, ``rise``, ``roof_thickness``,
      ``floor_thickness``, ``intermediate_slab_elevation``
    - roof: ``name``, ``predefined_type``, ``properties``, ``property_datatypes``,
      ``quantities``
    - optional ``space_attrs`` and ``luftraum_attrs`` for the two context spaces

    Returns ``(ifc_file, roof)``.
    """
    params = dict(params or {})

    width = float(params.get("width", DEFAULT_WIDTH))
    depth = float(params.get("depth", DEFAULT_DEPTH))
    eave_h = float(params.get("eave_height", DEFAULT_EAVE_HEIGHT))
    rise = float(params.get("rise", DEFAULT_RISE))
    roof_t = float(params.get("roof_thickness", DEFAULT_ROOF_THICKNESS))
    floor_t = float(params.get("floor_thickness", DEFAULT_FLOOR_THICKNESS))
    intermediate_z = float(
        params.get(
            "intermediate_slab_elevation",
            DEFAULT_INTERMEDIATE_SLAB_ELEVATION,
        )
    )

    if min(width, depth, eave_h, rise, roof_t, floor_t) <= 0:
        raise ValueError("all pitched-roof vignette dimensions must be positive")
    if intermediate_z <= 0 or intermediate_z + floor_t >= eave_h:
        raise ValueError(
            "intermediate slab must sit above the base and below the roof eaves"
        )

    name = params.get("name") or "SD-01"
    predefined_type = params.get("predefined_type") or "GABLE_ROOF"

    ifc_file, _project, _site, _building, storey, body_context = create_project_shell(
        params.get("project_name") or name,
        storey_name="DG",
    )
    body_context = get_body_context(ifc_file) or body_context
    storey_z = float(getattr(storey, "Elevation", None) or 0.0)

    # Floor plate under the attic (context)
    add_slab(
        ifc_file,
        name="Decke",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(0.0, 0.0, width, depth),
        thickness=floor_t,
        z_bottom=storey_z - floor_t,
        predefined_type="FLOOR",
    )

    # Half-width slab runs along the ridge axis to both gables.
    half_width = width * 0.5
    add_slab(
        ifc_file,
        name="Decke-Dachraum",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(half_width, 0.0, width, depth),
        thickness=floor_t,
        z_bottom=storey_z + intermediate_z,
        predefined_type="FLOOR",
    )

    # Normal room below the slab and the open-to-below half.
    lower_space_attrs = params.get("lower_space_attrs") or {}
    lower_space_qto = dict(
        (lower_space_attrs.get("quantities") or {}).get(
            "Qto_SpaceBaseQuantities"
        )
        or {}
    )
    lower_space_qto["NetFloorArea"] = round(width * depth, 2)
    lower_space_qto["GrossFloorArea"] = round(width * depth, 2)
    lower_space_qto["Height"] = round(intermediate_z, 2)
    lower_space_qto["GrossVolume"] = round(
        width * depth * intermediate_z, 2
    )
    lower_space_attrs = dict(lower_space_attrs)
    lower_space_attrs["quantities"] = dict(
        lower_space_attrs.get("quantities") or {}
    )
    lower_space_attrs["quantities"][
        "Qto_SpaceBaseQuantities"
    ] = lower_space_qto
    _create_space(
        ifc_file,
        storey=storey,
        body_context=body_context,
        storey_z=storey_z,
        attrs=lower_space_attrs,
        solid=_box_space_solid(
            ifc_file,
            width=width,
            depth=depth,
            height=intermediate_z,
            y_start=0.0,
        ),
        fallback_name="201",
        fallback_predefined_type="INTERNAL",
    )

    # Luftraum above the lower room on the side without an intermediate slab.
    luftraum_attrs = params.get("luftraum_attrs") or {}
    upper_z = intermediate_z + floor_t
    luftraum_volume = (
        half_width * (eave_h - intermediate_z)
        + 0.5 * half_width * rise
    ) * depth
    roof_half_volume = (
        half_width * (eave_h - upper_z)
        + 0.5 * half_width * rise
    ) * depth
    luftraum_qto = dict(
        (luftraum_attrs.get("quantities") or {}).get("Qto_SpaceBaseQuantities")
        or {}
    )
    luftraum_qto["NetFloorArea"] = round(half_width * depth, 2)
    luftraum_qto["GrossFloorArea"] = round(half_width * depth, 2)
    luftraum_qto["Height"] = round(eave_h + rise - intermediate_z, 2)
    luftraum_qto["GrossVolume"] = round(luftraum_volume, 2)
    luftraum_attrs = dict(luftraum_attrs)
    luftraum_attrs["quantities"] = dict(luftraum_attrs.get("quantities") or {})
    luftraum_attrs["quantities"]["Qto_SpaceBaseQuantities"] = luftraum_qto
    _create_space(
        ifc_file,
        storey=storey,
        body_context=body_context,
        storey_z=storey_z,
        attrs=luftraum_attrs,
        solid=_roof_half_space_solid(
            ifc_file,
            width=width,
            depth=depth,
            eave_height=eave_h,
            rise=rise,
            z_bottom=intermediate_z,
            side="left",
        ),
        fallback_name="LR-01",
        fallback_predefined_type="USERDEFINED",
    )

    # Dachraum above the slab — its top follows both roof slopes.
    space_attrs = params.get("space_attrs") or {}
    space = _create_space(
        ifc_file,
        storey=storey,
        body_context=body_context,
        storey_z=storey_z,
        attrs=space_attrs,
        solid=_roof_half_space_solid(
            ifc_file,
            width=width,
            depth=depth,
            eave_height=eave_h,
            rise=rise,
            z_bottom=upper_z,
            side="right",
        ),
        fallback_name="301",
        fallback_predefined_type="INTERNAL",
    )
    space_qto = dict(
        (space_attrs.get("quantities") or {}).get("Qto_SpaceBaseQuantities") or {}
    )
    space_qto["NetFloorArea"] = round(half_width * depth, 2)
    space_qto["GrossFloorArea"] = round(half_width * depth, 2)
    space_qto["Height"] = round(eave_h + rise - upper_z, 2)
    space_qto.setdefault(
        "GrossVolume",
        round(
            roof_half_volume, 2,
        ),
    )
    assign_qto(ifc_file, space, "Qto_SpaceBaseQuantities", space_qto)

    # Pitched roof (catalog accent)
    roof = create_entity(
        ifc_file,
        ifc_class="IfcRoof",
        name=str(name),
        predefined_type=str(predefined_type),
    )
    assign_container(ifc_file, relating_structure=storey, products=[roof])
    edit_object_placement(
        ifc_file,
        product=roof,
        matrix=translation_matrix(z=storey_z),
    )
    roof_solid = _gable_roof_solid(
        ifc_file,
        width=width,
        depth=depth,
        eave_height=eave_h,
        rise=rise,
        thickness=roof_t,
    )
    assign_representation(
        ifc_file,
        product=roof,
        representation=create_brep_body_representation(
            ifc_file, body_context, roof_solid
        ),
    )

    gross_area = pitched_roof_gross_area(width, depth, rise)
    volumes = dict(params.get("quantities") or {})
    qto = dict(volumes.get("Qto_RoofBaseQuantities") or {})
    qto["GrossArea"] = round(gross_area, 2)
    volumes["Qto_RoofBaseQuantities"] = qto

    resolved = {
        "Name": name,
        "PredefinedType": predefined_type,
        "properties": params.get("properties") or {},
        "property_datatypes": params.get("property_datatypes") or {},
        "quantities": volumes,
    }
    if params.get("ObjectType") is not None:
        resolved["ObjectType"] = params["ObjectType"]
    _apply_resolved_attributes(ifc_file, roof, resolved)

    psets = get_psets(roof, psets_only=True)
    load_bearing = (psets.get("Pset_RoofCommon") or {}).get("LoadBearing")
    if load_bearing is False:
        assign_pset(ifc_file, roof, "Pset_RoofCommon", {"LoadBearing": True})

    return ifc_file, roof
