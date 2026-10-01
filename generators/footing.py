"""IfcFooting / IfcColumn catalog vignette — pad footing, base slab, one column."""

from __future__ import annotations

from typing import Any

import ifcopenshell
from ifcopenshell.util.element import get_psets

from generators.base import assign_pset, assign_qto, create_project_shell, get_body_context
from generators.parts import add_extruded_product, rect_polyline

# Metres — corner pad under a base slab with a single column.
# Pad overhangs the slab corner so footing / slab / column stay distinct in isometric.
DEFAULT_SLAB_WIDTH = 4.0
DEFAULT_SLAB_DEPTH = 4.0
DEFAULT_SLAB_THICKNESS = 0.30
DEFAULT_FOOTING_WIDTH = 1.80
DEFAULT_FOOTING_DEPTH = 1.80
DEFAULT_FOOTING_THICKNESS = 0.55
DEFAULT_COLUMN_WIDTH = 0.35
DEFAULT_COLUMN_DEPTH = 0.35
DEFAULT_COLUMN_HEIGHT = 2.80
# Negative = pad overhang past slab min-corner (world −X / −Y)
DEFAULT_FOOTING_INSET = -0.30

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


def generate_footing(
    params: dict[str, Any] | None = None,
) -> tuple[ifcopenshell.file, ifcopenshell.entity_instance]:
    """Build a pad footing + base slab + one column vignette.

    ``params`` keys:
    - geometry overrides (``slab_*``, ``footing_*``, ``column_*``, ``footing_inset``)
    - ``close_slab`` — full rectangular plate (default False = L-cut for footing card)
    - ``omit_footing`` — slab + centred column only (column catalog card)
    - ``highlight`` — ``"footing"`` (default) or ``"column"``; returned primary
    - ``name`` / ``predefined_type`` for the highlighted product
    - ``properties`` / ``property_datatypes`` / ``quantities`` (YAML-resolved)
    - optional ``slab_attrs`` / ``footing_attrs`` / ``column_attrs`` for context

    Returns ``(ifc_file, primary)`` — footing or column per ``highlight``.
    """
    params = dict(params or {})

    slab_w = float(params.get("slab_width", DEFAULT_SLAB_WIDTH))
    slab_d = float(params.get("slab_depth", DEFAULT_SLAB_DEPTH))
    slab_t = float(params.get("slab_thickness", DEFAULT_SLAB_THICKNESS))
    foot_w = float(params.get("footing_width", DEFAULT_FOOTING_WIDTH))
    foot_d = float(params.get("footing_depth", DEFAULT_FOOTING_DEPTH))
    foot_t = float(params.get("footing_thickness", DEFAULT_FOOTING_THICKNESS))
    col_w = float(params.get("column_width", DEFAULT_COLUMN_WIDTH))
    col_d = float(params.get("column_depth", DEFAULT_COLUMN_DEPTH))
    col_h = float(params.get("column_height", DEFAULT_COLUMN_HEIGHT))
    inset = float(params.get("footing_inset", DEFAULT_FOOTING_INSET))
    omit_footing = bool(params.get("omit_footing", False))
    close_slab = bool(params.get("close_slab", False)) or omit_footing
    highlight = str(params.get("highlight") or "footing").strip().lower()
    if highlight not in {"footing", "column"}:
        raise ValueError(f"unsupported footing vignette highlight: {highlight!r}")
    if omit_footing and highlight != "column":
        raise ValueError("omit_footing requires highlight='column'")

    if min(slab_w, slab_d, slab_t, col_w, col_d, col_h) <= 0:
        raise ValueError("all vignette dimensions must be positive")
    if not omit_footing and min(foot_w, foot_d, foot_t) <= 0:
        raise ValueError("footing dimensions must be positive")
    if not omit_footing and (col_w > foot_w or col_d > foot_d):
        raise ValueError("column section must fit on the pad footing")

    if omit_footing:
        # Centred column on a closed plate; sits on the slab top.
        col_x0 = (slab_w - col_w) * 0.5
        col_y0 = (slab_d - col_d) * 0.5
        slab_poly = rect_polyline(0.0, 0.0, slab_w, slab_d)
        z_slab = 0.0
        z_column = slab_t
        foot_x0 = foot_y0 = foot_x1 = foot_y1 = 0.0
    else:
        # Pad at the far +X/+Y corner. Isometric camera looks from (+X,+Y,+Z),
        # so that corner faces the viewer.
        foot_x1 = slab_w - inset
        foot_y1 = slab_d - inset
        foot_x0 = foot_x1 - foot_w
        foot_y0 = foot_y1 - foot_d
        col_x0 = foot_x0 + (foot_w - col_w) * 0.5
        col_y0 = foot_y0 + (foot_d - col_d) * 0.5
        if col_x0 < 0 or col_y0 < 0 or col_x0 + col_w > slab_w or col_y0 + col_d > slab_d:
            raise ValueError("column must sit within the slab footprint")

        if close_slab:
            slab_poly = rect_polyline(0.0, 0.0, slab_w, slab_d)
        else:
            # Cut slab through mid-column so the pad stays visible (L-shaped plate).
            cut_x = col_x0 + col_w * 0.5
            cut_y = col_y0 + col_d * 0.5
            slab_poly = [
                (0.0, 0.0),
                (slab_w, 0.0),
                (slab_w, cut_y),
                (cut_x, cut_y),
                (cut_x, slab_d),
                (0.0, slab_d),
            ]
        z_slab = foot_t
        z_column = foot_t

    footing_attrs = params.get("footing_attrs") or {}
    column_attrs = params.get("column_attrs") or {}
    if highlight == "column":
        col_name = params.get("name") or column_attrs.get("Name") or "S-01"
        col_type = (
            params.get("predefined_type")
            or column_attrs.get("PredefinedType")
            or "COLUMN"
        )
        foot_name = footing_attrs.get("Name") or "F-01"
        foot_type = footing_attrs.get("PredefinedType") or "PAD_FOOTING"
    else:
        foot_name = params.get("name") or footing_attrs.get("Name") or "F-01"
        foot_type = (
            params.get("predefined_type")
            or footing_attrs.get("PredefinedType")
            or "PAD_FOOTING"
        )
        col_name = column_attrs.get("Name") or "S-01"
        col_type = column_attrs.get("PredefinedType") or "COLUMN"

    project_label = params.get("project_name") or (
        col_name if highlight == "column" else foot_name
    )
    ifc_file, _project, _site, _building, storey, body_context = create_project_shell(
        project_label,
        storey_name="EG" if omit_footing else "FD",
    )
    body_context = get_body_context(ifc_file) or body_context

    footing = None
    if not omit_footing:
        footing = add_extruded_product(
            ifc_file,
            ifc_class="IfcFooting",
            name=foot_name,
            body_context=body_context,
            storey=storey,
            polyline=rect_polyline(foot_x0, foot_y0, foot_x1, foot_y1),
            thickness=foot_t,
            z_bottom=0.0,
            predefined_type=foot_type,
        )

    slab_attrs = params.get("slab_attrs") or {}
    add_extruded_product(
        ifc_file,
        ifc_class="IfcSlab",
        name=slab_attrs.get("Name") or "Bodenplatte",
        body_context=body_context,
        storey=storey,
        polyline=slab_poly,
        thickness=slab_t,
        z_bottom=z_slab,
        predefined_type=slab_attrs.get("PredefinedType") or "BASESLAB",
    )

    column = add_extruded_product(
        ifc_file,
        ifc_class="IfcColumn",
        name=col_name,
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(col_x0, col_y0, col_x0 + col_w, col_y0 + col_d),
        thickness=col_h,
        z_bottom=z_column,
        predefined_type=col_type,
    )

    # Geometry-derived GrossVolume always wins over YAML defaults.
    volumes = dict(params.get("quantities") or {})
    if highlight == "column":
        qto = dict(volumes.get("Qto_ColumnBaseQuantities") or {})
        qto["GrossVolume"] = round(col_w * col_d * col_h, 3)
        volumes["Qto_ColumnBaseQuantities"] = qto
        primary = column
        primary_name = col_name
        primary_type = col_type
        load_bearing_pset = "Pset_ColumnCommon"
    else:
        qto = dict(volumes.get("Qto_FootingBaseQuantities") or {})
        qto["GrossVolume"] = round(foot_w * foot_d * foot_t, 3)
        volumes["Qto_FootingBaseQuantities"] = qto
        primary = footing
        primary_name = foot_name
        primary_type = foot_type
        load_bearing_pset = "Pset_FootingCommon"

    resolved = {
        "Name": primary_name,
        "PredefinedType": primary_type,
        "properties": params.get("properties") or {},
        "property_datatypes": params.get("property_datatypes") or {},
        "quantities": volumes,
    }
    if params.get("ObjectType") is not None:
        resolved["ObjectType"] = params["ObjectType"]
    _apply_resolved_attributes(ifc_file, primary, resolved)

    # Light context attrs on companion products (Name / PredefinedType already set)
    companions: list[tuple[ifcopenshell.entity_instance, dict[str, Any]]] = [
        (ifc_file.by_type("IfcSlab")[0], slab_attrs),
    ]
    if highlight == "column":
        if footing is not None:
            companions.append((footing, footing_attrs))
    else:
        companions.append((column, column_attrs))
    for product, attrs in companions:
        if attrs:
            _apply_resolved_attributes(ifc_file, product, attrs)

    # Sanity: LoadBearing must remain True for applicability
    psets = get_psets(primary, psets_only=True)
    load_bearing = (psets.get(load_bearing_pset) or {}).get("LoadBearing")
    if load_bearing is False:
        assign_pset(ifc_file, primary, load_bearing_pset, {"LoadBearing": True})

    return ifc_file, primary
