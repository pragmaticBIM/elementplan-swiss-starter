"""IfcGeographicElement retention volume — shallow storage basin on terrain."""

from __future__ import annotations

from typing import Any

import ifcopenshell
from ifcopenshell.api.geometry import assign_representation, edit_object_placement
from ifcopenshell.api.root import create_entity
from ifcopenshell.api.spatial import assign_container

from generators.base import assign_pset, assign_qto, create_project_shell, get_body_context
from generators.parts import (
    create_body_representation,
    create_extruded_area_solid,
    translation_matrix,
)

# Metres — shallow retention basin on a larger ground plate
DEFAULT_BASIN_LENGTH = 6.00
DEFAULT_BASIN_WIDTH = 4.00
DEFAULT_BASIN_DEPTH = 0.45
DEFAULT_GROUND_MARGIN = 2.00
DEFAULT_GROUND_THICKNESS = 0.30

_ENTITY_FIELD_MAP = ("Name", "LongName", "PredefinedType", "ObjectType", "Phase")


def _rect(half_x: float, half_y: float) -> list[tuple[float, float]]:
    return [
        (-half_x, -half_y),
        (half_x, -half_y),
        (half_x, half_y),
        (-half_x, half_y),
    ]


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


def _add_ground_slab(
    ifc_file: ifcopenshell.file,
    *,
    storey: ifcopenshell.entity_instance,
    body_context: ifcopenshell.entity_instance,
    half_x: float,
    half_y: float,
    thickness: float,
) -> None:
    product = create_entity(
        ifc_file,
        ifc_class="IfcSlab",
        name="Terrain",
        predefined_type="FLOOR",
    )
    assign_container(ifc_file, relating_structure=storey, products=[product])
    edit_object_placement(
        ifc_file,
        product=product,
        matrix=translation_matrix(z=-thickness),
    )
    solid = create_extruded_area_solid(
        ifc_file,
        _rect(half_x, half_y),
        thickness,
    )
    representation = create_body_representation(ifc_file, body_context, solid)
    assign_representation(ifc_file, product=product, representation=representation)


def generate_retention(
    params: dict[str, Any] | None = None,
) -> tuple[ifcopenshell.file, ifcopenshell.entity_instance]:
    """Build a shallow retention basin volume on a ground slab.

    Returns ``(ifc_file, retention_entity)``.
    """
    params = dict(params or {})
    length = float(params.get("length", DEFAULT_BASIN_LENGTH))
    width = float(params.get("width", DEFAULT_BASIN_WIDTH))
    depth = float(params.get("depth", DEFAULT_BASIN_DEPTH))
    margin = float(params.get("ground_margin", DEFAULT_GROUND_MARGIN))
    ground_thickness = float(params.get("ground_thickness", DEFAULT_GROUND_THICKNESS))

    if min(length, width, depth, ground_thickness) <= 0:
        raise ValueError("retention dimensions must be positive")

    name = params.get("name") or "RET-01"
    predefined_type = params.get("predefined_type") or "USERDEFINED"
    object_type = (
        params.get("object_type") or params.get("ObjectType") or "Retentionsvolumen"
    )

    ifc_file, _project, site, _building, storey, body_context = create_project_shell(
        params.get("project_name") or name,
        storey_name="Terrain",
        version="IFC4",
    )
    body_context = get_body_context(ifc_file) or body_context

    if params.get("with_context", True):
        _add_ground_slab(
            ifc_file,
            storey=storey,
            body_context=body_context,
            half_x=length / 2.0 + margin,
            half_y=width / 2.0 + margin,
            thickness=ground_thickness,
        )

    retention = create_entity(
        ifc_file,
        ifc_class="IfcGeographicElement",
        name=str(name),
        predefined_type=predefined_type,
    )
    retention.ObjectType = str(object_type)
    assign_container(ifc_file, relating_structure=site, products=[retention])
    edit_object_placement(
        ifc_file,
        product=retention,
        matrix=translation_matrix(z=-depth),
    )
    solid = create_extruded_area_solid(
        ifc_file,
        _rect(length / 2.0, width / 2.0),
        depth,
    )
    representation = create_body_representation(ifc_file, body_context, solid)
    assign_representation(ifc_file, product=retention, representation=representation)

    resolved = {
        "Name": name,
        "PredefinedType": predefined_type,
        "ObjectType": object_type,
        "properties": params.get("properties") or {},
        "property_datatypes": params.get("property_datatypes") or {},
        "quantities": params.get("quantities") or {},
    }
    _apply_resolved_attributes(ifc_file, retention, resolved)
    return ifc_file, retention
