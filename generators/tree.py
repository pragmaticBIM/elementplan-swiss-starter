"""IfcGeographicElement tree — crown sphere, trunk cylinder, root sphere."""

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
    create_sphere_brep,
    translation_matrix,
)

# Metres — schematic tree for catalog isometric
DEFAULT_CROWN_RADIUS = 2.20
DEFAULT_TRUNK_RADIUS = 0.18
DEFAULT_TRUNK_HEIGHT = 3.50
DEFAULT_ROOT_RADIUS = 1.40
DEFAULT_GROUND_PADDING = 3.50
DEFAULT_GROUND_THICKNESS = 0.15
# Nudge tree into the camera-facing notch so the crown does not cover the brand
DEFAULT_NOTCH_NUDGE = 2.00

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


def _terrain_polyline_with_root_cut(
    half_extent: float,
    cut: float,
) -> list[tuple[float, float]]:
    """Square terrain with an L-notch on the camera-facing (+X,+Y) corner.

    Removes the rectangle ``[cut, +half] × [cut, +half]`` so the buried root
    ball stays visible in the default isometric view (eye from +X+Y+Z).
    """
    h = half_extent
    return [
        (-h, -h),
        (h, -h),
        (h, cut),
        (cut, cut),
        (cut, h),
        (-h, h),
    ]


def _add_ground_slab(
    ifc_file: ifcopenshell.file,
    *,
    storey: ifcopenshell.entity_instance,
    body_context: ifcopenshell.entity_instance,
    half_extent: float,
    root_cut: float,
    thickness: float = DEFAULT_GROUND_THICKNESS,
) -> ifcopenshell.entity_instance:
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
        _terrain_polyline_with_root_cut(half_extent, root_cut),
        thickness,
    )
    representation = create_body_representation(ifc_file, body_context, solid)
    assign_representation(ifc_file, product=product, representation=representation)
    return product


def generate_tree(
    params: dict[str, Any] | None = None,
) -> tuple[ifcopenshell.file, ifcopenshell.entity_instance]:
    """Build a schematic tree: root ball, trunk, crown ball on a ground slab.

    ``params`` keys:
    - ``crown_radius``, ``trunk_radius``, ``trunk_height``, ``root_radius``
    - ``name`` / ``predefined_type`` / ``object_type``
    - ``properties`` / ``property_datatypes`` / ``quantities`` (YAML-resolved)
    - ``with_context`` (bool, default True): thin ground slab

    Returns ``(ifc_file, tree_entity)``.
    """
    params = dict(params or {})

    crown_r = float(params.get("crown_radius", DEFAULT_CROWN_RADIUS))
    trunk_r = float(params.get("trunk_radius", DEFAULT_TRUNK_RADIUS))
    trunk_h = float(params.get("trunk_height", DEFAULT_TRUNK_HEIGHT))
    root_r = float(params.get("root_radius", DEFAULT_ROOT_RADIUS))
    pad = float(params.get("ground_padding", DEFAULT_GROUND_PADDING))

    if min(crown_r, trunk_r, trunk_h, root_r) <= 0:
        raise ValueError("all tree dimensions must be positive")

    name = params.get("name") or "B0001"
    predefined_type = params.get("predefined_type") or "VEGETATION"
    object_type = params.get("object_type") or params.get("ObjectType") or "Baum"

    # Root ball fully below terrain (top flush with z=0); trunk from z=0;
    # crown sits on trunk top. Terrain is L-cut toward the isometric camera
    # so the buried ball stays visible. Tree is nudged into that notch so the
    # crown does not sit over the brand on the remaining plate arms.
    nudge = float(params.get("notch_nudge", DEFAULT_NOTCH_NUDGE))
    root_center_z = -root_r
    crown_center_z = trunk_h + 0.55 * crown_r

    ifc_file, _project, site, _building, storey, body_context = create_project_shell(
        params.get("project_name") or name,
        storey_name="Terrain",
        version="IFC4X3",
    )
    body_context = get_body_context(ifc_file) or body_context

    if params.get("with_context", True):
        half = max(crown_r, root_r) + pad
        # Notch past the (nudged) root centre toward −X/−Y so most of the ball shows.
        root_cut = nudge - 0.25 * root_r
        _add_ground_slab(
            ifc_file,
            storey=storey,
            body_context=body_context,
            half_extent=half,
            root_cut=root_cut,
        )

    tree = create_entity(
        ifc_file,
        ifc_class="IfcGeographicElement",
        name=str(name),
        predefined_type=predefined_type,
    )
    tree.ObjectType = str(object_type)
    assign_container(ifc_file, relating_structure=site, products=[tree])
    edit_object_placement(
        ifc_file,
        product=tree,
        matrix=translation_matrix(x=nudge, y=nudge),
    )

    root_ball = create_sphere_brep(
        ifc_file, radius=root_r, center=(0.0, 0.0, root_center_z)
    )
    trunk = create_cylinder_solid(
        ifc_file,
        radius=trunk_r,
        height=trunk_h,
        origin=(0.0, 0.0, 0.0),
    )
    crown = create_sphere_brep(
        ifc_file, radius=crown_r, center=(0.0, 0.0, crown_center_z)
    )

    # Mixed SweptSolid + Brep → SolidModel
    representation = ifc_file.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=body_context,
        RepresentationIdentifier="Body",
        RepresentationType="SolidModel",
        Items=[root_ball, trunk, crown],
    )
    assign_representation(ifc_file, product=tree, representation=representation)

    resolved = {
        "Name": name,
        "PredefinedType": predefined_type,
        "ObjectType": object_type,
        "properties": params.get("properties") or {},
        "property_datatypes": params.get("property_datatypes") or {},
        "quantities": params.get("quantities") or {},
    }
    _apply_resolved_attributes(ifc_file, tree, resolved)

    return ifc_file, tree
