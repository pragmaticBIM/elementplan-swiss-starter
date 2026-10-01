"""Generate IfcSpace parking bays with a simple garage vignette."""

from __future__ import annotations

from typing import Any

import ifcopenshell

from generators.base import create_project_shell, get_body_context
from generators.covering import add_covering
from generators.parts import rect_polyline
from generators.slab import add_slab
from generators.space import (
    FLOOR_COVERING_THICKNESS,
    FLOOR_SLAB_THICKNESS,
    WALL_THICKNESS,
    _create_space_entity,
    _shoelace_area,
)
from generators.wall import add_wall

DEFAULT_BAY_WIDTH = 2.7
DEFAULT_BAY_DEPTH = 5.0
DEFAULT_BAY_COUNT = 3
DEFAULT_PARKING_HEIGHT = 2.2
# Drive aisle / street in front of the bays (toward −Y); 3 m roadway width.
DEFAULT_STREET_DEPTH = 3.0


def generate_parking(
    params: dict[str, Any],
) -> tuple[ifcopenshell.file, list[ifcopenshell.entity_instance]]:
    """Create three (or N) PARKING spaces side by side with slab, flooring, wall.

    Layout (Y grows toward the head wall)::

        [wall]
        [P0001][P0002][P0003]   ← bays flush to wall; flooring to wall face
        [      Strasse       ]   ← 3 m aisle, same height as parking
        (slab under street + bays + wall; one flooring over street + bays)

    Required / typical params:
      - height (float, m) — clear parking / street space height
      - bay_width / width (float, m) — single bay along X (default 2.7)
      - bay_depth / depth (float, m) — bay depth along Y (default 5.0)
      - bay_count (int, default 3)

    Optional:
      - names: list of Name strings (default P0001…P000N)
      - bay_attrs: list of per-bay attr dicts (quantities / properties)
      - street_depth: drive-aisle width (default 3.0)
      - with_context (bool, default True): slab + flooring + back wall + street

    Returns ``(ifc_file, parking_space_entities)``.
    """
    height = float(params.get("height") or DEFAULT_PARKING_HEIGHT)
    if height <= 0:
        raise ValueError("height must be positive")

    bay_width = float(
        params.get("bay_width", params.get("width", DEFAULT_BAY_WIDTH))
    )
    bay_depth = float(
        params.get("bay_depth", params.get("depth", DEFAULT_BAY_DEPTH))
    )
    bay_count = int(params.get("bay_count", DEFAULT_BAY_COUNT))
    if bay_width <= 0 or bay_depth <= 0:
        raise ValueError("bay_width and bay_depth must be positive")
    if bay_count < 1:
        raise ValueError("bay_count must be at least 1")

    street_depth = float(params.get("street_depth", DEFAULT_STREET_DEPTH))
    # Street matches parking clear height unless overridden.
    street_height = float(params.get("street_height", height))
    if street_depth <= 0 or street_height <= 0:
        raise ValueError("street_depth and street_height must be positive")

    total_width = bay_width * bay_count
    wall_t = WALL_THICKNESS
    # Street in front (−Y); bays flush to the head wall (+Y).
    y_street0 = -street_depth
    y_bay0 = 0.0
    y_bay1 = bay_depth
    y_wall0 = bay_depth
    y_wall1 = bay_depth + wall_t

    ifc_file = params.get("ifc_file")
    storey = params.get("storey")
    body_context = params.get("body_context")
    if ifc_file is None or storey is None:
        shell_name = params.get("project_name") or params.get("name") or "Parkplaetze"
        ifc_file, _project, _site, _building, storey, body_context = create_project_shell(
            name=f"Catalog — {shell_name}"
        )
    elif body_context is None:
        body_context = get_body_context(ifc_file)

    names = list(params.get("names") or [])
    while len(names) < bay_count:
        names.append(f"P{len(names) + 1:04d}")

    bay_attrs_list = list(params.get("bay_attrs") or [])
    while len(bay_attrs_list) < bay_count:
        bay_attrs_list.append({})

    spaces: list[ifcopenshell.entity_instance] = []
    for index in range(bay_count):
        x0 = index * bay_width
        poly = rect_polyline(x0, y_bay0, x0 + bay_width, y_bay1)
        area = _shoelace_area(poly)
        attrs = bay_attrs_list[index] or {}
        quantities = dict(attrs.get("quantities") or {})
        quantities.setdefault("GrossFloorArea", area)
        quantities.setdefault("GrossVolume", area * height)
        quantities.setdefault("Height", height)
        quantities.setdefault("NetFloorArea", round(area, 2))

        space = _create_space_entity(
            ifc_file,
            storey=storey,
            body_context=body_context,
            name=str(attrs.get("name") or names[index]),
            long_name=attrs.get("long_name"),
            predefined_type=str(attrs.get("predefined_type") or "PARKING"),
            polyline=poly,
            height=height,
            quantities=quantities,
            properties=attrs.get("properties") or {},
            properties_datatypes=attrs.get("property_datatypes") or {},
            object_type=attrs.get("object_type"),
        )
        spaces.append(space)

    if params.get("with_context", True):
        z_floor_covering = -FLOOR_COVERING_THICKNESS
        # Wall sits on the slab alongside the covering (same as interior vignette).
        z_floor_slab_top = z_floor_covering
        z_floor_slab = z_floor_slab_top - FLOOR_SLAB_THICKNESS
        wall_height = height - z_floor_slab_top

        # Slab exactly under street + bays + wall (no overhang).
        slab_footprint = rect_polyline(0.0, y_street0, total_width, y_wall1)
        # One covering over street + bays, flush to the wall face.
        flooring_footprint = rect_polyline(0.0, y_street0, total_width, y_wall0)
        add_slab(
            ifc_file,
            name="Parking-FloorSlab",
            body_context=body_context,
            storey=storey,
            polyline=slab_footprint,
            thickness=FLOOR_SLAB_THICKNESS,
            z_bottom=z_floor_slab,
            predefined_type="FLOOR",
        )
        add_covering(
            ifc_file,
            name="Parking-Flooring",
            body_context=body_context,
            storey=storey,
            polyline=flooring_footprint,
            thickness=FLOOR_COVERING_THICKNESS,
            z_bottom=z_floor_covering,
            predefined_type="FLOORING",
        )
        add_wall(
            ifc_file,
            name="Parking-Wall",
            body_context=body_context,
            storey=storey,
            origin=(0.0, y_wall0, z_floor_slab_top),
            length=total_width,
            height=wall_height,
            thickness=wall_t,
            direction_xy=(1.0, 0.0),
            predefined_type="SOLIDWALL",
        )

        street_poly = rect_polyline(0.0, y_street0, total_width, y_bay0)
        street_area = _shoelace_area(street_poly)
        _create_space_entity(
            ifc_file,
            storey=storey,
            body_context=body_context,
            name="Strasse",
            long_name="Strasse",
            predefined_type="EXTERNAL",
            polyline=street_poly,
            height=street_height,
            quantities={
                "GrossFloorArea": street_area,
                "GrossVolume": street_area * street_height,
                "Height": street_height,
                "NetFloorArea": round(street_area, 2),
            },
            properties={"Pset_SpaceCommon": {"IsExternal": True}},
            properties_datatypes={"Pset_SpaceCommon": {"IsExternal": "IfcBoolean"}},
        )

    return ifc_file, spaces
