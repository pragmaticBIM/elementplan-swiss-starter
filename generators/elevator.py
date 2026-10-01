"""IfcSpace elevator shaft — storey-wise Aufzugsraumobjekte with slab opening."""

from __future__ import annotations

from typing import Any

import ifcopenshell

from generators.base import create_project_shell, get_body_context
from generators.parts import rect_polyline
from generators.slab import add_slab
from generators.space import (
    DOOR_HEIGHT,
    DOOR_WIDTH,
    FLOOR_SLAB_THICKNESS,
    WALL_THICKNESS,
    _create_space_entity,
    _shoelace_area,
)
from generators.wall import add_opening_in_wall, add_wall

# Typical passenger-shaft clear (metres); one storey height.
DEFAULT_SHAFT_WIDTH = 1.60
DEFAULT_SHAFT_DEPTH = 2.00
DEFAULT_HEIGHT = 2.80
# Landing collar beyond the outer wall faces; open front ends flush with the walls.
DEFAULT_SLAB_MARGIN = 1.20

def generate_elevator(
    params: dict[str, Any] | None = None,
) -> tuple[ifcopenshell.file, list[ifcopenshell.entity_instance]]:
    """Build an open-front shaft with two storey-separated spaces and wall openings.

    Layout (Y toward the isometric camera / open front)::

        [back wall]                 ← −Y, meets left/right at corners
        [left][spaces][right openings]
        [open front]                ← +Y, toward camera
        [U-shaped landing slab]     ← under the walls; open front flush with wall ends

    The two IfcSpace volumes stack directly without a vertical gap.
    Upper storey walls sit on the slab top (slab thickness between wall courses).

    Typical params:
      - width / shaft_width, depth / shaft_depth, height
      - slab_margin (m beyond outer wall faces)
      - name / long_name / predefined_type / quantities / properties
      - upper_name (default ``{name}-OG``)
    """
    params = dict(params or {})

    width = float(params.get("width", params.get("shaft_width", DEFAULT_SHAFT_WIDTH)))
    depth = float(params.get("depth", params.get("shaft_depth", DEFAULT_SHAFT_DEPTH)))
    height = float(params.get("height", DEFAULT_HEIGHT))
    wall_t = float(params.get("wall_thickness", WALL_THICKNESS))
    slab_t = float(params.get("slab_thickness", FLOOR_SLAB_THICKNESS))
    slab_margin = float(params.get("slab_margin", DEFAULT_SLAB_MARGIN))
    door_w = float(params.get("door_width", DOOR_WIDTH))
    door_h = float(params.get("door_height", DOOR_HEIGHT))

    if min(width, depth, height, wall_t, slab_t, slab_margin, door_w, door_h) <= 0:
        raise ValueError("all elevator vignette dimensions must be positive")
    if door_w >= width or door_h >= height:
        raise ValueError("door must fit inside the front shaft wall")

    name = params.get("name") or params.get("Name") or "A-01"
    upper_name = params.get("upper_name") or f"{name}-OG"
    long_name = params.get("long_name") or params.get("LongName") or "Aufzug"
    predefined_type = (
        params.get("predefined_type") or params.get("PredefinedType") or "INTERNAL"
    )

    ifc_file = params.get("ifc_file")
    storey = params.get("storey")
    body_context = params.get("body_context")
    if ifc_file is None or storey is None:
        shell_name = params.get("project_name") or name
        ifc_file, _project, _site, _building, storey, body_context = create_project_shell(
            name=f"Catalog — {shell_name}"
        )
    elif body_context is None:
        body_context = get_body_context(ifc_file)

    shaft_poly = rect_polyline(0.0, 0.0, width, depth)
    area = _shoelace_area(shaft_poly)
    base_quantities = dict(params.get("quantities") or {})
    base_quantities.setdefault("GrossFloorArea", round(area, 2))
    base_quantities.setdefault("NetFloorArea", round(area, 2))
    base_quantities.setdefault("GrossVolume", round(area * height, 2))
    base_quantities.setdefault("Height", height)

    # Spaces stack in the clear shaft; slab sits under the wall footprints.
    z_lower = 0.0
    z_slab = height
    z_upper = height
    z_upper_walls = z_slab + slab_t

    spaces: list[ifcopenshell.entity_instance] = []
    for space_name, z_bottom in ((str(name), z_lower), (str(upper_name), z_upper)):
        quantities = dict(base_quantities)
        spaces.append(
            _create_space_entity(
                ifc_file,
                storey=storey,
                body_context=body_context,
                name=space_name,
                long_name=str(long_name) if long_name is not None else None,
                predefined_type=str(predefined_type),
                polyline=shaft_poly,
                height=height,
                quantities=quantities,
                properties=params.get("properties") or {},
                properties_datatypes=params.get("property_datatypes") or {},
                object_type=params.get("object_type") or params.get("ObjectType"),
                z_bottom=z_bottom,
            )
        )

    if params.get("with_context", True):
        # U-shaped landing under the walls (inner cut = shaft clear); open front
        # ends flush with the front ends of the side walls.
        slab_x0 = -wall_t - slab_margin
        slab_y0 = -wall_t - slab_margin
        slab_x1 = width + wall_t + slab_margin
        slab_poly = [
            (slab_x0, slab_y0),
            (slab_x1, slab_y0),
            (slab_x1, depth),
            (width, depth),
            (width, 0.0),
            (0.0, 0.0),
            (0.0, depth),
            (slab_x0, depth),
        ]
        add_slab(
            ifc_file,
            name="Aufzug-Geschossdecke",
            body_context=body_context,
            storey=storey,
            polyline=slab_poly,
            thickness=slab_t,
            z_bottom=z_slab,
            predefined_type="FLOOR",
        )

        # Keep the camera-side front fully open. Lower walls meet the slab soffit;
        # upper walls stand on the slab top.
        # Openings only — no door fillings (avoids glazed leaf in the preview).
        wall_storeys = (
            ("EG", z_lower, height),
            ("OG", z_upper_walls, height),
        )
        opening_along = (depth + wall_t - door_w) * 0.5
        for storey_suffix, wall_z, storey_wall_height in wall_storeys:
            add_wall(
                ifc_file,
                name=f"Aufzug-Wand-Hinten-{storey_suffix}",
                body_context=body_context,
                storey=storey,
                origin=(width, 0.0, wall_z),
                length=width,
                height=storey_wall_height,
                thickness=wall_t,
                direction_xy=(-1.0, 0.0),
                predefined_type="SOLIDWALL",
            )
            add_wall(
                ifc_file,
                name=f"Aufzug-Wand-Links-{storey_suffix}",
                body_context=body_context,
                storey=storey,
                origin=(0.0, -wall_t, wall_z),
                length=depth + wall_t,
                height=storey_wall_height,
                thickness=wall_t,
                direction_xy=(0.0, 1.0),
                predefined_type="SOLIDWALL",
            )
            # Continuous wall Body — voids via IfcOpeningElement only
            # (fragmenting with openings= would draw piers/lintels as separate walls).
            right_origin = (width + wall_t, -wall_t, wall_z)
            right_wall = add_wall(
                ifc_file,
                name=f"Aufzug-Wand-Rechts-{storey_suffix}",
                body_context=body_context,
                storey=storey,
                origin=right_origin,
                length=depth + wall_t,
                height=storey_wall_height,
                thickness=wall_t,
                direction_xy=(0.0, 1.0),
                predefined_type="SOLIDWALL",
            )
            add_opening_in_wall(
                ifc_file,
                host=right_wall,
                name=f"Aufzug-Oeffnung-{storey_suffix}",
                body_context=body_context,
                along=opening_along,
                sill=0.0,
                clear_width=door_w,
                clear_height=door_h,
                wall_thickness=wall_t,
                wall_origin=right_origin,
                direction_xy=(0.0, 1.0),
            )

    return ifc_file, spaces
