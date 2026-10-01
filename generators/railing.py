"""Simplified IfcRailing added to the shared exterior-space balcony vignette."""

from __future__ import annotations

from typing import Any

import ifcopenshell
from ifcopenshell.api.geometry import assign_representation, edit_object_placement
from ifcopenshell.api.root import create_entity
from ifcopenshell.api.spatial import assign_container

from generators.base import assign_pset, assign_qto, get_body_context
from generators.parts import (
    create_body_representation,
    create_extruded_area_solid,
    rect_polyline,
    translation_matrix,
)
from generators.space import (
    CLADDING_GAP,
    CLADDING_THICKNESS,
    EXTERIOR_WALL_THICKNESS,
    generate_space,
)

DEFAULT_RAILING_LENGTH = 5.0
DEFAULT_RAILING_HEIGHT = 1.10
DEFAULT_RAILING_THICKNESS = 0.08
DEFAULT_BALCONY_DEPTH = 1.5


def generate_railing(
    params: dict[str, Any],
) -> tuple[ifcopenshell.file, ifcopenshell.entity_instance]:
    """Reuse the exterior-space picture and add a railing at the balcony edge."""
    length = float(params.get("railing_length", DEFAULT_RAILING_LENGTH))
    height = float(params.get("railing_height", DEFAULT_RAILING_HEIGHT))
    thickness = float(params.get("railing_thickness", DEFAULT_RAILING_THICKNESS))
    balcony_depth = float(params.get("balcony_depth", DEFAULT_BALCONY_DEPTH))

    if length <= 0 or height <= 0 or thickness <= 0:
        raise ValueError("railing length, height, and thickness must be positive")

    space_params = dict(params.get("space_params") or {})
    if not space_params:
        raise ValueError("space_params is required (reuse the exterior-space vignette)")
    space_params.setdefault("with_context", True)
    space_params.setdefault("vignette", "exterior")
    ifc_file, _exterior_space = generate_space(space_params)
    storeys = ifc_file.by_type("IfcBuildingStorey")
    if not storeys:
        raise ValueError("exterior-space vignette has no building storey")
    storey = storeys[0]
    body_context = get_body_context(ifc_file)

    resolved = dict(params.get("resolved_attributes") or {})
    name = str(resolved.get("Name") or params.get("name") or "G-01")
    predefined_type = str(
        resolved.get("PredefinedType")
        or params.get("predefined_type")
        or "GUARDRAIL"
    )
    interior_width = float(space_params.get("interior_width", 2.0))
    include_cladding = bool(space_params.get("include_cladding", True))
    facade_outer = interior_width + EXTERIOR_WALL_THICKNESS
    if include_cladding:
        facade_outer += CLADDING_GAP + CLADDING_THICKNESS
    edge_x = facade_outer + balcony_depth

    railing = create_entity(
        ifc_file,
        ifc_class="IfcRailing",
        name=name,
        predefined_type=predefined_type,
    )
    assign_container(ifc_file, relating_structure=storey, products=[railing])
    edit_object_placement(
        ifc_file,
        product=railing,
        matrix=translation_matrix(),
    )
    solid = create_extruded_area_solid(
        ifc_file,
        rect_polyline(edge_x - thickness, 0.0, edge_x, length),
        height,
    )
    representation = create_body_representation(ifc_file, body_context, solid)
    assign_representation(ifc_file, product=railing, representation=representation)

    for pset_name, properties in (resolved.get("properties") or {}).items():
        assign_pset(
            ifc_file,
            railing,
            pset_name,
            properties,
            datatypes=(resolved.get("property_datatypes") or {}).get(pset_name),
        )
    for qto_name, quantities in (resolved.get("quantities") or {}).items():
        assign_qto(ifc_file, railing, qto_name, quantities)

    return ifc_file, railing
