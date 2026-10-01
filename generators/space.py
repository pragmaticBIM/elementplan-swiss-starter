"""Generate a standards-correct IfcSpace, optionally with a room vignette."""

from __future__ import annotations

from typing import Any, Sequence

import ifcopenshell
from ifcopenshell.api.aggregate import assign_object
from ifcopenshell.api.root import create_entity

from generators.base import (
    assign_pset,
    assign_qto,
    create_project_shell,
    get_body_context,
)
from generators.covering import add_covering, add_vertical_covering
from generators.parts import (
    bounds_2d,
    create_body_representation,
    create_extruded_area_solid,
    rect_polyline,
    translation_matrix,
)
from generators.slab import add_slab
from generators.wall import add_opening_filling, add_opening_in_wall, add_wall
from ifcopenshell.api.geometry import assign_representation, edit_object_placement

# Vignette defaults (metres)
FLOOR_SLAB_THICKNESS = 0.30
FLOOR_COVERING_THICKNESS = 0.10
CEILING_COVERING_THICKNESS = 0.10
CEILING_SLAB_THICKNESS = 0.30
WALL_THICKNESS = 0.20
# Exterior SOLIDWALL is deeper so door/window frames sit flush with the outer face
# (no proud frames). Interior partitions keep WALL_THICKNESS.
EXTERIOR_WALL_THICKNESS = 0.36
CLADDING_THICKNESS = 0.05
CLADDING_GAP = 0.01  # avoid coplanar wall/cladding faces (z-fighting in PNG)
NEIGHBOR_SPACE_WIDTH = 3.0
DEFAULT_FINISH_CEILING_HEIGHT = 2.6
DEFAULT_EXTERIOR_SPACE_HEIGHT = 1.0
DEFAULT_BALCONY_DEPTH = 1.5
DEFAULT_INTERIOR_HEIGHT = 2.8
DOOR_WIDTH = 0.90
DOOR_HEIGHT = 2.10
WINDOW_WIDTH = 1.20
WINDOW_HEIGHT = 1.40
WINDOW_SILL = 0.90


def _shoelace_area(points: Sequence[Sequence[float]]) -> float:
    """Absolute polygon area via the shoelace formula (2D)."""
    if len(points) < 3:
        raise ValueError("boundary must have at least 3 points")
    area = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = float(points[i][0]), float(points[i][1])
        x2, y2 = float(points[(i + 1) % n][0]), float(points[(i + 1) % n][1])
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def _boundary_from_params(params: dict[str, Any]) -> list[tuple[float, float]]:
    """Resolve rectangular (width, depth) or explicit polygon boundary."""
    boundary = params.get("boundary")
    if boundary:
        pts = [(float(p[0]), float(p[1])) for p in boundary]
        if len(pts) < 3:
            raise ValueError("boundary must have at least 3 points")
        if pts[0] == pts[-1] and len(pts) > 3:
            pts = pts[:-1]
        return pts

    width = params.get("width")
    depth = params.get("depth")
    if width is None or depth is None:
        raise ValueError("provide either boundary or both width and depth")
    w, d = float(width), float(depth)
    if w <= 0 or d <= 0:
        raise ValueError("width and depth must be positive")
    return [(0.0, 0.0), (w, 0.0), (w, d), (0.0, d)]


def _create_space_entity(
    ifc_file: ifcopenshell.file,
    *,
    storey: ifcopenshell.entity_instance,
    body_context: ifcopenshell.entity_instance,
    name: str,
    long_name: str | None,
    predefined_type: str,
    polyline: Sequence[Sequence[float]],
    height: float,
    quantities: dict[str, Any] | None = None,
    properties: dict[str, dict[str, Any]] | None = None,
    properties_datatypes: dict[str, dict[str, str]] | None = None,
    object_type: str | None = None,
    z_bottom: float = 0.0,
) -> ifcopenshell.entity_instance:
    space = create_entity(
        ifc_file,
        ifc_class="IfcSpace",
        name=str(name),
        predefined_type=str(predefined_type),
    )
    if long_name is not None:
        space.LongName = str(long_name)
    if object_type is not None:
        space.ObjectType = str(object_type)

    assign_object(ifc_file, relating_object=storey, products=[space])
    # edit_object_placement expects a world matrix; match the storey elevation so
    # the space sits at the storey origin locally (not Z-compensated to world 0).
    storey_z = float(getattr(storey, "Elevation", None) or 0.0)
    edit_object_placement(
        ifc_file,
        product=space,
        matrix=translation_matrix(z=storey_z + float(z_bottom)),
    )

    solid = create_extruded_area_solid(
        ifc_file,
        [(float(p[0]), float(p[1])) for p in polyline],
        float(height),
    )
    representation = create_body_representation(ifc_file, body_context, solid)
    assign_representation(ifc_file, product=space, representation=representation)

    if quantities:
        assign_qto(ifc_file, space, "Qto_SpaceBaseQuantities", quantities)
    property_datatypes = properties_datatypes or {}
    for pset_name, props in (properties or {}).items():
        assign_pset(
            ifc_file,
            space,
            pset_name,
            props,
            datatypes=property_datatypes.get(pset_name),
        )
    return space


def _add_space_vignette(
    ifc_file: ifcopenshell.file,
    *,
    storey: ifcopenshell.entity_instance,
    body_context: ifcopenshell.entity_instance,
    primary_polyline: Sequence[Sequence[float]],
    height: float,
    primary_name: str,
    finish_ceiling_height: float | None = None,
    neighbor_attrs: dict[str, Any] | None = None,
    include_ceiling_covering: bool = True,
    include_ceiling_slab: bool = True,
    include_neighbor_space: bool = True,
    include_floor_slab: bool = True,
    include_floor_covering: bool = True,
    include_exterior_envelope: bool = False,
    include_partition_openings: bool = False,
    omit_camera_facing_envelope: bool = False,
    neighbor_space_width: float = NEIGHBOR_SPACE_WIDTH,
) -> ifcopenshell.entity_instance | None:
    """Add floor/ceiling fabric, one partition wall, and a neighbouring space.

    ``height`` is FFL → underside of the structural top slab (both spaces fill that).
    Primary room only: suspended ceiling underside at ``finish_ceiling_height``.
    Neighbour has floor covering but no ceiling covering.

    Optional ``include_exterior_envelope`` wraps both rooms in SOLIDWALL envelope
    with closed outer corners (N/S walls span the full outer footprint).
    Optional ``omit_camera_facing_envelope`` drops the +Y long wall so the
    isometric view reads into the rooms (door/window cards).
    Optional ``include_partition_openings`` cuts an interior door + window into the
    partition (IsExternal fillings applied later by fabric accent).

    Returns the neighbour ``IfcSpace`` when ``include_neighbor_space`` is True,
    otherwise ``None`` (fabric + partition still added).
    """
    min_x, min_y, max_x, max_y = bounds_2d(primary_polyline)
    depth = max_y - min_y
    neighbor_width = float(neighbor_space_width)
    if neighbor_width <= 0:
        raise ValueError("neighbor_space_width must be positive")
    wall_t = WALL_THICKNESS
    ext_t = EXTERIOR_WALL_THICKNESS

    neighbor_poly = rect_polyline(
        max_x + wall_t,
        min_y,
        max_x + wall_t + neighbor_width,
        max_y,
    )
    rooms_max_x = max_x + wall_t + neighbor_width
    if include_exterior_envelope:
        # North lip matches the facing wall's outer face. When that wall is
        # omitted, stop the slab on the space plane so it does not project
        # past the open side.
        slab_max_y = max_y if omit_camera_facing_envelope else max_y + ext_t
        slab_footprint = rect_polyline(
            min_x - ext_t,
            min_y - ext_t,
            rooms_max_x + ext_t,
            slab_max_y,
        )
    else:
        slab_footprint = rect_polyline(min_x, min_y, rooms_max_x, max_y)

    z_floor_covering = -FLOOR_COVERING_THICKNESS
    z_floor_slab_top = z_floor_covering if include_floor_covering else 0.0
    z_floor_slab = z_floor_slab_top - FLOOR_SLAB_THICKNESS
    z_ceiling_slab = height
    wall_height = z_ceiling_slab - z_floor_slab_top

    if include_floor_slab:
        add_slab(
            ifc_file,
            name=f"{primary_name}-FloorSlab",
            body_context=body_context,
            storey=storey,
            polyline=slab_footprint,
            thickness=FLOOR_SLAB_THICKNESS,
            z_bottom=z_floor_slab,
            predefined_type="FLOOR",
        )
    if include_floor_covering:
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
    if include_ceiling_covering:
        finish_h = (
            float(finish_ceiling_height)
            if finish_ceiling_height is not None
            else DEFAULT_FINISH_CEILING_HEIGHT
        )
        if finish_h <= 0 or finish_h >= height:
            raise ValueError(
                f"finish_ceiling_height ({finish_h}) must be between 0 and space height ({height})"
            )
        add_covering(
            ifc_file,
            name=f"{primary_name}-CeilingCovering",
            body_context=body_context,
            storey=storey,
            polyline=primary_polyline,
            thickness=CEILING_COVERING_THICKNESS,
            z_bottom=finish_h,
            predefined_type="CEILING",
        )
    if include_ceiling_slab:
        add_slab(
            ifc_file,
            name=f"{primary_name}-CeilingSlab",
            body_context=body_context,
            storey=storey,
            polyline=slab_footprint,
            thickness=CEILING_SLAB_THICKNESS,
            z_bottom=z_ceiling_slab,
            predefined_type="FLOOR",
        )

    partition_origin = (max_x + wall_t, min_y, z_floor_slab_top)
    partition = add_wall(
        ifc_file,
        name=f"{primary_name}-Partition",
        body_context=body_context,
        storey=storey,
        origin=partition_origin,
        length=depth,
        height=wall_height,
        thickness=wall_t,
        direction_xy=(0.0, 1.0),
        predefined_type="PARTITIONING",
    )

    if include_exterior_envelope:
        # Thickness grows local +Y = world −X for north–south walls (dir 0,1);
        # local +Y = world +Y for east–west walls (dir 1,0).
        # N/S walls span the outer footprint; W/E walls fit between them.
        # This closes each corner with a butt joint instead of overlapping the
        # two wall solids in an ext_t × ext_t square.
        slab_w = rooms_max_x - min_x
        outer_w = slab_w + 2.0 * ext_t
        side_y0 = min_y
        side_len = depth
        add_wall(
            ifc_file,
            name=f"{primary_name}-EnvelopeWest",
            body_context=body_context,
            storey=storey,
            origin=(min_x, side_y0, z_floor_slab_top),
            length=side_len,
            height=wall_height,
            thickness=ext_t,
            direction_xy=(0.0, 1.0),
            predefined_type="SOLIDWALL",
        )
        add_wall(
            ifc_file,
            name=f"{primary_name}-EnvelopeEast",
            body_context=body_context,
            storey=storey,
            origin=(rooms_max_x + ext_t, side_y0, z_floor_slab_top),
            length=side_len,
            height=wall_height,
            thickness=ext_t,
            direction_xy=(0.0, 1.0),
            predefined_type="SOLIDWALL",
        )
        add_wall(
            ifc_file,
            name=f"{primary_name}-EnvelopeSouth",
            body_context=body_context,
            storey=storey,
            origin=(min_x - ext_t, min_y - ext_t, z_floor_slab_top),
            length=outer_w,
            height=wall_height,
            thickness=ext_t,
            direction_xy=(1.0, 0.0),
            predefined_type="SOLIDWALL",
        )
        if not omit_camera_facing_envelope:
            add_wall(
                ifc_file,
                name=f"{primary_name}-EnvelopeNorth",
                body_context=body_context,
                storey=storey,
                origin=(min_x - ext_t, max_y, z_floor_slab_top),
                length=outer_w,
                height=wall_height,
                thickness=ext_t,
                direction_xy=(1.0, 0.0),
                predefined_type="SOLIDWALL",
            )

    if include_partition_openings:
        door_along = depth - DOOR_WIDTH - 0.40
        window_along = 0.40
        door_opening = add_opening_in_wall(
            ifc_file,
            host=partition,
            name=f"{primary_name}-DoorOpening",
            body_context=body_context,
            along=door_along,
            sill=0.0,
            clear_width=DOOR_WIDTH,
            clear_height=DOOR_HEIGHT,
            wall_thickness=wall_t,
            wall_origin=partition_origin,
            direction_xy=(0.0, 1.0),
        )
        window_opening = add_opening_in_wall(
            ifc_file,
            host=partition,
            name=f"{primary_name}-WindowOpening",
            body_context=body_context,
            along=window_along,
            sill=WINDOW_SILL,
            clear_width=WINDOW_WIDTH,
            clear_height=WINDOW_HEIGHT,
            wall_thickness=wall_t,
            wall_origin=partition_origin,
            direction_xy=(0.0, 1.0),
        )
        add_opening_filling(
            ifc_file,
            opening=door_opening,
            name=f"{primary_name}-InteriorDoor",
            body_context=body_context,
            storey=storey,
            along=door_along,
            sill=0.0,
            clear_width=DOOR_WIDTH,
            clear_height=DOOR_HEIGHT,
            wall_thickness=wall_t,
            wall_origin=partition_origin,
            direction_xy=(0.0, 1.0),
            ifc_class="IfcDoor",
            predefined_type="DOOR",
            frame_width=0.10,
            exterior_protrusion=0.0,
        )
        add_opening_filling(
            ifc_file,
            opening=window_opening,
            name=f"{primary_name}-InteriorWindow",
            body_context=body_context,
            storey=storey,
            along=window_along,
            sill=WINDOW_SILL,
            clear_width=WINDOW_WIDTH,
            clear_height=WINDOW_HEIGHT,
            wall_thickness=wall_t,
            wall_origin=partition_origin,
            direction_xy=(0.0, 1.0),
            ifc_class="IfcWindow",
            predefined_type="WINDOW",
            leaf_thickness=0.025,
            frame_width=0.10,
            exterior_protrusion=0.0,
        )

    if not include_neighbor_space:
        return None

    neighbor_area = _shoelace_area(neighbor_poly)
    attrs = neighbor_attrs or {}
    neighbor_quantities = dict(attrs.get("quantities") or {})
    neighbor_quantities.setdefault("GrossFloorArea", neighbor_area)
    neighbor_quantities.setdefault("GrossVolume", neighbor_area * height)
    neighbor_quantities.setdefault("Height", height)
    neighbor_quantities.setdefault("NetFloorArea", round(neighbor_area, 2))
    # No suspended ceiling in neighbour → FinishCeilingHeight equals structural height
    neighbor_quantities.setdefault("FinishCeilingHeight", height)

    return _create_space_entity(
        ifc_file,
        storey=storey,
        body_context=body_context,
        name=str(attrs.get("name") or f"{primary_name}-N"),
        long_name=attrs.get("long_name") or "Flur",
        predefined_type=str(attrs.get("predefined_type") or "INTERNAL"),
        polyline=neighbor_poly,
        height=height,
        quantities=neighbor_quantities,
        properties=attrs.get("properties") or {},
        properties_datatypes=attrs.get("property_datatypes") or {},
    )


def _add_exterior_space_vignette(
    ifc_file: ifcopenshell.file,
    *,
    storey: ifcopenshell.entity_instance,
    body_context: ifcopenshell.entity_instance,
    exterior_polyline: Sequence[Sequence[float]],
    exterior_height: float,
    exterior_name: str,
    interior_width: float,
    interior_depth: float,
    interior_height: float,
    finish_ceiling_height: float | None = None,
    interior_attrs: dict[str, Any] | None = None,
    include_interior_space: bool = True,
    include_cladding: bool = True,
    include_ceiling_covering: bool = True,
    include_ceiling_slab: bool = True,
    include_balcony: bool = True,
    include_upper_balcony: bool | None = None,
    cladding_covers_slab: bool = False,
    include_balcony_floor_covering: bool = False,
) -> ifcopenshell.entity_instance | None:
    """Half interior room + exterior wall/cladding/openings + balcony slab context.

    Exterior space footprint is already created by the caller; this builds the
    fabric around it. Returns the interior context space when included.

    ``include_upper_balcony`` defaults to ``include_balcony`` when omitted.
    ``cladding_covers_slab`` extends cladding by the ceiling-slab thickness so
    the facade covers the exposed slab edge (door / window cards; no upper
    balcony). With no walk-out balcony it also drops to the floor-slab bottom
    so both slab front edges sit behind the cladding (window card).
    """
    if include_upper_balcony is None:
        include_upper_balcony = include_balcony
    wall_t = EXTERIOR_WALL_THICKNESS
    clad_t = CLADDING_THICKNESS
    int_w = float(interior_width)
    int_d = float(interior_depth)
    int_h = float(interior_height)

    ext_min_x, _ext_min_y, ext_max_x, _ext_max_y = bounds_2d(exterior_polyline)
    balcony_depth = ext_max_x - ext_min_x
    interior_poly = rect_polyline(0.0, 0.0, int_w, int_d)
    # Balcony from the wall outer face so cladding rests on the terrace top
    # (not floating past the lip). Depth is measured from the cladding outer face.
    facade_outer = int_w + wall_t + (
        (CLADDING_GAP + clad_t) if include_cladding else 0.0
    )
    balcony_poly = rect_polyline(
        int_w + wall_t,
        0.0,
        facade_outer + balcony_depth,
        int_d,
    )

    z_floor_slab_top = 0.0
    z_floor_slab = z_floor_slab_top - FLOOR_SLAB_THICKNESS
    z_ceiling_slab = int_h
    finish_h = (
        float(finish_ceiling_height)
        if finish_ceiling_height is not None
        else DEFAULT_FINISH_CEILING_HEIGHT
    )
    if finish_h <= 0 or finish_h >= int_h:
        raise ValueError(
            f"finish_ceiling_height ({finish_h}) must be between 0 and interior height ({int_h})"
        )
    # Wall supports the slab soffit. Cladding normally stops at the balcony
    # soffit so it does not seam through the balcony top. When cladding is
    # omitted, the wall covers the top-slab edge. Door/window cards (no upper
    # balcony) raise cladding via cladding_covers_slab; window (no balcony)
    # also drops cladding over the floor-slab edge.
    wall_height = z_ceiling_slab - z_floor_slab_top
    _slab_cover = CEILING_SLAB_THICKNESS if include_ceiling_slab else 0.0
    _cover_slabs = cladding_covers_slab and include_cladding
    _floor_cover = (
        FLOOR_SLAB_THICKNESS if _cover_slabs and not include_balcony else 0.0
    )
    cladding_height = wall_height + (
        (_slab_cover if _cover_slabs else 0.0) + _floor_cover
    )
    facade_height = (
        wall_height + _slab_cover
        if (not include_cladding and include_ceiling_slab)
        else wall_height
    )

    # Floor slab stops at the wall outer face; cladding sits proud outside
    structural_slab = rect_polyline(0.0, 0.0, int_w + wall_t, int_d)
    add_slab(
        ifc_file,
        name=f"{exterior_name}-FloorSlab",
        body_context=body_context,
        storey=storey,
        polyline=structural_slab,
        thickness=FLOOR_SLAB_THICKNESS,
        z_bottom=z_floor_slab,
        predefined_type="FLOOR",
    )
    if include_ceiling_covering:
        add_covering(
            ifc_file,
            name=f"{exterior_name}-CeilingCovering",
            body_context=body_context,
            storey=storey,
            polyline=interior_poly,
            thickness=CEILING_COVERING_THICKNESS,
            z_bottom=finish_h,
            predefined_type="CEILING",
        )
    # Ceiling over the interior; matching balcony plate outside the cladding so
    # cladding stops cleanly at the balcony soffit / top junction.
    if include_ceiling_slab:
        add_slab(
            ifc_file,
            name=f"{exterior_name}-CeilingSlab",
            body_context=body_context,
            storey=storey,
            polyline=structural_slab,
            thickness=CEILING_SLAB_THICKNESS,
            z_bottom=z_ceiling_slab,
            predefined_type="FLOOR",
        )
        if include_upper_balcony:
            # From wall outer past cladding — continuous white top; cladding
            # stops at the soffit (no orange seam on the balcony top).
            upper_balcony_poly = rect_polyline(
                int_w + wall_t,
                0.0,
                facade_outer + balcony_depth,
                int_d,
            )
            add_slab(
                ifc_file,
                name=f"{exterior_name}-BalconySlabUpper",
                body_context=body_context,
                storey=storey,
                polyline=upper_balcony_poly,
                thickness=CEILING_SLAB_THICKNESS,
                z_bottom=z_ceiling_slab,
                predefined_type="FLOOR",
            )

    if include_balcony:
        # Balcony slab flush with finished floor level
        add_slab(
            ifc_file,
            name=f"{exterior_name}-BalconySlab",
            body_context=body_context,
            storey=storey,
            polyline=balcony_poly,
            thickness=FLOOR_SLAB_THICKNESS,
            z_bottom=z_floor_slab,
            predefined_type="FLOOR",
        )
        if include_balcony_floor_covering:
            add_covering(
                ifc_file,
                name=f"{exterior_name}-FloorCovering",
                body_context=body_context,
                storey=storey,
                polyline=balcony_poly,
                thickness=FLOOR_COVERING_THICKNESS,
                z_bottom=z_floor_slab_top,
                predefined_type="FLOORING",
            )

    wall_origin_z = (int_w + wall_t, 0.0, z_floor_slab_top)
    # Door near +Y end, window near -Y end along the facade
    door_along = int_d - DOOR_WIDTH - 0.40
    window_along = 0.40
    # Continuous wall/cladding Body — openings via IfcOpeningElement (PNG preview
    # subtracts them so flush frames sit in real holes without fragment seams).
    exterior_wall = add_wall(
        ifc_file,
        name=f"{exterior_name}-ExteriorWall",
        body_context=body_context,
        storey=storey,
        origin=wall_origin_z,
        length=int_d,
        height=facade_height,
        thickness=wall_t,
        direction_xy=(0.0, 1.0),
        predefined_type="SOLIDWALL",
    )
    cladding = None
    if include_cladding:
        # Cladding outside the wall with a small gap so faces do not z-fight
        # (coplanar wall exterior / cladding interior created seam lines above openings).
        # Default: stops at the balcony soffit. Door/window: cladding_covers_slab
        # raises it by the ceiling-slab thickness; window (no balcony) also
        # starts at the floor-slab bottom so both edges sit behind the facade.
        clad_origin = (
            int_w + wall_t + CLADDING_GAP + clad_t,
            0.0,
            z_floor_slab_top - _floor_cover,
        )
        cladding = add_vertical_covering(
            ifc_file,
            name=f"{exterior_name}-Cladding",
            body_context=body_context,
            storey=storey,
            origin=clad_origin,
            length=int_d,
            height=cladding_height,
            thickness=clad_t,
            direction_xy=(0.0, 1.0),
            predefined_type="CLADDING",
        )

    door_opening = add_opening_in_wall(
        ifc_file,
        host=exterior_wall,
        name=f"{exterior_name}-DoorOpening",
        body_context=body_context,
        along=door_along,
        sill=0.0,
        clear_width=DOOR_WIDTH,
        clear_height=DOOR_HEIGHT,
        wall_thickness=wall_t,
        wall_origin=wall_origin_z,
        direction_xy=(0.0, 1.0),
    )
    window_opening = add_opening_in_wall(
        ifc_file,
        host=exterior_wall,
        name=f"{exterior_name}-WindowOpening",
        body_context=body_context,
        along=window_along,
        sill=WINDOW_SILL,
        clear_width=WINDOW_WIDTH,
        clear_height=WINDOW_HEIGHT,
        wall_thickness=wall_t,
        wall_origin=wall_origin_z,
        direction_xy=(0.0, 1.0),
    )
    # Same openings in cladding — voids go through the facade layers.
    # Sills are relative to clad_origin; shift when cladding starts below floor.
    if cladding is not None:
        add_opening_in_wall(
            ifc_file,
            host=cladding,
            name=f"{exterior_name}-DoorOpening-Cladding",
            body_context=body_context,
            along=door_along,
            sill=_floor_cover,
            clear_width=DOOR_WIDTH,
            clear_height=DOOR_HEIGHT,
            wall_thickness=clad_t,
            wall_origin=clad_origin,
            direction_xy=(0.0, 1.0),
        )
        add_opening_in_wall(
            ifc_file,
            host=cladding,
            name=f"{exterior_name}-WindowOpening-Cladding",
            body_context=body_context,
            along=window_along,
            sill=WINDOW_SILL + _floor_cover,
            clear_width=WINDOW_WIDTH,
            clear_height=WINDOW_HEIGHT,
            wall_thickness=clad_t,
            wall_origin=clad_origin,
            direction_xy=(0.0, 1.0),
        )
    add_opening_filling(
        ifc_file,
        opening=door_opening,
        name=f"{exterior_name}-Door",
        body_context=body_context,
        storey=storey,
        along=door_along,
        sill=0.0,
        clear_width=DOOR_WIDTH,
        clear_height=DOOR_HEIGHT,
        wall_thickness=wall_t,
        wall_origin=wall_origin_z,
        direction_xy=(0.0, 1.0),
        ifc_class="IfcDoor",
        predefined_type="DOOR",
        frame_width=0.10,
        exterior_protrusion=0.0,
    )
    add_opening_filling(
        ifc_file,
        opening=window_opening,
        name=f"{exterior_name}-Window",
        body_context=body_context,
        storey=storey,
        along=window_along,
        sill=WINDOW_SILL,
        clear_width=WINDOW_WIDTH,
        clear_height=WINDOW_HEIGHT,
        wall_thickness=wall_t,
        wall_origin=wall_origin_z,
        direction_xy=(0.0, 1.0),
        ifc_class="IfcWindow",
        predefined_type="WINDOW",
        leaf_thickness=0.025,
        frame_width=0.10,
        exterior_protrusion=0.0,
    )

    if not include_interior_space:
        return None

    # Interior context space
    attrs = interior_attrs or {}
    interior_area = _shoelace_area(interior_poly)
    interior_quantities = dict(attrs.get("quantities") or {})
    interior_quantities.setdefault("GrossFloorArea", interior_area)
    interior_quantities.setdefault("GrossVolume", interior_area * int_h)
    interior_quantities.setdefault("Height", int_h)
    interior_quantities.setdefault("NetFloorArea", round(interior_area, 2))
    interior_quantities.setdefault("FinishCeilingHeight", finish_h)

    return _create_space_entity(
        ifc_file,
        storey=storey,
        body_context=body_context,
        name=str(attrs.get("name") or f"{exterior_name}-INT"),
        long_name=attrs.get("long_name") or "Buero",
        predefined_type=str(attrs.get("predefined_type") or "INTERNAL"),
        polyline=interior_poly,
        height=int_h,
        quantities=interior_quantities,
        properties=attrs.get("properties") or {},
        properties_datatypes=attrs.get("property_datatypes") or {},
    )


def generate_space(
    params: dict[str, Any],
) -> tuple[ifcopenshell.file, ifcopenshell.entity_instance]:
    """Create an IfcSpace with extruded Body geometry and quantities.

    Required params:
      - height (float, m)
      - boundary (list of [x, y]) OR width + depth (float, m)

    Optional params:
      - name / Name, long_name / LongName, predefined_type / PredefinedType
      - ifc_file, storey, body_context (reuse an existing project shell)
      - properties: {pset_name: {prop: value}}
      - net_floor_area / NetFloorArea (added to Qto if provided)
      - with_context (bool, default True): add slab/covering/wall + neighbour space
      - vignette: ``interior`` (default) or ``exterior``

    Returns ``(ifc_file, primary_space_entity)``.
    """
    height = params.get("height")
    if height is None:
        raise ValueError("height is required")
    height = float(height)
    if height <= 0:
        raise ValueError("height must be positive")

    polyline = _boundary_from_params(params)
    gross_floor_area = _shoelace_area(polyline)
    gross_volume = gross_floor_area * height

    ifc_file = params.get("ifc_file")
    storey = params.get("storey")
    body_context = params.get("body_context")

    if ifc_file is None or storey is None:
        shell_name = params.get("project_name") or params.get("name") or params.get("Name") or "Space"
        ifc_file, _project, _site, _building, storey, body_context = create_project_shell(
            name=f"Catalog — {shell_name}"
        )
    elif body_context is None:
        body_context = get_body_context(ifc_file)

    name = params.get("name") or params.get("Name") or "Space"
    long_name = params.get("long_name") or params.get("LongName")
    predefined_type = (
        params.get("predefined_type") or params.get("PredefinedType") or "INTERNAL"
    )
    vignette = str(params.get("vignette") or (
        "exterior" if str(predefined_type).upper() == "EXTERNAL" else "interior"
    )).lower()

    # Prefer YAML-mapped quantities from catalog/mapping; fall back to geometry
    quantities: dict[str, Any] = dict(
        (params.get("quantities") or {}).get("Qto_SpaceBaseQuantities") or {}
    )
    quantities.setdefault("GrossFloorArea", gross_floor_area)
    quantities.setdefault("GrossVolume", gross_volume)
    quantities.setdefault("Height", height)
    net_floor_area = params.get("net_floor_area", params.get("NetFloorArea"))
    if net_floor_area is not None:
        quantities["NetFloorArea"] = float(net_floor_area)
    finish_ceiling = params.get("FinishCeilingHeight")
    if finish_ceiling is not None:
        quantities["FinishCeilingHeight"] = float(finish_ceiling)

    # Extra Qto_* bundles from mapping (if any beyond SpaceBase)
    extra_qtos = {
        qto_name: props
        for qto_name, props in (params.get("quantities") or {}).items()
        if qto_name != "Qto_SpaceBaseQuantities"
    }

    # Exterior vignette places the balcony footprint outside cladding; remap polyline
    if vignette == "exterior" and params.get("with_context", True):
        int_w = float(params.get("interior_width", 2.0))
        int_d = float(params.get("interior_depth", params.get("depth", 5.0)))
        balcony_depth = float(params.get("width") or DEFAULT_BALCONY_DEPTH)
        if params.get("boundary"):
            # Keep explicit boundary as given
            pass
        else:
            polyline = rect_polyline(
                int_w + EXTERIOR_WALL_THICKNESS + CLADDING_GAP + CLADDING_THICKNESS,
                0.0,
                int_w
                + EXTERIOR_WALL_THICKNESS
                + CLADDING_GAP
                + CLADDING_THICKNESS
                + balcony_depth,
                int_d,
            )
            gross_floor_area = _shoelace_area(polyline)
            gross_volume = gross_floor_area * height
            quantities["GrossFloorArea"] = gross_floor_area
            quantities["GrossVolume"] = gross_volume
            quantities.setdefault("NetFloorArea", round(gross_floor_area, 2))

    omit_primary_space = bool(params.get("omit_primary_space", False))
    space: ifcopenshell.entity_instance | None = None
    if not omit_primary_space:
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
            properties=params.get("properties") or {},
            properties_datatypes=params.get("property_datatypes") or {},
            object_type=params.get("object_type") or params.get("ObjectType"),
        )
        for qto_name, props in extra_qtos.items():
            assign_qto(ifc_file, space, qto_name, props)
        if vignette == "exterior":
            # Sit just above the balcony slab so faces do not z-fight in the PNG
            storey_z = float(getattr(storey, "Elevation", None) or 0.0)
            edit_object_placement(
                ifc_file,
                product=space,
                matrix=translation_matrix(z=storey_z + 0.002),
            )

    with_context = params.get("with_context", True)
    if with_context and vignette == "exterior":
        finish_ceiling = quantities.get("FinishCeilingHeight")
        if finish_ceiling is None:
            finish_ceiling = params.get(
                "finish_ceiling_height", DEFAULT_FINISH_CEILING_HEIGHT
            )
        include_interior_space = params.get("include_interior_space")
        if include_interior_space is None:
            include_interior_space = not omit_primary_space
        _add_exterior_space_vignette(
            ifc_file,
            storey=storey,
            body_context=body_context,
            exterior_polyline=polyline,
            exterior_height=height,
            exterior_name=str(name),
            interior_width=float(params.get("interior_width", 2.0)),
            interior_depth=float(params.get("interior_depth", params.get("depth", 5.0))),
            interior_height=float(params.get("interior_height", DEFAULT_INTERIOR_HEIGHT)),
            finish_ceiling_height=float(finish_ceiling),
            interior_attrs=params.get("interior_attrs"),
            include_interior_space=bool(include_interior_space),
            include_cladding=bool(params.get("include_cladding", True)),
            include_ceiling_covering=bool(
                params.get("include_ceiling_covering", True)
            ),
            include_ceiling_slab=bool(params.get("include_ceiling_slab", True)),
            include_balcony=bool(params.get("include_balcony", True)),
            include_upper_balcony=(
                bool(params["include_upper_balcony"])
                if "include_upper_balcony" in params
                else None
            ),
            cladding_covers_slab=bool(params.get("cladding_covers_slab", False)),
            include_balcony_floor_covering=bool(
                params.get("include_balcony_floor_covering", False)
            ),
        )
    elif with_context:
        finish_ceiling = quantities.get("FinishCeilingHeight")
        if finish_ceiling is None:
            finish_ceiling = params.get("finish_ceiling_height", DEFAULT_FINISH_CEILING_HEIGHT)
        _add_space_vignette(
            ifc_file,
            storey=storey,
            body_context=body_context,
            primary_polyline=polyline,
            height=height,
            primary_name=str(name),
            finish_ceiling_height=float(finish_ceiling) if finish_ceiling is not None else None,
            neighbor_attrs=params.get("neighbor_attrs"),
            include_ceiling_covering=bool(params.get("include_ceiling_covering", True)),
            include_ceiling_slab=bool(params.get("include_ceiling_slab", True)),
            include_neighbor_space=bool(params.get("include_neighbor_space", True)),
            include_floor_slab=bool(params.get("include_floor_slab", True)),
            include_floor_covering=bool(params.get("include_floor_covering", True)),
            include_exterior_envelope=bool(params.get("include_exterior_envelope", False)),
            include_partition_openings=bool(params.get("include_partition_openings", False)),
            omit_camera_facing_envelope=bool(
                params.get("omit_camera_facing_envelope", False)
            ),
            neighbor_space_width=float(
                params.get("neighbor_space_width", NEIGHBOR_SPACE_WIDTH)
            ),
        )

    if space is None:
        # Callers that omit the primary space (e.g. opening vignette) still need a
        # product handle — prefer the partition wall when present.
        walls = ifc_file.by_type("IfcWall")
        for wall in walls:
            if (wall.Name or "").endswith("-Partition") or getattr(
                wall, "PredefinedType", None
            ) == "PARTITIONING":
                return ifc_file, wall
        if walls:
            return ifc_file, walls[-1]
        raise ValueError("omit_primary_space requires with_context fabric")

    return ifc_file, space
