"""Schematic street scene: tree, car, and road on a ground slab.

Standalone illustration. Not a catalog element and not a Fachmodell picture.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Sequence

import ifcopenshell
from ifcopenshell.api.geometry import assign_representation, edit_object_placement
from ifcopenshell.api.root import create_entity
from ifcopenshell.api.spatial import assign_container

from generators.base import create_project_shell, get_body_context
from generators.parts import (
    _axis2placement3d,
    _closed_polyline_2d,
    add_extruded_product,
    create_body_representation,
    create_cylinder_solid,
    create_extruded_area_solid,
    create_sphere_brep,
    rect_polyline,
    translation_matrix,
)

TREE_NAME = "B0001"
ROAD_NAME = "Strasse"
CAR_NAME = "Auto"

# Metres. Road runs along X; the tree sits on the far side of the strip.
_GROUND = (-1.0, -0.6, 17.0, 9.2)
_GROUND_THICKNESS = 0.15
_ROAD = (0.8, 2.8, 15.2, 6.3)
_ROAD_THICKNESS = 0.12

_TREE_XY = (3.2, 1.35)
_CROWN_RADIUS = 1.35
_TRUNK_RADIUS = 0.14
_TRUNK_HEIGHT = 2.05

_CAR_X0 = 6.15
_CAR_X1 = 10.35
_CAR_Y0 = 3.85
_CAR_Y1 = 5.65
_WHEEL_RADIUS = 0.34
_WHEEL_WIDTH = 0.22
_WHEEL_SEGMENTS = 32


def _axle_cylinder(
    ifc_file: ifcopenshell.file,
    *,
    radius: float,
    width: float,
    center: Sequence[float],
    axle: Sequence[float] = (0.0, 1.0, 0.0),
) -> ifcopenshell.entity_instance:
    """Short cylinder whose axis follows ``axle`` (wheel disk)."""
    ax, ay, az = (float(axle[0]), float(axle[1]), float(axle[2]))
    length = math.sqrt(ax * ax + ay * ay + az * az)
    ax, ay, az = ax / length, ay / length, az / length
    half = width / 2.0
    origin = (
        float(center[0]) - ax * half,
        float(center[1]) - ay * half,
        float(center[2]) - az * half,
    )
    ref = (0.0, 0.0, 1.0) if abs(ax) > 0.9 else (1.0, 0.0, 0.0)
    profile = [
        (
            radius * math.cos(2.0 * math.pi * i / _WHEEL_SEGMENTS),
            radius * math.sin(2.0 * math.pi * i / _WHEEL_SEGMENTS),
        )
        for i in range(_WHEEL_SEGMENTS)
    ]
    swept = ifc_file.create_entity(
        "IfcArbitraryClosedProfileDef",
        ProfileType="AREA",
        ProfileName=None,
        OuterCurve=_closed_polyline_2d(ifc_file, profile),
    )
    return ifc_file.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=swept,
        Position=_axis2placement3d(ifc_file, origin, axis=(ax, ay, az), ref_direction=ref),
        ExtrudedDirection=ifc_file.create_entity(
            "IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)
        ),
        Depth=float(width),
    )


def _add_tree(
    ifc_file: ifcopenshell.file,
    *,
    site: ifcopenshell.entity_instance,
    body_context: ifcopenshell.entity_instance,
) -> ifcopenshell.entity_instance:
    tree = create_entity(
        ifc_file,
        ifc_class="IfcGeographicElement",
        name=TREE_NAME,
        predefined_type="VEGETATION",
    )
    tree.ObjectType = "Baum"
    assign_container(ifc_file, relating_structure=site, products=[tree])
    edit_object_placement(
        ifc_file,
        product=tree,
        matrix=translation_matrix(x=_TREE_XY[0], y=_TREE_XY[1]),
    )
    trunk = create_cylinder_solid(
        ifc_file,
        radius=_TRUNK_RADIUS,
        height=_TRUNK_HEIGHT,
        segments=_WHEEL_SEGMENTS,
    )
    crown = create_sphere_brep(
        ifc_file,
        radius=_CROWN_RADIUS,
        center=(0.0, 0.0, _TRUNK_HEIGHT + 0.55 * _CROWN_RADIUS),
        n_u=24,
        n_v=16,
    )
    representation = ifc_file.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=body_context,
        RepresentationIdentifier="Body",
        RepresentationType="SolidModel",
        Items=[trunk, crown],
    )
    assign_representation(ifc_file, product=tree, representation=representation)
    return tree


def _add_car(
    ifc_file: ifcopenshell.file,
    *,
    storey: ifcopenshell.entity_instance,
    body_context: ifcopenshell.entity_instance,
) -> ifcopenshell.entity_instance:
    road_top = _ROAD_THICKNESS
    body_bottom = road_top + 0.28
    body_height = 0.48
    cabin_bottom = body_bottom + body_height - 0.08
    cabin_height = 0.46
    inset_x = 1.15
    inset_y = 0.16

    body = create_extruded_area_solid(
        ifc_file,
        rect_polyline(_CAR_X0, _CAR_Y0, _CAR_X1, _CAR_Y1),
        body_height,
        origin=(0.0, 0.0, body_bottom),
    )
    cabin = create_extruded_area_solid(
        ifc_file,
        rect_polyline(
            _CAR_X0 + inset_x,
            _CAR_Y0 + inset_y,
            _CAR_X1 - inset_x * 0.55,
            _CAR_Y1 - inset_y,
        ),
        cabin_height,
        origin=(0.0, 0.0, cabin_bottom),
    )
    wheel_z = road_top + _WHEEL_RADIUS
    wheel_x = (_CAR_X0 + 0.72, _CAR_X1 - 0.72)
    wheel_y = (_CAR_Y0 + 0.08, _CAR_Y1 - 0.08)
    wheels = [
        _axle_cylinder(
            ifc_file,
            radius=_WHEEL_RADIUS,
            width=_WHEEL_WIDTH,
            center=(x, y, wheel_z),
        )
        for x in wheel_x
        for y in wheel_y
    ]
    car = create_entity(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name=CAR_NAME,
        predefined_type="USERDEFINED",
    )
    car.ObjectType = "Auto"
    assign_container(ifc_file, relating_structure=storey, products=[car])
    edit_object_placement(ifc_file, product=car)
    assign_representation(
        ifc_file,
        product=car,
        representation=create_body_representation(
            ifc_file, body_context, [body, cabin, *wheels]
        ),
    )
    return car


def generate_street_scene() -> tuple[
    ifcopenshell.file, dict[str, ifcopenshell.entity_instance]
]:
    """Build ground, road, tree, and car. Returns ``(ifc_file, products)``."""
    ifc_file, _project, site, _building, storey, body_context = create_project_shell(
        "Strasse",
        storey_name="Terrain",
        version="IFC4X3",
    )
    body_context = get_body_context(ifc_file) or body_context

    add_extruded_product(
        ifc_file,
        ifc_class="IfcSlab",
        name="Terrain",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(*_GROUND),
        thickness=_GROUND_THICKNESS,
        z_bottom=-_GROUND_THICKNESS,
        predefined_type="BASESLAB",
    )
    road = add_extruded_product(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name=ROAD_NAME,
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(*_ROAD),
        thickness=_ROAD_THICKNESS,
        predefined_type="USERDEFINED",
    )
    road.ObjectType = "Strasse"
    tree = _add_tree(ifc_file, site=site, body_context=body_context)
    car = _add_car(ifc_file, storey=storey, body_context=body_context)
    return ifc_file, {"tree": tree, "road": road, "car": car}


def render_street_scene_picture(repo_root: Path | None = None) -> Path:
    """Write the IFC, catalog PNG, and print TIFF for the street scene."""
    from render.isometric import PRINT_DPI, render_isometric
    from render.print_raster import PRINT_RESOLUTION

    root = repo_root or Path(__file__).resolve().parents[1]
    ifc_file, products = generate_street_scene()
    attachments = root / "media" / "attachments"
    images = root / "media" / "images"
    attachments.mkdir(parents=True, exist_ok=True)
    images.mkdir(parents=True, exist_ok=True)

    ifc_path = attachments / "scene-tree-car-road.ifc"
    png = images / "scene-tree-car-road.png"
    tif = images / "scene-tree-car-road-print.tif"
    ifc_file.write(str(ifc_path))

    guids = [products[key].GlobalId for key in ("tree", "road", "car")]
    render_isometric(
        ifc_file,
        png,
        primary_guids=guids,
        camera_padding=1.35,
        engrave=False,
        watermark=False,
    )
    render_isometric(
        ifc_file,
        tif,
        primary_guids=guids,
        camera_padding=1.35,
        resolution=PRINT_RESOLUTION,
        engrave=False,
        watermark=False,
        dpi=PRINT_DPI,
    )
    return png


if __name__ == "__main__":
    print(render_street_scene_picture())
