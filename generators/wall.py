"""IfcWall helpers for vignette / catalog context geometry."""

from __future__ import annotations

from typing import Sequence, TypedDict

import ifcopenshell
from ifcopenshell.api.feature import add_feature, add_filling
from ifcopenshell.api.geometry import assign_representation, edit_object_placement
from ifcopenshell.api.root import create_entity
from ifcopenshell.api.spatial import assign_container

from generators.parts import (
    axis_placement_matrix,
    create_body_representation,
    create_extruded_area_solid,
)


class WallOpeningSpec(TypedDict):
    along: float
    sill: float
    width: float
    height: float


def _subtract_rects(
    rects: list[tuple[float, float, float, float]],
    cut: tuple[float, float, float, float],
) -> list[tuple[float, float, float, float]]:
    """Subtract axis-aligned ``cut`` (x0,z0,x1,z1) from ``rects`` in the XZ plane."""
    cx0, cz0, cx1, cz1 = cut
    result: list[tuple[float, float, float, float]] = []
    for x0, z0, x1, z1 in rects:
        if cx1 <= x0 or cx0 >= x1 or cz1 <= z0 or cz0 >= z1:
            result.append((x0, z0, x1, z1))
            continue
        if z1 > cz1:
            result.append((x0, cz1, x1, z1))
        if z0 < cz0:
            result.append((x0, z0, x1, cz0))
        z_lo, z_hi = max(z0, cz0), min(z1, cz1)
        if z_lo < z_hi:
            if x0 < cx0:
                result.append((x0, z_lo, cx0, z_hi))
            if x1 > cx1:
                result.append((cx1, z_lo, x1, z_hi))
    return [(a, b, c, d) for a, b, c, d in result if c > a + 1e-9 and d > b + 1e-9]


def vertical_body_solids_with_openings(
    ifc_file: ifcopenshell.file,
    *,
    length: float,
    height: float,
    thickness: float,
    openings: Sequence[WallOpeningSpec] | None = None,
) -> list[ifcopenshell.entity_instance]:
    """Extruded wall/cladding solids in local frame, with rectangular openings cut out.

    Local: +X along length, +Y thickness, +Z height. Openings are cut in the XZ
    elevation so tessellation shows real holes without relying on IfcBooleanResult.
    """
    rects: list[tuple[float, float, float, float]] = [
        (0.0, 0.0, float(length), float(height))
    ]
    for opening in openings or ():
        x0 = float(opening["along"])
        z0 = float(opening["sill"])
        rects = _subtract_rects(
            rects,
            (x0, z0, x0 + float(opening["width"]), z0 + float(opening["height"])),
        )

    solids: list[ifcopenshell.entity_instance] = []
    t = float(thickness)
    for x0, z0, x1, z1 in rects:
        profile = [(x0, 0.0), (x1, 0.0), (x1, t), (x0, t)]
        solids.append(
            create_extruded_area_solid(
                ifc_file, profile, z1 - z0, origin=(0.0, 0.0, z0)
            )
        )
    return solids


def add_wall(
    ifc_file: ifcopenshell.file,
    *,
    name: str,
    body_context: ifcopenshell.entity_instance,
    storey: ifcopenshell.entity_instance,
    origin: Sequence[float],
    length: float,
    height: float,
    thickness: float = 0.2,
    direction_xy: Sequence[float] = (1.0, 0.0),
    predefined_type: str = "PARTITIONING",
    openings: Sequence[WallOpeningSpec] | None = None,
) -> ifcopenshell.entity_instance:
    """Add a straight wall. ``direction_xy`` is the wall centre-line in plan.

    Local profile: length along +X, thickness along +Y, extruded +Z by ``height``.
    Optional ``openings`` punch rectangular holes in the Body geometry.
    """
    wall = create_entity(
        ifc_file,
        ifc_class="IfcWall",
        name=name,
        predefined_type=predefined_type,
    )
    assign_container(ifc_file, relating_structure=storey, products=[wall])

    dx, dy = float(direction_xy[0]), float(direction_xy[1])
    edit_object_placement(
        ifc_file,
        product=wall,
        matrix=axis_placement_matrix(
            (
                float(origin[0]),
                float(origin[1]),
                float(origin[2]) if len(origin) > 2 else 0.0,
            ),
            local_x=(dx, dy, 0.0),
            local_z=(0.0, 0.0, 1.0),
        ),
    )
    solids = vertical_body_solids_with_openings(
        ifc_file,
        length=length,
        height=height,
        thickness=thickness,
        openings=openings,
    )
    representation = create_body_representation(ifc_file, body_context, solids)
    assign_representation(ifc_file, product=wall, representation=representation)
    return wall


def add_opening_in_wall(
    ifc_file: ifcopenshell.file,
    *,
    host: ifcopenshell.entity_instance,
    name: str,
    body_context: ifcopenshell.entity_instance,
    along: float,
    sill: float,
    clear_width: float,
    clear_height: float,
    wall_thickness: float,
    wall_origin: Sequence[float],
    direction_xy: Sequence[float] = (1.0, 0.0),
    predefined_type: str = "OPENING",
) -> ifcopenshell.entity_instance:
    """Create an IfcOpeningElement and relate it to ``host`` (void through host).

    The host keeps a continuous Body; the opening is an IfcOpeningElement linked
    with IfcRelVoidsElement. Preview rendering subtracts opening meshes from the
    host so the PNG shows a through-opening without fragmenting the wall solid.
    """
    opening = create_entity(
        ifc_file,
        ifc_class="IfcOpeningElement",
        name=name,
        predefined_type=predefined_type,
    )
    dx, dy = float(direction_xy[0]), float(direction_xy[1])
    edit_object_placement(
        ifc_file,
        product=opening,
        matrix=axis_placement_matrix(
            (
                float(wall_origin[0]),
                float(wall_origin[1]),
                float(wall_origin[2]) if len(wall_origin) > 2 else 0.0,
            ),
            local_x=(dx, dy, 0.0),
            local_z=(0.0, 0.0, 1.0),
        ),
    )
    t = float(wall_thickness) + 0.02
    profile = [
        (float(along), -0.01),
        (float(along) + float(clear_width), -0.01),
        (float(along) + float(clear_width), t),
        (float(along), t),
    ]
    solid = create_extruded_area_solid(
        ifc_file,
        profile,
        float(clear_height),
        origin=(0.0, 0.0, float(sill)),
    )
    representation = create_body_representation(ifc_file, body_context, solid)
    assign_representation(ifc_file, product=opening, representation=representation)
    add_feature(ifc_file, feature=opening, element=host)
    return opening


def _box_solid(
    ifc_file: ifcopenshell.file,
    *,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    z0: float,
    z1: float,
) -> ifcopenshell.entity_instance:
    """Axis-aligned box as IfcExtrudedAreaSolid in the wall local frame."""
    depth = float(z1) - float(z0)
    if depth <= 0 or float(x1) <= float(x0) or float(y1) <= float(y0):
        raise ValueError("box extents must be positive")
    profile = [
        (float(x0), float(y0)),
        (float(x1), float(y0)),
        (float(x1), float(y1)),
        (float(x0), float(y1)),
    ]
    return create_extruded_area_solid(
        ifc_file, profile, depth, origin=(0.0, 0.0, float(z0))
    )


def _framed_opening_solids(
    ifc_file: ifcopenshell.file,
    *,
    along: float,
    sill: float,
    clear_width: float,
    clear_height: float,
    wall_thickness: float,
    frame_width: float,
    frame_depth: float,
    leaf_thickness: float,
    kind: str,
    exterior_protrusion: float = 0.04,
) -> tuple[list[ifcopenshell.entity_instance], list[ifcopenshell.entity_instance]]:
    """Build frame solids and separate glass solids for a door or window.

    Returns ``(frame_solids, glass_solids)``. Door lower leaf stays with the
    frame (opaque); the upper lite is glass.
    """
    x0 = float(along)
    x1 = x0 + float(clear_width)
    z0 = float(sill)
    z1 = z0 + float(clear_height)
    fw = float(frame_width)
    y_ext = -float(exterior_protrusion)
    y_int = min(float(wall_thickness), float(frame_depth))
    lt = min(float(leaf_thickness), max(0.02, (y_int - y_ext) * 0.35))
    # Glass sits inset from the exterior frame face; keep enough thickness so the
    # isometric preview shows solid black panes (not edge-only hatching).
    glass_thickness = max(lt, 0.04)
    y_leaf0 = y_ext + 0.015
    y_leaf1 = y_leaf0 + glass_thickness

    frame: list[ifcopenshell.entity_instance] = [
        _box_solid(
            ifc_file, x0=x0, x1=x0 + fw, y0=y_ext, y1=y_int, z0=z0, z1=z1
        ),
        _box_solid(
            ifc_file, x0=x1 - fw, x1=x1, y0=y_ext, y1=y_int, z0=z0, z1=z1
        ),
        _box_solid(
            ifc_file,
            x0=x0 + fw,
            x1=x1 - fw,
            y0=y_ext,
            y1=y_int,
            z0=z1 - fw,
            z1=z1,
        ),
    ]
    glass: list[ifcopenshell.entity_instance] = []

    if kind == "window":
        frame.append(
            _box_solid(
                ifc_file,
                x0=x0 + fw,
                x1=x1 - fw,
                y0=y_ext,
                y1=y_int,
                z0=z0,
                z1=z0 + fw,
            )
        )
        mid = 0.5 * (x0 + x1)
        frame.append(
            _box_solid(
                ifc_file,
                x0=mid - fw * 0.4,
                x1=mid + fw * 0.4,
                y0=y_ext,
                y1=y_int,
                z0=z0 + fw,
                z1=z1 - fw,
            )
        )
        for gx0, gx1 in ((x0 + fw, mid - fw * 0.4), (mid + fw * 0.4, x1 - fw)):
            glass.append(
                _box_solid(
                    ifc_file,
                    x0=gx0,
                    x1=gx1,
                    y0=y_leaf0,
                    y1=y_leaf1,
                    z0=z0 + fw,
                    z1=z1 - fw,
                )
            )
    else:
        threshold = min(0.025, fw * 0.4)
        frame.append(
            _box_solid(
                ifc_file,
                x0=x0 + fw,
                x1=x1 - fw,
                y0=y_ext,
                y1=y_int,
                z0=z0,
                z1=z0 + threshold,
            )
        )
        leaf_bottom = z0 + threshold
        leaf_top = z1 - fw
        mid_z = leaf_bottom + 0.55 * (leaf_top - leaf_bottom)
        frame.append(
            _box_solid(
                ifc_file,
                x0=x0 + fw,
                x1=x1 - fw,
                y0=y_ext,
                y1=y_int,
                z0=mid_z - fw * 0.45,
                z1=mid_z + fw * 0.45,
            )
        )
        # Opaque lower door leaf
        frame.append(
            _box_solid(
                ifc_file,
                x0=x0 + fw,
                x1=x1 - fw,
                y0=y_leaf0,
                y1=y_leaf1,
                z0=leaf_bottom,
                z1=mid_z - fw * 0.45,
            )
        )
        # Glazed upper lite
        glass.append(
            _box_solid(
                ifc_file,
                x0=x0 + fw,
                x1=x1 - fw,
                y0=y_leaf0,
                y1=y_leaf1,
                z0=mid_z + fw * 0.45,
                z1=leaf_top,
            )
        )

    return frame, glass


def _get_or_create_surface_style(
    ifc_file: ifcopenshell.file,
    *,
    name: str,
    rgb: tuple[float, float, float],
    transparency: float,
) -> ifcopenshell.entity_instance:
    """Reuse an IfcSurfaceStyle by name, or create shading with transparency."""
    from ifcopenshell.api.style import add_style, add_surface_style

    for style in ifc_file.by_type("IfcSurfaceStyle"):
        if style.Name == name:
            return style
    style = add_style(ifc_file, name=name)
    add_surface_style(
        ifc_file,
        style=style,
        ifc_class="IfcSurfaceStyleShading",
        attributes={
            "SurfaceColour": {
                "Name": None,
                "Red": float(rgb[0]),
                "Green": float(rgb[1]),
                "Blue": float(rgb[2]),
            },
            "Transparency": float(transparency),
        },
    )
    return style


def _get_or_create_named_material(
    ifc_file: ifcopenshell.file,
    *,
    name: str,
    category: str | None = None,
) -> ifcopenshell.entity_instance:
    from ifcopenshell.api.material import add_material

    for material in ifc_file.by_type("IfcMaterial"):
        if material.Name == name:
            return material
    return add_material(ifc_file, name=name, category=category)


def _assign_item_styles(
    ifc_file: ifcopenshell.file,
    items: Sequence[ifcopenshell.entity_instance],
    style: ifcopenshell.entity_instance,
) -> None:
    from ifcopenshell.api.style import assign_item_style

    for item in items:
        assign_item_style(ifc_file, item=item, style=style)


def add_opening_filling(
    ifc_file: ifcopenshell.file,
    *,
    opening: ifcopenshell.entity_instance,
    name: str,
    body_context: ifcopenshell.entity_instance,
    storey: ifcopenshell.entity_instance,
    along: float,
    sill: float,
    clear_width: float,
    clear_height: float,
    wall_thickness: float,
    wall_origin: Sequence[float],
    direction_xy: Sequence[float] = (1.0, 0.0),
    ifc_class: str = "IfcDoor",
    predefined_type: str = "DOOR",
    leaf_thickness: float = 0.03,
    frame_width: float = 0.08,
    frame_depth: float | None = None,
    exterior_protrusion: float = 0.04,
) -> ifcopenshell.entity_instance:
    """Place a framed door/window with separate transparent glass plates.

    Frame geometry lives on the ``IfcDoor`` / ``IfcWindow`` (opaque white style).
    Glazing is modelled as ``IfcPlate`` products with a transparent Glass material
    so IFC carries real glass transparency and the isometric preview can colour
    frames white and glass black independently.
    """
    from ifcopenshell.api.material import assign_material
    from ifcopenshell.api.style import assign_material_style

    filling = create_entity(
        ifc_file,
        ifc_class=ifc_class,
        name=name,
        predefined_type=predefined_type,
    )
    assign_container(ifc_file, relating_structure=storey, products=[filling])
    dx, dy = float(direction_xy[0]), float(direction_xy[1])
    placement = axis_placement_matrix(
        (
            float(wall_origin[0]),
            float(wall_origin[1]),
            float(wall_origin[2]) if len(wall_origin) > 2 else 0.0,
        ),
        local_x=(dx, dy, 0.0),
        local_z=(0.0, 0.0, 1.0),
    )
    edit_object_placement(ifc_file, product=filling, matrix=placement)

    kind = "window" if ifc_class == "IfcWindow" else "door"
    fd = float(frame_depth) if frame_depth is not None else max(
        float(wall_thickness) * 0.55, 0.10
    )
    frame_solids, glass_solids = _framed_opening_solids(
        ifc_file,
        along=along,
        sill=sill,
        clear_width=clear_width,
        clear_height=clear_height,
        wall_thickness=wall_thickness,
        frame_width=frame_width,
        frame_depth=fd,
        leaf_thickness=leaf_thickness,
        kind=kind,
        exterior_protrusion=exterior_protrusion,
    )

    frame_style = _get_or_create_surface_style(
        ifc_file, name="Frame", rgb=(1.0, 1.0, 1.0), transparency=0.0
    )
    glass_style = _get_or_create_surface_style(
        ifc_file, name="Glass", rgb=(0.7, 0.85, 0.95), transparency=0.7
    )
    frame_material = _get_or_create_named_material(
        ifc_file, name="Frame", category="metal"
    )
    glass_material = _get_or_create_named_material(
        ifc_file, name="Glass", category="glass"
    )
    assign_material_style(
        ifc_file, material=frame_material, style=frame_style, context=body_context
    )
    assign_material_style(
        ifc_file, material=glass_material, style=glass_style, context=body_context
    )

    frame_rep = create_body_representation(ifc_file, body_context, frame_solids)
    assign_representation(ifc_file, product=filling, representation=frame_rep)
    _assign_item_styles(ifc_file, frame_solids, frame_style)
    assign_material(ifc_file, products=[filling], material=frame_material)
    add_filling(ifc_file, opening=opening, element=filling)

    if glass_solids:
        glass = create_entity(
            ifc_file,
            ifc_class="IfcPlate",
            name=f"{name}-Glass",
            predefined_type="CURTAIN_PANEL",
        )
        glass.ObjectType = "Glass"
        assign_container(ifc_file, relating_structure=storey, products=[glass])
        edit_object_placement(ifc_file, product=glass, matrix=placement)
        glass_rep = create_body_representation(ifc_file, body_context, glass_solids)
        assign_representation(ifc_file, product=glass, representation=glass_rep)
        _assign_item_styles(ifc_file, glass_solids, glass_style)
        assign_material(ifc_file, products=[glass], material=glass_material)

    return filling
