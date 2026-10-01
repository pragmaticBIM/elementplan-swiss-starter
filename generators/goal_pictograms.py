"""Isometric pictograms for project goals (Ziele and Rahmenbedingungen).

Each scene is a small IFC vignette on one shared ground plate. The returned
product is the only amber accent (``primary_guids``); everything else stays
white context. Geometry is boxes and cylinders, same helpers as the element
cards. All scenes share one orthographic camera (``CAMERA_BOUNDS``).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable, Sequence

import ifcopenshell
import numpy as np
from ifcopenshell.api.geometry import assign_representation, edit_object_placement
from ifcopenshell.api.root import create_entity
from ifcopenshell.api.spatial import assign_container

from generators.base import create_project_shell, get_body_context
from generators.furniture import (
    DEFAULT_CHAIR_BACK_HEIGHT,
    DEFAULT_CHAIR_BACK_THICKNESS,
    DEFAULT_CHAIR_DEPTH,
    DEFAULT_CHAIR_SEAT_HEIGHT,
    DEFAULT_CHAIR_SEAT_THICKNESS,
    DEFAULT_CHAIR_WIDTH,
)
from generators.parts import (
    axis_placement_matrix,
    create_body_representation,
    create_cylinder_solid,
    create_extruded_area_solid,
    translation_matrix,
)
from generators.wall import vertical_body_solids_with_openings

SceneBuilder = Callable[
    [], tuple[ifcopenshell.file, ifcopenshell.entity_instance]
]

# Slug → name of the single amber product.
ACCENT_NAMES: dict[str, str] = {
    "existing-conditions": "Scannerkopf",
    "construction-method-prefabrication": "Fertigteil",
    "procurement-strategy": "Vergabepaket",
    "fit-out-standard": "Bodenbelag",
    "facility-management": "Etikett",
    "costs-quantities": "Münze",
    "schedule-coordination": "Markierter Tag",
    "decision-certainty": "Gewählte Variante",
    "permit-certainty": "Stempelabdruck",
    "planning-certainty": "Detailausschnitt",
    "verifiable-sustainability": "Materialpass",
}

# One plate, one camera, for every pictogram. Padding is tuned so the plate
# lands near 62% of the frame width under the orthographic isometric lens.
PLATE_NAME = "Bodenplatte"
PLATE_W = 1.24
PLATE_D = 0.92
PLATE_T = 0.018
CAMERA_PADDING = 1.48
CAMERA_BOUNDS = np.array(
    [[0.0, 0.0, -0.78], [PLATE_W, PLATE_D, 0.48]],
    dtype=np.float64,
)


class _Ctx:
    def __init__(
        self,
        ifc_file: ifcopenshell.file,
        storey: ifcopenshell.entity_instance,
        body: ifcopenshell.entity_instance,
    ) -> None:
        self.ifc = ifc_file
        self.storey = storey
        self.body = body


def _open(name: str) -> _Ctx:
    ifc_file, _project, _site, _building, storey, body = create_project_shell(
        name, storey_name="EG"
    )
    body = get_body_context(ifc_file) or body
    return _Ctx(ifc_file, storey, body)


def _box_solid(
    ifc_file: ifcopenshell.file,
    x0: float,
    y0: float,
    z0: float,
    x1: float,
    y1: float,
    z1: float,
) -> ifcopenshell.entity_instance:
    return create_extruded_area_solid(
        ifc_file,
        [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
        z1 - z0,
        origin=(0.0, 0.0, z0),
    )


def _product(
    ctx: _Ctx,
    name: str,
    solids: Sequence[ifcopenshell.entity_instance],
    *,
    ifc_class: str = "IfcBuildingElementProxy",
    predefined_type: str = "USERDEFINED",
    matrix: np.ndarray | None = None,
) -> ifcopenshell.entity_instance:
    product = create_entity(
        ctx.ifc,
        ifc_class=ifc_class,
        name=name,
        predefined_type=predefined_type,
    )
    if hasattr(product, "ObjectType"):
        product.ObjectType = name
    assign_container(ctx.ifc, relating_structure=ctx.storey, products=[product])
    edit_object_placement(
        ctx.ifc,
        product=product,
        matrix=translation_matrix() if matrix is None else matrix,
    )
    representation = create_body_representation(ctx.ifc, ctx.body, list(solids))
    assign_representation(ctx.ifc, product=product, representation=representation)
    return product


def _box(
    ctx: _Ctx,
    name: str,
    x0: float,
    y0: float,
    z0: float,
    x1: float,
    y1: float,
    z1: float,
) -> ifcopenshell.entity_instance:
    return _product(ctx, name, [_box_solid(ctx.ifc, x0, y0, z0, x1, y1, z1)])


def _cylinder(
    ctx: _Ctx,
    name: str,
    cx: float,
    cy: float,
    z0: float,
    radius: float,
    height: float,
    *,
    segments: int = 24,
) -> ifcopenshell.entity_instance:
    solid = create_cylinder_solid(
        ctx.ifc,
        radius=radius,
        height=height,
        origin=(cx, cy, z0),
        segments=segments,
    )
    return _product(ctx, name, [solid])


def _unit(vector: Sequence[float]) -> np.ndarray:
    array = np.asarray(vector, dtype=np.float64)
    length = float(np.linalg.norm(array))
    if length < 1e-9:
        raise ValueError("direction must be non-zero")
    return array / length


def _perpendicular(axis: np.ndarray) -> np.ndarray:
    helper = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(axis, helper))) > 0.85:
        helper = np.array([0.0, 1.0, 0.0])
    return _unit(np.cross(helper, axis))


def _strut(
    ctx: _Ctx,
    name: str,
    start: Sequence[float],
    end: Sequence[float],
    thickness: float,
) -> ifcopenshell.entity_instance:
    """Thin bar from ``start`` to ``end``, square section centred on the axis."""
    origin = np.asarray(start, dtype=np.float64)
    delta = np.asarray(end, dtype=np.float64) - origin
    length = float(np.linalg.norm(delta))
    local_z = delta / length
    local_x = _perpendicular(local_z)
    half = thickness * 0.5
    solid = create_extruded_area_solid(
        ctx.ifc,
        [(-half, -half), (half, -half), (half, half), (-half, half)],
        length,
    )
    return _product(
        ctx,
        name,
        [solid],
        matrix=axis_placement_matrix(origin, local_x=local_x, local_z=local_z),
    )


def _outline(
    ifc_file: ifcopenshell.file,
    x0: float,
    y0: float,
    z0: float,
    x1: float,
    y1: float,
    z1: float,
    thickness: float,
) -> list[ifcopenshell.entity_instance]:
    """Four bars forming a rectangle in plan, extruded from z0 to z1."""
    t = thickness
    return [
        _box_solid(ifc_file, x0, y0, z0, x1, y0 + t, z1),
        _box_solid(ifc_file, x0, y1 - t, z0, x1, y1, z1),
        _box_solid(ifc_file, x0, y0 + t, z0, x0 + t, y1 - t, z1),
        _box_solid(ifc_file, x1 - t, y0 + t, z0, x1, y1 - t, z1),
    ]


def _ground(ctx: _Ctx) -> None:
    """Same thin white plate in every scene. Objects rest on ``PLATE_T``."""
    _box(ctx, PLATE_NAME, 0.0, 0.0, 0.0, PLATE_W, PLATE_D, PLATE_T)


def _annulus_solids(
    ifc_file: ifcopenshell.file,
    cx: float,
    cy: float,
    z0: float,
    z1: float,
    r_in: float,
    r_out: float,
    *,
    segments: int = 14,
) -> list[ifcopenshell.entity_instance]:
    """Flat ring in the XY plane, extruded from z0 to z1."""
    solids: list[ifcopenshell.entity_instance] = []
    for index in range(segments):
        a0 = 2.0 * math.pi * index / segments
        a1 = 2.0 * math.pi * (index + 1) / segments
        polyline = [
            (cx + r_out * math.cos(a0), cy + r_out * math.sin(a0)),
            (cx + r_out * math.cos(a1), cy + r_out * math.sin(a1)),
            (cx + r_in * math.cos(a1), cy + r_in * math.sin(a1)),
            (cx + r_in * math.cos(a0), cy + r_in * math.sin(a0)),
        ]
        solids.append(
            create_extruded_area_solid(
                ifc_file, polyline, z1 - z0, origin=(0.0, 0.0, z0)
            )
        )
    return solids


def _arch(ctx: _Ctx, name: str, center: Sequence[float], radius: float, tube: float) -> None:
    """Semicircular binding ring in the YZ plane, peak toward +Z."""
    origin = np.asarray(center, dtype=np.float64)
    segments = 5
    points = []
    for index in range(segments + 1):
        angle = math.pi * index / segments
        points.append(
            origin
            + radius * np.array([0.0, math.cos(angle), math.sin(angle)])
        )
    for index in range(segments):
        _strut(ctx, f"{name} {index + 1}", points[index], points[index + 1], tube)


def _h_line(
    ifc_file: ifcopenshell.file,
    x0: float,
    x1: float,
    y: float,
    z0: float,
    z1: float,
    depth: float,
) -> ifcopenshell.entity_instance:
    """Line on a vertical +Y face, running along X."""
    return _box_solid(ifc_file, x0, y, z0, x1, y + depth, z1)


def _v_line(
    ifc_file: ifcopenshell.file,
    x0: float,
    x1: float,
    y: float,
    z0: float,
    z1: float,
    depth: float,
) -> ifcopenshell.entity_instance:
    """Line on a vertical +Y face, running along Z."""
    return _box_solid(ifc_file, x0, y, z0, x1, y + depth, z1)


def _plan_bar_x(
    ifc_file: ifcopenshell.file,
    x0: float,
    x1: float,
    y: float,
    z: float,
    thickness: float,
    height: float,
) -> ifcopenshell.entity_instance:
    half = thickness * 0.5
    return _box_solid(ifc_file, x0, y - half, z, x1, y + half, z + height)


def _plan_bar_y(
    ifc_file: ifcopenshell.file,
    x: float,
    y0: float,
    y1: float,
    z: float,
    thickness: float,
    height: float,
) -> ifcopenshell.entity_instance:
    half = thickness * 0.5
    return _box_solid(ifc_file, x - half, y0, z, x + half, y1, z + height)


def _crate_solids(
    ifc_file: ifcopenshell.file,
    x: float,
    y: float,
    z: float,
    *,
    width: float = 0.30,
    depth: float = 0.24,
    height: float = 0.20,
) -> list[ifcopenshell.entity_instance]:
    """Equal transport crate with a lid and slats on the two visible sides."""
    lid = 0.032
    body_top = z + height - lid
    solids = [
        _box_solid(ifc_file, x, y, z, x + width, y + depth, body_top),
        _box_solid(
            ifc_file,
            x + 0.018,
            y + 0.016,
            body_top,
            x + width - 0.018,
            y + depth - 0.016,
            z + height,
        ),
    ]
    slat_t = 0.006
    for index in range(3):
        zz = z + 0.028 + index * 0.042
        solids.append(
            _box_solid(
                ifc_file,
                x + 0.02,
                y + depth,
                zz,
                x + width - 0.02,
                y + depth + slat_t,
                zz + 0.012,
            )
        )
        solids.append(
            _box_solid(
                ifc_file,
                x + width,
                y + 0.02,
                zz,
                x + width + slat_t,
                y + depth - 0.02,
                zz + 0.012,
            )
        )
    return solids


def _chair_solids(
    ifc_file: ifcopenshell.file,
    *,
    x0: float,
    y0: float,
    z0: float,
    scale: float = 1.0,
) -> list[ifcopenshell.entity_instance]:
    """Same proportions as the furniture card; backrest on the far side."""
    width = DEFAULT_CHAIR_WIDTH * scale
    depth = DEFAULT_CHAIR_DEPTH * scale
    seat_h = DEFAULT_CHAIR_SEAT_HEIGHT * scale
    seat_t = DEFAULT_CHAIR_SEAT_THICKNESS * scale
    back_h = DEFAULT_CHAIR_BACK_HEIGHT * scale
    back_t = DEFAULT_CHAIR_BACK_THICKNESS * scale
    x1 = x0 + width
    y1 = y0 + depth
    z_seat = z0 + seat_h - seat_t
    solids = [
        _box_solid(ifc_file, x0, y0, z_seat, x1, y1, z_seat + seat_t),
        _box_solid(
            ifc_file,
            x0,
            y0,
            z_seat + seat_t,
            x1,
            y0 + back_t,
            z_seat + seat_t + back_h,
        ),
    ]
    leg = min(0.05 * scale, width * 0.12, depth * 0.12)
    for lx, ly in (
        (x0, y0),
        (x1 - leg, y0),
        (x0, y1 - leg),
        (x1 - leg, y1 - leg),
    ):
        solids.append(
            _box_solid(ifc_file, lx, ly, z0, lx + leg, ly + leg, z_seat)
        )
    return solids


def generate_existing_conditions() -> tuple[
    ifcopenshell.file, ifcopenshell.entity_instance
]:
    """Wall fragment with a window, scanner on a tripod. Amber: scanner head."""
    ctx = _open("existing-conditions")
    _ground(ctx)
    wall_x, wall_y = 0.16, 0.08
    wall_l, wall_h, wall_t = 0.78, 0.42, 0.11
    _product(
        ctx,
        "Mauer",
        vertical_body_solids_with_openings(
            ctx.ifc,
            length=wall_l,
            height=wall_h,
            thickness=wall_t,
            openings=[
                {"along": 0.26, "sill": 0.12, "width": 0.26, "height": 0.20}
            ],
        ),
        matrix=translation_matrix(wall_x, wall_y, PLATE_T),
    )
    cx, cy = 0.58, 0.52
    hub = (cx, cy, 0.20)
    for index, foot in enumerate(
        (
            (cx - 0.22, cy - 0.16, PLATE_T),
            (cx + 0.20, cy - 0.08, PLATE_T),
            (cx + 0.02, cy + 0.22, PLATE_T),
        )
    ):
        _strut(ctx, f"Stativbein {index + 1}", foot, hub, 0.016)
    _cylinder(ctx, "Stativkopf", cx, cy, hub[2] - 0.012, 0.028, 0.028)
    column_h = 0.06
    _cylinder(ctx, "Stativsäule", cx, cy, hub[2] + 0.016, 0.012, column_h)
    head_z = hub[2] + 0.016 + column_h
    radius = 0.155
    amber = _product(
        ctx,
        ACCENT_NAMES["existing-conditions"],
        [
            create_cylinder_solid(
                ctx.ifc, radius=radius, height=0.055, origin=(cx, cy, head_z), segments=24
            ),
            create_cylinder_solid(
                ctx.ifc,
                radius=radius * 0.38,
                height=0.032,
                origin=(cx, cy, head_z + 0.055),
                segments=24,
            ),
            create_cylinder_solid(
                ctx.ifc,
                radius=radius,
                height=0.055,
                origin=(cx, cy, head_z + 0.087),
                segments=24,
            ),
        ],
    )
    return ctx.ifc, amber


def generate_construction_method_prefabrication() -> tuple[
    ifcopenshell.file, ifcopenshell.entity_instance
]:
    """Three structural bays with one panel ready to install. Amber: panel."""
    ctx = _open("construction-method-prefabrication")
    _ground(ctx)
    z0 = PLATE_T
    frame_y = 0.20
    column_w = 0.055
    frame_h = 0.40
    for index, x in enumerate((0.15, 0.47, 0.79, 1.05)):
        _box(
            ctx,
            f"Stütze {index + 1}",
            x,
            frame_y,
            z0,
            x + column_w,
            frame_y + column_w,
            z0 + frame_h,
        )
    _box(
        ctx,
        "Träger",
        0.15,
        frame_y,
        z0 + frame_h,
        1.105,
        frame_y + column_w,
        z0 + frame_h + column_w,
    )
    panel_x0, panel_x1 = 0.51, 0.775
    panel_y0 = frame_y + column_w + 0.035
    panel_z1 = z0 + 0.33
    amber = _product(
        ctx,
        ACCENT_NAMES["construction-method-prefabrication"],
        [
            _box_solid(
                ctx.ifc,
                panel_x0,
                panel_y0,
                z0,
                panel_x1,
                panel_y0 + 0.065,
                panel_z1,
            ),
            create_cylinder_solid(
                ctx.ifc,
                radius=0.018,
                height=0.035,
                origin=(panel_x0 + 0.06, panel_y0 + 0.032, panel_z1),
                segments=16,
            ),
            create_cylinder_solid(
                ctx.ifc,
                radius=0.018,
                height=0.035,
                origin=(panel_x1 - 0.06, panel_y0 + 0.032, panel_z1),
                segments=16,
            ),
        ],
    )
    return ctx.ifc, amber


def generate_procurement_strategy() -> tuple[
    ifcopenshell.file, ifcopenshell.entity_instance
]:
    """Three equal crates, slightly offset, with side slats. Amber: one crate."""
    ctx = _open("procurement-strategy")
    _ground(ctx)
    _product(ctx, "Kiste links", _crate_solids(ctx.ifc, 0.16, 0.40, PLATE_T))
    amber = _product(
        ctx,
        ACCENT_NAMES["procurement-strategy"],
        _crate_solids(ctx.ifc, 0.46, 0.22, PLATE_T),
    )
    _product(ctx, "Kiste rechts", _crate_solids(ctx.ifc, 0.76, 0.38, PLATE_T))
    return ctx.ifc, amber


def generate_fit_out_standard() -> tuple[
    ifcopenshell.file, ifcopenshell.entity_instance
]:
    """Chair on a square floor swatch. Amber: the swatch, kept inside 8–20%."""
    ctx = _open("fit-out-standard")
    _ground(ctx)
    side = 0.42
    swatch_t = 0.012
    sx = (PLATE_W - side) * 0.5
    sy = (PLATE_D - side) * 0.5
    amber = _product(
        ctx,
        ACCENT_NAMES["fit-out-standard"],
        [
            _box_solid(
                ctx.ifc, sx, sy, PLATE_T, sx + side, sy + side, PLATE_T + swatch_t
            )
        ],
    )
    scale = 0.48
    x0 = sx + (side - DEFAULT_CHAIR_WIDTH * scale) * 0.5
    y0 = sy + (side - DEFAULT_CHAIR_DEPTH * scale) * 0.55
    _product(
        ctx,
        "Sessel",
        _chair_solids(ctx.ifc, x0=x0, y0=y0, z0=PLATE_T + swatch_t, scale=scale),
        ifc_class="IfcFurniture",
        predefined_type="CHAIR",
    )
    return ctx.ifc, amber


def generate_facility_management() -> tuple[
    ifcopenshell.file, ifcopenshell.entity_instance
]:
    """Key lying on the plate, tag on a string. Amber: the tag."""
    ctx = _open("facility-management")
    _ground(ctx)
    z0, z1 = PLATE_T, PLATE_T + 0.016
    cx, cy = 0.42, 0.34
    r_out, r_in = 0.145, 0.078
    _product(
        ctx,
        "Schlüssel",
        [
            *_annulus_solids(ctx.ifc, cx, cy, z0, z1, r_in, r_out),
            _box_solid(ctx.ifc, cx + r_in, cy - 0.016, z0, cx + 0.52, cy + 0.016, z1),
            _box_solid(ctx.ifc, cx + 0.40, cy + 0.016, z0, cx + 0.45, cy + 0.07, z1),
            _box_solid(ctx.ifc, cx + 0.46, cy + 0.016, z0, cx + 0.50, cy + 0.055, z1),
            _box_solid(ctx.ifc, cx + 0.50, cy + 0.016, z0, cx + 0.545, cy + 0.04, z1),
        ],
    )
    tag_x, tag_y = 0.12, 0.58
    tag_w, tag_d, tag_h = 0.40, 0.22, 0.014
    _strut(
        ctx,
        "Schnur",
        (cx, cy + r_out, z1),
        (tag_x + tag_w * 0.45, tag_y, PLATE_T + tag_h),
        0.012,
    )
    amber = _box(
        ctx,
        ACCENT_NAMES["facility-management"],
        tag_x,
        tag_y,
        PLATE_T,
        tag_x + tag_w,
        tag_y + tag_d,
        PLATE_T + tag_h,
    )
    return ctx.ifc, amber


def generate_costs_quantities() -> tuple[
    ifcopenshell.file, ifcopenshell.entity_instance
]:
    """Two or three aligned coin stacks. Amber: middle coin of the tallest."""
    ctx = _open("costs-quantities")
    _ground(ctx)
    radius = 0.175
    height = 0.020
    gap = 0.005
    counts = (3, 6, 4)
    step = 0.40
    y = PLATE_D * 0.50
    x_mid = PLATE_W * 0.50
    amber: ifcopenshell.entity_instance | None = None
    for stack, count in enumerate(counts):
        cx = x_mid + (stack - 1) * step
        marked = (count - 1) // 2
        for index in range(count):
            z0 = PLATE_T + index * (height + gap)
            is_amber = stack == 1 and index == marked
            name = (
                ACCENT_NAMES["costs-quantities"]
                if is_amber
                else f"Münze {stack + 1}-{index + 1}"
            )
            coin = _cylinder(ctx, name, cx, y, z0, radius, height, segments=24)
            if is_amber:
                amber = coin
    assert amber is not None
    return ctx.ifc, amber


def generate_schedule_coordination() -> tuple[
    ifcopenshell.file, ifcopenshell.entity_instance
]:
    """Standing calendar: spiral binding, header bar, flat day grid. Amber: one day."""
    ctx = _open("schedule-coordination")
    _ground(ctx)
    board_w, board_h, board_t = 0.76, 0.46, 0.045
    x0 = (PLATE_W - board_w) * 0.5
    y0 = 0.30
    z0 = PLATE_T
    face_y = y0 + board_t
    line_d = 0.007
    _product(
        ctx,
        "Kalender",
        [
            _box_solid(ctx.ifc, x0, y0, z0, x0 + board_w, face_y, z0 + board_h),
            _box_solid(
                ctx.ifc,
                x0 + 0.06,
                face_y,
                z0 + board_h - 0.105,
                x0 + board_w - 0.06,
                face_y + 0.008,
                z0 + board_h - 0.055,
            ),
        ],
    )
    for index, fx in enumerate((0.12, 0.30, 0.48, 0.64)):
        _arch(
            ctx,
            f"Spirale {index + 1}",
            (x0 + fx, y0 + board_t * 0.5, z0 + board_h),
            0.022,
            0.008,
        )
    cols, rows = 3, 2
    grid_x0 = x0 + 0.06
    grid_x1 = x0 + board_w - 0.06
    grid_z0 = z0 + 0.04
    grid_z1 = z0 + board_h - 0.145
    xs = [grid_x0 + (grid_x1 - grid_x0) * col / cols for col in range(cols + 1)]
    zs = [grid_z0 + (grid_z1 - grid_z0) * row / rows for row in range(rows + 1)]
    lines: list[ifcopenshell.entity_instance] = []
    for x in xs:
        lines.append(_v_line(ctx.ifc, x - 0.005, x + 0.005, face_y, grid_z0, grid_z1, line_d))
    for z in zs:
        lines.append(_h_line(ctx.ifc, grid_x0, grid_x1, face_y, z - 0.004, z + 0.004, line_d))
    _product(ctx, "Tagesraster", lines)
    marked_col, marked_row = 1, 1
    amber = _box(
        ctx,
        ACCENT_NAMES["schedule-coordination"],
        xs[marked_col] + 0.008,
        face_y,
        zs[marked_row] + 0.006,
        xs[marked_col + 1] - 0.008,
        face_y + 0.004,
        zs[marked_row + 1] - 0.006,
    )
    return ctx.ifc, amber


def generate_decision_certainty() -> tuple[
    ifcopenshell.file, ifcopenshell.entity_instance
]:
    """Three comparable option cards. Amber: selected middle option."""
    ctx = _open("decision-certainty")
    _ground(ctx)
    z0 = PLATE_T
    card_w, card_d, card_h = 0.25, 0.42, 0.025
    y0 = (PLATE_D - card_d) * 0.5
    amber: ifcopenshell.entity_instance | None = None
    for index, x0 in enumerate((0.13, 0.495, 0.86)):
        name = (
            ACCENT_NAMES["decision-certainty"]
            if index == 1
            else f"Variante {index + 1}"
        )
        solids = [
            _box_solid(
                ctx.ifc,
                x0,
                y0,
                z0,
                x0 + card_w,
                y0 + card_d,
                z0 + card_h,
            ),
            _box_solid(
                ctx.ifc,
                x0 + 0.045,
                y0 + 0.07,
                z0 + card_h,
                x0 + card_w - 0.045,
                y0 + 0.11,
                z0 + card_h + 0.012,
            ),
            _box_solid(
                ctx.ifc,
                x0 + 0.045,
                y0 + 0.17,
                z0 + card_h,
                x0 + card_w - 0.08,
                y0 + 0.21,
                z0 + card_h + 0.012,
            ),
            _box_solid(
                ctx.ifc,
                x0 + 0.045,
                y0 + 0.27,
                z0 + card_h,
                x0 + card_w - 0.06,
                y0 + 0.31,
                z0 + card_h + 0.012,
            ),
        ]
        card = _product(ctx, name, solids)
        if index == 1:
            amber = card
    assert amber is not None
    return ctx.ifc, amber


def generate_permit_certainty() -> tuple[
    ifcopenshell.file, ifcopenshell.entity_instance
]:
    """Stamp hovering over a plan sheet. Amber: the imprint directly below it."""
    ctx = _open("permit-certainty")
    _ground(ctx)
    sheet_t = 0.012
    sx, sy, sw, sd = 0.14, 0.12, 0.96, 0.68
    sheet_top = PLATE_T + sheet_t
    _product(
        ctx,
        "Planbogen",
        [
            _box_solid(ctx.ifc, sx, sy, PLATE_T, sx + sw, sy + sd, sheet_top),
            *_outline(
                ctx.ifc,
                sx + 0.04,
                sy + 0.04,
                sheet_top,
                sx + sw - 0.04,
                sy + sd - 0.04,
                sheet_top + 0.006,
                0.008,
            ),
        ],
    )
    base_w, base_d, base_h = 0.26, 0.18, 0.045
    bx = sx + (sw - base_w) * 0.55
    by = sy + (sd - base_d) * 0.48
    gap = 0.08
    base_z = sheet_top + gap
    _product(
        ctx,
        "Stempel",
        [
            _box_solid(
                ctx.ifc, bx, by, base_z, bx + base_w, by + base_d, base_z + base_h
            ),
            create_cylinder_solid(
                ctx.ifc,
                radius=0.028,
                height=0.12,
                origin=(bx + base_w * 0.5, by + base_d * 0.5, base_z + base_h),
                segments=20,
            ),
            create_cylinder_solid(
                ctx.ifc,
                radius=0.048,
                height=0.026,
                origin=(
                    bx + base_w * 0.5,
                    by + base_d * 0.5,
                    base_z + base_h + 0.12,
                ),
                segments=20,
            ),
        ],
    )
    # Larger than the base so the mark stays visible under an orthographic stamp.
    pad_x, pad_y = 0.10, 0.08
    amber = _box(
        ctx,
        ACCENT_NAMES["permit-certainty"],
        bx - pad_x,
        by - pad_y,
        sheet_top,
        bx + base_w + pad_x,
        by + base_d + pad_y,
        sheet_top + 0.008,
    )
    return ctx.ifc, amber


def generate_planning_certainty() -> tuple[
    ifcopenshell.file, ifcopenshell.entity_instance
]:
    """Plan sheet with a room and a roll lying on it. Amber: corner detail frame."""
    ctx = _open("planning-certainty")
    _ground(ctx)
    sheet_t = 0.012
    sx, sy, sw, sd = 0.12, 0.10, 1.00, 0.72
    sheet_top = PLATE_T + sheet_t
    _product(
        ctx,
        "Planbogen",
        [
            _box_solid(ctx.ifc, sx, sy, PLATE_T, sx + sw, sy + sd, sheet_top),
            *_outline(
                ctx.ifc,
                sx + 0.025,
                sy + 0.025,
                sheet_top,
                sx + sw - 0.025,
                sy + sd - 0.025,
                sheet_top + 0.005,
                0.008,
            ),
        ],
    )
    rx0, ry0, rx1, ry1 = sx + 0.08, sy + 0.30, sx + 0.42, sy + 0.56
    gap0, gap1 = rx0 + 0.10, rx0 + 0.22
    bar_t, bar_h = 0.012, 0.007
    _product(
        ctx,
        "Grundriss",
        [
            _plan_bar_x(ctx.ifc, rx0, rx1, ry0, sheet_top, bar_t, bar_h),
            _plan_bar_y(ctx.ifc, rx1, ry0, ry1, sheet_top, bar_t, bar_h),
            _plan_bar_x(ctx.ifc, gap1, rx1, ry1, sheet_top, bar_t, bar_h),
            _plan_bar_x(ctx.ifc, rx0, gap0, ry1, sheet_top, bar_t, bar_h),
            _plan_bar_y(ctx.ifc, rx0, ry0, ry1, sheet_top, bar_t, bar_h),
        ],
    )
    radius, length = 0.058, 0.52
    _product(
        ctx,
        "Planrolle",
        [
            create_cylinder_solid(ctx.ifc, radius=radius, height=length, segments=20),
            create_cylinder_solid(
                ctx.ifc,
                radius=radius + 0.012,
                height=0.05,
                origin=(0.0, 0.0, length * 0.55),
                segments=20,
            ),
        ],
        matrix=axis_placement_matrix(
            (sx + 0.22, sy + 0.14, sheet_top + radius),
            local_x=(0.0, 0.0, 1.0),
            local_z=(1.0, 0.0, 0.0),
        ),
    )
    fx0, fy0 = sx + sw - 0.54, sy + sd - 0.42
    amber = _product(
        ctx,
        ACCENT_NAMES["planning-certainty"],
        _outline(
            ctx.ifc,
            fx0,
            fy0,
            sheet_top,
            fx0 + 0.48,
            fy0 + 0.34,
            sheet_top + 0.008,
            0.064,
        ),
    )
    return ctx.ifc, amber


def generate_verifiable_sustainability() -> tuple[
    ifcopenshell.file, ifcopenshell.entity_instance
]:
    """Short timber beam, end grain, tag on a string. Amber: the tag."""
    ctx = _open("verifiable-sustainability")
    _ground(ctx)
    bw, bd, bh = 0.72, 0.20, 0.16
    x0 = (PLATE_W - bw) * 0.5 - 0.06
    y0 = 0.28
    z0 = PLATE_T
    x1 = x0 + bw
    _box(ctx, "Holzbalken", x0, y0, z0, x1, y0 + bd, z0 + bh)
    grain: list[ifcopenshell.entity_instance] = []
    for index in range(3):
        gz = z0 + 0.035 + index * 0.042
        grain.append(
            _box_solid(ctx.ifc, x1, y0 + 0.03, gz, x1 + 0.004, y0 + bd - 0.03, gz + 0.008)
        )
    _product(ctx, "Maserung", grain)
    tag_w, tag_d, tag_h = 0.42, 0.26, 0.014
    tag_x, tag_y = x0 + 0.08, y0 + bd + 0.05
    _strut(
        ctx,
        "Schnur",
        (x1 - 0.16, y0 + bd, z0 + bh * 0.62),
        (tag_x + tag_w * 0.3, tag_y, PLATE_T + tag_h),
        0.012,
    )
    amber = _box(
        ctx,
        ACCENT_NAMES["verifiable-sustainability"],
        tag_x,
        tag_y,
        PLATE_T,
        tag_x + tag_w,
        tag_y + tag_d,
        PLATE_T + tag_h,
    )
    return ctx.ifc, amber


GENERATORS: dict[str, SceneBuilder] = {
    "existing-conditions": generate_existing_conditions,
    "construction-method-prefabrication": generate_construction_method_prefabrication,
    "procurement-strategy": generate_procurement_strategy,
    "fit-out-standard": generate_fit_out_standard,
    "facility-management": generate_facility_management,
    "costs-quantities": generate_costs_quantities,
    "schedule-coordination": generate_schedule_coordination,
    "decision-certainty": generate_decision_certainty,
    "permit-certainty": generate_permit_certainty,
    "planning-certainty": generate_planning_certainty,
    "verifiable-sustainability": generate_verifiable_sustainability,
}


def render_goal_pictograms(media_dir: Path) -> None:
    """Write catalogue PNG and print TIFF for every goal pictogram."""
    from render.isometric import render_isometric
    from render.print_raster import PRINT_DPI, PRINT_RESOLUTION

    media_dir.mkdir(parents=True, exist_ok=True)
    for slug, build in GENERATORS.items():
        ifc_file, primary = build()
        common = dict(
            primary_guids=[primary.GlobalId],
            color_flooring=False,
            engrave=False,
            orthographic=True,
            fit_content=False,
            camera_bounds=CAMERA_BOUNDS,
            camera_padding=CAMERA_PADDING,
        )
        render_isometric(
            ifc_file,
            media_dir / f"{slug}.png",
            watermark=True,
            **common,
        )
        render_isometric(
            ifc_file,
            media_dir / f"{slug}-print.tif",
            watermark=False,
            resolution=PRINT_RESOLUTION,
            dpi=PRINT_DPI,
            **common,
        )
        print(f"OK  {slug}")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    render_goal_pictograms(root / "media" / "images")


if __name__ == "__main__":
    main()
