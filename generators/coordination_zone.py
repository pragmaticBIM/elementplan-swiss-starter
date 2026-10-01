"""IfcBuildingElementProxy Koordinationszone over the Luftraum roof / beams."""

from __future__ import annotations

from typing import Any

import ifcopenshell

from generators.base import assign_pset, assign_qto, get_body_context
from generators.luftraum import (
    BEAM_DEPTH,
    DEFAULT_UPPER_HEIGHT,
    TOP_SLAB_RAISE,
    generate_luftraum,
)
from generators.parts import add_extruded_product, bounds_2d, rect_polyline
from generators.space import (
    CEILING_SLAB_THICKNESS,
    NEIGHBOR_SPACE_WIDTH,
    WALL_THICKNESS,
    _boundary_from_params,
    _shoelace_area,
)

# Metres — transparent volume wrapping roof slab + beams
DEFAULT_ZONE_HEIGHT = 1.70  # wraps beams+slab; +0.50 m below soffit vs prior 1.20
DEFAULT_ZONE_MARGIN = 0.0  # XY flush with beam/slab envelope (oversized in Z only)
DEFAULT_ZONE_PAD_BELOW = 0.60  # clear below beam soffit (was 0.10; +0.50 m)
DEFAULT_ZONE_PAD_ABOVE = 0.30  # clear above roof top

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


def generate_coordination_zone(
    params: dict[str, Any],
) -> tuple[ifcopenshell.file, ifcopenshell.entity_instance]:
    """Reuse the Luftraum fabric; accent one oversized Koordinationszone at the roof.

    Layout matches the Luftraum roof/beam vignette without IfcSpace volumes. A
    single transparent proxy wraps the top slab and beams, flush with the beam
    ends / slab envelope in XY (optional ``zone_margin`` overhang).

    ``params`` keys:
    - ``luftraum_params``: geometry passed to ``generate_luftraum``
    - ``zone_height`` (float, m): proxy extrusion height (default covers beams+slab)
    - ``zone_margin`` (float, m): XY overhang beyond the bay (default 1.00)
    - ``name`` / ``predefined_type`` / ``object_type``
    - ``properties`` / ``property_datatypes`` / ``quantities``

    Returns ``(ifc_file, coordination_proxy)``.
    """
    luftraum_params = dict(params.get("luftraum_params") or {})
    if not luftraum_params:
        raise ValueError("luftraum_params is required (reuse the Luftraum vignette)")
    luftraum_params.setdefault("with_context", True)
    luftraum_params["omit_spaces"] = True

    ifc_file, _context = generate_luftraum(luftraum_params)
    body_context = get_body_context(ifc_file)
    storey = ifc_file.by_type("IfcBuildingStorey")[0]

    height = float(luftraum_params["height"])
    upper_height = float(luftraum_params.get("upper_height", DEFAULT_UPPER_HEIGHT))
    primary_polyline = _boundary_from_params(luftraum_params)
    min_x, min_y, max_x, max_y = bounds_2d(primary_polyline)
    wall_t = WALL_THICKNESS
    neighbor_w = NEIGHBOR_SPACE_WIDTH
    margin = float(params.get("zone_margin", DEFAULT_ZONE_MARGIN))
    if margin < 0:
        raise ValueError("zone_margin must be non-negative")

    # Flush with beam ends / top-slab envelope; optional equal XY margin
    zone_poly = rect_polyline(
        min_x - margin,
        min_y - margin,
        max_x + wall_t + neighbor_w + margin,
        max_y + margin,
    )

    z_top_slab = height + upper_height + TOP_SLAB_RAISE
    z_beam_bottom = z_top_slab - BEAM_DEPTH
    z_roof_top = z_top_slab + CEILING_SLAB_THICKNESS

    # One volume wrapping roof + beams
    stack_bottom = z_beam_bottom - DEFAULT_ZONE_PAD_BELOW
    stack_top = z_roof_top + DEFAULT_ZONE_PAD_ABOVE
    min_height = stack_top - stack_bottom
    zone_height = float(params.get("zone_height", max(DEFAULT_ZONE_HEIGHT, min_height)))
    if zone_height <= 0:
        raise ValueError("zone_height must be positive")
    if zone_height < min_height:
        zone_height = min_height
    # Top-align so the box always clears the roof
    z_bottom = stack_top - zone_height
    if z_bottom < stack_bottom - 1e-6:
        z_bottom = stack_bottom
        zone_height = stack_top - z_bottom

    name = params.get("name") or "KOORD-01"
    predefined_type = params.get("predefined_type") or "USERDEFINED"
    object_type = (
        params.get("object_type") or params.get("ObjectType") or "Koordinationszone"
    )

    footprint = _shoelace_area(zone_poly)
    volumes = dict(params.get("quantities") or {})
    qto = dict(volumes.get("Qto_BuildingElementProxyBaseQuantities") or {})
    qto["GrossVolume"] = round(footprint * zone_height, 3)
    volumes["Qto_BuildingElementProxyBaseQuantities"] = qto

    zone = add_extruded_product(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name=name,
        body_context=body_context,
        storey=storey,
        polyline=zone_poly,
        thickness=zone_height,
        z_bottom=z_bottom,
        predefined_type=predefined_type,
    )

    resolved = {
        "Name": name,
        "PredefinedType": predefined_type,
        "ObjectType": object_type,
        "properties": params.get("properties") or {},
        "property_datatypes": params.get("property_datatypes") or {},
        "quantities": volumes,
    }
    _apply_resolved_attributes(ifc_file, zone, resolved)

    return ifc_file, zone
