"""Two-storey stair vignette with an enclosed room below the upper flight."""

from __future__ import annotations

from typing import Any, Sequence

import ifcopenshell
from ifcopenshell.api.aggregate import assign_object
from ifcopenshell.api.geometry import assign_representation, edit_object_placement
from ifcopenshell.api.root import create_entity
from ifcopenshell.api.spatial import assign_container

from generators.base import (
    assign_pset,
    assign_qto,
    create_multi_storey_shell,
    get_body_context,
)
from generators.parts import (
    create_body_representation,
    create_extruded_area_solid,
    create_faceted_brep,
    rect_polyline,
    translation_matrix,
)
from generators.wall import add_opening_in_wall


DEFAULT_STOREY_HEIGHT = 3.0
DEFAULT_FLIGHT_WIDTH = 1.1
DEFAULT_FLIGHT_RUN = 3.0
DEFAULT_LANDING_DEPTH = 1.0
DEFAULT_STEP_COUNT = 9
DEFAULT_TREAD_THICKNESS = 0.14
DEFAULT_WAIST_THICKNESS = 0.18
DEFAULT_WALL_THICKNESS = 0.16


def _add_product(
    ifc_file: ifcopenshell.file,
    *,
    ifc_class: str,
    name: str,
    body_context: ifcopenshell.entity_instance,
    storey: ifcopenshell.entity_instance,
    solids: Sequence[ifcopenshell.entity_instance],
    predefined_type: str | None = None,
) -> ifcopenshell.entity_instance:
    product = create_entity(
        ifc_file,
        ifc_class=ifc_class,
        name=name,
        predefined_type=predefined_type,
    )
    if product.is_a("IfcSpace"):
        assign_object(ifc_file, relating_object=storey, products=[product])
    else:
        assign_container(ifc_file, relating_structure=storey, products=[product])
    edit_object_placement(ifc_file, product=product, matrix=translation_matrix())
    items = list(solids)
    representation = (
        ifc_file.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=body_context,
            RepresentationIdentifier="Body",
            RepresentationType="SurfaceOrSolidModel",
            Items=items,
        )
        if any(item.is_a("IfcFacetedBrep") for item in items)
        else create_body_representation(ifc_file, body_context, items)
    )
    assign_representation(ifc_file, product=product, representation=representation)
    return product


def _extruded_yz_profile(
    ifc_file: ifcopenshell.file,
    *,
    x0: float,
    x1: float,
    profile: Sequence[tuple[float, float]],
) -> ifcopenshell.entity_instance:
    """Extrude a closed YZ profile across X as one faceted solid."""
    count = len(profile)
    if count < 3:
        raise ValueError("flight profile needs at least three points")
    vertices = [
        *((x0, float(y), float(z)) for y, z in profile),
        *((x1, float(y), float(z)) for y, z in profile),
    ]
    # CCW from outside so normals point outward. Inverted winding lights the
    # stair brown instead of the catalog orange used on the landing slab.
    faces: list[tuple[int, ...]] = [
        tuple(range(count)),
        tuple(reversed(range(count, 2 * count))),
    ]
    for index in range(count):
        next_index = (index + 1) % count
        faces.append(
            (
                index,
                count + index,
                count + next_index,
                next_index,
            )
        )
    return create_faceted_brep(ifc_file, vertices, faces)


def _extruded_xz_profile(
    ifc_file: ifcopenshell.file,
    *,
    y0: float,
    y1: float,
    profile: Sequence[tuple[float, float]],
) -> ifcopenshell.entity_instance:
    """Extrude a closed XZ profile across Y as one faceted solid."""
    count = len(profile)
    if count < 3:
        raise ValueError("wall profile needs at least three points")
    vertices = [
        *((float(x), y0, float(z)) for x, z in profile),
        *((float(x), y1, float(z)) for x, z in profile),
    ]
    faces: list[tuple[int, ...]] = [
        tuple(range(count)),
        tuple(reversed(range(count, 2 * count))),
    ]
    for index in range(count):
        next_index = (index + 1) % count
        faces.append(
            (
                index,
                count + index,
                count + next_index,
                next_index,
            )
        )
    return create_faceted_brep(ifc_file, vertices, faces)


def _concrete_flight_solid(
    ifc_file: ifcopenshell.file,
    *,
    x0: float,
    x1: float,
    run: float,
    step_count: int,
    top_levels: Sequence[float],
    tread_thickness: float,
    waist_thickness: float,
    underside_end_levels: tuple[float, float],
) -> ifcopenshell.entity_instance:
    """Create steps and sloping concrete waist as one monolithic solid."""
    if len(top_levels) != step_count:
        raise ValueError("top_levels must contain one value per step")
    tread_depth = run / step_count
    profile: list[tuple[float, float]] = [(0.0, float(top_levels[0]))]
    for index, level in enumerate(top_levels):
        y1 = (index + 1) * tread_depth
        profile.append((y1, float(level)))
        if index + 1 < step_count:
            profile.append((y1, float(top_levels[index + 1])))
    profile.extend(
        [
            (
                run,
                float(underside_end_levels[1])
                - tread_thickness
                - waist_thickness,
            ),
            (
                0.0,
                float(underside_end_levels[0])
                - tread_thickness
                - waist_thickness,
            ),
        ]
    )
    return _extruded_yz_profile(ifc_file, x0=x0, x1=x1, profile=profile)


def _apply_resolved_attributes(
    ifc_file: ifcopenshell.file,
    product: ifcopenshell.entity_instance,
    resolved: dict[str, Any] | None,
) -> None:
    if not resolved:
        return
    for field in ("Name", "LongName", "Description", "PredefinedType", "ObjectType"):
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


def generate_stair(
    params: dict[str, Any] | None = None,
) -> tuple[
    ifcopenshell.file,
    list[ifcopenshell.entity_instance],
    list[ifcopenshell.entity_instance],
    list[ifcopenshell.entity_instance],
]:
    """Build lower flight, landing, dashed upper flight, wall, door, and room.

    The lower flight belongs to EG. The landing and upper flight belong to 1.OG,
    matching the storey assignment demonstrated by the catalog image.
    """
    params = dict(params or {})
    storey_h = float(params.get("storey_height", DEFAULT_STOREY_HEIGHT))
    flight_w = float(params.get("flight_width", DEFAULT_FLIGHT_WIDTH))
    flight_run = float(params.get("flight_run", DEFAULT_FLIGHT_RUN))
    landing_d = float(params.get("landing_depth", DEFAULT_LANDING_DEPTH))
    step_count = int(params.get("step_count", DEFAULT_STEP_COUNT))
    tread_t = float(params.get("tread_thickness", DEFAULT_TREAD_THICKNESS))
    waist_t = float(params.get("waist_thickness", DEFAULT_WAIST_THICKNESS))
    wall_t = float(params.get("wall_thickness", DEFAULT_WALL_THICKNESS))
    if min(storey_h, flight_w, flight_run, landing_d, tread_t, waist_t, wall_t) <= 0:
        raise ValueError("all stair vignette dimensions must be positive")
    if step_count < 3:
        raise ValueError("step_count must be at least 3")

    ifc_file, _project, _site, _building, storeys, body_context = (
        create_multi_storey_shell(
            params.get("project_name") or "Treppe",
            storey_names=("EG", "1.OG", "2.OG"),
            storey_elevations=(0.0, storey_h, 2.0 * storey_h),
        )
    )
    lower_storey, upper_storey, second_upper_storey = storeys
    body_context = get_body_context(ifc_file) or body_context

    gap = 0.18
    upper_x0 = flight_w + gap
    upper_x1 = upper_x0 + flight_w
    wall_y = 0.45
    landing_y0 = flight_run
    landing_y1 = flight_run + landing_d
    half_h = storey_h * 0.5
    rise = half_h / step_count

    # Each flight is one monolithic concrete solid: steps and waist are merged.
    lower_levels = [(index + 1) * rise for index in range(step_count)]
    upper_levels = [storey_h - index * rise for index in range(step_count)]
    lower_solids = [
        _concrete_flight_solid(
            ifc_file,
            x0=0.0,
            x1=flight_w,
            run=flight_run,
            step_count=step_count,
            top_levels=lower_levels,
            tread_thickness=tread_t,
            waist_thickness=waist_t,
            underside_end_levels=(rise, half_h),
        )
    ]
    upper_solids = [
        _concrete_flight_solid(
            ifc_file,
            x0=upper_x0,
            x1=upper_x1,
            run=flight_run,
            step_count=step_count,
            top_levels=upper_levels,
            tread_thickness=tread_t,
            waist_thickness=waist_t,
            underside_end_levels=(storey_h, half_h + rise),
        )
    ]
    copied_lower_solids = [
        _concrete_flight_solid(
            ifc_file,
            x0=0.0,
            x1=flight_w,
            run=flight_run,
            step_count=step_count,
            top_levels=[level + storey_h for level in lower_levels],
            tread_thickness=tread_t,
            waist_thickness=waist_t,
            underside_end_levels=(rise + storey_h, half_h + storey_h),
        )
    ]
    copied_upper_solids = [
        _concrete_flight_solid(
            ifc_file,
            x0=upper_x0,
            x1=upper_x1,
            run=flight_run,
            step_count=step_count,
            top_levels=[level + storey_h for level in upper_levels],
            tread_thickness=tread_t,
            waist_thickness=waist_t,
            underside_end_levels=(
                2.0 * storey_h,
                half_h + rise + storey_h,
            ),
        )
    ]

    lower_flight = _add_product(
        ifc_file,
        ifc_class="IfcStair",
        name="Unterer Treppenlauf",
        body_context=body_context,
        storey=lower_storey,
        solids=lower_solids,
        predefined_type="HALF_TURN_STAIR",
    )
    landing = _add_product(
        ifc_file,
        ifc_class="IfcSlab",
        name="Zwischenpodest (1.OG)",
        body_context=body_context,
        storey=upper_storey,
        solids=[
            create_extruded_area_solid(
                ifc_file,
                rect_polyline(0.0, landing_y0, upper_x1, landing_y1),
                tread_t,
                origin=(0.0, 0.0, half_h - tread_t),
            )
        ],
        predefined_type="LANDING",
    )
    upper_flight = _add_product(
        ifc_file,
        ifc_class="IfcStair",
        name="Oberer Treppenlauf (1.OG)",
        body_context=body_context,
        storey=upper_storey,
        solids=upper_solids,
        predefined_type="HALF_TURN_STAIR",
    )
    copied_lower_flight = _add_product(
        ifc_file,
        ifc_class="IfcStair",
        name="Unterer Treppenlauf 1.OG–2.OG",
        body_context=body_context,
        storey=upper_storey,
        solids=copied_lower_solids,
        predefined_type="HALF_TURN_STAIR",
    )
    copied_landing = _add_product(
        ifc_file,
        ifc_class="IfcSlab",
        name="Zwischenpodest (2.OG)",
        body_context=body_context,
        storey=second_upper_storey,
        solids=[
            create_extruded_area_solid(
                ifc_file,
                rect_polyline(0.0, landing_y0, upper_x1, landing_y1),
                tread_t,
                origin=(0.0, 0.0, half_h + storey_h - tread_t),
            )
        ],
        predefined_type="LANDING",
    )
    copied_upper_flight = _add_product(
        ifc_file,
        ifc_class="IfcStair",
        name="Oberer Treppenlauf (2.OG)",
        body_context=body_context,
        storey=second_upper_storey,
        solids=copied_upper_solids,
        predefined_type="HALF_TURN_STAIR",
    )

    # One connected L-shaped solid extends below the upper flight and the landing.
    room_height = half_h - tread_t
    room_y0 = wall_y + wall_t
    room_polyline = [
        (upper_x0, room_y0),
        (upper_x1, room_y0),
        (upper_x1, landing_y1),
        (0.0, landing_y1),
        (0.0, landing_y0),
        (upper_x0, landing_y0),
    ]
    lower_room = _add_product(
        ifc_file,
        ifc_class="IfcSpace",
        name="Raum unter oberem Treppenlauf und Podest",
        body_context=body_context,
        storey=lower_storey,
        solids=[
            create_extruded_area_solid(
                ifc_file,
                room_polyline,
                room_height,
            )
        ],
        predefined_type="INTERNAL",
    )

    # One horizontal space spans the complete stair footprint from landing to landing.
    upper_space = _add_product(
        ifc_file,
        ifc_class="IfcSpace",
        name="Treppenraum 1.OG – Podest bis Podest",
        body_context=body_context,
        storey=upper_storey,
        solids=[
            create_extruded_area_solid(
                ifc_file,
                rect_polyline(0.0, 0.0, upper_x1, landing_y1),
                storey_h - tread_t,
                origin=(0.0, 0.0, half_h),
            )
        ],
        predefined_type="INTERNAL",
    )

    # Cross-wall below the high end of the upper flight. It is perpendicular to
    # the stair direction and keeps an unfilled wall opening.
    wall_length = flight_w
    wall_origin = (upper_x0, wall_y, 0.0)
    door_width = min(0.75, wall_length - 0.25)
    door_height = 2.05
    door_along = (wall_length - door_width) * 0.5
    door_x0 = upper_x0 + door_along
    door_x1 = door_x0 + door_width
    wall_height = (
        storey_h
        - tread_t
        - waist_t
        + (half_h - storey_h) * ((wall_y + wall_t) / flight_run)
    )
    wall_solids = [
        _extruded_xz_profile(
            ifc_file,
            y0=wall_y,
            y1=wall_y + wall_t,
            profile=[
                (upper_x0, 0.0),
                (door_x0, 0.0),
                (door_x0, door_height),
                (door_x1, door_height),
                (door_x1, 0.0),
                (upper_x1, 0.0),
                (upper_x1, wall_height),
                (upper_x0, wall_height),
            ],
        ),
    ]
    wall = _add_product(
        ifc_file,
        ifc_class="IfcWall",
        name="Wand unter oberem Treppenlauf",
        body_context=body_context,
        storey=lower_storey,
        solids=wall_solids,
        predefined_type="PARTITIONING",
    )
    add_opening_in_wall(
        ifc_file,
        host=wall,
        name="Türöffnung unter Treppe",
        body_context=body_context,
        along=door_along,
        sill=0.0,
        clear_width=door_width,
        clear_height=door_height,
        wall_thickness=wall_t,
        wall_origin=wall_origin,
        direction_xy=(1.0, 0.0),
    )

    resolved = dict(params.get("resolved_attributes") or {})
    _apply_resolved_attributes(ifc_file, lower_flight, resolved)
    return (
        ifc_file,
        [lower_flight, landing, upper_flight],
        [
            copied_lower_flight,
            copied_landing,
            copied_upper_flight,
        ],
        [lower_room, upper_space],
    )
