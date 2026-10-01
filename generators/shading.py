"""IfcShadingDevice: vertical lamellas on a 1 m cantilever above the exterior window."""

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
    WINDOW_HEIGHT,
    WINDOW_SILL,
    WINDOW_WIDTH,
    generate_space,
)

DEFAULT_CANTILEVER = 1.0
DEFAULT_LAMELLA_COUNT = 6
DEFAULT_LAMELLA_THICKNESS = 0.04
DEFAULT_LAMELLA_HEIGHT = 0.50
# Keep in sync with ``space.py`` exterior vignette (window near the −Y end).
WINDOW_ALONG = 0.40


def generate_shading(
    params: dict[str, Any],
) -> tuple[ifcopenshell.file, ifcopenshell.entity_instance]:
    """Reuse the exterior-window vignette and add vertical lamellas above it."""
    cantilever = float(params.get("cantilever", DEFAULT_CANTILEVER))
    lamella_count = int(params.get("lamella_count", DEFAULT_LAMELLA_COUNT))
    thickness = float(params.get("lamella_thickness", DEFAULT_LAMELLA_THICKNESS))
    lamella_height = float(params.get("lamella_height", DEFAULT_LAMELLA_HEIGHT))
    if cantilever <= 0 or lamella_count < 2 or thickness <= 0 or lamella_height <= 0:
        raise ValueError("cantilever, lamella count, thickness, and height must be positive")

    space_params = dict(params.get("space_params") or {})
    if not space_params:
        raise ValueError("space_params is required (reuse the exterior-window vignette)")
    space_params.setdefault("with_context", True)
    space_params.setdefault("vignette", "exterior")
    space_params.setdefault("omit_primary_space", True)
    space_params.setdefault("include_interior_space", False)
    space_params.setdefault("include_balcony", False)
    space_params.setdefault("include_upper_balcony", False)
    space_params.setdefault("cladding_covers_slab", True)

    ifc_file, _handle = generate_space(space_params)
    storeys = ifc_file.by_type("IfcBuildingStorey")
    if not storeys:
        raise ValueError("exterior-window vignette has no building storey")
    storey = storeys[0]
    body_context = get_body_context(ifc_file)

    resolved = dict(params.get("resolved_attributes") or {})
    name = str(resolved.get("Name") or params.get("name") or "SS-01")
    predefined_type = str(
        resolved.get("PredefinedType") or params.get("predefined_type") or "JALOUSIE"
    )

    interior_width = float(space_params.get("interior_width", 2.0))
    include_cladding = bool(space_params.get("include_cladding", True))
    facade_outer = interior_width + EXTERIOR_WALL_THICKNESS
    if include_cladding:
        facade_outer += CLADDING_GAP + CLADDING_THICKNESS

    span_start = float(params.get("window_along", WINDOW_ALONG))
    span_end = span_start + float(params.get("window_width", WINDOW_WIDTH))
    usable = span_end - span_start - thickness
    step = usable / (lamella_count - 1)
    z_head = float(params.get("window_sill", WINDOW_SILL)) + float(
        params.get("window_height", WINDOW_HEIGHT)
    )

    solids = []
    for index in range(lamella_count):
        y0 = span_start + index * step
        solids.append(
            create_extruded_area_solid(
                ifc_file,
                rect_polyline(facade_outer, y0, facade_outer + cantilever, y0 + thickness),
                lamella_height,
                origin=(0.0, 0.0, z_head),
            )
        )

    shading = create_entity(
        ifc_file,
        ifc_class="IfcShadingDevice",
        name=name,
        predefined_type=predefined_type,
    )
    assign_container(ifc_file, relating_structure=storey, products=[shading])
    edit_object_placement(
        ifc_file,
        product=shading,
        matrix=translation_matrix(),
    )
    representation = create_body_representation(ifc_file, body_context, solids)
    assign_representation(ifc_file, product=shading, representation=representation)

    for pset_name, properties in (resolved.get("properties") or {}).items():
        assign_pset(
            ifc_file,
            shading,
            pset_name,
            properties,
            datatypes=(resolved.get("property_datatypes") or {}).get(pset_name),
        )
    for qto_name, quantities in (resolved.get("quantities") or {}).items():
        assign_qto(ifc_file, shading, qto_name, quantities)

    return ifc_file, shading
