"""IfcBuildingElementProxy Wartungsraum — long multi-part monoblock + filter clearance."""

from __future__ import annotations

from typing import Any

import ifcopenshell

from generators.base import assign_pset, assign_qto, create_project_shell, get_body_context
from generators.parts import add_extruded_product, rect_polyline

# Metres — long AHU monoblock (sections along +X) with 90 cm clear zone at the filter.
# Section order (airflow): Ansaug → Filter → Erhitzer → Kühler → Ventilator → Ausblas.
DEFAULT_UNIT_DEPTH = 1.20
DEFAULT_MAINTENANCE_DEPTH = 0.90
DEFAULT_MAINTENANCE_HEIGHT = 2.00
DEFAULT_SLAB_THICKNESS = 0.20
DEFAULT_SLAB_PADDING = 0.40

# (name, length along X, height) — filter is index 1; Wartungsraum sits in front of it.
_DEFAULT_SECTIONS: tuple[tuple[str, float, float], ...] = (
    ("Ansaug", 0.80, 1.40),
    ("Filter", 0.70, 1.55),
    ("Erhitzer", 0.75, 1.40),
    ("Kuehler", 0.75, 1.40),
    ("Ventilator", 1.00, 1.75),
    ("Ausblas", 0.50, 1.15),
)

# Back-compat aliases used by catalog/mapping.py
DEFAULT_CUBE_DEPTH = DEFAULT_UNIT_DEPTH
DEFAULT_CUBE_HEIGHT = max(h for _, _, h in _DEFAULT_SECTIONS)
DEFAULT_CUBE_WIDTH = sum(length for _, length, _ in _DEFAULT_SECTIONS)
DEFAULT_FILTER_INDEX = 1
DEFAULT_FILTER_LENGTH = _DEFAULT_SECTIONS[DEFAULT_FILTER_INDEX][1]

_ENTITY_FIELD_MAP = ("Name", "LongName", "Description", "PredefinedType", "ObjectType", "Phase")


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


def _section_layout(
    sections: tuple[tuple[str, float, float], ...],
) -> list[tuple[str, float, float, float, float]]:
    """Return (name, x0, x1, length, height) for each section along +X."""
    layout: list[tuple[str, float, float, float, float]] = []
    x = 0.0
    for name, length, height in sections:
        layout.append((name, x, x + length, length, height))
        x += length
    return layout


def generate_maintenance_space(
    params: dict[str, Any] | None = None,
) -> tuple[ifcopenshell.file, ifcopenshell.entity_instance]:
    """Build slab + long multi-part monoblock + 90 cm Wartungsraum at the filter.

    Layout (top view): monoblock along +X (Ansaug → … → Ausblas); maintenance
    clearance in front of the Filter section toward +Y (viewer).

    ``params`` keys:
    - ``unit_depth`` (or legacy ``cube_depth``)
    - ``maintenance_depth`` / ``maintenance_height`` / ``slab_*``
    - ``name`` / ``predefined_type`` / ``object_type`` for the Wartungsraum
    - ``properties`` / ``property_datatypes`` / ``quantities`` (YAML-resolved)

    Returns ``(ifc_file, maintenance_proxy)``.
    """
    params = dict(params or {})

    unit_d = float(params.get("unit_depth", params.get("cube_depth", DEFAULT_UNIT_DEPTH)))
    maint_d = float(params.get("maintenance_depth", DEFAULT_MAINTENANCE_DEPTH))
    maint_h = float(params.get("maintenance_height", DEFAULT_MAINTENANCE_HEIGHT))
    slab_t = float(params.get("slab_thickness", DEFAULT_SLAB_THICKNESS))
    pad = float(params.get("slab_padding", DEFAULT_SLAB_PADDING))
    filter_index = int(params.get("filter_index", DEFAULT_FILTER_INDEX))

    sections = _DEFAULT_SECTIONS
    layout = _section_layout(sections)
    unit_w = layout[-1][2]
    max_h = max(h for *_, h in layout)

    if min(unit_d, unit_w, max_h, maint_d, maint_h, slab_t) <= 0:
        raise ValueError("all maintenance-space vignette dimensions must be positive")
    if not 0 <= filter_index < len(layout):
        raise ValueError(f"filter_index must be in 0..{len(layout) - 1}")

    name = params.get("name") or "WR-01"
    predefined_type = params.get("predefined_type") or "USERDEFINED"
    object_type = params.get("object_type") or params.get("ObjectType") or "Wartungsraum"

    filter_name, filter_x0, filter_x1, filter_len, _filter_h = layout[filter_index]

    # Unit at y ∈ [0, unit_d]; clearance in front of Filter toward +Y (camera).
    unit_y0, unit_y1 = 0.0, unit_d
    maint_x0, maint_x1 = filter_x0, filter_x1
    maint_y0, maint_y1 = unit_y1, unit_y1 + maint_d

    slab_x0, slab_y0 = -pad, -pad
    slab_x1, slab_y1 = unit_w + pad, unit_d + maint_d + pad

    ifc_file, _project, _site, _building, storey, body_context = create_project_shell(
        params.get("project_name") or name,
        storey_name="EG",
    )
    body_context = get_body_context(ifc_file) or body_context

    z_slab = 0.0
    z_top = slab_t

    add_extruded_product(
        ifc_file,
        ifc_class="IfcSlab",
        name="Bodenplatte",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(slab_x0, slab_y0, slab_x1, slab_y1),
        thickness=slab_t,
        z_bottom=z_slab,
        predefined_type="FLOOR",
    )

    # Continuous skid under all modules so the chain reads as one monoblock.
    skid_h = 0.10
    skid = add_extruded_product(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name="Monoblock-Grundrahmen",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(0.0, unit_y0, unit_w, unit_y1),
        thickness=skid_h,
        z_bottom=z_top,
        predefined_type="USERDEFINED",
    )
    skid.ObjectType = "Monoblock"

    z_modules = z_top + skid_h
    for sec_name, x0, x1, _length, height in layout:
        part = add_extruded_product(
            ifc_file,
            ifc_class="IfcBuildingElementProxy",
            name=f"Monoblock-{sec_name}",
            body_context=body_context,
            storey=storey,
            polyline=rect_polyline(x0, unit_y0, x1, unit_y1),
            thickness=height,
            z_bottom=z_modules,
            predefined_type="USERDEFINED",
        )
        part.ObjectType = "Monoblock"

    # Filter access door on the +Y face — clarifies why the Wartungsraum sits here.
    door_t = 0.06
    door_inset = 0.08
    door_h = layout[filter_index][4] * 0.85
    door = add_extruded_product(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name="Monoblock-Filtertuer",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(
            filter_x0 + door_inset,
            unit_y1,
            filter_x1 - door_inset,
            unit_y1 + door_t,
        ),
        thickness=door_h,
        z_bottom=z_modules + 0.05,
        predefined_type="USERDEFINED",
    )
    door.ObjectType = "Monoblock"

    # Short intake / supply duct stubs so the unit reads as an AHU monoblock.
    duct_d = unit_d * 0.45
    duct_y0 = unit_y0 + (unit_d - duct_d) * 0.5
    duct_h = 0.55
    duct_z = z_modules + 0.40
    intake = add_extruded_product(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name="Monoblock-Ansaugstutzen",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(-0.35, duct_y0, 0.0, duct_y0 + duct_d),
        thickness=duct_h,
        z_bottom=duct_z,
        predefined_type="USERDEFINED",
    )
    intake.ObjectType = "Monoblock"
    supply = add_extruded_product(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name="Monoblock-Ausblasstutzen",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(unit_w, duct_y0, unit_w + 0.35, duct_y0 + duct_d),
        thickness=duct_h,
        z_bottom=duct_z,
        predefined_type="USERDEFINED",
    )
    supply.ObjectType = "Monoblock"

    maintenance = add_extruded_product(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name=name,
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(maint_x0, maint_y0, maint_x1, maint_y1),
        thickness=maint_h,
        z_bottom=z_top,
        predefined_type=predefined_type,
    )

    volumes = dict(params.get("quantities") or {})
    qto = dict(volumes.get("Qto_BuildingElementProxyBaseQuantities") or {})
    qto["GrossVolume"] = round(filter_len * maint_d * maint_h, 3)
    volumes["Qto_BuildingElementProxyBaseQuantities"] = qto

    resolved = {
        "Name": name,
        "PredefinedType": predefined_type,
        "ObjectType": object_type,
        "Description": f"Freiraum vor {filter_name}",
        "properties": params.get("properties") or {},
        "property_datatypes": params.get("property_datatypes") or {},
        "quantities": volumes,
    }
    _apply_resolved_attributes(ifc_file, maintenance, resolved)

    return ifc_file, maintenance
