"""Generate IfcSpace Luftraum with a two-storey atrium / void vignette.

Layout (adapted from the interior-space room vignette):
- Lower storey: primary + neighbour spaces, floor fabric, partition (lower only)
- Mid slab + flooring over neighbour, cantilevered 1.5 m into the void
- Upper space on that mid slab reaches the top-slab soffit; suspended ceiling
  under the beams across the full footprint (including the Luftraum void)
- Raised top slab with beams hanging below (visible in the void)
- Luftraum in the remaining void: top of lower primary → underside of top slab
"""

from __future__ import annotations

from typing import Any, Sequence

import ifcopenshell

from generators.base import (
    assign_qto,
    create_project_shell,
    get_body_context,
)
from generators.covering import add_covering
from generators.parts import add_extruded_product, bounds_2d, rect_polyline
from generators.slab import add_slab
from generators.space import (
    CEILING_COVERING_THICKNESS,
    CEILING_SLAB_THICKNESS,
    DEFAULT_FINISH_CEILING_HEIGHT,
    FLOOR_COVERING_THICKNESS,
    FLOOR_SLAB_THICKNESS,
    NEIGHBOR_SPACE_WIDTH,
    WALL_THICKNESS,
    _boundary_from_params,
    _create_space_entity,
    _shoelace_area,
)
from generators.wall import add_wall

DEFAULT_UPPER_HEIGHT = 2.8
# Mid slab / upper flooring cantilever from the partition into the Luftraum
OVERHANG_INTO_LUFTRAUM = 1.5
# Beams hang below the raised top slab (visible through the atrium void)
BEAM_WIDTH = 0.25
BEAM_DEPTH = 0.50
BEAM_COUNT = 4
# Extra clear above the upper-storey height so the top slab sits distinctly higher
TOP_SLAB_RAISE = 0.70


def _add_beams_under_slab(
    ifc_file: ifcopenshell.file,
    *,
    body_context: ifcopenshell.entity_instance,
    storey: ifcopenshell.entity_instance,
    primary_name: str,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    z_top_slab: float,
    beam_width: float = BEAM_WIDTH,
    beam_depth: float = BEAM_DEPTH,
    beam_count: int = BEAM_COUNT,
) -> list[ifcopenshell.entity_instance]:
    """Place rectangular IfcBeams spanning in +X under the top slab."""
    if beam_count < 1:
        return []
    span = y1 - y0
    if span <= beam_width * beam_count:
        raise ValueError("footprint too shallow for the requested beams")
    # Evenly space beam centre-lines between the slab edges (span across width)
    step = span / (beam_count + 1)
    z_beam = z_top_slab - beam_depth
    beams: list[ifcopenshell.entity_instance] = []
    for i in range(beam_count):
        cy = y0 + step * (i + 1)
        half = beam_width * 0.5
        beams.append(
            add_extruded_product(
                ifc_file,
                ifc_class="IfcBeam",
                name=f"{primary_name}-Beam-{i + 1:02d}",
                body_context=body_context,
                storey=storey,
                polyline=rect_polyline(x0, cy - half, x1, cy + half),
                thickness=beam_depth,
                z_bottom=z_beam,
                predefined_type="BEAM",
            )
        )
    return beams


def _add_luftraum_vignette(
    ifc_file: ifcopenshell.file,
    *,
    storey: ifcopenshell.entity_instance,
    body_context: ifcopenshell.entity_instance,
    primary_polyline: Sequence[Sequence[float]],
    lower_height: float,
    upper_height: float,
    primary_name: str,
    finish_ceiling_height: float | None = None,
    overhang: float | None = None,
    neighbor_attrs: dict[str, Any] | None = None,
    upper_attrs: dict[str, Any] | None = None,
    include_ceiling_covering: bool = True,
    cap_spaces_at_ceiling: bool = False,
    omit_spaces: bool = False,
    top_slab_half: bool = False,
) -> tuple[
    ifcopenshell.entity_instance | None,
    ifcopenshell.entity_instance | None,
    list[ifcopenshell.entity_instance],
]:
    """Fabric + optional context spaces around the Luftraum void.

    When ``omit_spaces``, only slabs / coverings / wall / beams are created.
    When ``cap_spaces_at_ceiling``, the upper gallery stops at the Abhangdecke
    (leaves beams + top slab clear for overlays such as Koordinationszone).
    When ``top_slab_half``, the raised top slab covers only the neighbour /
    gallery half of the footprint so beams over the atrium stay visible.

    Returns ``(lower_neighbor, upper_neighbor, beams)``.
    """
    min_x, min_y, max_x, max_y = bounds_2d(primary_polyline)
    depth = max_y - min_y
    neighbor_width = NEIGHBOR_SPACE_WIDTH
    wall_t = WALL_THICKNESS
    overhang_m = float(OVERHANG_INTO_LUFTRAUM if overhang is None else overhang)
    if overhang_m <= 0 or overhang_m >= (max_x - min_x):
        raise ValueError(
            f"overhang ({overhang_m}) must be between 0 and primary width ({max_x - min_x})"
        )

    neighbor_poly = rect_polyline(
        max_x + wall_t,
        min_y,
        max_x + wall_t + neighbor_width,
        max_y,
    )
    # Mid slab: neighbour + wall strip + overhang into the Luftraum
    mid_poly = rect_polyline(
        max_x - overhang_m,
        min_y,
        max_x + wall_t + neighbor_width,
        max_y,
    )
    full_x1 = max_x + wall_t + neighbor_width
    full_footprint = rect_polyline(min_x, min_y, full_x1, max_y)
    # Neighbour / gallery half — cutaway over the atrium for beam previews
    top_slab_poly = (
        rect_polyline((min_x + full_x1) * 0.5, min_y, full_x1, max_y)
        if top_slab_half
        else full_footprint
    )

    z_floor_covering = -FLOOR_COVERING_THICKNESS
    z_floor_slab_top = z_floor_covering
    z_floor_slab = z_floor_slab_top - FLOOR_SLAB_THICKNESS
    z_mid_slab = lower_height
    z_mid_slab_top = z_mid_slab + CEILING_SLAB_THICKNESS
    z_upper_covering = z_mid_slab_top
    z_upper_ffl = z_upper_covering + FLOOR_COVERING_THICKNESS
    # Upper storey clear sits under the raised beam / slab zone
    z_upper_storey_top = z_mid_slab + upper_height
    z_top_slab = z_upper_storey_top + TOP_SLAB_RAISE
    z_beam_bottom = z_top_slab - BEAM_DEPTH
    # Partition only on the lower storey (no wall above the mid slab)
    wall_height = z_mid_slab - z_floor_slab_top

    add_slab(
        ifc_file,
        name=f"{primary_name}-FloorSlab",
        body_context=body_context,
        storey=storey,
        polyline=full_footprint,
        thickness=FLOOR_SLAB_THICKNESS,
        z_bottom=z_floor_slab,
        predefined_type="FLOOR",
    )
    add_covering(
        ifc_file,
        name=f"{primary_name}-FloorCovering",
        body_context=body_context,
        storey=storey,
        polyline=primary_polyline,
        thickness=FLOOR_COVERING_THICKNESS,
        z_bottom=z_floor_covering,
        predefined_type="FLOORING",
    )
    add_covering(
        ifc_file,
        name=f"{primary_name}-N-FloorCovering",
        body_context=body_context,
        storey=storey,
        polyline=neighbor_poly,
        thickness=FLOOR_COVERING_THICKNESS,
        z_bottom=z_floor_covering,
        predefined_type="FLOORING",
    )

    # Mid slab + flooring cantilevered into the Luftraum
    add_slab(
        ifc_file,
        name=f"{primary_name}-MidSlab",
        body_context=body_context,
        storey=storey,
        polyline=mid_poly,
        thickness=CEILING_SLAB_THICKNESS,
        z_bottom=z_mid_slab,
        predefined_type="FLOOR",
    )
    add_covering(
        ifc_file,
        name=f"{primary_name}-N-UpperFloorCovering",
        body_context=body_context,
        storey=storey,
        polyline=mid_poly,
        thickness=FLOOR_COVERING_THICKNESS,
        z_bottom=z_upper_covering,
        predefined_type="FLOORING",
    )

    # Raised top slab; beams hang directly underneath across the full bay
    add_slab(
        ifc_file,
        name=f"{primary_name}-TopSlab",
        body_context=body_context,
        storey=storey,
        polyline=top_slab_poly,
        thickness=CEILING_SLAB_THICKNESS,
        z_bottom=z_top_slab,
        predefined_type="FLOOR",
    )
    beams = _add_beams_under_slab(
        ifc_file,
        body_context=body_context,
        storey=storey,
        primary_name=str(primary_name),
        x0=min_x,
        x1=full_x1,
        y0=min_y,
        y1=max_y,
        z_top_slab=z_top_slab,
    )

    # Suspended ceiling under the beams — full footprint (through the Luftraum void)
    finish_h = (
        float(finish_ceiling_height)
        if finish_ceiling_height is not None
        else DEFAULT_FINISH_CEILING_HEIGHT
    )
    plenum = max(0.05, lower_height - finish_h) if finish_h < lower_height else 0.2
    z_ceiling = z_beam_bottom - plenum
    if z_ceiling <= z_upper_ffl or z_ceiling >= z_beam_bottom:
        raise ValueError(
            f"upper ceiling z ({z_ceiling}) must sit between upper FFL ({z_upper_ffl}) "
            f"and beam soffit ({z_beam_bottom})"
        )
    if include_ceiling_covering:
        add_covering(
            ifc_file,
            name=f"{primary_name}-CeilingCovering",
            body_context=body_context,
            storey=storey,
            polyline=full_footprint,
            thickness=CEILING_COVERING_THICKNESS,
            z_bottom=z_ceiling,
            predefined_type="CEILING",
        )

    add_wall(
        ifc_file,
        name=f"{primary_name}-Partition",
        body_context=body_context,
        storey=storey,
        origin=(max_x + wall_t, min_y, z_floor_slab_top),
        length=depth,
        height=wall_height,
        thickness=wall_t,
        direction_xy=(0.0, 1.0),
        predefined_type="PARTITIONING",
    )

    if omit_spaces:
        return None, None, beams

    neighbor_area = _shoelace_area(neighbor_poly)
    attrs = neighbor_attrs or {}
    neighbor_quantities = dict(attrs.get("quantities") or {})
    neighbor_quantities.setdefault("GrossFloorArea", neighbor_area)
    neighbor_quantities.setdefault("GrossVolume", neighbor_area * lower_height)
    neighbor_quantities.setdefault("Height", lower_height)
    neighbor_quantities.setdefault("NetFloorArea", round(neighbor_area, 2))
    neighbor_quantities.setdefault("FinishCeilingHeight", lower_height)

    lower_neighbor = _create_space_entity(
        ifc_file,
        storey=storey,
        body_context=body_context,
        name=str(attrs.get("name") or f"{primary_name}-N"),
        long_name=attrs.get("long_name") or "Flur",
        predefined_type=str(attrs.get("predefined_type") or "INTERNAL"),
        polyline=neighbor_poly,
        height=lower_height,
        quantities=neighbor_quantities,
        properties=attrs.get("properties") or {},
        properties_datatypes=attrs.get("property_datatypes") or {},
    )

    upper_area = _shoelace_area(mid_poly)
    # Upper gallery normally reaches the top-slab soffit; optional cap at Abhangdecke
    upper_space_top = z_ceiling if cap_spaces_at_ceiling else z_top_slab
    upper_space_height = upper_space_top - z_upper_ffl
    upper_finish = z_ceiling - z_upper_ffl
    upper = upper_attrs or {}
    upper_quantities = dict(upper.get("quantities") or {})
    upper_quantities.setdefault("GrossFloorArea", upper_area)
    upper_quantities.setdefault("GrossVolume", upper_area * upper_space_height)
    upper_quantities.setdefault("Height", upper_space_height)
    upper_quantities.setdefault("NetFloorArea", round(upper_area, 2))
    upper_quantities.setdefault("FinishCeilingHeight", upper_finish)

    upper_neighbor = _create_space_entity(
        ifc_file,
        storey=storey,
        body_context=body_context,
        name=str(upper.get("name") or f"{primary_name}-N-OG"),
        long_name=upper.get("long_name") or "Buero",
        predefined_type=str(upper.get("predefined_type") or "INTERNAL"),
        polyline=mid_poly,
        height=upper_space_height,
        quantities=upper_quantities,
        properties=upper.get("properties") or {},
        properties_datatypes=upper.get("property_datatypes") or {},
        z_bottom=z_upper_ffl,
    )

    return lower_neighbor, upper_neighbor, beams


def generate_luftraum(
    params: dict[str, Any],
) -> tuple[ifcopenshell.file, ifcopenshell.entity_instance]:
    """Create a Luftraum (USERDEFINED / ObjectType=Luftraum) with atrium vignette.

    Required params:
      - height (float, m): lower interior space height (= Luftraum bottom)
      - boundary OR width + depth: lower primary footprint

    Optional:
      - upper_height (float, m): upper-storey clear height above mid slab (default 2.8);
        Luftraum also includes TOP_SLAB_RAISE up to the top-slab soffit
      - finish_ceiling_height: suspended ceiling in the upper bay only
      - neighbor_attrs / upper_attrs: context space attributes
      - with_context (bool, default True)
      - omit_luftraum (bool, default False): fabric + context spaces only (no void)
      - omit_spaces (bool, default False): fabric only — no IfcSpace volumes
      - include_ceiling_covering (bool, default True)
      - cap_spaces_at_ceiling (bool, default False): stop Luftraum + upper gallery
        at the Abhangdecke so beams/top slab stay clear
      - top_slab_half (bool, default False): top slab only over the neighbour /
        gallery half (beam catalog cutaway)

    Returns ``(ifc_file, luftraum_space)``. When spaces are omitted, primary is the
    storey (callers that only need fabric should ignore it).
    """
    height = params.get("height")
    if height is None:
        raise ValueError("height is required")
    height = float(height)
    if height <= 0:
        raise ValueError("height must be positive")

    upper_height = float(params.get("upper_height", DEFAULT_UPPER_HEIGHT))
    if upper_height <= 0:
        raise ValueError("upper_height must be positive")

    primary_polyline = _boundary_from_params(params)
    min_x, min_y, max_x, max_y = bounds_2d(primary_polyline)
    overhang = float(params.get("overhang", OVERHANG_INTO_LUFTRAUM))
    if overhang <= 0 or overhang >= (max_x - min_x):
        raise ValueError(
            f"overhang ({overhang}) must be between 0 and primary width ({max_x - min_x})"
        )
    # Void footprint = primary minus the mid-slab cantilever
    luftraum_polyline = rect_polyline(min_x, min_y, max_x - overhang, max_y)
    gross_floor_area = _shoelace_area(luftraum_polyline)
    finish_ceiling = float(
        params.get("FinishCeilingHeight")
        or params.get("finish_ceiling_height")
        or DEFAULT_FINISH_CEILING_HEIGHT
    )
    omit_spaces = bool(params.get("omit_spaces", False))
    omit_luftraum = bool(params.get("omit_luftraum", False)) or omit_spaces
    cap_spaces_at_ceiling = bool(params.get("cap_spaces_at_ceiling", False))
    # Void reaches the raised top-slab soffit (upper storey + raised beam zone),
    # or stops at the Abhangdecke when capped for roof/beam overlays.
    if cap_spaces_at_ceiling:
        plenum = (
            max(0.05, height - finish_ceiling)
            if finish_ceiling < height
            else 0.2
        )
        z_ceiling = height + upper_height + TOP_SLAB_RAISE - BEAM_DEPTH - plenum
        luftraum_height = z_ceiling - height
    else:
        luftraum_height = upper_height + TOP_SLAB_RAISE
    gross_volume = gross_floor_area * luftraum_height
    primary_area = _shoelace_area(primary_polyline)

    ifc_file = params.get("ifc_file")
    storey = params.get("storey")
    body_context = params.get("body_context")

    if ifc_file is None or storey is None:
        shell_name = params.get("project_name") or params.get("name") or params.get("Name") or "Luftraum"
        ifc_file, _project, _site, _building, storey, body_context = create_project_shell(
            name=f"Catalog — {shell_name}"
        )
    elif body_context is None:
        body_context = get_body_context(ifc_file)

    name = params.get("name") or params.get("Name") or "LR-01"
    long_name = params.get("long_name") or params.get("LongName")
    predefined_type = (
        params.get("predefined_type") or params.get("PredefinedType") or "USERDEFINED"
    )
    object_type = params.get("object_type") or params.get("ObjectType") or "Luftraum"

    quantities: dict[str, Any] = dict(
        (params.get("quantities") or {}).get("Qto_SpaceBaseQuantities") or {}
    )
    quantities["GrossFloorArea"] = gross_floor_area
    quantities["GrossVolume"] = gross_volume
    quantities["Height"] = luftraum_height
    quantities["NetFloorArea"] = round(gross_floor_area, 2)

    lower_space: ifcopenshell.entity_instance | None = None
    if not omit_spaces:
        # Lower primary interior space (full bay under void + cantilever)
        lower_attrs = params.get("lower_attrs") or {}
        lower_quantities = dict(lower_attrs.get("quantities") or {})
        lower_quantities.setdefault("GrossFloorArea", primary_area)
        lower_quantities.setdefault("GrossVolume", primary_area * height)
        lower_quantities.setdefault("Height", height)
        lower_quantities.setdefault("NetFloorArea", round(primary_area, 2))
        # No suspended ceiling in the lower room
        lower_quantities["FinishCeilingHeight"] = height

        lower_space = _create_space_entity(
            ifc_file,
            storey=storey,
            body_context=body_context,
            name=str(lower_attrs.get("name") or "101"),
            long_name=lower_attrs.get("long_name") or "Buero",
            predefined_type=str(lower_attrs.get("predefined_type") or "INTERNAL"),
            polyline=primary_polyline,
            height=height,
            quantities=lower_quantities,
            properties=lower_attrs.get("properties") or {},
            properties_datatypes=lower_attrs.get("property_datatypes") or {},
        )

    luftraum: ifcopenshell.entity_instance | None = None
    if not omit_luftraum:
        luftraum = _create_space_entity(
            ifc_file,
            storey=storey,
            body_context=body_context,
            name=str(name),
            long_name=str(long_name) if long_name is not None else "Luftraum",
            predefined_type=str(predefined_type),
            polyline=luftraum_polyline,
            height=luftraum_height,
            quantities=quantities,
            properties=params.get("properties") or {},
            properties_datatypes=params.get("property_datatypes") or {},
            object_type=str(object_type),
            z_bottom=height,
        )
        for qto_name, props in (params.get("quantities") or {}).items():
            if qto_name == "Qto_SpaceBaseQuantities":
                continue
            assign_qto(ifc_file, luftraum, qto_name, props)

    include_ceiling_covering = bool(params.get("include_ceiling_covering", True))
    top_slab_half = bool(params.get("top_slab_half", False))
    if params.get("with_context", True):
        _add_luftraum_vignette(
            ifc_file,
            storey=storey,
            body_context=body_context,
            primary_polyline=primary_polyline,
            lower_height=height,
            upper_height=upper_height,
            primary_name=str(name),
            finish_ceiling_height=finish_ceiling,
            overhang=overhang,
            neighbor_attrs=params.get("neighbor_attrs"),
            upper_attrs=params.get("upper_attrs"),
            include_ceiling_covering=include_ceiling_covering,
            cap_spaces_at_ceiling=cap_spaces_at_ceiling,
            omit_spaces=omit_spaces,
            top_slab_half=top_slab_half,
        )

    if luftraum is not None:
        return ifc_file, luftraum
    if lower_space is not None:
        return ifc_file, lower_space
    return ifc_file, storey
