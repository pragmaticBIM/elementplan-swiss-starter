"""Catalog vignette: storey-wise Bruttovolumen (L-flats + stair + foundation)."""

from __future__ import annotations

from typing import Any

import ifcopenshell
from ifcopenshell.api.geometry import assign_representation, edit_object_placement

from generators.base import assign_qto, create_multi_storey_shell
from generators.parts import (
    create_body_representation,
    create_extruded_area_solid,
    rect_polyline,
    translation_matrix,
)
from generators.space import _create_space_entity, _shoelace_area

# Metres — two L-shaped flats + small stair; continuous storey heights (YAML).
DEFAULT_BUILDING_WIDTH = 16.0
DEFAULT_BUILDING_DEPTH = 11.0
DEFAULT_STAIR_WIDTH = 2.2
DEFAULT_STAIR_DEPTH = 3.0
DEFAULT_PLOT_THICKNESS = 0.20
DEFAULT_STOREY_HEIGHT = 3.0
# Foundation / base: underside of base slab → FFL (YAML Untergeschoss rule), thin vignette
DEFAULT_FOUNDATION_HEIGHT = 0.50
DEFAULT_FOUNDATION_STOREY = "FD"
DEFAULT_UPPER_STOREY_NAMES = ("EG", "01", "02")

# Per upper storey: flat A, stair, flat B (foundation is separate)
UPPER_UNIT_KEYS = ("flat_a", "stair", "flat_b")


def _offset(
    points: list[tuple[float, float]], ox: float, oy: float
) -> list[tuple[float, float]]:
    return [(x + ox, y + oy) for x, y in points]


def _unit_footprints(
    *,
    origin_x: float,
    origin_y: float,
    building_width: float,
    building_depth: float,
    stair_width: float,
    stair_depth: float,
) -> dict[str, list[tuple[float, float]]]:
    """Two interlocking L-shaped flats + small stair in the crook (no overlaps).

    Local building coords (0..W, 0..D)::

        Flat A = left bar + bottom bar (L)
        Stair  = small rectangle in the inner crook
        Flat B = right bar + top bar (mirrored L)
    """
    w = float(building_width)
    d = float(building_depth)
    sw = float(stair_width)
    sd = float(stair_depth)
    if sw <= 0 or sd <= 0 or sw >= w or sd >= d:
        raise ValueError("stair footprint must fit inside the building")

    # Crook so the two L areas are equal: left bar width = right bar width.
    left_w = (w - sw) * 0.5
    bottom_h = (d - sd) * 0.5
    sx0 = left_w
    sy0 = bottom_h
    sx1 = left_w + sw
    sy1 = bottom_h + sd

    # Flat A: left full-depth bar + bottom bar under the stair / right side
    flat_a = [
        (0.0, 0.0),
        (sx1, 0.0),
        (sx1, sy0),
        (sx0, sy0),
        (sx0, d),
        (0.0, d),
    ]
    stair = [
        (sx0, sy0),
        (sx1, sy0),
        (sx1, sy1),
        (sx0, sy1),
    ]
    # Flat B: right full-depth bar + top bar over the stair / left side
    flat_b = [
        (sx1, 0.0),
        (w, 0.0),
        (w, d),
        (sx0, d),
        (sx0, sy1),
        (sx1, sy1),
    ]
    foundation = rect_polyline(0.0, 0.0, w, d)

    # Sanity: areas must sum to the building footprint
    total = _shoelace_area(flat_a) + _shoelace_area(stair) + _shoelace_area(flat_b)
    expected = w * d
    if abs(total - expected) > 1e-6:
        raise ValueError(
            f"unit footprints overlap or leave gaps: area sum {total} != {expected}"
        )

    return {
        "flat_a": _offset(flat_a, origin_x, origin_y),
        "stair": _offset(stair, origin_x, origin_y),
        "flat_b": _offset(flat_b, origin_x, origin_y),
        "foundation": _offset(foundation, origin_x, origin_y),
    }


def _add_volume(
    ifc_file: ifcopenshell.file,
    *,
    storey: ifcopenshell.entity_instance,
    body_context: ifcopenshell.entity_instance,
    polyline: list[tuple[float, float]],
    height: float,
    template: dict[str, Any],
    storey_name: str,
    default_suffix: str,
) -> ifcopenshell.entity_instance:
    area = _shoelace_area(polyline)
    quantities = dict(
        (template.get("quantities") or {}).get("Qto_SpaceBaseQuantities") or {}
    )
    quantities["GrossFloorArea"] = round(area, 2)
    quantities["GrossVolume"] = round(area * height, 2)
    quantities["Height"] = height

    name = template.get("name") or template.get("Name")
    if not name:
        name = f"{storey_name}-{default_suffix}"
    else:
        name = str(name).format(storey=storey_name)

    long_name = template.get("long_name") or template.get("LongName")
    predefined_type = (
        template.get("predefined_type")
        or template.get("PredefinedType")
        or "GFA"
    )
    object_type = template.get("object_type") or template.get("ObjectType")

    space = _create_space_entity(
        ifc_file,
        storey=storey,
        body_context=body_context,
        name=str(name),
        long_name=str(long_name) if long_name is not None else None,
        predefined_type=str(predefined_type),
        polyline=polyline,
        height=height,
        quantities=quantities,
        properties=template.get("properties") or {},
        properties_datatypes=template.get("property_datatypes") or {},
        object_type=str(object_type) if object_type is not None else None,
    )
    for qto_name, props in (template.get("quantities") or {}).items():
        if qto_name == "Qto_SpaceBaseQuantities":
            continue
        assign_qto(ifc_file, space, qto_name, props)
    return space


def generate_gross_volumes(
    params: dict[str, Any] | None = None,
) -> tuple[ifcopenshell.file, list[ifcopenshell.entity_instance]]:
    """Build Bruttovolumen: FD (0.5 m) + upper storeys with 2 L-flats + stair.

    Upper volumes run FFL → next FFL (continuous, no vertical gaps). Foundation
    is a single full-footprint volume on storey ``FD`` (YAML base-slab rule).

    Returns ``(ifc_file, spaces)``: foundation first, then per upper storey
    flat A, stair, flat B.
    """
    params = dict(params or {})
    upper_names = tuple(params.get("storey_names") or DEFAULT_UPPER_STOREY_NAMES)
    if len(upper_names) < 1:
        raise ValueError("at least one upper storey is required")

    height = float(params.get("height", DEFAULT_STOREY_HEIGHT))
    if height <= 0:
        raise ValueError("height must be positive")
    # Continuous storeys: spacing equals height (YAML: OK Fertigboden → OK next)
    spacing = float(params.get("storey_spacing", height))
    foundation_h = float(params.get("foundation_height", DEFAULT_FOUNDATION_HEIGHT))
    if foundation_h <= 0:
        raise ValueError("foundation_height must be positive")
    foundation_name = str(params.get("foundation_storey") or DEFAULT_FOUNDATION_STOREY)

    bldg_w = float(params.get("building_width", DEFAULT_BUILDING_WIDTH))
    bldg_d = float(params.get("building_depth", DEFAULT_BUILDING_DEPTH))
    stair_w = float(params.get("stair_width", DEFAULT_STAIR_WIDTH))
    stair_d = float(params.get("stair_depth", DEFAULT_STAIR_DEPTH))
    # Default plot = building footprint so the front edge stops with the volume.
    # Optional larger plot_* keep the +Y edge flush (yard toward −Y).
    plot_w = float(params.get("plot_width", bldg_w))
    plot_d = float(params.get("plot_depth", bldg_d))
    plot_t = float(params.get("plot_thickness", DEFAULT_PLOT_THICKNESS))
    if plot_w < bldg_w or plot_d < bldg_d:
        raise ValueError("plot must cover the building footprint")

    origin_x = (plot_w - bldg_w) * 0.5
    origin_y = plot_d - bldg_d
    footprints = _unit_footprints(
        origin_x=origin_x,
        origin_y=origin_y,
        building_width=bldg_w,
        building_depth=bldg_d,
        stair_width=stair_w,
        stair_depth=stair_d,
    )

    # FD underside at -foundation_h; top of foundation = EG FFL at Z=0
    storey_names = (foundation_name, *upper_names)
    elevations = (-foundation_h, *tuple(float(i) * spacing for i in range(len(upper_names))))
    project_name = params.get("project_name") or "Bruttovolumen"

    ifc_file, _project, site, _building, storeys, body_context = create_multi_storey_shell(
        project_name,
        storey_names=storey_names,
        storey_elevations=elevations,
    )

    # Plot sits on the foundation top (EG FFL); edges flush with the gross volume.
    plot_poly = rect_polyline(0.0, 0.0, plot_w, plot_d)
    edit_object_placement(
        ifc_file,
        product=site,
        matrix=translation_matrix(z=0.0),
    )
    solid = create_extruded_area_solid(ifc_file, plot_poly, plot_t)
    representation = create_body_representation(ifc_file, body_context, solid)
    assign_representation(ifc_file, product=site, representation=representation)

    unit_templates: dict[str, dict[str, Any]] = params.get("unit_templates") or {}
    spaces: list[ifcopenshell.entity_instance] = []

    # Foundation: one full-footprint volume on FD
    spaces.append(
        _add_volume(
            ifc_file,
            storey=storeys[0],
            body_context=body_context,
            polyline=footprints["foundation"],
            height=foundation_h,
            template=dict(unit_templates.get("foundation") or {}),
            storey_name=foundation_name,
            default_suffix="FD",
        )
    )

    suffixes = {"flat_a": "WA", "stair": "TR", "flat_b": "WB"}
    for storey, storey_name in zip(storeys[1:], upper_names):
        for key in UPPER_UNIT_KEYS:
            spaces.append(
                _add_volume(
                    ifc_file,
                    storey=storey,
                    body_context=body_context,
                    polyline=footprints[key],
                    height=height,
                    template=dict(unit_templates.get(key) or {}),
                    storey_name=storey_name,
                    default_suffix=suffixes[key],
                )
            )

    return ifc_file, spaces
