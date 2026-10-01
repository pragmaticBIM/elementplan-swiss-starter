"""Interior wall / cladding / door / window catalog generators.

Reuse the interior-space vignette without IfcSpace volumes. Accent either the
partition IfcWall, a tile splashback (Fliesenschild) as IfcCovering CLADDING,
a drywall reinforcement panel inside that partition, or an interior door / window
in the partition (with envelope walls when openings are present).
"""

from __future__ import annotations

from typing import Any

import ifcopenshell
import ifcopenshell.util.element as element_util

from generators.base import assign_pset, assign_qto, get_body_context
from generators.covering import add_vertical_covering
from generators.parts import add_extruded_product, rect_polyline
from generators.wall import add_wall

# Tile splashback (Fliesenschild) on the camera-facing partition face.
DEFAULT_CLADDING_THICKNESS = 0.02
CLADDING_GAP = 0.01  # avoid coplanar wall/cladding faces
SPLASH_WIDTH = 1.20
# Stop at the top of the flooring (finished floor is z = 0).
SPLASH_SILL = 0.0
# Top is 90 cm above the previous 1.55 m head.
SPLASH_TOP = 2.45
SPLASH_HEIGHT = SPLASH_TOP - SPLASH_SILL
SPLASH_END_INSET = 0.80  # keep the shield toward the camera end of the wall

# Schematic wall-hung washbasin in front of the splash (metres).
BASIN_WIDTH = 0.60
BASIN_DEPTH = 0.46
BASIN_HEIGHT = 0.16
BASIN_RIM_Z = 0.85
BASIN_GAP = 0.01

PARALLEL_WALL_OFFSET = 1.0
PARALLEL_WALL_END_INSET = 0.65
PARALLEL_WALL_THICKNESS = 0.2

# Limited backing panel centred in the host wall thickness, floor to head.
REINF_WIDTH = 1.20
REINF_HEIGHT = 2.15
REINF_SILL = 0.0
REINF_END_INSET = 0.90
REINF_THICKNESS = 0.04


def _find_partition_wall(ifc_file: ifcopenshell.file) -> ifcopenshell.entity_instance:
    walls = [
        wall
        for wall in ifc_file.by_type("IfcWall")
        if getattr(wall, "PredefinedType", None) in {"PARTITIONING", "SOLIDWALL"}
        or (wall.Name or "").endswith("-Partition")
    ]
    if not walls:
        raise ValueError("no partition IfcWall in vignette")
    # Prefer the named partition over envelope SOLIDWALLs
    for wall in walls:
        if (wall.Name or "").endswith("-Partition") or getattr(
            wall, "PredefinedType", None
        ) == "PARTITIONING":
            return wall
    return walls[0]


def _find_interior_door(ifc_file: ifcopenshell.file) -> ifcopenshell.entity_instance:
    doors = list(ifc_file.by_type("IfcDoor"))
    if not doors:
        raise ValueError("no IfcDoor in interior vignette")
    return doors[0]


def _find_interior_window(ifc_file: ifcopenshell.file) -> ifcopenshell.entity_instance:
    windows = list(ifc_file.by_type("IfcWindow"))
    if not windows:
        raise ValueError("no IfcWindow in interior vignette")
    return windows[0]


def _wall_origin_length_height(
    wall: ifcopenshell.entity_instance,
) -> tuple[tuple[float, float, float], float, float]:
    """Recover world origin (base), centre-line length and height from Body."""
    placement = wall.ObjectPlacement
    axis = placement.RelativePlacement
    origin = axis.Location.Coordinates
    ox, oy, oz = float(origin[0]), float(origin[1]), float(origin[2])

    length = 5.0
    height = 2.8
    for rep in wall.Representation.Representations:
        for item in rep.Items:
            if not item.is_a("IfcExtrudedAreaSolid"):
                continue
            height = float(item.Depth)
            profile = item.SweptArea
            if profile.is_a("IfcArbitraryClosedProfileDef"):
                pts = profile.OuterCurve.Points
                xs = [float(p.Coordinates[0]) for p in pts]
                length = max(xs) - min(xs)
                break
    return (ox, oy, oz), length, height


def _splash_along(wall_length: float) -> float:
    """Start of the splash along the wall, biased toward the camera (+Y)."""
    along = wall_length - SPLASH_END_INSET - SPLASH_WIDTH
    if along < 0.15:
        along = max(0.0, (wall_length - SPLASH_WIDTH) * 0.5)
    if along + SPLASH_WIDTH > wall_length + 1e-6:
        raise ValueError("partition is too short for the tile splashback")
    return along


def _add_interior_cladding(
    ifc_file: ifcopenshell.file,
    *,
    wall: ifcopenshell.entity_instance,
    name: str,
    thickness: float,
) -> ifcopenshell.entity_instance:
    """Add a tile splashback on the neighbour-room face of the partition.

    That face reads in the default isometric (+X,+Y,+Z); the primary-room face
    would sit on the far side of the wall and stay hidden. The shield is a
    limited panel (not full wall height), with a schematic washbasin in front.
    """
    body_context = get_body_context(ifc_file)
    storey = element_util.get_container(wall)
    if storey is None:
        raise ValueError("partition wall has no storey container")

    (ox, oy, _oz), length, _height = _wall_origin_length_height(wall)
    along = _splash_along(length)
    # Partition origin is the neighbour face; thickness grows world −X.
    # Cladding sits proud on the neighbour side (same pattern as exterior).
    face_x = ox + CLADDING_GAP + thickness
    clad_origin = (face_x, oy + along, SPLASH_SILL)
    covering = add_vertical_covering(
        ifc_file,
        name=name,
        body_context=body_context,
        storey=storey,
        origin=clad_origin,
        length=SPLASH_WIDTH,
        height=SPLASH_HEIGHT,
        thickness=thickness,
        direction_xy=(0.0, 1.0),
        predefined_type="CLADDING",
    )
    _add_schematic_washbasin(
        ifc_file,
        body_context=body_context,
        storey=storey,
        face_x=face_x,
        center_y=oy + along + SPLASH_WIDTH * 0.5,
    )
    return covering


def _add_schematic_washbasin(
    ifc_file: ifcopenshell.file,
    *,
    body_context: ifcopenshell.entity_instance,
    storey: ifcopenshell.entity_instance,
    face_x: float,
    center_y: float,
) -> None:
    """Single wall-hung box in front of the splash (+X, camera side)."""
    x0 = face_x + BASIN_GAP
    y0 = center_y - BASIN_WIDTH * 0.5
    y1 = center_y + BASIN_WIDTH * 0.5
    x1 = x0 + BASIN_DEPTH

    basin = add_extruded_product(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name="Waschbecken",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(x0, y0, x1, y1),
        thickness=BASIN_HEIGHT,
        z_bottom=BASIN_RIM_Z - BASIN_HEIGHT,
        predefined_type="USERDEFINED",
    )
    basin.ObjectType = "Waschbecken"


def _add_parallel_wall_on_flooring(
    ifc_file: ifcopenshell.file,
    *,
    wall: ifcopenshell.entity_instance,
    name: str,
    predefined_type: str,
    offset: float = PARALLEL_WALL_OFFSET,
    end_inset: float = PARALLEL_WALL_END_INSET,
    thickness: float = PARALLEL_WALL_THICKNESS,
) -> ifcopenshell.entity_instance:
    """Add a parallel partition with its base at finished-floor level."""
    body_context = get_body_context(ifc_file)
    storey = element_util.get_container(wall)
    if storey is None:
        raise ValueError("partition wall has no storey container")

    (ox, oy, oz), length, height = _wall_origin_length_height(wall)
    top_z = oz + height
    finished_floor_z = 0.0
    parallel_length = length - 2.0 * end_inset
    if parallel_length <= 0:
        raise ValueError("partition is too short for the parallel wall")

    return add_wall(
        ifc_file,
        name=name,
        body_context=body_context,
        storey=storey,
        origin=(
            ox + offset,
            oy + end_inset,
            finished_floor_z,
        ),
        length=parallel_length,
        height=top_z - finished_floor_z,
        thickness=thickness,
        direction_xy=(0.0, 1.0),
        predefined_type=predefined_type,
    )


def _wall_thickness(wall: ifcopenshell.entity_instance) -> float:
    """Recover extruded thickness (local +Y) from the wall Body."""
    for rep in wall.Representation.Representations:
        for item in rep.Items:
            if not item.is_a("IfcExtrudedAreaSolid"):
                continue
            profile = item.SweptArea
            if profile.is_a("IfcArbitraryClosedProfileDef"):
                ys = [float(p.Coordinates[1]) for p in profile.OuterCurve.Points]
                if ys:
                    return max(ys) - min(ys)
    return PARALLEL_WALL_THICKNESS


def _add_drywall_reinforcement(
    ifc_file: ifcopenshell.file,
    *,
    wall: ifcopenshell.entity_instance,
    name: str,
) -> ifcopenshell.entity_instance:
    """Add one backing panel centred inside ``wall``.

    Wall thickness grows world −X from the camera-facing face. The panel stays
    a limited rectangle within that thickness, not a second wall.
    """
    from ifcopenshell.api.geometry import assign_representation, edit_object_placement
    from ifcopenshell.api.root import create_entity
    from ifcopenshell.api.spatial import assign_container

    from generators.parts import axis_placement_matrix, create_body_representation
    from generators.wall import vertical_body_solids_with_openings

    body_context = get_body_context(ifc_file)
    storey = element_util.get_container(wall)
    if storey is None:
        raise ValueError("partition wall has no storey container")

    (ox, oy, _oz), length, _height = _wall_origin_length_height(wall)
    wall_thickness = _wall_thickness(wall)
    if REINF_THICKNESS > wall_thickness + 1e-6:
        raise ValueError("drywall reinforcement is thicker than the host wall")
    along = length - REINF_END_INSET - REINF_WIDTH
    if along < 0.15:
        along = max(0.0, (length - REINF_WIDTH) * 0.5)
    if along + REINF_WIDTH > length + 1e-6:
        raise ValueError("partition is too short for the drywall reinforcement")
    # Centre the panel in the wall: local +Y (thickness) is world −X.
    face_inset = (wall_thickness - REINF_THICKNESS) * 0.5

    panel = create_entity(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name=name,
        predefined_type="USERDEFINED",
    )
    assign_container(ifc_file, relating_structure=storey, products=[panel])
    edit_object_placement(
        ifc_file,
        product=panel,
        matrix=axis_placement_matrix(
            (ox - face_inset, oy + along, REINF_SILL),
            local_x=(0.0, 1.0, 0.0),
            local_z=(0.0, 0.0, 1.0),
        ),
    )
    solids = vertical_body_solids_with_openings(
        ifc_file,
        length=REINF_WIDTH,
        height=REINF_HEIGHT,
        thickness=REINF_THICKNESS,
    )
    representation = create_body_representation(ifc_file, body_context, solids)
    assign_representation(ifc_file, product=panel, representation=representation)
    return panel


def _apply_product_attrs(
    ifc_file: ifcopenshell.file,
    primary: ifcopenshell.entity_instance,
    params: dict[str, Any],
) -> None:
    name = params.get("name") or params.get("Name")
    if name:
        primary.Name = str(name)

    predefined_type = params.get("predefined_type") or params.get("PredefinedType")
    if predefined_type is not None and hasattr(primary, "PredefinedType"):
        primary.PredefinedType = str(predefined_type)

    object_type = params.get("object_type") or params.get("ObjectType")
    if object_type is not None and hasattr(primary, "ObjectType"):
        primary.ObjectType = str(object_type)

    for qto_name, props in (params.get("quantities") or {}).items():
        assign_qto(ifc_file, primary, qto_name, props)

    property_datatypes = params.get("property_datatypes") or {}
    for pset_name, props in (params.get("properties") or {}).items():
        assign_pset(
            ifc_file,
            primary,
            pset_name,
            props,
            datatypes=property_datatypes.get(pset_name),
        )


def generate_interior_fabric(
    params: dict[str, Any],
) -> (
    tuple[ifcopenshell.file, ifcopenshell.entity_instance]
    | tuple[
        ifcopenshell.file,
        ifcopenshell.entity_instance,
        list[ifcopenshell.entity_instance],
    ]
):
    """Build the interior-space fabric without spaces; accent wall, cladding, reinforcement, door, or window.

    ``accent`` is ``wall``, ``cladding``, ``reinforcement``, ``door``, or ``window``.
    Geometry matches the Innenräume vignette with an open top so the partition
    reads clearly; attributes come from the element YAML.
    The reinforcement accent returns the host wall as a third value so the
    preview can draw it dotted and see-through.
    """
    from generators.space import generate_space

    space_params = dict(params.get("space_params") or {})
    if not space_params:
        raise ValueError("space_params is required (reuse the interior-space vignette)")
    space_params.setdefault("with_context", True)
    space_params["omit_primary_space"] = True
    space_params["include_neighbor_space"] = False
    space_params["include_ceiling_covering"] = False
    space_params["include_ceiling_slab"] = False

    accent = str(params.get("accent") or "wall").lower()
    if accent not in {"wall", "cladding", "reinforcement", "door", "window"}:
        raise ValueError(
            "unsupported accent="
            f"{accent!r}; expected wall, cladding, reinforcement, door, or window"
        )

    ifc_file, handle = generate_space(space_params)

    if accent == "door":
        primary = _find_interior_door(ifc_file)
    elif accent == "window":
        primary = _find_interior_window(ifc_file)
    else:
        wall = handle if handle.is_a("IfcWall") else _find_partition_wall(ifc_file)
        if accent == "cladding":
            clad_t = float(params.get("cladding_thickness") or DEFAULT_CLADDING_THICKNESS)
            clad_name = str(params.get("name") or params.get("Name") or "WB-01")
            primary = _add_interior_cladding(
                ifc_file, wall=wall, name=clad_name, thickness=clad_t
            )
        elif accent == "reinforcement" or space_params.get("parallel_wall_on_flooring"):
            wall_name = (
                "IW-01"
                if accent == "reinforcement"
                else str(params.get("name") or params.get("Name") or "IW-01")
            )
            wall_type = (
                "PARTITIONING"
                if accent == "reinforcement"
                else str(
                    params.get("predefined_type")
                    or params.get("PredefinedType")
                    or "PARTITIONING"
                )
            )
            host = _add_parallel_wall_on_flooring(
                ifc_file,
                wall=wall,
                name=wall_name,
                predefined_type=wall_type,
                offset=float(
                    space_params.get("parallel_wall_offset", PARALLEL_WALL_OFFSET)
                ),
                end_inset=float(
                    space_params.get(
                        "parallel_wall_end_inset", PARALLEL_WALL_END_INSET
                    )
                ),
                thickness=float(
                    space_params.get(
                        "parallel_wall_thickness", PARALLEL_WALL_THICKNESS
                    )
                ),
            )
            if accent == "reinforcement":
                panel_name = str(params.get("name") or params.get("Name") or "TV-01")
                primary = _add_drywall_reinforcement(
                    ifc_file, wall=host, name=panel_name
                )
                _apply_product_attrs(ifc_file, primary, params)
                return ifc_file, primary, [host]
            primary = host
        else:
            primary = wall

    _apply_product_attrs(ifc_file, primary, params)
    return ifc_file, primary
