"""Catalog vignette for Project / Site / Building / Storey and slab hierarchy pictures."""

from __future__ import annotations

from typing import Any, Literal

import ifcopenshell
from ifcopenshell.api.geometry import assign_representation, edit_object_placement
from ifcopenshell.api.root import create_entity
from ifcopenshell.api.spatial import assign_container

from catalog.schema import DEFAULT_STOREY_NAMES
from generators.base import assign_pset, assign_qto, create_multi_storey_shell
from generators.parts import (
    create_body_representation,
    create_extruded_area_solid,
    rect_polyline,
    translation_matrix,
)

HighlightMode = Literal[
    "project",
    "site",
    "building",
    "storey",
    "slab-base",
    "slab-floor",
    "slab-roof",
    "slab-balcony",
]

# Metres — shared vignette geometry
DEFAULT_BUILDING_WIDTH = 8.0
DEFAULT_BUILDING_DEPTH = 6.0
DEFAULT_PLOT_WIDTH = 16.0
DEFAULT_PLOT_DEPTH = 14.0
DEFAULT_SLAB_THICKNESS = 0.35
DEFAULT_PLOT_THICKNESS = 0.20
DEFAULT_STOREY_SPACING = 3.0
DEFAULT_BALCONY_DEPTH = 1.5
DEFAULT_BALCONY_WIDTH = 4.0
# First upper floor (storey index 1 → "01") hosts the balcony plate.
_BALCONY_STOREY_INDEX = 1

# Bottom → top PredefinedType for the three opaque floor plates
_SLAB_PREDEFINED_TYPES: tuple[str, ...] = ("BASESLAB", "FLOOR", "ROOF")
_SLAB_DEFAULT_NAMES: tuple[str, ...] = ("Bodenplatte", "Decke", "Flachdach")

_ENTITY_FIELD_MAP = ("Name", "LongName", "PredefinedType", "ObjectType", "Phase")

_SLAB_HIGHLIGHTS = frozenset({"slab-base", "slab-floor", "slab-roof"})
_SLAB_INDEX_BY_HIGHLIGHT: dict[str, int] = {
    "slab-base": 0,
    "slab-floor": 1,
    "slab-roof": 2,
}
_ALL_HIGHLIGHTS = frozenset(
    {
        "project",
        "site",
        "building",
        "storey",
        "slab-base",
        "slab-floor",
        "slab-roof",
        "slab-balcony",
    }
)


def _apply_resolved_attributes(
    ifc_file: ifcopenshell.file,
    product: ifcopenshell.entity_instance,
    resolved: dict[str, Any] | None,
) -> None:
    """Write YAML-resolved entity fields, psets and qtos onto ``product``."""
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


def _assign_extruded_body(
    ifc_file: ifcopenshell.file,
    product: ifcopenshell.entity_instance,
    *,
    body_context: ifcopenshell.entity_instance,
    polyline: list[tuple[float, float]],
    thickness: float,
    z_bottom: float = 0.0,
) -> None:
    """Attach a horizontal extruded Body; placement Z is absolute world."""
    edit_object_placement(
        ifc_file,
        product=product,
        matrix=translation_matrix(z=z_bottom),
    )
    solid = create_extruded_area_solid(ifc_file, polyline, float(thickness))
    representation = create_body_representation(ifc_file, body_context, solid)
    assign_representation(ifc_file, product=product, representation=representation)


def _centered_rect(
    width: float, depth: float, *, within_width: float, within_depth: float
) -> list[tuple[float, float]]:
    x0 = (within_width - width) * 0.5
    y0 = (within_depth - depth) * 0.5
    return rect_polyline(x0, y0, x0 + width, y0 + depth)


def _balcony_polyline(
    *,
    building_poly: list[tuple[float, float]],
    balcony_width: float,
    balcony_depth: float,
) -> list[tuple[float, float]]:
    """Project a balcony from the +Y façade of the building footprint."""
    xs = [p[0] for p in building_poly]
    ys = [p[1] for p in building_poly]
    x0, x1 = min(xs), max(xs)
    y1 = max(ys)
    cx = 0.5 * (x0 + x1)
    half_w = min(balcony_width, x1 - x0) * 0.5
    return rect_polyline(cx - half_w, y1, cx + half_w, y1 + balcony_depth)


def _add_storey_slab(
    ifc_file: ifcopenshell.file,
    *,
    name: str,
    predefined_type: str,
    body_context: ifcopenshell.entity_instance,
    storey: ifcopenshell.entity_instance,
    polyline: list[tuple[float, float]],
    thickness: float,
) -> ifcopenshell.entity_instance:
    """Create an IfcSlab on a storey; extrusion starts at the storey elevation."""
    slab = create_entity(
        ifc_file,
        ifc_class="IfcSlab",
        name=name,
        predefined_type=predefined_type,
    )
    assign_container(ifc_file, relating_structure=storey, products=[slab])
    # edit_object_placement expects a world matrix; match storey elevation so the
    # slab sits at the storey origin locally (same pattern as generate_space).
    storey_z = float(getattr(storey, "Elevation", None) or 0.0)
    edit_object_placement(
        ifc_file,
        product=slab,
        matrix=translation_matrix(z=storey_z),
    )
    solid = create_extruded_area_solid(ifc_file, polyline, float(thickness))
    representation = create_body_representation(ifc_file, body_context, solid)
    assign_representation(ifc_file, product=slab, representation=representation)
    return slab


def generate_spatial_structure(
    params: dict[str, Any] | None = None,
) -> tuple[ifcopenshell.file, list[ifcopenshell.entity_instance]]:
    """Build an opaque plot + three storey slabs for hierarchy / slab catalog pictures.

    ``params`` keys:
    - ``highlight``: ``project`` | ``site`` | ``building`` | ``storey``
      | ``slab-base`` | ``slab-floor`` | ``slab-roof`` | ``slab-balcony``
    - ``project_attrs`` / ``site_attrs`` / ``building_attrs`` / ``storey_attrs``
    - ``slab_attrs``: optional list (bottom→top) of YAML-resolved slab attributes
    - ``balcony_attrs``: optional YAML-resolved attrs for the 01 balcony
      (IfcSlab FLOOR + IsExternal)
    - optional geometry overrides (widths, thicknesses, spacing, balcony_*)

    Returns ``(ifc_file, primary_products)`` where ``primary_products`` are the
    entities to accent in the isometric preview.
    """
    params = dict(params or {})
    highlight: HighlightMode = params.get("highlight") or "project"
    if highlight not in _ALL_HIGHLIGHTS:
        raise ValueError(f"unsupported highlight mode: {highlight!r}")

    plot_w = float(params.get("plot_width", DEFAULT_PLOT_WIDTH))
    plot_d = float(params.get("plot_depth", DEFAULT_PLOT_DEPTH))
    bldg_w = float(params.get("building_width", DEFAULT_BUILDING_WIDTH))
    bldg_d = float(params.get("building_depth", DEFAULT_BUILDING_DEPTH))
    slab_t = float(params.get("slab_thickness", DEFAULT_SLAB_THICKNESS))
    plot_t = float(params.get("plot_thickness", DEFAULT_PLOT_THICKNESS))
    spacing = float(params.get("storey_spacing", DEFAULT_STOREY_SPACING))
    balcony_w = float(params.get("balcony_width", DEFAULT_BALCONY_WIDTH))
    balcony_d = float(params.get("balcony_depth", DEFAULT_BALCONY_DEPTH))
    storey_names = tuple(params.get("storey_names") or DEFAULT_STOREY_NAMES)
    if len(storey_names) < 1:
        raise ValueError("at least one storey is required")

    elevations = tuple(float(i) * spacing for i in range(len(storey_names)))
    project_attrs = params.get("project_attrs") or {}
    project_name = (
        params.get("project_name")
        or project_attrs.get("Name")
        or "Musterprojekt"
    )

    ifc_file, project, site, building, storeys, body_context = create_multi_storey_shell(
        project_name,
        storey_names=storey_names,
        storey_elevations=elevations,
    )

    plot_poly = rect_polyline(0.0, 0.0, plot_w, plot_d)
    building_poly = _centered_rect(
        bldg_w, bldg_d, within_width=plot_w, within_depth=plot_d
    )

    # Plot sits just below Z=0 so storey slabs rest on top of it.
    _assign_extruded_body(
        ifc_file,
        site,
        body_context=body_context,
        polyline=plot_poly,
        thickness=plot_t,
        z_bottom=-plot_t,
    )

    # Opaque floor plates as real IfcSlab products (shared by hierarchy + slab cards).
    slab_attrs_list = list(params.get("slab_attrs") or [])
    slabs: list[ifcopenshell.entity_instance] = []
    for index, storey in enumerate(storeys):
        predefined = (
            _SLAB_PREDEFINED_TYPES[index]
            if index < len(_SLAB_PREDEFINED_TYPES)
            else "FLOOR"
        )
        default_name = (
            _SLAB_DEFAULT_NAMES[index]
            if index < len(_SLAB_DEFAULT_NAMES)
            else f"Slab-{index}"
        )
        attrs = slab_attrs_list[index] if index < len(slab_attrs_list) else {}
        name = attrs.get("Name") or default_name
        predefined = attrs.get("PredefinedType") or predefined
        slab = _add_storey_slab(
            ifc_file,
            name=name,
            predefined_type=predefined,
            body_context=body_context,
            storey=storey,
            polyline=building_poly,
            thickness=slab_t,
        )
        _apply_resolved_attributes(ifc_file, slab, attrs)
        slabs.append(slab)

    # Projecting balcony on the first upper floor — IfcSlab FLOOR + IsExternal.
    balcony: ifcopenshell.entity_instance | None = None
    if len(storeys) > _BALCONY_STOREY_INDEX and balcony_d > 0 and balcony_w > 0:
        balcony_attrs = params.get("balcony_attrs") or {}
        balcony = _add_storey_slab(
            ifc_file,
            name=balcony_attrs.get("Name") or "Balkon",
            predefined_type=balcony_attrs.get("PredefinedType") or "FLOOR",
            body_context=body_context,
            storey=storeys[_BALCONY_STOREY_INDEX],
            polyline=_balcony_polyline(
                building_poly=building_poly,
                balcony_width=balcony_w,
                balcony_depth=balcony_d,
            ),
            thickness=slab_t,
        )
        _apply_resolved_attributes(ifc_file, balcony, balcony_attrs)

    _apply_resolved_attributes(ifc_file, project, project_attrs)
    _apply_resolved_attributes(ifc_file, site, params.get("site_attrs"))
    _apply_resolved_attributes(ifc_file, building, params.get("building_attrs"))
    storey_attrs_list = params.get("storey_attrs") or []
    for storey, storey_attrs in zip(storeys, storey_attrs_list):
        _apply_resolved_attributes(ifc_file, storey, storey_attrs)

    if highlight == "site":
        primary = [site]
    elif highlight == "building":
        primary = list(slabs)
        if balcony is not None:
            primary.append(balcony)
    elif highlight == "storey":
        # Graded accents on the three storey plates; balcony matches its floor (01).
        primary = list(slabs)
        if balcony is not None:
            primary.append(balcony)
    elif highlight == "slab-balcony":
        if balcony is None:
            raise ValueError("slab-balcony highlight requires a balcony plate")
        primary = [balcony]
    elif highlight in _SLAB_HIGHLIGHTS:
        primary = [slabs[_SLAB_INDEX_BY_HIGHLIGHT[highlight]]]
    else:  # project
        primary = [site, *slabs]
        if balcony is not None:
            primary.append(balcony)

    return ifc_file, primary
