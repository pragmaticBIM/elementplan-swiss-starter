"""IfcGeographicElement tree pit — substrate box with schematic trunk marker."""

from __future__ import annotations

from typing import Any

import ifcopenshell
from ifcopenshell.api.geometry import assign_representation, edit_object_placement
from ifcopenshell.api.root import create_entity
from ifcopenshell.api.spatial import assign_container

from generators.base import assign_pset, assign_qto, create_project_shell, get_body_context
from generators.parts import (
    create_body_representation,
    create_cylinder_solid,
    create_extruded_area_solid,
    translation_matrix,
)

# Metres — cubic tree pit with a short trunk stub above grade
DEFAULT_PIT_LENGTH = 2.40
DEFAULT_PIT_WIDTH = 2.40
DEFAULT_PIT_DEPTH = 1.00
DEFAULT_GROUND_MARGIN = 1.80
DEFAULT_GROUND_THICKNESS = 0.25
DEFAULT_TRUNK_RADIUS = 0.12
DEFAULT_TRUNK_HEIGHT = 0.90

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


def generate_tree_pit(
    params: dict[str, Any] | None = None,
) -> tuple[ifcopenshell.file, ifcopenshell.entity_instance]:
    """Build a tree-pit substrate volume with a short trunk marker.

    Returns ``(ifc_file, tree_pit_entity)``.
    """
    params = dict(params or {})
    length = float(params.get("length", DEFAULT_PIT_LENGTH))
    width = float(params.get("width", DEFAULT_PIT_WIDTH))
    depth = float(params.get("depth", DEFAULT_PIT_DEPTH))
    margin = float(params.get("ground_margin", DEFAULT_GROUND_MARGIN))
    ground_thickness = float(params.get("ground_thickness", DEFAULT_GROUND_THICKNESS))

    if min(length, width, depth, ground_thickness) <= 0:
        raise ValueError("tree pit dimensions must be positive")

    name = params.get("name") or "BG0001"
    predefined_type = params.get("predefined_type") or "USERDEFINED"
    object_type = params.get("object_type") or params.get("ObjectType") or "Baumgrube"

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

    pit = create_entity(
        ifc_file,
        ifc_class="IfcGeographicElement",
        name=str(name),
        predefined_type=predefined_type,
    )
    pit.ObjectType = str(object_type)
    assign_container(ifc_file, relating_structure=site, products=[pit])
    edit_object_placement(
        ifc_file,
        product=pit,
        matrix=translation_matrix(z=-depth),
    )
    solid = create_extruded_area_solid(
        ifc_file,
        _rect(length / 2.0, width / 2.0),
        depth,
    )
    representation = create_body_representation(ifc_file, body_context, solid)
    assign_representation(ifc_file, product=pit, representation=representation)

    trunk = create_entity(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name="Stamm",
        predefined_type="USERDEFINED",
    )
    trunk.ObjectType = "Stamm"
    assign_container(ifc_file, relating_structure=storey, products=[trunk])
    trunk_solid = create_cylinder_solid(
        ifc_file,
        radius=float(params.get("trunk_radius", DEFAULT_TRUNK_RADIUS)),
        height=float(params.get("trunk_height", DEFAULT_TRUNK_HEIGHT)),
    )
    trunk_repr = create_body_representation(ifc_file, body_context, trunk_solid)
    assign_representation(ifc_file, product=trunk, representation=trunk_repr)

    resolved = {
        "Name": name,
        "PredefinedType": predefined_type,
        "ObjectType": object_type,
        "properties": params.get("properties") or {},
        "property_datatypes": params.get("property_datatypes") or {},
        "quantities": params.get("quantities") or {},
    }
    _apply_resolved_attributes(ifc_file, pit, resolved)
    return ifc_file, pit
