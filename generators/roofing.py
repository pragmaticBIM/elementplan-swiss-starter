"""IfcCovering ROOFING (Gefälledämmung) — flat roof + parapet + cladding vignette."""

from __future__ import annotations

from typing import Any, Sequence

import ifcopenshell
from ifcopenshell.api.geometry import assign_representation, edit_object_placement
from ifcopenshell.api.root import create_entity
from ifcopenshell.api.spatial import assign_container

from generators.base import assign_pset, assign_qto, create_project_shell, get_body_context
from generators.covering import add_covering, add_vertical_covering
from generators.parts import (
    add_extruded_product,
    axis_placement_matrix,
    create_body_representation,
    create_tapered_extruded_solid,
    rect_polyline,
)
from generators.wall import add_wall

# Metres — flat roof plate with Attika + cladding; tapered insulation on top.
DEFAULT_SLAB_WIDTH = 4.0
DEFAULT_SLAB_DEPTH = 4.0
DEFAULT_SLAB_THICKNESS = 0.28
DEFAULT_PARAPET_HEIGHT = 0.50
DEFAULT_PARAPET_THICKNESS = 0.20
DEFAULT_CLADDING_THICKNESS = 0.05
DEFAULT_CLADDING_GAP = 0.0  # flush to outer Attika face
DEFAULT_EXTERIOR_INSULATION_THICKNESS = 0.12  # roof-side of Attika (Aufkantung)
DEFAULT_ATTIKA_TOP_THICKNESS = 0.08  # insulation covering on Attika top
DEFAULT_ROOFING_THICK_START = 0.32  # high side (away from parapet)
DEFAULT_ROOFING_THICK_END = 0.06  # low side (at parapet)
DEFAULT_ROOFING_EDGE_INSET = 0.0  # flush to slab edges / Attika insulation

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


def add_tapered_covering(
    ifc_file: ifcopenshell.file,
    *,
    name: str,
    body_context: ifcopenshell.entity_instance,
    storey: ifcopenshell.entity_instance,
    origin: Sequence[float],
    length: float,
    fall_length: float,
    thickness_start: float,
    thickness_end: float,
    fall_direction_xy: Sequence[float] = (0.0, 1.0),
    length_direction_xy: Sequence[float] = (1.0, 0.0),
    predefined_type: str = "ROOFING",
) -> ifcopenshell.entity_instance:
    """Horizontal covering with linear fall (Gefälle) along ``fall_direction_xy``."""
    covering = create_entity(
        ifc_file,
        ifc_class="IfcCovering",
        name=name,
        predefined_type=predefined_type,
    )
    assign_container(ifc_file, relating_structure=storey, products=[covering])

    fx, fy = float(fall_direction_xy[0]), float(fall_direction_xy[1])
    lx, ly = float(length_direction_xy[0]), float(length_direction_xy[1])
    # Solid local: X = fall, Y = up, Z = length (extrusion)
    edit_object_placement(
        ifc_file,
        product=covering,
        matrix=axis_placement_matrix(
            (
                float(origin[0]),
                float(origin[1]),
                float(origin[2]) if len(origin) > 2 else 0.0,
            ),
            local_x=(fx, fy, 0.0),
            local_z=(lx, ly, 0.0),
        ),
    )
    solid = create_tapered_extruded_solid(
        ifc_file,
        length=length,
        fall_length=fall_length,
        thickness_start=thickness_start,
        thickness_end=thickness_end,
    )
    representation = create_body_representation(ifc_file, body_context, solid)
    assign_representation(ifc_file, product=covering, representation=representation)
    return covering


def generate_roofing(
    params: dict[str, Any] | None = None,
) -> tuple[ifcopenshell.file, list[ifcopenshell.entity_instance]]:
    """Build roof slab + parapet + cladding + tapered ROOFING; accent only ROOFING.

    ``params`` keys:
    - geometry overrides (``slab_*``, ``parapet_*``, ``cladding_*``, ``roofing_*``,
      ``interior_insulation_thickness``, ``attika_top_thickness``)
    - ``name`` / ``predefined_type`` for the covering
    - ``properties`` / ``property_datatypes`` / ``quantities`` (YAML-resolved)
    - optional ``slab_attrs`` / ``wall_attrs`` / ``cladding_attrs`` for context

    Returns ``(ifc_file, [roofing, attika_top])``.
    """
    params = dict(params or {})

    slab_w = float(params.get("slab_width", DEFAULT_SLAB_WIDTH))
    slab_d = float(params.get("slab_depth", DEFAULT_SLAB_DEPTH))
    slab_t = float(params.get("slab_thickness", DEFAULT_SLAB_THICKNESS))
    parapet_h = float(params.get("parapet_height", DEFAULT_PARAPET_HEIGHT))
    parapet_t = float(params.get("parapet_thickness", DEFAULT_PARAPET_THICKNESS))
    clad_t = float(params.get("cladding_thickness", DEFAULT_CLADDING_THICKNESS))
    clad_gap = float(params.get("cladding_gap", DEFAULT_CLADDING_GAP))
    # Prefer the renamed key; keep the old override name for existing samples.
    int_insul_t = float(
        params.get(
            "interior_insulation_thickness",
            params.get(
                "exterior_insulation_thickness",
                DEFAULT_EXTERIOR_INSULATION_THICKNESS,
            ),
        )
    )
    attika_top_t = float(
        params.get("attika_top_thickness", DEFAULT_ATTIKA_TOP_THICKNESS)
    )
    t_start = float(params.get("roofing_thickness_start", DEFAULT_ROOFING_THICK_START))
    t_end = float(params.get("roofing_thickness_end", DEFAULT_ROOFING_THICK_END))
    inset = float(params.get("roofing_edge_inset", DEFAULT_ROOFING_EDGE_INSET))

    if (
        min(
            slab_w,
            slab_d,
            slab_t,
            parapet_h,
            parapet_t,
            clad_t,
            int_insul_t,
            attika_top_t,
            t_start,
            t_end,
        )
        <= 0
    ):
        raise ValueError("all roofing vignette dimensions must be positive")
    if clad_gap < 0:
        raise ValueError("cladding_gap must be non-negative")
    if t_end >= t_start:
        raise ValueError("roofing_thickness_end must be less than roofing_thickness_start")

    name = params.get("name") or "GD-01"
    predefined_type = params.get("predefined_type") or "ROOFING"

    ifc_file, _project, _site, _building, storey, body_context = create_project_shell(
        params.get("project_name") or name,
        storey_name="FD",
    )
    body_context = get_body_context(ifc_file) or body_context

    z_slab = 0.0
    z_top = slab_t

    slab_attrs = params.get("slab_attrs") or {}
    add_extruded_product(
        ifc_file,
        ifc_class="IfcSlab",
        name=slab_attrs.get("Name") or "Flachdach",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(0.0, 0.0, slab_w, slab_d),
        thickness=slab_t,
        z_bottom=z_slab,
        predefined_type=slab_attrs.get("PredefinedType") or "ROOF",
    )

    # Parapet on the +Y edge (viewer-facing). Thickness grows local +Y.
    wall_attrs = params.get("wall_attrs") or {}
    wall_y0 = slab_d - parapet_t
    wall_origin = (0.0, wall_y0, z_top)
    add_wall(
        ifc_file,
        name=wall_attrs.get("Name") or "Attika",
        body_context=body_context,
        storey=storey,
        origin=wall_origin,
        length=slab_w,
        height=parapet_h,
        thickness=parapet_t,
        direction_xy=(1.0, 0.0),
        predefined_type=wall_attrs.get("PredefinedType") or "SOLIDWALL",
    )

    # Interior insulation on the roof-side face of the Attika (Aufkantung).
    # Context only — not accented; the tapered ROOFING plate is the primary.
    interior_insulation = add_vertical_covering(
        ifc_file,
        name=f"{name}-Attika-Innen",
        body_context=body_context,
        storey=storey,
        origin=(0.0, wall_y0 - int_insul_t, z_top),
        length=slab_w,
        height=parapet_h,
        thickness=int_insul_t,
        direction_xy=(1.0, 0.0),
        predefined_type=predefined_type,
    )

    # Cladding flush on the outer Attika / slab front face.
    clad_height = slab_t + parapet_h
    cladding_attrs = params.get("cladding_attrs") or {}
    clad_origin = (0.0, slab_d + clad_gap, z_slab)
    add_vertical_covering(
        ifc_file,
        name=cladding_attrs.get("Name") or "Fassadenbekleidung",
        body_context=body_context,
        storey=storey,
        origin=clad_origin,
        length=slab_w,
        height=clad_height,
        thickness=clad_t,
        direction_xy=(1.0, 0.0),
        predefined_type=cladding_attrs.get("PredefinedType") or "CLADDING",
    )

    # Insulation covering on top of Attika (inner strip + wall + cladding).
    attika_top_y0 = wall_y0 - int_insul_t
    attika_top_y1 = slab_d + clad_gap + clad_t
    attika_top = add_covering(
        ifc_file,
        name=f"{name}-Attika-Oben",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(0.0, attika_top_y0, slab_w, attika_top_y1),
        thickness=attika_top_t,
        z_bottom=z_top + parapet_h,
        predefined_type=predefined_type,
    )

    # Fall toward the parapet (+Y): thick at far edge, thin at Attika insulation.
    # Default inset 0 → flush to slab edges and the roof-side Attika face.
    roof_x0 = inset
    roof_y0 = inset
    roof_x1 = slab_w - inset
    roof_y1 = wall_y0 - int_insul_t - inset
    fall_length = roof_y1 - roof_y0
    roof_length = roof_x1 - roof_x0
    if fall_length <= 0 or roof_length <= 0:
        raise ValueError("roofing footprint must fit inside the slab clear of the parapet")

    roofing = add_tapered_covering(
        ifc_file,
        name=name,
        body_context=body_context,
        storey=storey,
        origin=(roof_x0, roof_y0, z_top),
        length=roof_length,
        fall_length=fall_length,
        thickness_start=t_start,
        thickness_end=t_end,
        fall_direction_xy=(0.0, 1.0),
        length_direction_xy=(1.0, 0.0),
        predefined_type=predefined_type,
    )

    net_area = round(roof_length * fall_length, 2)
    volumes = dict(params.get("quantities") or {})
    qto = dict(volumes.get("Qto_CoveringBaseQuantities") or {})
    qto["NetArea"] = net_area
    volumes["Qto_CoveringBaseQuantities"] = qto

    resolved = {
        "Name": name,
        "PredefinedType": predefined_type,
        "properties": params.get("properties") or {},
        "property_datatypes": params.get("property_datatypes") or {},
        "quantities": volumes,
    }
    if params.get("ObjectType") is not None:
        resolved["ObjectType"] = params["ObjectType"]
    _apply_resolved_attributes(ifc_file, roofing, resolved)

    _apply_resolved_attributes(
        ifc_file,
        interior_insulation,
        {
            "Name": f"{name}-Attika-Innen",
            "PredefinedType": predefined_type,
            "quantities": {
                "Qto_CoveringBaseQuantities": {
                    "NetArea": round(slab_w * parapet_h, 2),
                }
            },
        },
    )
    _apply_resolved_attributes(
        ifc_file,
        attika_top,
        {
            "Name": f"{name}-Attika-Oben",
            "PredefinedType": predefined_type,
            "quantities": {
                "Qto_CoveringBaseQuantities": {
                    "NetArea": round(slab_w * (attika_top_y1 - attika_top_y0), 2),
                }
            },
        },
    )

    for product, attrs in (
        (ifc_file.by_type("IfcSlab")[0], slab_attrs),
        (ifc_file.by_type("IfcWall")[0], wall_attrs),
        (
            next(
                c
                for c in ifc_file.by_type("IfcCovering")
                if getattr(c, "PredefinedType", None) == "CLADDING"
            ),
            cladding_attrs,
        ),
    ):
        if attrs:
            _apply_resolved_attributes(ifc_file, product, attrs)

    # Accent tapered roof plate + Attika-top insulation; cladding stays white for brand.
    return ifc_file, [roofing, attika_top]
