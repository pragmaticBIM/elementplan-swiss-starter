"""Map pragmaticBIM catalog instance dicts to generator params."""

from __future__ import annotations

import math
from typing import Any, Callable

from catalog.schema import (
    BEAM_DEFAULTS,
    BEAM_ELEMENT_SLUG,
    BUILDING_ELEMENT_SLUG,
    BUILDING_DEFAULTS,
    CEILING_DEFAULTS,
    CEILING_ELEMENT_SLUG,
    CLADDING_EXTERIOR_DEFAULTS,
    CLADDING_EXTERIOR_ELEMENT_SLUG,
    CLADDING_INTERIOR_DEFAULTS,
    CLADDING_INTERIOR_ELEMENT_SLUG,
    COORDINATION_ZONE_DEFAULTS,
    COORDINATION_ZONE_ELEMENT_SLUG,
    DEFAULT_STOREY_NAMES,
    DETAIL_REFERENCE_DEFAULTS,
    DETAIL_REFERENCE_ELEMENT_SLUG,
    DOOR_EXTERIOR_DEFAULTS,
    DOOR_EXTERIOR_ELEMENT_SLUG,
    DOOR_INTERIOR_DEFAULTS,
    DOOR_INTERIOR_ELEMENT_SLUG,
    DRYWALL_REINFORCEMENT_DEFAULTS,
    DRYWALL_REINFORCEMENT_ELEMENT_SLUG,
    EXTERIOR_SPACE_ELEMENT_SLUG,
    FLOOR_COVERING_DEFAULTS,
    FLOOR_COVERING_ELEMENT_SLUG,
    FLOOR_COVERING_EXTERIOR_DEFAULTS,
    FLOOR_COVERING_EXTERIOR_ELEMENT_SLUG,
    COLUMN_DEFAULTS,
    COLUMN_ELEMENT_SLUG,
    FOOTING_DEFAULTS,
    FOOTING_ELEMENT_SLUG,
    GROSS_VOLUME_ELEMENT_SLUG,
    MAINTENANCE_SPACE_DEFAULTS,
    MAINTENANCE_SPACE_ELEMENT_SLUG,
    INSTALLATION_PATH_DEFAULTS,
    INSTALLATION_PATH_ELEMENT_SLUG,
    TURNING_RADIUS_DEFAULTS,
    TURNING_RADIUS_ELEMENT_SLUG,
    DECISION_VOLUME_DEFAULTS,
    DECISION_VOLUME_ELEMENT_SLUG,
    MOVEMENT_CLEARANCE_DEFAULTS,
    MOVEMENT_CLEARANCE_ELEMENT_SLUG,
    BUILDING_LAW_PARCEL_DEFAULTS,
    BUILDING_LAW_PARCEL_ELEMENT_SLUG,
    SURROUNDING_BUILDING_DEFAULTS,
    SURROUNDING_BUILDING_ELEMENT_SLUG,
    CONSTRUCTION_LOGISTICS_DEFAULTS,
    CONSTRUCTION_LOGISTICS_ELEMENT_SLUG,
    PLANNING_CONSTRAINT_DEFAULTS,
    PLANNING_CONSTRAINT_ELEMENT_SLUG,
    UMBAU_PERIMETER_DEFAULTS,
    UMBAU_PERIMETER_ELEMENT_SLUG,
    TREE_DEFAULTS,
    TREE_ELEMENT_SLUG,
    HUMUS_DEFAULTS,
    HUMUS_ELEMENT_SLUG,
    TREE_PIT_DEFAULTS,
    TREE_PIT_ELEMENT_SLUG,
    RETENTION_DEFAULTS,
    RETENTION_ELEMENT_SLUG,
    BUILT_IN_FURNITURE_DEFAULTS,
    BUILT_IN_FURNITURE_ELEMENT_SLUG,
    FURNITURE_DEFAULTS,
    FURNITURE_ELEMENT_SLUG,
    ROOF_PITCHED_DEFAULTS,
    ROOF_PITCHED_ELEMENT_SLUG,
    ROOFING_DEFAULTS,
    ROOFING_ELEMENT_SLUG,
    RAILING_DEFAULTS,
    RAILING_ELEMENT_SLUG,
    SHADING_DEVICE_DEFAULTS,
    SHADING_DEVICE_ELEMENT_SLUG,
    GROSS_VOLUME_UNIT_DEFAULTS,
    LUFTRAUM_ELEMENT_SLUG,
    OPENING_DEFAULTS,
    OPENING_ELEMENT_SLUG,
    PARKING_ELEMENT_SLUG,
    ELEVATOR_ELEMENT_SLUG,
    VORSATZSCHALE_ELEMENT_SLUG,
    PROJECT_ELEMENT_SLUG,
    PROJECT_DEFAULTS,
    SITE_ELEMENT_SLUG,
    SITE_DEFAULTS,
    SLAB_BASE_DEFAULTS,
    SLAB_BASE_ELEMENT_SLUG,
    SLAB_BALCONY_DEFAULTS,
    SLAB_BALCONY_ELEMENT_SLUG,
    SLAB_FLOOR_DEFAULTS,
    SLAB_FLOOR_ELEMENT_SLUG,
    SLAB_ROOF_DEFAULTS,
    SLAB_ROOF_ELEMENT_SLUG,
    SPACE_ELEMENT_SLUG,
    STAIR_DEFAULTS,
    STAIR_ELEMENT_SLUG,
    STOREY_ELEMENT_SLUG,
    WALL_EXTERIOR_DEFAULTS,
    WALL_EXTERIOR_ELEMENT_SLUG,
    WALL_INTERIOR_DEFAULTS,
    WALL_INTERIOR_ELEMENT_SLUG,
    WALL_INTERIOR_LB_DEFAULTS,
    WALL_INTERIOR_LB_ELEMENT_SLUG,
    WINDOW_EXTERIOR_DEFAULTS,
    WINDOW_EXTERIOR_ELEMENT_SLUG,
    WINDOW_INTERIOR_DEFAULTS,
    WINDOW_INTERIOR_ELEMENT_SLUG,
    build_element_attributes_from_yaml,
    build_interior_context_attributes,
    build_luftraum_lower_attributes,
    build_luftraum_upper_attributes,
    build_neighbor_space_attributes,
    build_space_attributes_from_yaml,
    exterior_space_defaults,
    luftraum_defaults,
    parking_defaults,
    elevator_defaults,
    vorsatzschale_defaults,
    roof_attic_space_defaults,
)
from generators.beam import generate_beam
from generators.covering import generate_covering
from generators.detail_reference import generate_detail_references
from generators.exterior_fabric import generate_exterior_fabric
from generators.interior_fabric import (
    DEFAULT_CLADDING_THICKNESS as INTERIOR_CLADDING_THICKNESS,
    PARALLEL_WALL_THICKNESS,
    REINF_HEIGHT,
    REINF_WIDTH,
    SPLASH_HEIGHT,
    SPLASH_WIDTH,
    generate_interior_fabric,
)
from generators.footing import (
    DEFAULT_COLUMN_DEPTH,
    DEFAULT_COLUMN_HEIGHT,
    DEFAULT_COLUMN_WIDTH,
    DEFAULT_FOOTING_DEPTH,
    DEFAULT_FOOTING_THICKNESS,
    DEFAULT_FOOTING_WIDTH,
    DEFAULT_SLAB_DEPTH,
    DEFAULT_SLAB_THICKNESS as FOOTING_VIGNETTE_SLAB_THICKNESS,
    DEFAULT_SLAB_WIDTH,
    generate_footing,
)
from generators.maintenance_space import (
    DEFAULT_CUBE_DEPTH,
    DEFAULT_CUBE_HEIGHT,
    DEFAULT_CUBE_WIDTH,
    DEFAULT_FILTER_LENGTH,
    DEFAULT_MAINTENANCE_DEPTH,
    DEFAULT_MAINTENANCE_HEIGHT,
    DEFAULT_SLAB_PADDING,
    DEFAULT_SLAB_THICKNESS as MAINT_SLAB_THICKNESS,
    generate_maintenance_space,
)
from generators.installation_path import (
    DEFAULT_CORRIDOR_WIDTH,
    DEFAULT_DOOR_WIDTH,
    DEFAULT_LEG_A,
    DEFAULT_LEG_B,
    DEFAULT_PATH_HEIGHT,
    DEFAULT_PATH_OVERSHOOT,
    DEFAULT_PATH_WIDTH,
    DEFAULT_SLAB_PADDING as INSTALL_SLAB_PADDING,
    DEFAULT_WALL_HEIGHT as INSTALL_WALL_HEIGHT,
    DEFAULT_COLUMN_SIZE,
    generate_installation_path,
)
from generators.decision_volume import (
    DEFAULT_PLAN_DEPTH as DECISION_PLAN_DEPTH,
    DEFAULT_PLAN_WIDTH as DECISION_PLAN_WIDTH,
    DEFAULT_WALL_HEIGHT as DECISION_WALL_HEIGHT,
    generate_decision_volume,
)
from generators.movement_clearance import generate_movement_clearance
from generators.turning_radius import (
    DEFAULT_APPROACH,
    DEFAULT_ARC_SEGMENTS,
    DEFAULT_CUBE_SIZE,
    DEFAULT_ENVELOPE_SIMPLIFY,
    DEFAULT_NOSE_LENGTH,
    DEFAULT_POSE_COUNT,
    DEFAULT_PROXY_HEIGHT,
    DEFAULT_PROXY_INNER_MID,
    DEFAULT_PROXY_OUTER,
    DEFAULT_SLAB_PADDING as TURN_SLAB_PADDING,
    DEFAULT_STREET_CLEARANCE,
    DEFAULT_STREET_WIDTH,
    DEFAULT_TURN_ANGLE_DEG,
    DEFAULT_VEHICLE_LENGTH,
    DEFAULT_VEHICLE_WIDTH,
    generate_turning_radius,
)
from generators.building_law_parcel import (
    DEFAULT_PARCEL_A_WIDTH,
    DEFAULT_PARCEL_B_WIDTH,
    DEFAULT_PARCEL_BOTTOM,
    DEFAULT_PARCEL_C_WIDTH,
    DEFAULT_PARCEL_DEPTH,
    DEFAULT_PARCEL_TOP,
    DEFAULT_PLOT_THICKNESS as PARCEL_PLOT_THICKNESS,
    DEFAULT_SURFACE_MARGIN,
    generate_building_law_parcel,
)
from generators.surrounding_building import (
    DEFAULT_GAP as NEIGHBOR_GAP,
    DEFAULT_NEIGHBOR_SPECS,
    DEFAULT_PLOT_THICKNESS as NEIGHBOR_PLOT_THICKNESS,
    DEFAULT_PROJECT_DEPTH,
    DEFAULT_PROJECT_HEIGHT,
    DEFAULT_PROJECT_WIDTH,
    generate_surrounding_building,
)
from generators.construction_logistics import (
    DEFAULT_BUILDING_DEPTH as LOG_BUILDING_DEPTH,
    DEFAULT_BUILDING_HEIGHT as LOG_BUILDING_HEIGHT,
    DEFAULT_BUILDING_WIDTH as LOG_BUILDING_WIDTH,
    DEFAULT_CONTAINER_DEPTH,
    DEFAULT_CONTAINER_HEIGHT,
    DEFAULT_CONTAINER_WIDTH,
    DEFAULT_CRANE_HEIGHT,
    DEFAULT_CRANE_JIB_HEIGHT,
    DEFAULT_CRANE_JIB_LENGTH,
    DEFAULT_CRANE_JIB_WIDTH,
    DEFAULT_CRANE_MAST,
    DEFAULT_CRANE_PAD,
    DEFAULT_CRANE_PAD_THICKNESS,
    DEFAULT_FENCE_HEIGHT,
    DEFAULT_FENCE_THICKNESS,
    DEFAULT_PLOT_THICKNESS as LOG_PLOT_THICKNESS,
    DEFAULT_STORAGE_DEPTH,
    DEFAULT_STORAGE_HEIGHT,
    DEFAULT_STORAGE_WIDTH,
    DEFAULT_YARD_DEPTH,
    DEFAULT_YARD_SIDE,
    generate_construction_logistics,
)
from generators.planning_constraint import (
    DEFAULT_BUILDING_DEPTH as CONSTRAINT_BUILDING_DEPTH,
    DEFAULT_BUILDING_HEIGHT as CONSTRAINT_BUILDING_HEIGHT,
    DEFAULT_BUILDING_WIDTH as CONSTRAINT_BUILDING_WIDTH,
    DEFAULT_FLIGHT_DEPTH as CONSTRAINT_FLIGHT_DEPTH,
    DEFAULT_FLIGHT_HEIGHT as CONSTRAINT_FLIGHT_HEIGHT,
    DEFAULT_FLIGHT_WIDTH as CONSTRAINT_FLIGHT_WIDTH,
    DEFAULT_FLOOD_HEIGHT,
    DEFAULT_PLOT_THICKNESS as CONSTRAINT_PLOT_THICKNESS,
    DEFAULT_RAIL_HEIGHT,
    DEFAULT_RAIL_WIDTH,
    DEFAULT_YARD as CONSTRAINT_YARD,
    generate_planning_constraint,
)
from generators.umbau_perimeter import (
    DEFAULT_PERIMETER_HEIGHT,
    DEFAULT_PLAN_DEPTH as UMBAU_PLAN_DEPTH,
    DEFAULT_PLAN_WIDTH as UMBAU_PLAN_WIDTH,
    DEFAULT_SLAB_THICKNESS as UMBAU_SLAB_THICKNESS,
    DEFAULT_SPLIT_X as UMBAU_SPLIT_X,
    DEFAULT_WALL_HEIGHT as UMBAU_WALL_HEIGHT,
    DEFAULT_WALL_THICKNESS as UMBAU_WALL_THICKNESS,
    generate_umbau_perimeter,
)
from generators.stair import (
    DEFAULT_FLIGHT_RUN,
    DEFAULT_FLIGHT_WIDTH,
    DEFAULT_LANDING_DEPTH,
    DEFAULT_STEP_COUNT,
    DEFAULT_STOREY_HEIGHT,
    DEFAULT_TREAD_THICKNESS,
    DEFAULT_WAIST_THICKNESS,
    DEFAULT_WALL_THICKNESS,
    generate_stair,
)
from generators.railing import (
    DEFAULT_BALCONY_DEPTH as RAILING_BALCONY_DEPTH,
    DEFAULT_RAILING_HEIGHT,
    DEFAULT_RAILING_LENGTH,
    DEFAULT_RAILING_THICKNESS,
    generate_railing,
)
from generators.shading import (
    DEFAULT_CANTILEVER,
    DEFAULT_LAMELLA_COUNT,
    DEFAULT_LAMELLA_HEIGHT,
    generate_shading,
)
from generators.tree import (
    DEFAULT_CROWN_RADIUS,
    DEFAULT_ROOT_RADIUS,
    DEFAULT_TRUNK_HEIGHT,
    DEFAULT_TRUNK_RADIUS,
    generate_tree,
)
from generators.humus import (
    DEFAULT_LAYER_LENGTH,
    DEFAULT_LAYER_THICKNESS,
    DEFAULT_LAYER_WIDTH,
    generate_humus,
)
from generators.tree_pit import (
    DEFAULT_PIT_DEPTH,
    DEFAULT_PIT_LENGTH,
    DEFAULT_PIT_WIDTH,
    generate_tree_pit,
)
from generators.retention import (
    DEFAULT_BASIN_DEPTH,
    DEFAULT_BASIN_LENGTH,
    DEFAULT_BASIN_WIDTH,
    generate_retention,
)
from generators.furniture import (
    DEFAULT_CHAIR_DEPTH,
    DEFAULT_CHAIR_WIDTH,
    DEFAULT_ROOM_DEPTH as FURNITURE_ROOM_DEPTH,
    DEFAULT_ROOM_WIDTH as FURNITURE_ROOM_WIDTH,
    DEFAULT_SLAB_THICKNESS as FURNITURE_SLAB_THICKNESS,
    DEFAULT_TABLE_DEPTH,
    DEFAULT_TABLE_HEIGHT,
    DEFAULT_TABLE_WIDTH,
    DEFAULT_WALL_HEIGHT as FURNITURE_WALL_HEIGHT,
    generate_built_in_furniture,
    generate_furniture,
)
from generators.coordination_zone import (
    DEFAULT_ZONE_HEIGHT,
    DEFAULT_ZONE_MARGIN,
    generate_coordination_zone,
)
from generators.roof import (
    DEFAULT_DEPTH as ROOF_DEFAULT_DEPTH,
    DEFAULT_EAVE_HEIGHT,
    DEFAULT_FLOOR_THICKNESS as ROOF_FLOOR_THICKNESS,
    DEFAULT_INTERMEDIATE_SLAB_ELEVATION,
    DEFAULT_RISE,
    DEFAULT_ROOF_THICKNESS,
    DEFAULT_WIDTH as ROOF_DEFAULT_WIDTH,
    generate_pitched_roof,
    pitched_roof_gross_area,
)
from generators.roofing import (
    DEFAULT_PARAPET_HEIGHT,
    DEFAULT_PARAPET_THICKNESS,
    DEFAULT_ROOFING_EDGE_INSET,
    DEFAULT_ROOFING_THICK_END,
    DEFAULT_ROOFING_THICK_START,
    DEFAULT_SLAB_DEPTH as ROOFING_SLAB_DEPTH,
    DEFAULT_SLAB_THICKNESS as ROOFING_SLAB_THICKNESS,
    DEFAULT_SLAB_WIDTH as ROOFING_SLAB_WIDTH,
    generate_roofing,
)
from generators.gross_volume import generate_gross_volumes
from generators.luftraum import (
    BEAM_DEPTH,
    BEAM_WIDTH,
    OVERHANG_INTO_LUFTRAUM,
    TOP_SLAB_RAISE,
    generate_luftraum,
)
from generators.opening import generate_opening
from generators.parking import (
    DEFAULT_BAY_COUNT,
    DEFAULT_BAY_DEPTH,
    DEFAULT_BAY_WIDTH,
    DEFAULT_PARKING_HEIGHT,
    generate_parking,
)
from generators.elevator import (
    DEFAULT_HEIGHT as ELEVATOR_DEFAULT_HEIGHT,
    DEFAULT_SHAFT_DEPTH,
    DEFAULT_SHAFT_WIDTH,
    generate_elevator,
)
from generators.vorsatzschale import (
    DEFAULT_FACING_THICKNESS,
    DEFAULT_GAP,
    DEFAULT_HEIGHT as VORSATZ_DEFAULT_HEIGHT,
    DEFAULT_ROOM_DEPTH,
    DEFAULT_ROOM_WIDTH,
    generate_vorsatzschale,
)
from generators.reference_point import (
    DEFAULT_ORIGIN_LV95,
    generate_reference_points,
)
from generators.space import (
    CEILING_SLAB_THICKNESS,
    DOOR_HEIGHT,
    DOOR_WIDTH,
    FLOOR_COVERING_THICKNESS,
    NEIGHBOR_SPACE_WIDTH,
    EXTERIOR_WALL_THICKNESS,
    WALL_THICKNESS,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    generate_space,
)
from generators.spatial_structure import (
    DEFAULT_BALCONY_DEPTH,
    DEFAULT_BALCONY_WIDTH,
    DEFAULT_BUILDING_DEPTH,
    DEFAULT_BUILDING_WIDTH,
    DEFAULT_SLAB_THICKNESS,
    generate_spatial_structure,
)

# Dispatch table — extend when more element generators land.
ELEMENT_GENERATORS: dict[str, Callable[[dict[str, Any]], tuple]] = {
    "IfcSpace": generate_space,
    "SPACE-INT": generate_space,
    "SPACE-EXT": generate_space,
    "SPACE-PARK": generate_parking,
    "SPACE-ELEVATOR": generate_elevator,
    "SPACE-VORSATZ": generate_vorsatzschale,
    "SPACE-AIR": generate_luftraum,
    "IfcCovering": generate_covering,
    "ARC-CEILING": generate_covering,
    "ARC-FLOOR-COV": generate_covering,
    "ARC-FLOOR-COV-EXT": generate_covering,
    "SPACE-GROSS": generate_gross_volumes,
    "Bezugspunkt": generate_reference_points,
    "SURVEY-REF": generate_reference_points,
    "IfcProject": generate_spatial_structure,
    "PROJECT": generate_spatial_structure,
    "IfcSite": generate_spatial_structure,
    "SITE": generate_spatial_structure,
    "IfcBuilding": generate_spatial_structure,
    "BUILDING": generate_spatial_structure,
    "IfcBuildingStorey": generate_spatial_structure,
    "STOREY": generate_spatial_structure,
    "IfcSlab": generate_spatial_structure,
    "ARC-SLAB-BASE": generate_spatial_structure,
    "ARC-SLAB-FLOOR": generate_spatial_structure,
    "ARC-ROOF-FLAT": generate_spatial_structure,
    "ARC-SLAB-BALCONY": generate_spatial_structure,
    "IfcOpeningElement": generate_opening,
    "ARC-OPENING-VOID": generate_opening,
    "IfcFooting": generate_footing,
    "ARC-FOOTING": generate_footing,
    "IfcColumn": generate_footing,
    "ARC-COLUMN": generate_footing,
    "ARC-MAINT-SPACE": generate_maintenance_space,
    "ARC-INSTALL-PATH": generate_installation_path,
    "ARC-TURN-RAD": generate_turning_radius,
    "ARC-DEC-VOL": generate_decision_volume,
    "ARC-MOVEMENT-CLEARANCE": generate_movement_clearance,
    "ARC-PARCEL": generate_building_law_parcel,
    "ARC-UMG-NEIGHBOR": generate_surrounding_building,
    "ARC-SITE-LOG": generate_construction_logistics,
    "ARC-CONSTRAINT": generate_planning_constraint,
    "ARC-UMBAU-PER": generate_umbau_perimeter,
    "ARC-STAIR": generate_stair,
    "IfcStair": generate_stair,
    "ARC-RAILING": generate_railing,
    "IfcRailing": generate_railing,
    "ARC-SHADING": generate_shading,
    "IfcShadingDevice": generate_shading,
    "LAN-TREE": generate_tree,
    "LAN-HUMUS": generate_humus,
    "LAN-TREEPIT": generate_tree_pit,
    "LAN-RETENTION": generate_retention,
    "FURN": generate_furniture,
    "IfcFurniture": generate_furniture,
    "ARC-FURN-BUILTIN": generate_built_in_furniture,
    "ARC-COORD-ZONE": generate_coordination_zone,
    "IfcBeam": generate_beam,
    "ARC-BEAM": generate_beam,
    "IfcRoof": generate_pitched_roof,
    "ARC-ROOF-PITCH": generate_pitched_roof,
    "ARC-ROOF-DRAIN": generate_roofing,
    "IfcWall": generate_exterior_fabric,
    "ARC-WALL-EXT": generate_exterior_fabric,
    "ARC-WALL-CLAD-EXT": generate_exterior_fabric,
    "ARC-WALL-INT": generate_interior_fabric,
    "ARC-WALL-INT-LB": generate_interior_fabric,
    "ARC-WALL-CLAD": generate_interior_fabric,
    "ARC-DRYWALL-REINF": generate_interior_fabric,
    "IfcDoor": generate_exterior_fabric,
    "ARC-DOOR-EXT": generate_exterior_fabric,
    "ARC-DOOR-INT": generate_interior_fabric,
    "IfcWindow": generate_exterior_fabric,
    "ARC-WINDOW-EXT": generate_exterior_fabric,
    "ARC-WINDOW-INT": generate_interior_fabric,
    "ARC-DET-REF": generate_detail_references,
    "Detailverweis": generate_detail_references,
}

SPACE_TYPES = frozenset({"IfcSpace", "SPACE-INT"})
EXTERIOR_SPACE_TYPES = frozenset({"SPACE-EXT"})
PARKING_TYPES = frozenset({"SPACE-PARK"})
ELEVATOR_TYPES = frozenset({"SPACE-ELEVATOR"})
VORSATZSCHALE_TYPES = frozenset({"SPACE-VORSATZ"})
LUFTRAUM_TYPES = frozenset({"SPACE-AIR"})
COVERING_TYPES = frozenset({"IfcCovering", "ARC-CEILING", "ARC-FLOOR-COV", "ARC-FLOOR-COV-EXT"})
CEILING_COVERING_TYPES = frozenset({"IfcCovering", "ARC-CEILING"})
FLOOR_COVERING_TYPES = frozenset({"ARC-FLOOR-COV"})
FLOOR_COVERING_EXTERIOR_TYPES = frozenset({"ARC-FLOOR-COV-EXT"})
GROSS_VOLUME_TYPES = frozenset({"SPACE-GROSS"})
REFERENCE_POINT_TYPES = frozenset({"Bezugspunkt", "SURVEY-REF"})
SPATIAL_STRUCTURE_TYPES = frozenset(
    {
        "IfcProject",
        "PROJECT",
        "IfcSite",
        "SITE",
        "IfcBuilding",
        "BUILDING",
        "IfcBuildingStorey",
        "STOREY",
    }
)
SLAB_TYPES = frozenset(
    {
        "IfcSlab",
        "ARC-SLAB-BASE",
        "ARC-SLAB-FLOOR",
        "ARC-ROOF-FLAT",
        "ARC-SLAB-BALCONY",
    }
)
OPENING_TYPES = frozenset({"IfcOpeningElement", "ARC-OPENING-VOID"})
FOOTING_TYPES = frozenset({"IfcFooting", "ARC-FOOTING"})
COLUMN_TYPES = frozenset({"IfcColumn", "ARC-COLUMN"})
MAINTENANCE_SPACE_TYPES = frozenset({"ARC-MAINT-SPACE"})
INSTALLATION_PATH_TYPES = frozenset({"ARC-INSTALL-PATH"})
TURNING_RADIUS_TYPES = frozenset({"ARC-TURN-RAD"})
DECISION_VOLUME_TYPES = frozenset({"ARC-DEC-VOL"})
MOVEMENT_CLEARANCE_TYPES = frozenset({"ARC-MOVEMENT-CLEARANCE"})
BUILDING_LAW_PARCEL_TYPES = frozenset({"ARC-PARCEL"})
SURROUNDING_BUILDING_TYPES = frozenset({"ARC-UMG-NEIGHBOR"})
CONSTRUCTION_LOGISTICS_TYPES = frozenset({"ARC-SITE-LOG"})
PLANNING_CONSTRAINT_TYPES = frozenset({"ARC-CONSTRAINT"})
UMBAU_PERIMETER_TYPES = frozenset({"ARC-UMBAU-PER"})
STAIR_TYPES = frozenset({"ARC-STAIR", "IfcStair"})
RAILING_TYPES = frozenset({"ARC-RAILING", "IfcRailing"})
SHADING_DEVICE_TYPES = frozenset({"ARC-SHADING", "IfcShadingDevice"})
TREE_TYPES = frozenset({"LAN-TREE"})
HUMUS_TYPES = frozenset({"LAN-HUMUS"})
TREE_PIT_TYPES = frozenset({"LAN-TREEPIT"})
RETENTION_TYPES = frozenset({"LAN-RETENTION"})
FURNITURE_TYPES = frozenset({"FURN", "IfcFurniture", "ARC-FURN-BUILTIN"})
COORDINATION_ZONE_TYPES = frozenset({"ARC-COORD-ZONE"})
BEAM_TYPES = frozenset({"IfcBeam", "ARC-BEAM"})
ROOF_PITCHED_TYPES = frozenset({"IfcRoof", "ARC-ROOF-PITCH"})
ROOFING_TYPES = frozenset({"ARC-ROOF-DRAIN"})
EXTERIOR_WALL_TYPES = frozenset({"IfcWall", "ARC-WALL-EXT"})
EXTERIOR_CLADDING_TYPES = frozenset({"ARC-WALL-CLAD-EXT"})
INTERIOR_WALL_TYPES = frozenset({"ARC-WALL-INT"})
INTERIOR_WALL_LB_TYPES = frozenset({"ARC-WALL-INT-LB"})
INTERIOR_CLADDING_TYPES = frozenset({"ARC-WALL-CLAD"})
DRYWALL_REINFORCEMENT_TYPES = frozenset({"ARC-DRYWALL-REINF"})
DOOR_EXTERIOR_TYPES = frozenset({"IfcDoor", "ARC-DOOR-EXT"})
DOOR_INTERIOR_TYPES = frozenset({"ARC-DOOR-INT"})
WINDOW_EXTERIOR_TYPES = frozenset({"IfcWindow", "ARC-WINDOW-EXT"})
WINDOW_INTERIOR_TYPES = frozenset({"ARC-WINDOW-INT"})
DOOR_TYPES = DOOR_EXTERIOR_TYPES | DOOR_INTERIOR_TYPES
WINDOW_TYPES = WINDOW_EXTERIOR_TYPES | WINDOW_INTERIOR_TYPES
INTERIOR_FABRIC_TYPES = (
    INTERIOR_WALL_TYPES
    | INTERIOR_WALL_LB_TYPES
    | INTERIOR_CLADDING_TYPES
    | DRYWALL_REINFORCEMENT_TYPES
    | DOOR_INTERIOR_TYPES
    | WINDOW_INTERIOR_TYPES
)
EXTERIOR_FABRIC_TYPES = (
    EXTERIOR_WALL_TYPES
    | EXTERIOR_CLADDING_TYPES
    | DOOR_EXTERIOR_TYPES
    | WINDOW_EXTERIOR_TYPES
)
DETAIL_REFERENCE_TYPES = frozenset({"ARC-DET-REF", "Detailverweis"})

_HIGHLIGHT_BY_TYPE: dict[str, str] = {
    "IfcProject": "project",
    "PROJECT": "project",
    "IfcSite": "site",
    "SITE": "site",
    "IfcBuilding": "building",
    "BUILDING": "building",
    "IfcBuildingStorey": "storey",
    "STOREY": "storey",
    "IfcSlab": "slab-floor",
    "ARC-SLAB-BASE": "slab-base",
    "ARC-SLAB-FLOOR": "slab-floor",
    "ARC-ROOF-FLAT": "slab-roof",
    "ARC-SLAB-BALCONY": "slab-balcony",
}

_ELEMENT_SLUG_BY_TYPE: dict[str, str] = {
    "IfcSpace": SPACE_ELEMENT_SLUG,
    "SPACE-INT": SPACE_ELEMENT_SLUG,
    "SPACE-EXT": EXTERIOR_SPACE_ELEMENT_SLUG,
    "SPACE-PARK": PARKING_ELEMENT_SLUG,
    "SPACE-ELEVATOR": ELEVATOR_ELEMENT_SLUG,
    "SPACE-VORSATZ": VORSATZSCHALE_ELEMENT_SLUG,
    "SPACE-AIR": LUFTRAUM_ELEMENT_SLUG,
    "IfcCovering": CEILING_ELEMENT_SLUG,
    "ARC-CEILING": CEILING_ELEMENT_SLUG,
    "ARC-FLOOR-COV": FLOOR_COVERING_ELEMENT_SLUG,
    "ARC-FLOOR-COV-EXT": FLOOR_COVERING_EXTERIOR_ELEMENT_SLUG,
    "IfcOpeningElement": OPENING_ELEMENT_SLUG,
    "ARC-OPENING-VOID": OPENING_ELEMENT_SLUG,
    "IfcWall": WALL_EXTERIOR_ELEMENT_SLUG,
    "ARC-WALL-EXT": WALL_EXTERIOR_ELEMENT_SLUG,
    "ARC-WALL-CLAD-EXT": CLADDING_EXTERIOR_ELEMENT_SLUG,
    "ARC-WALL-INT": WALL_INTERIOR_ELEMENT_SLUG,
    "ARC-WALL-INT-LB": WALL_INTERIOR_LB_ELEMENT_SLUG,
    "ARC-WALL-CLAD": CLADDING_INTERIOR_ELEMENT_SLUG,
    "ARC-DRYWALL-REINF": DRYWALL_REINFORCEMENT_ELEMENT_SLUG,
    "IfcDoor": DOOR_EXTERIOR_ELEMENT_SLUG,
    "ARC-DOOR-EXT": DOOR_EXTERIOR_ELEMENT_SLUG,
    "ARC-DOOR-INT": DOOR_INTERIOR_ELEMENT_SLUG,
    "IfcWindow": WINDOW_EXTERIOR_ELEMENT_SLUG,
    "ARC-WINDOW-EXT": WINDOW_EXTERIOR_ELEMENT_SLUG,
    "ARC-WINDOW-INT": WINDOW_INTERIOR_ELEMENT_SLUG,
}


def _shoelace_area(points: list) -> float:
    n = len(points)
    area = 0.0
    for i in range(n):
        x1, y1 = float(points[i][0]), float(points[i][1])
        x2, y2 = float(points[(i + 1) % n][0]), float(points[(i + 1) % n][1])
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def _geometry_from_entry(entry: dict[str, Any]) -> dict[str, float]:
    height = entry.get("height")
    if height is None:
        raise ValueError(f"entry {entry.get('id')!r}: height is required")
    height = float(height)
    if height <= 0:
        raise ValueError("height must be positive")

    boundary = entry.get("boundary")
    if boundary:
        pts = [(float(p[0]), float(p[1])) for p in boundary]
        if pts[0] == pts[-1] and len(pts) > 3:
            pts = pts[:-1]
        area = _shoelace_area(pts)
    else:
        width = entry.get("width")
        depth = entry.get("depth")
        if width is None or depth is None:
            raise ValueError(
                f"entry {entry.get('id')!r}: provide boundary or both width and depth"
            )
        area = float(width) * float(depth)

    return {"height": height, "area": area}


def is_space_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in SPACE_TYPES


def is_covering_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in COVERING_TYPES


def map_space_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a catalog Space instance dict into ``generate_space`` params.

    Attribute / property / quantity values are taken from entry overrides when
    present, otherwise from stable defaults aligned with
    ``elements/spaces-interior.yaml`` value lists (typical office space).
    """
    if not is_space_entry(entry):
        raise ValueError(
            f"unsupported element_type for Space mapping: {entry.get('element_type')!r}"
        )

    geometry = _geometry_from_entry(entry)
    slug = _ELEMENT_SLUG_BY_TYPE[entry["element_type"]]
    resolved = build_space_attributes_from_yaml(
        entry=entry, geometry=geometry, element_slug=slug
    )

    # Neighbour vignette: same height; area recomputed in the generator from its footprint
    neighbor_attrs = build_neighbor_space_attributes(
        geometry={"height": geometry["height"], "area": 15.0},
        element_slug=slug,
    )

    qto = (resolved.get("quantities") or {}).get("Qto_SpaceBaseQuantities") or {}
    finish_ceiling = qto.get("FinishCeilingHeight", entry.get("FinishCeilingHeight", 2.6))

    params: dict[str, Any] = {
        "name": resolved.get("Name") or entry.get("name") or "Space",
        "long_name": resolved.get("LongName") or entry.get("long_name"),
        "predefined_type": resolved.get("PredefinedType") or "INTERNAL",
        "height": geometry["height"],
        "finish_ceiling_height": float(finish_ceiling),
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": resolved.get("quantities") or {},
        "neighbor_attrs": neighbor_attrs,
        "vignette": "interior",
    }

    if entry.get("boundary"):
        params["boundary"] = entry["boundary"]
    else:
        params["width"] = float(entry["width"])
        params["depth"] = float(entry["depth"])

    if entry.get("with_context") is not None:
        params["with_context"] = entry["with_context"]
    if entry.get("include_ceiling_covering") is not None:
        params["include_ceiling_covering"] = entry["include_ceiling_covering"]
    if entry.get("include_ceiling_slab") is not None:
        params["include_ceiling_slab"] = entry["include_ceiling_slab"]
    if entry.get("include_exterior_envelope") is not None:
        params["include_exterior_envelope"] = entry["include_exterior_envelope"]
    if entry.get("include_partition_openings") is not None:
        params["include_partition_openings"] = entry["include_partition_openings"]
    if entry.get("omit_camera_facing_envelope") is not None:
        params["omit_camera_facing_envelope"] = entry["omit_camera_facing_envelope"]

    return params


def is_exterior_space_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in EXTERIOR_SPACE_TYPES


def map_exterior_space_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a catalog exterior-space entry into ``generate_space`` params.

    Primary volume is the balcony (1 m high). Context is half an interior room
    with exterior wall, cladding, openings, and balcony slab.
    """
    if not is_exterior_space_entry(entry):
        raise ValueError(
            f"unsupported element_type for exterior Space mapping: {entry.get('element_type')!r}"
        )

    geometry = _geometry_from_entry(entry)
    slug = _ELEMENT_SLUG_BY_TYPE[entry["element_type"]]
    resolved = build_space_attributes_from_yaml(
        entry=entry,
        geometry=geometry,
        element_slug=slug,
        defaults=exterior_space_defaults(),
    )

    interior_width = float(entry.get("interior_width", 2.0))
    interior_depth = float(entry.get("interior_depth", entry.get("depth", 5.0)))
    interior_height = float(entry.get("interior_height", 2.8))
    finish_ceiling = float(entry.get("FinishCeilingHeight", 2.6))
    interior_attrs = build_interior_context_attributes(
        geometry={
            "height": interior_height,
            "area": interior_width * interior_depth,
            "finish_ceiling_height": finish_ceiling,
        }
    )

    params: dict[str, Any] = {
        "name": resolved.get("Name") or entry.get("name") or "Space",
        "long_name": resolved.get("LongName") or entry.get("long_name"),
        "predefined_type": resolved.get("PredefinedType") or "EXTERNAL",
        "height": geometry["height"],
        "finish_ceiling_height": finish_ceiling,
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": resolved.get("quantities") or {},
        "vignette": "exterior",
        "interior_width": interior_width,
        "interior_depth": interior_depth,
        "interior_height": interior_height,
        "interior_attrs": interior_attrs,
        # Walk-out terrace only — no BalconySlabUpper overhang (isolated from
        # cladding flush-join experiments). Cover the interior slab edge.
        "include_upper_balcony": False,
        "cladding_covers_slab": True,
    }

    if entry.get("boundary"):
        params["boundary"] = entry["boundary"]
    else:
        params["width"] = float(entry["width"])
        params["depth"] = float(entry["depth"])

    if entry.get("with_context") is not None:
        params["with_context"] = entry["with_context"]

    return params


def is_parking_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in PARKING_TYPES


def is_elevator_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in ELEVATOR_TYPES


def map_elevator_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert an elevator catalog entry into ``generate_elevator`` params.

    Shaft vignette: one floor slab + four shaft walls + door + accent IfcSpace.
    """
    if not is_elevator_entry(entry):
        raise ValueError(
            "unsupported element_type for elevator mapping: "
            f"{entry.get('element_type')!r}"
        )

    width = float(entry.get("width", entry.get("shaft_width", DEFAULT_SHAFT_WIDTH)))
    depth = float(entry.get("depth", entry.get("shaft_depth", DEFAULT_SHAFT_DEPTH)))
    height = float(entry.get("height", ELEVATOR_DEFAULT_HEIGHT))
    area = width * depth

    resolved = build_space_attributes_from_yaml(
        entry=entry,
        geometry={"height": height, "area": area},
        element_slug=ELEVATOR_ELEMENT_SLUG,
        defaults=elevator_defaults(),
    )
    qto = (resolved.get("quantities") or {}).get("Qto_SpaceBaseQuantities") or {}

    params: dict[str, Any] = {
        "project_name": entry.get("project_name") or entry.get("id") or "Aufzug",
        "name": resolved.get("Name") or elevator_defaults()["Name"],
        "long_name": resolved.get("LongName") or elevator_defaults()["LongName"],
        "predefined_type": resolved.get("PredefinedType") or "INTERNAL",
        "object_type": resolved.get("ObjectType"),
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": qto,
        "width": width,
        "depth": depth,
        "height": height,
    }
    if entry.get("with_context") is not None:
        params["with_context"] = entry["with_context"]
    if entry.get("wall_thickness") is not None:
        params["wall_thickness"] = entry["wall_thickness"]
    if entry.get("slab_thickness") is not None:
        params["slab_thickness"] = entry["slab_thickness"]
    if entry.get("door_width") is not None:
        params["door_width"] = entry["door_width"]
    if entry.get("door_height") is not None:
        params["door_height"] = entry["door_height"]
    if entry.get("slab_margin") is not None:
        params["slab_margin"] = entry["slab_margin"]
    if entry.get("upper_name") is not None:
        params["upper_name"] = entry["upper_name"]
    return params


def is_vorsatzschale_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in VORSATZSCHALE_TYPES


def map_vorsatzschale_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a Vorsatzschale catalog entry into ``generate_vorsatzschale`` params.

    Bathroom vignette: slab + Tragwand + 7 cm facing wall, 20 cm clear gap
    (accent IfcSpace), schematic toilet in front of the facing wall.
    """
    if not is_vorsatzschale_entry(entry):
        raise ValueError(
            "unsupported element_type for Vorsatzschale mapping: "
            f"{entry.get('element_type')!r}"
        )

    width = float(entry.get("width", entry.get("room_width", DEFAULT_ROOM_WIDTH)))
    room_depth = float(entry.get("room_depth", DEFAULT_ROOM_DEPTH))
    height = float(entry.get("height", VORSATZ_DEFAULT_HEIGHT))
    gap = float(entry.get("gap", DEFAULT_GAP))
    facing_t = float(entry.get("facing_thickness", DEFAULT_FACING_THICKNESS))
    area = width * gap

    resolved = build_space_attributes_from_yaml(
        entry=entry,
        geometry={"height": height, "area": area},
        element_slug=VORSATZSCHALE_ELEMENT_SLUG,
        defaults=vorsatzschale_defaults(),
    )
    qto = (resolved.get("quantities") or {}).get("Qto_SpaceBaseQuantities") or {}

    params: dict[str, Any] = {
        "project_name": entry.get("project_name") or entry.get("id") or "Vorsatzschale",
        "name": resolved.get("Name") or vorsatzschale_defaults()["Name"],
        "long_name": resolved.get("LongName"),
        "predefined_type": resolved.get("PredefinedType") or "USERDEFINED",
        "object_type": resolved.get("ObjectType")
        or vorsatzschale_defaults()["ObjectType"],
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": qto,
        "width": width,
        "room_depth": room_depth,
        "height": height,
        "gap": gap,
        "facing_thickness": facing_t,
    }
    if entry.get("with_context") is not None:
        params["with_context"] = entry["with_context"]
    if entry.get("wall_thickness") is not None:
        params["wall_thickness"] = entry["wall_thickness"]
    if entry.get("slab_thickness") is not None:
        params["slab_thickness"] = entry["slab_thickness"]
    return params


def map_parking_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a catalog parking entry into ``generate_parking`` params.

    Three 2.7×5 m PARKING bays by default (P0001…P0003), with slab under street
    + bays + wall, one flooring over street + bays (inset by wall thickness from
    the head wall), and a 3 m street aisle at the same clear height.
    """
    if not is_parking_entry(entry):
        raise ValueError(
            f"unsupported element_type for parking mapping: {entry.get('element_type')!r}"
        )

    bay_width = float(entry.get("bay_width", entry.get("width", DEFAULT_BAY_WIDTH)))
    bay_depth = float(entry.get("bay_depth", entry.get("depth", DEFAULT_BAY_DEPTH)))
    bay_count = int(entry.get("bay_count", DEFAULT_BAY_COUNT))
    height = float(entry.get("height", DEFAULT_PARKING_HEIGHT))
    bay_area = bay_width * bay_depth

    names = list(entry.get("names") or [])
    while len(names) < bay_count:
        names.append(f"P{len(names) + 1:04d}")

    bay_attrs: list[dict[str, Any]] = []
    for index in range(bay_count):
        bay_entry = {
            **{k: v for k, v in entry.items() if k not in {"Name", "name", "names"}},
            "Name": names[index],
        }
        resolved = build_space_attributes_from_yaml(
            entry=bay_entry,
            geometry={"height": height, "area": bay_area},
            element_slug=PARKING_ELEMENT_SLUG,
            defaults=parking_defaults(),
        )
        qto = (resolved.get("quantities") or {}).get("Qto_SpaceBaseQuantities") or {}
        bay_attrs.append(
            {
                "name": resolved.get("Name") or names[index],
                "long_name": resolved.get("LongName"),
                "predefined_type": resolved.get("PredefinedType") or "PARKING",
                "object_type": resolved.get("ObjectType"),
                "properties": resolved.get("properties") or {},
                "property_datatypes": resolved.get("property_datatypes") or {},
                "quantities": qto,
            }
        )

    params: dict[str, Any] = {
        "project_name": entry.get("project_name") or entry.get("id") or "Parkplaetze",
        "height": height,
        "bay_width": bay_width,
        "bay_depth": bay_depth,
        "bay_count": bay_count,
        "names": names,
        "bay_attrs": bay_attrs,
    }
    if entry.get("with_context") is not None:
        params["with_context"] = entry["with_context"]
    return params


def is_luftraum_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in LUFTRAUM_TYPES


def map_luftraum_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a catalog Luftraum entry into ``generate_luftraum`` params.

    ``height`` is the lower interior space (Luftraum bottom). ``upper_height`` is
    the upper-storey clear height; Luftraum Height / GrossVolume also include the
    raised beam zone up to the top-slab soffit.
    """
    if not is_luftraum_entry(entry):
        raise ValueError(
            f"unsupported element_type for Luftraum mapping: {entry.get('element_type')!r}"
        )

    lower_geometry = _geometry_from_entry(entry)
    upper_height = float(entry.get("upper_height", lower_geometry["height"]))
    if upper_height <= 0:
        raise ValueError("upper_height must be positive")
    luftraum_height = upper_height + TOP_SLAB_RAISE

    overhang = float(entry.get("overhang", OVERHANG_INTO_LUFTRAUM))
    depth = float(entry.get("depth") or 5.0)
    if entry.get("width") is not None:
        void_area = (float(entry["width"]) - overhang) * depth
    else:
        void_area = max(0.1, lower_geometry["area"] - overhang * depth)
    mid_area = (
        overhang + WALL_THICKNESS + NEIGHBOR_SPACE_WIDTH
    ) * depth

    luftraum_geometry = {
        "height": luftraum_height,
        "area": void_area,
    }
    resolved = build_space_attributes_from_yaml(
        entry=entry,
        geometry=luftraum_geometry,
        element_slug=LUFTRAUM_ELEMENT_SLUG,
        defaults=luftraum_defaults(),
    )

    finish_ceiling = float(entry.get("FinishCeilingHeight", 2.6))
    neighbor_attrs = build_neighbor_space_attributes(
        geometry={"height": lower_geometry["height"], "area": 15.0},
        element_slug=SPACE_ELEMENT_SLUG,
    )
    # Upper gallery to top-slab soffit; clear ≈ (upper_height + raise) − mid fabric
    upper_clear = max(
        0.1,
        upper_height
        + TOP_SLAB_RAISE
        - CEILING_SLAB_THICKNESS
        - FLOOR_COVERING_THICKNESS,
    )
    upper_attrs = build_luftraum_upper_attributes(
        geometry={"height": upper_clear, "area": mid_area}
    )
    lower_attrs = build_luftraum_lower_attributes(
        geometry={
            "height": lower_geometry["height"],
            "area": lower_geometry["area"],
            "finish_ceiling_height": lower_geometry["height"],
        }
    )

    params: dict[str, Any] = {
        "name": resolved.get("Name") or entry.get("name") or "LR-01",
        "long_name": resolved.get("LongName") or entry.get("long_name") or "Luftraum",
        "predefined_type": resolved.get("PredefinedType") or "USERDEFINED",
        "object_type": resolved.get("ObjectType") or "Luftraum",
        "height": lower_geometry["height"],
        "upper_height": upper_height,
        "overhang": overhang,
        "finish_ceiling_height": finish_ceiling,
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": resolved.get("quantities") or {},
        "neighbor_attrs": neighbor_attrs,
        "upper_attrs": upper_attrs,
        "lower_attrs": lower_attrs,
    }

    if entry.get("boundary"):
        params["boundary"] = entry["boundary"]
    else:
        params["width"] = float(entry["width"])
        params["depth"] = float(entry["depth"])

    if entry.get("with_context") is not None:
        params["with_context"] = entry["with_context"]

    return params


def map_covering_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a covering catalog entry into ``generate_covering`` params.

    - Floor interior: interior-space vignette (``architecture-floor-covering.yaml``)
    - Floor exterior: exterior-space vignette + balcony FLOORING covering
    - Ceiling: Luftraum atrium (``architecture-ceiling-suspended.yaml``) so the
      suspended plate reads clearly through the void
    """
    if not is_covering_entry(entry):
        raise ValueError(
            f"unsupported element_type for Covering mapping: {entry.get('element_type')!r}"
        )

    is_floor = entry["element_type"] in FLOOR_COVERING_TYPES
    is_floor_ext = entry["element_type"] in FLOOR_COVERING_EXTERIOR_TYPES
    slug = _ELEMENT_SLUG_BY_TYPE[entry["element_type"]]

    if is_floor_ext:
        space_entry = {
            "id": entry.get("id"),
            "element_type": "SPACE-EXT",
            "height": entry.get("height", 1.0),
            "width": entry.get("width", 2.0),
            "depth": entry.get("depth", 4.0),
            "FinishCeilingHeight": entry.get("FinishCeilingHeight", 2.6),
            "with_context": entry.get("with_context", True),
        }
        if entry.get("boundary"):
            space_entry["boundary"] = entry["boundary"]
        space_params = map_exterior_space_params(space_entry)
        space_params["include_balcony_floor_covering"] = True
        geometry = _geometry_from_entry(space_entry)
        defaults = FLOOR_COVERING_EXTERIOR_DEFAULTS
        default_name = "Bodenbelag-Aussen"
        default_type = "FLOORING"
        vignette_key = "space_params"
        vignette_params = space_params
    elif is_floor:
        space_entry = {
            "id": entry.get("id"),
            "element_type": "IfcSpace",
            "height": entry.get("height", 2.8),
            "FinishCeilingHeight": entry.get("FinishCeilingHeight", 2.6),
            "with_context": entry.get("with_context", True),
        }
        if entry.get("boundary"):
            space_entry["boundary"] = entry["boundary"]
        else:
            space_entry["width"] = entry.get("width", 4.0)
            space_entry["depth"] = entry.get("depth", 5.0)

        space_params = map_space_params(space_entry)
        space_params["include_ceiling_slab"] = entry.get("include_ceiling_slab", True)
        geometry = _geometry_from_entry(space_entry)
        defaults = FLOOR_COVERING_DEFAULTS
        default_name = "Bodenaufbau"
        default_type = "FLOORING"
        vignette_key = "space_params"
        vignette_params = space_params
    else:
        luftraum_params = map_luftraum_params(_luftraum_entry_from_shared(entry))
        luftraum_params["omit_luftraum"] = False
        luftraum_params["include_ceiling_covering"] = True
        luftraum_params["project_name"] = (
            entry.get("project_name") or entry.get("id") or "Abhangdecke"
        )
        width = float(luftraum_params.get("width") or entry.get("width", 4.0))
        depth = float(luftraum_params.get("depth") or entry.get("depth", 5.0))
        # Full-footprint ceiling under beams (void + partition + neighbour)
        ceiling_area = (width + WALL_THICKNESS + NEIGHBOR_SPACE_WIDTH) * depth
        geometry = {"area": ceiling_area, "height": float(entry.get("height", 2.8))}
        defaults = CEILING_DEFAULTS
        default_name = "Abhangdecke"
        default_type = "CEILING"
        vignette_key = "luftraum_params"
        vignette_params = luftraum_params

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=slug,
        defaults=defaults,
        geometry=geometry,
    )

    # Geometry-derived NetArea always wins
    quantities = resolved.get("quantities") or {}
    qto = quantities.setdefault("Qto_CoveringBaseQuantities", {})
    qto["NetArea"] = round(float(geometry["area"]), 2)

    return {
        vignette_key: vignette_params,
        "name": entry.get("name") or default_name,
        "predefined_type": resolved.get("PredefinedType") or default_type,
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": quantities,
    }


def is_opening_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in OPENING_TYPES


def is_footing_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in FOOTING_TYPES


def is_column_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in COLUMN_TYPES


def is_maintenance_space_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in MAINTENANCE_SPACE_TYPES


def is_installation_path_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in INSTALLATION_PATH_TYPES


def is_turning_radius_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in TURNING_RADIUS_TYPES


def is_decision_volume_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in DECISION_VOLUME_TYPES


def is_building_law_parcel_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in BUILDING_LAW_PARCEL_TYPES


def is_surrounding_building_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in SURROUNDING_BUILDING_TYPES


def is_construction_logistics_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in CONSTRUCTION_LOGISTICS_TYPES


def is_planning_constraint_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in PLANNING_CONSTRAINT_TYPES


def is_umbau_perimeter_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in UMBAU_PERIMETER_TYPES


def is_tree_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in TREE_TYPES


def is_humus_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in HUMUS_TYPES


def is_tree_pit_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in TREE_PIT_TYPES


def is_retention_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in RETENTION_TYPES


def is_furniture_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in FURNITURE_TYPES


def is_coordination_zone_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in COORDINATION_ZONE_TYPES


def is_beam_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in BEAM_TYPES


def is_roof_pitched_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in ROOF_PITCHED_TYPES


def is_roofing_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in ROOFING_TYPES


def is_exterior_fabric_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in EXTERIOR_FABRIC_TYPES


def is_interior_fabric_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in INTERIOR_FABRIC_TYPES


def is_detail_reference_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in DETAIL_REFERENCE_TYPES


def _exterior_space_entry_from_fabric(entry: dict[str, Any]) -> dict[str, Any]:
    """Shared geometry for exterior wall/cladding/door/window catalog cards."""
    return {
        "id": entry.get("id"),
        "element_type": "SPACE-EXT",
        "height": entry.get("height", 1.0),
        "width": entry.get("width", 1.5),
        "depth": entry.get("depth", 5.0),
        "interior_width": entry.get("interior_width", 2.0),
        "interior_depth": entry.get("interior_depth", entry.get("depth", 5.0)),
        "interior_height": entry.get("interior_height", 2.8),
        "FinishCeilingHeight": entry.get("FinishCeilingHeight", 2.6),
        "with_context": entry.get("with_context", True),
        **(
            {"boundary": entry["boundary"]}
            if entry.get("boundary") is not None
            else {}
        ),
    }


def map_exterior_fabric_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert wall/cladding/door/window entry → ``generate_exterior_fabric`` params.

    Geometry matches ``space-exterior-01`` without IfcSpace volumes; accent is the
    product named by ``element_type``.
    """
    if not is_exterior_fabric_entry(entry):
        raise ValueError(
            f"unsupported element_type for exterior fabric: {entry.get('element_type')!r}"
        )

    element_type = entry["element_type"]
    space_params = map_exterior_space_params(_exterior_space_entry_from_fabric(entry))
    space_params["omit_primary_space"] = True
    space_params["include_interior_space"] = False
    # Wall accent needs an unobstructed facade face (cladding would hide it)
    # and an open top (no ceiling slab / suspended ceiling).
    if element_type in EXTERIOR_WALL_TYPES:
        space_params["include_cladding"] = False
        space_params["include_ceiling_covering"] = False
        space_params["include_ceiling_slab"] = False
        space_params["include_upper_balcony"] = False
    # Cladding accent: same open top as the wall card (no ceiling slab / no
    # upper balcony). Keeps the walk-out terrace so cladding sits on it.
    # Isolated here — do not reintroduce BalconySlabUpper for this accent.
    if element_type in EXTERIOR_CLADDING_TYPES:
        space_params["include_ceiling_covering"] = False
        space_params["include_ceiling_slab"] = False
        space_params["include_upper_balcony"] = False
    # Window accent drops the projecting balcony so the opening reads clearly;
    # raise/drop cladding to cover both slab front edges (no terrace lip).
    if element_type in WINDOW_EXTERIOR_TYPES:
        space_params["include_balcony"] = False
        space_params["include_upper_balcony"] = False
        space_params["cladding_covers_slab"] = True
    # Door accent keeps the walk-out terrace but drops the matching upper
    # balcony plate so the top edge stays flush with the interior ceiling;
    # raise cladding alone to cover that exposed slab thickness.
    if element_type in DOOR_EXTERIOR_TYPES:
        space_params["include_upper_balcony"] = False
        space_params["cladding_covers_slab"] = True

    if element_type in EXTERIOR_WALL_TYPES:
        accent = "wall"
        slug = WALL_EXTERIOR_ELEMENT_SLUG
        defaults = WALL_EXTERIOR_DEFAULTS
        default_name = WALL_EXTERIOR_DEFAULTS["Name"]
        default_type = "SOLIDWALL"
        geometry = {
            "height": float(entry.get("interior_height", 2.8)),
            "area": float(entry.get("interior_depth", entry.get("depth", 5.0)))
            * EXTERIOR_WALL_THICKNESS,
        }
    elif element_type in EXTERIOR_CLADDING_TYPES:
        accent = "cladding"
        slug = CLADDING_EXTERIOR_ELEMENT_SLUG
        defaults = CLADDING_EXTERIOR_DEFAULTS
        default_name = CLADDING_EXTERIOR_DEFAULTS["Name"]
        default_type = "CLADDING"
        geometry = {
            "height": float(entry.get("interior_height", 2.8)),
            "area": float(entry.get("interior_depth", entry.get("depth", 5.0)))
            * 0.05,
        }
    elif element_type in DOOR_EXTERIOR_TYPES:
        accent = "door"
        slug = DOOR_EXTERIOR_ELEMENT_SLUG
        defaults = {
            **DOOR_EXTERIOR_DEFAULTS,
            "OverallWidth": float(entry.get("OverallWidth", DOOR_WIDTH)),
            "OverallHeight": float(entry.get("OverallHeight", DOOR_HEIGHT)),
        }
        default_name = DOOR_EXTERIOR_DEFAULTS["Name"]
        default_type = "DOOR"
        geometry = {
            "height": float(defaults["OverallHeight"]),
            "area": float(defaults["OverallWidth"]) * float(defaults["OverallHeight"]),
        }
    else:
        accent = "window"
        slug = WINDOW_EXTERIOR_ELEMENT_SLUG
        defaults = WINDOW_EXTERIOR_DEFAULTS
        default_name = WINDOW_EXTERIOR_DEFAULTS["Name"]
        default_type = "WINDOW"
        geometry = {
            "height": float(entry.get("OverallHeight", WINDOW_HEIGHT)),
            "area": float(entry.get("OverallWidth", WINDOW_WIDTH))
            * float(entry.get("OverallHeight", WINDOW_HEIGHT)),
        }

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=slug,
        defaults=defaults,
        geometry=geometry,
    )

    return {
        "space_params": space_params,
        "accent": accent,
        "name": entry.get("name") or resolved.get("Name") or default_name,
        "predefined_type": resolved.get("PredefinedType") or default_type,
        "object_type": resolved.get("ObjectType"),
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": resolved.get("quantities") or {},
    }


def map_interior_fabric_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert interior wall/cladding entry → ``generate_interior_fabric`` params.

    Geometry matches the Innenräume vignette without spaces / ceiling slab so the
    partition reads clearly; accent is the product named by ``element_type``.
    """
    if not is_interior_fabric_entry(entry):
        raise ValueError(
            f"unsupported element_type for interior fabric: {entry.get('element_type')!r}"
        )

    element_type = entry["element_type"]
    height = float(entry.get("height", 2.8))
    depth = float(entry.get("depth", 5.0))
    width = float(entry.get("width", 4.0))
    neighbor_width = NEIGHBOR_SPACE_WIDTH
    if element_type in INTERIOR_WALL_TYPES | DRYWALL_REINFORCEMENT_TYPES:
        total_clear_and_walls = width + WALL_THICKNESS + NEIGHBOR_SPACE_WIDTH
        width = (total_clear_and_walls - 2.0 * WALL_THICKNESS) / 3.0
        neighbor_width = 2.0 * width + WALL_THICKNESS

    space_entry = {
        "id": entry.get("id"),
        "element_type": "IfcSpace",
        "height": height,
        "FinishCeilingHeight": entry.get("FinishCeilingHeight", 2.6),
        "with_context": entry.get("with_context", True),
    }
    if entry.get("boundary"):
        space_entry["boundary"] = entry["boundary"]
    else:
        space_entry["width"] = width
        space_entry["depth"] = depth

    space_params = map_space_params(space_entry)
    space_params["omit_primary_space"] = True
    space_params["include_neighbor_space"] = False
    space_params["include_ceiling_covering"] = False
    space_params["include_ceiling_slab"] = False
    space_params["neighbor_space_width"] = neighbor_width

    if element_type in INTERIOR_WALL_TYPES | DRYWALL_REINFORCEMENT_TYPES:
        accent = "wall"
        slug = WALL_INTERIOR_ELEMENT_SLUG
        defaults = WALL_INTERIOR_DEFAULTS
        default_name = WALL_INTERIOR_DEFAULTS["Name"]
        default_type = "PARTITIONING"
        space_params["include_exterior_envelope"] = True
        # Open the +Y envelope wall so both rooms and the partition stay visible.
        space_params["omit_camera_facing_envelope"] = True
        # Keep the original wall as context and accent a second parallel partition
        # whose base sits on top of the finished flooring.
        space_params["parallel_wall_on_flooring"] = True
        parallel_offset = width + WALL_THICKNESS
        parallel_end_inset = 0.0
        wall_t = float(
            entry.get("parallel_wall_thickness", PARALLEL_WALL_THICKNESS)
        )
        parallel_length = depth - 2.0 * parallel_end_inset
        if parallel_length <= 0:
            raise ValueError("parallel wall end inset leaves no wall length")
        space_params["parallel_wall_offset"] = parallel_offset
        space_params["parallel_wall_end_inset"] = parallel_end_inset
        space_params["parallel_wall_thickness"] = wall_t
        geometry = {
            "height": height,
            "area": parallel_length * height,
            "width": wall_t,
            "volume": parallel_length * height * wall_t,
        }
        if element_type in DRYWALL_REINFORCEMENT_TYPES:
            accent = "reinforcement"
            slug = DRYWALL_REINFORCEMENT_ELEMENT_SLUG
            defaults = DRYWALL_REINFORCEMENT_DEFAULTS
            default_name = DRYWALL_REINFORCEMENT_DEFAULTS["Name"]
            default_type = "USERDEFINED"
            geometry = {
                "height": REINF_HEIGHT,
                "area": REINF_WIDTH * REINF_HEIGHT,
            }
    elif element_type in INTERIOR_WALL_LB_TYPES:
        accent = "wall"
        slug = WALL_INTERIOR_LB_ELEMENT_SLUG
        defaults = WALL_INTERIOR_LB_DEFAULTS
        default_name = WALL_INTERIOR_LB_DEFAULTS["Name"]
        default_type = "SOLIDWALL"
        space_params["include_exterior_envelope"] = True
        space_params["omit_camera_facing_envelope"] = True
        wall_t = WALL_THICKNESS
        geometry = {
            "height": height,
            "area": depth * height,
            "width": wall_t,
            "volume": depth * height * wall_t,
        }
    elif element_type in DOOR_INTERIOR_TYPES:
        accent = "door"
        slug = DOOR_INTERIOR_ELEMENT_SLUG
        defaults = {
            **DOOR_INTERIOR_DEFAULTS,
            "OverallWidth": float(entry.get("OverallWidth", DOOR_WIDTH)),
            "OverallHeight": float(entry.get("OverallHeight", DOOR_HEIGHT)),
        }
        default_name = DOOR_INTERIOR_DEFAULTS["Name"]
        default_type = "DOOR"
        geometry = {
            "height": float(defaults["OverallHeight"]),
            "area": float(defaults["OverallWidth"]) * float(defaults["OverallHeight"]),
        }
        space_params["include_exterior_envelope"] = True
        space_params["include_partition_openings"] = True
        # Open the +Y long wall so the partition openings read in isometric.
        space_params["omit_camera_facing_envelope"] = True
    elif element_type in WINDOW_INTERIOR_TYPES:
        accent = "window"
        slug = WINDOW_INTERIOR_ELEMENT_SLUG
        defaults = WINDOW_INTERIOR_DEFAULTS
        default_name = WINDOW_INTERIOR_DEFAULTS["Name"]
        default_type = "WINDOW"
        geometry = {
            "height": float(entry.get("OverallHeight", WINDOW_HEIGHT)),
            "area": float(entry.get("OverallWidth", WINDOW_WIDTH))
            * float(entry.get("OverallHeight", WINDOW_HEIGHT)),
        }
        space_params["include_exterior_envelope"] = True
        space_params["include_partition_openings"] = True
        space_params["omit_camera_facing_envelope"] = True
    else:
        accent = "cladding"
        slug = CLADDING_INTERIOR_ELEMENT_SLUG
        defaults = CLADDING_INTERIOR_DEFAULTS
        default_name = CLADDING_INTERIOR_DEFAULTS["Name"]
        default_type = "CLADDING"
        geometry = {
            "height": SPLASH_HEIGHT,
            "area": SPLASH_WIDTH * SPLASH_HEIGHT,
        }

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=slug,
        defaults=defaults,
        geometry=geometry,
    )

    quantities = resolved.get("quantities") or {}
    if accent == "wall":
        qto = quantities.setdefault("Qto_WallBaseQuantities", {})
        qto["NetSideArea"] = round(float(geometry["area"]), 2)
        qto["Width"] = round(float(geometry["width"]), 3)
        qto["GrossVolume"] = round(float(geometry["volume"]), 3)
    elif accent != "reinforcement":
        qto = quantities.setdefault("Qto_CoveringBaseQuantities", {})
        qto["NetArea"] = round(float(geometry["area"]), 2)

    params: dict[str, Any] = {
        "space_params": space_params,
        "accent": accent,
        "name": entry.get("name") or resolved.get("Name") or default_name,
        "predefined_type": resolved.get("PredefinedType") or default_type,
        "object_type": resolved.get("ObjectType"),
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": quantities,
    }
    if accent == "cladding":
        params["cladding_thickness"] = float(
            entry.get("cladding_thickness", INTERIOR_CLADDING_THICKNESS)
        )
    return params


def map_detail_reference_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a Detailverweis entry → ``generate_detail_references`` params.

    Geometry matches ``wall-exterior-01``; two junction volumes get YAML attrs.
    """
    if not is_detail_reference_entry(entry):
        raise ValueError(
            f"unsupported element_type for detail reference: {entry.get('element_type')!r}"
        )

    fabric_entry = {
        "id": entry.get("id"),
        "element_type": "ARC-WALL-EXT",
        "height": entry.get("height", 1.0),
        "width": entry.get("width", 1.5),
        "depth": entry.get("depth", 5.0),
        "interior_width": entry.get("interior_width", 2.0),
        "interior_depth": entry.get("interior_depth", entry.get("depth", 5.0)),
        "interior_height": entry.get("interior_height", 2.8),
        "FinishCeilingHeight": entry.get("FinishCeilingHeight", 2.6),
        "with_context": entry.get("with_context", True),
    }
    fabric_params = map_exterior_fabric_params(fabric_entry)

    volume_names = entry.get("volume_names") or ["AW-Balkon", "AW-Türschwelle"]
    volume_attrs: list[dict[str, Any]] = []
    for index, name in enumerate(volume_names):
        defaults = {
            **DETAIL_REFERENCE_DEFAULTS,
            "Name": str(name),
        }
        # Per-volume overrides: volumes[i].Name etc.
        volumes = entry.get("volumes") or []
        overrides = dict(volumes[index]) if index < len(volumes) else {}
        volume_entry = {**entry, **overrides, "Name": overrides.get("Name", name)}
        resolved = build_element_attributes_from_yaml(
            entry=volume_entry,
            element_slug=DETAIL_REFERENCE_ELEMENT_SLUG,
            defaults=defaults,
            geometry={},
        )
        volume_attrs.append(
            {
                "Name": volume_entry.get("Name")
                or resolved.get("Name")
                or defaults["Name"],
                "PredefinedType": resolved.get("PredefinedType") or "USERDEFINED",
                "ObjectType": resolved.get("ObjectType") or "Detailverweis",
                "properties": resolved.get("properties") or {},
                "property_datatypes": resolved.get("property_datatypes") or {},
            }
        )

    return {
        "fabric_params": fabric_params,
        "interior_depth": float(
            entry.get("interior_depth", entry.get("depth", 5.0))
        ),
        "balcony_depth": float(entry.get("width", 1.5)),
        "volumes": [
            {"name": attrs["Name"]} for attrs in volume_attrs
        ],
        "volume_attrs": volume_attrs,
    }


def map_footing_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a footing catalog entry into ``generate_footing`` params.

    Vignette: pad footing (accent) + base slab + one column.
    """
    if not is_footing_entry(entry):
        raise ValueError(
            f"unsupported element_type for Footing mapping: {entry.get('element_type')!r}"
        )

    foot_w = float(entry.get("footing_width", DEFAULT_FOOTING_WIDTH))
    foot_d = float(entry.get("footing_depth", DEFAULT_FOOTING_DEPTH))
    foot_t = float(entry.get("footing_thickness", DEFAULT_FOOTING_THICKNESS))
    geometry = {"area": foot_w * foot_d, "height": foot_t}

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=FOOTING_ELEMENT_SLUG,
        defaults=FOOTING_DEFAULTS,
        geometry=geometry,
    )

    quantities = resolved.get("quantities") or {}
    qto = quantities.setdefault("Qto_FootingBaseQuantities", {})
    qto["GrossVolume"] = round(foot_w * foot_d * foot_t, 3)

    params: dict[str, Any] = {
        "project_name": entry.get("project_name") or entry.get("id") or "Fundament",
        "name": entry.get("name") or resolved.get("Name") or FOOTING_DEFAULTS["Name"],
        "predefined_type": resolved.get("PredefinedType") or "PAD_FOOTING",
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": quantities,
        "slab_attrs": {
            "Name": "Bodenplatte",
            "PredefinedType": "BASESLAB",
        },
        "column_attrs": {
            "Name": "S-01",
            "PredefinedType": "COLUMN",
        },
        "footing_width": foot_w,
        "footing_depth": foot_d,
        "footing_thickness": foot_t,
        "slab_width": float(entry.get("slab_width", DEFAULT_SLAB_WIDTH)),
        "slab_depth": float(entry.get("slab_depth", DEFAULT_SLAB_DEPTH)),
        "slab_thickness": float(
            entry.get("slab_thickness", FOOTING_VIGNETTE_SLAB_THICKNESS)
        ),
        "column_width": float(entry.get("column_width", DEFAULT_COLUMN_WIDTH)),
        "column_depth": float(entry.get("column_depth", DEFAULT_COLUMN_DEPTH)),
        "column_height": float(entry.get("column_height", DEFAULT_COLUMN_HEIGHT)),
    }
    if entry.get("footing_inset") is not None:
        params["footing_inset"] = float(entry["footing_inset"])
    if resolved.get("ObjectType") is not None:
        params["ObjectType"] = resolved["ObjectType"]
    return params


def map_column_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a column catalog entry into ``generate_footing`` params.

    Closed slab + centred column (no footing pad); accent the column.
    """
    if not is_column_entry(entry):
        raise ValueError(
            f"unsupported element_type for Column mapping: {entry.get('element_type')!r}"
        )

    col_w = float(entry.get("column_width", DEFAULT_COLUMN_WIDTH))
    col_d = float(entry.get("column_depth", DEFAULT_COLUMN_DEPTH))
    col_h = float(entry.get("column_height", DEFAULT_COLUMN_HEIGHT))
    geometry = {"area": col_w * col_d, "height": col_h}

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=COLUMN_ELEMENT_SLUG,
        defaults=COLUMN_DEFAULTS,
        geometry=geometry,
    )

    quantities = resolved.get("quantities") or {}
    qto = quantities.setdefault("Qto_ColumnBaseQuantities", {})
    qto["GrossVolume"] = round(col_w * col_d * col_h, 3)

    params: dict[str, Any] = {
        "project_name": entry.get("project_name") or entry.get("id") or "Stuetze",
        "name": entry.get("name") or resolved.get("Name") or COLUMN_DEFAULTS["Name"],
        "predefined_type": resolved.get("PredefinedType") or "COLUMN",
        "highlight": "column",
        "omit_footing": True,
        "close_slab": True,
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": quantities,
        "slab_attrs": {
            "Name": "Bodenplatte",
            "PredefinedType": "BASESLAB",
        },
        "slab_width": float(entry.get("slab_width", DEFAULT_SLAB_WIDTH)),
        "slab_depth": float(entry.get("slab_depth", DEFAULT_SLAB_DEPTH)),
        "slab_thickness": float(
            entry.get("slab_thickness", FOOTING_VIGNETTE_SLAB_THICKNESS)
        ),
        "column_width": col_w,
        "column_depth": col_d,
        "column_height": col_h,
    }
    if resolved.get("ObjectType") is not None:
        params["ObjectType"] = resolved["ObjectType"]
    return params


def map_maintenance_space_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a Wartungsraum catalog entry into ``generate_maintenance_space`` params.

    Vignette: floor slab + long multi-part monoblock + 90 cm clearance at filter (accent).
    """
    if not is_maintenance_space_entry(entry):
        raise ValueError(
            "unsupported element_type for maintenance space: "
            f"{entry.get('element_type')!r}"
        )

    unit_d = float(entry.get("unit_depth", entry.get("cube_depth", DEFAULT_CUBE_DEPTH)))
    maint_d = float(entry.get("maintenance_depth", DEFAULT_MAINTENANCE_DEPTH))
    maint_h = float(entry.get("maintenance_height", DEFAULT_MAINTENANCE_HEIGHT))
    # Clearance footprint matches the Filter module length (not the full unit).
    filter_len = float(entry.get("filter_length", DEFAULT_FILTER_LENGTH))
    geometry = {"area": filter_len * maint_d, "height": maint_h}

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=MAINTENANCE_SPACE_ELEMENT_SLUG,
        defaults=MAINTENANCE_SPACE_DEFAULTS,
        geometry=geometry,
    )

    quantities = resolved.get("quantities") or {}
    qto = quantities.setdefault("Qto_BuildingElementProxyBaseQuantities", {})
    qto["GrossVolume"] = round(filter_len * maint_d * maint_h, 3)

    params: dict[str, Any] = {
        "project_name": entry.get("project_name") or entry.get("id") or "Wartungsraum",
        "name": entry.get("name")
        or resolved.get("Name")
        or MAINTENANCE_SPACE_DEFAULTS["Name"],
        "predefined_type": resolved.get("PredefinedType") or "USERDEFINED",
        "object_type": resolved.get("ObjectType")
        or MAINTENANCE_SPACE_DEFAULTS["ObjectType"],
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": quantities,
        "unit_depth": unit_d,
        "cube_depth": unit_d,
        "cube_width": float(entry.get("cube_width", DEFAULT_CUBE_WIDTH)),
        "cube_height": float(entry.get("cube_height", DEFAULT_CUBE_HEIGHT)),
        "maintenance_depth": maint_d,
        "maintenance_height": maint_h,
        "slab_thickness": float(entry.get("slab_thickness", MAINT_SLAB_THICKNESS)),
        "slab_padding": float(entry.get("slab_padding", DEFAULT_SLAB_PADDING)),
    }
    return params


def map_installation_path_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert an Einbringweg catalog entry into ``generate_installation_path`` params.

    Vignette: L-corridor with a door partition and a centred, door-sized path.
    """
    if not is_installation_path_entry(entry):
        raise ValueError(
            "unsupported element_type for installation path: "
            f"{entry.get('element_type')!r}"
        )

    door_w = float(entry.get("door_width", DEFAULT_DOOR_WIDTH))
    door_h = float(entry.get("door_height", DEFAULT_PATH_HEIGHT))
    pw = float(entry.get("path_width", door_w))
    ph = float(entry.get("path_height", door_h))
    cw = float(entry.get("corridor_width", DEFAULT_CORRIDOR_WIDTH))
    leg_a = float(entry.get("leg_a", DEFAULT_LEG_A))
    leg_b = float(entry.get("leg_b", DEFAULT_LEG_B))
    overshoot = float(entry.get("path_overshoot", DEFAULT_PATH_OVERSHOOT))
    path_a = leg_a + overshoot
    path_b = leg_b + overshoot
    # Centred L footprint: equal clearance to both corridor walls.
    path_offset = (cw - pw) * 0.5
    path_area = (
        (path_b - path_offset) * pw
        + (path_a - path_offset - pw) * pw
    )
    geometry = {"area": path_area, "height": ph}

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=INSTALLATION_PATH_ELEMENT_SLUG,
        defaults=INSTALLATION_PATH_DEFAULTS,
        geometry=geometry,
    )

    quantities = resolved.get("quantities") or {}
    qto = quantities.setdefault("Qto_BuildingElementProxyBaseQuantities", {})
    qto["GrossVolume"] = round(path_area * ph, 3)

    params: dict[str, Any] = {
        "project_name": entry.get("project_name") or entry.get("id") or "Einbringweg",
        "name": entry.get("name")
        or resolved.get("Name")
        or INSTALLATION_PATH_DEFAULTS["Name"],
        "predefined_type": resolved.get("PredefinedType") or "USERDEFINED",
        "object_type": resolved.get("ObjectType")
        or INSTALLATION_PATH_DEFAULTS["ObjectType"],
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": quantities,
        "corridor_width": cw,
        "path_width": pw,
        "path_height": ph,
        "path_overshoot": overshoot,
        "leg_a": leg_a,
        "leg_b": leg_b,
        "door_width": door_w,
        "door_height": door_h,
        "column_size": float(entry.get("column_size", DEFAULT_COLUMN_SIZE)),
        "wall_height": float(entry.get("wall_height", INSTALL_WALL_HEIGHT)),
        "slab_padding": float(entry.get("slab_padding", INSTALL_SLAB_PADDING)),
    }
    return params


def map_turning_radius_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a Wenderadius catalog entry into ``generate_turning_radius`` params.

    Vignette: street clear of cube; the smooth Lastzug Fahrkurve hits it.
    GrossVolume is recomputed in the generator from the swept envelope.
    """
    if not is_turning_radius_entry(entry):
        raise ValueError(
            "unsupported element_type for turning radius: "
            f"{entry.get('element_type')!r}"
        )

    cube = float(entry.get("cube_size", DEFAULT_CUBE_SIZE))
    clearance = float(entry.get("street_clearance", DEFAULT_STREET_CLEARANCE))
    street_w = float(entry.get("street_width", DEFAULT_STREET_WIDTH))
    approach = float(entry.get("approach", DEFAULT_APPROACH))
    proxy_h = float(entry.get("proxy_height", DEFAULT_PROXY_HEIGHT))
    proxy_out = float(entry.get("proxy_outer", DEFAULT_PROXY_OUTER))
    vehicle_w = float(entry.get("vehicle_width", DEFAULT_VEHICLE_WIDTH))
    vehicle_l = float(entry.get("vehicle_length", DEFAULT_VEHICLE_LENGTH))
    nose = float(entry.get("nose_length", DEFAULT_NOSE_LENGTH))
    proxy_in_mid = float(entry.get("proxy_inner_mid", DEFAULT_PROXY_INNER_MID))
    turn_deg = float(entry.get("turn_angle_deg", DEFAULT_TURN_ANGLE_DEG))
    pose_count = int(entry.get("pose_count", DEFAULT_POSE_COUNT))
    envelope_simplify = float(
        entry.get("envelope_simplify", DEFAULT_ENVELOPE_SIMPLIFY)
    )
    segments = int(entry.get("arc_segments", DEFAULT_ARC_SEGMENTS))
    # Placeholder area until the generator unions the pose footprints.
    turn_frac = turn_deg / 360.0
    proxy_in_entry = proxy_out - vehicle_w
    area_entry = turn_frac * math.pi * (proxy_out * proxy_out - proxy_in_entry * proxy_in_entry)
    area_mid = turn_frac * math.pi * (proxy_out * proxy_out - proxy_in_mid * proxy_in_mid)
    proxy_area = 0.5 * (area_entry + area_mid)
    geometry = {"area": proxy_area, "height": proxy_h}

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=TURNING_RADIUS_ELEMENT_SLUG,
        defaults=TURNING_RADIUS_DEFAULTS,
        geometry=geometry,
    )

    quantities = resolved.get("quantities") or {}
    qto = quantities.setdefault("Qto_BuildingElementProxyBaseQuantities", {})
    qto["GrossVolume"] = round(proxy_area * proxy_h, 3)

    params: dict[str, Any] = {
        "project_name": entry.get("project_name") or entry.get("id") or "Wenderadius",
        "name": entry.get("name")
        or resolved.get("Name")
        or TURNING_RADIUS_DEFAULTS["Name"],
        "predefined_type": resolved.get("PredefinedType") or "USERDEFINED",
        "object_type": resolved.get("ObjectType")
        or TURNING_RADIUS_DEFAULTS["ObjectType"],
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": quantities,
        "cube_size": cube,
        "street_clearance": clearance,
        "street_width": street_w,
        "approach": approach,
        "proxy_height": proxy_h,
        "proxy_outer": proxy_out,
        "vehicle_width": vehicle_w,
        "vehicle_length": vehicle_l,
        "nose_length": nose,
        "proxy_inner_mid": proxy_in_mid,
        "turn_angle_deg": turn_deg,
        "pose_count": pose_count,
        "envelope_simplify": envelope_simplify,
        "arc_segments": segments,
        "slab_padding": float(entry.get("slab_padding", TURN_SLAB_PADDING)),
    }
    return params


def map_decision_volume_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert an Entscheidungskörper catalog entry into generator params.

    Vignette: one storey with several decision volumes in different rooms.
    """
    if not is_decision_volume_entry(entry):
        raise ValueError(
            "unsupported element_type for decision volume: "
            f"{entry.get('element_type')!r}"
        )

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=DECISION_VOLUME_ELEMENT_SLUG,
        defaults=DECISION_VOLUME_DEFAULTS,
        geometry={"area": 1.0, "height": 1.0},
    )

    params: dict[str, Any] = {
        "project_name": entry.get("project_name") or entry.get("id") or "Entscheidungskörper",
        "predefined_type": resolved.get("PredefinedType") or "USERDEFINED",
        "object_type": resolved.get("ObjectType")
        or DECISION_VOLUME_DEFAULTS["ObjectType"],
        "property_datatypes": resolved.get("property_datatypes") or {},
        "plan_width": float(entry.get("plan_width", DECISION_PLAN_WIDTH)),
        "plan_depth": float(entry.get("plan_depth", DECISION_PLAN_DEPTH)),
        "wall_height": float(entry.get("wall_height", DECISION_WALL_HEIGHT)),
    }
    return params


def is_movement_clearance_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in MOVEMENT_CLEARANCE_TYPES


def map_movement_clearance_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a Bewegungsfläche catalog entry into generator params.

    Vignette: accessible wet room with fixed fixtures and one left-side Wendefläche.
    """
    if not is_movement_clearance_entry(entry):
        raise ValueError(
            "unsupported element_type for movement clearance: "
            f"{entry.get('element_type')!r}"
        )

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=MOVEMENT_CLEARANCE_ELEMENT_SLUG,
        defaults=MOVEMENT_CLEARANCE_DEFAULTS,
        geometry={"area": 1.2 * 1.2, "height": 1.5},
    )

    params: dict[str, Any] = {
        "project_name": entry.get("project_name") or entry.get("id") or "Bewegungsfläche",
        "predefined_type": resolved.get("PredefinedType") or "USERDEFINED",
        "object_type": resolved.get("ObjectType")
        or MOVEMENT_CLEARANCE_DEFAULTS["ObjectType"],
    }
    return params


def map_building_law_parcel_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a Baurechtliche Parzelle catalog entry into generator params.

    Vignette: three parcel volumes extending through a terrain surface.
    """
    if not is_building_law_parcel_entry(entry):
        raise ValueError(
            "unsupported element_type for building-law parcel: "
            f"{entry.get('element_type')!r}"
        )

    parcel_bottom = float(entry.get("parcel_bottom", DEFAULT_PARCEL_BOTTOM))
    parcel_top = float(entry.get("parcel_top", DEFAULT_PARCEL_TOP))
    parcel_h = parcel_top - parcel_bottom
    if parcel_h <= 0:
        raise ValueError("parcel_top must be greater than parcel_bottom")
    parcel_d = float(entry.get("parcel_depth", DEFAULT_PARCEL_DEPTH))
    width_a = float(entry.get("parcel_a_width", DEFAULT_PARCEL_A_WIDTH))
    width_b = float(entry.get("parcel_b_width", DEFAULT_PARCEL_B_WIDTH))
    width_c = float(entry.get("parcel_c_width", DEFAULT_PARCEL_C_WIDTH))
    area_a = width_a * parcel_d
    geometry = {"area": area_a, "height": parcel_h}

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=BUILDING_LAW_PARCEL_ELEMENT_SLUG,
        defaults=BUILDING_LAW_PARCEL_DEFAULTS,
        geometry=geometry,
    )

    quantities = resolved.get("quantities") or {}
    qto = quantities.setdefault("Qto_BuildingElementProxyBaseQuantities", {})
    qto["GrossVolume"] = round(area_a * parcel_h, 3)

    parcel_names = entry.get("parcel_names") or [
        entry.get("name") or resolved.get("Name") or BUILDING_LAW_PARCEL_DEFAULTS["Name"],
        "1235",
        "1236",
    ]

    params: dict[str, Any] = {
        "project_name": entry.get("project_name") or entry.get("id") or "Baurechtliche Parzelle",
        "name": entry.get("name")
        or resolved.get("Name")
        or BUILDING_LAW_PARCEL_DEFAULTS["Name"],
        "predefined_type": resolved.get("PredefinedType") or "USERDEFINED",
        "object_type": resolved.get("ObjectType")
        or BUILDING_LAW_PARCEL_DEFAULTS["ObjectType"],
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": quantities,
        "parcel_names": list(parcel_names),
        "parcel_bottom": parcel_bottom,
        "parcel_top": parcel_top,
        "parcel_depth": parcel_d,
        "parcel_a_width": width_a,
        "parcel_b_width": width_b,
        "parcel_c_width": width_c,
        "surface_margin": float(
            entry.get("surface_margin", DEFAULT_SURFACE_MARGIN)
        ),
        "plot_thickness": float(entry.get("plot_thickness", PARCEL_PLOT_THICKNESS)),
    }
    return params


def map_surrounding_building_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert an Umgebungsbau catalog entry into generator params.

    Vignette: opaque project mass with three neighbour gross volumes.
    """
    if not is_surrounding_building_entry(entry):
        raise ValueError(
            "unsupported element_type for surrounding building: "
            f"{entry.get('element_type')!r}"
        )

    project_w = float(entry.get("project_width", DEFAULT_PROJECT_WIDTH))
    project_d = float(entry.get("project_depth", DEFAULT_PROJECT_DEPTH))
    project_h = float(entry.get("project_height", DEFAULT_PROJECT_HEIGHT))
    gap = float(entry.get("gap", NEIGHBOR_GAP))

    neighbor_specs = entry.get("neighbor_specs") or list(DEFAULT_NEIGHBOR_SPECS)
    first = neighbor_specs[0]
    first_area = float(first[1]) * float(first[2])
    first_h = float(first[3])
    geometry = {"area": first_area, "height": first_h}

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=SURROUNDING_BUILDING_ELEMENT_SLUG,
        defaults=SURROUNDING_BUILDING_DEFAULTS,
        geometry=geometry,
    )

    quantities = resolved.get("quantities") or {}
    qto = quantities.setdefault("Qto_BuildingElementProxyBaseQuantities", {})
    qto["GrossVolume"] = round(first_area * first_h, 3)

    params: dict[str, Any] = {
        "project_name": entry.get("project_name")
        or entry.get("id")
        or "Umgebungsbauten",
        "name": entry.get("name")
        or resolved.get("Name")
        or SURROUNDING_BUILDING_DEFAULTS["Name"],
        "predefined_type": resolved.get("PredefinedType") or "USERDEFINED",
        "object_type": resolved.get("ObjectType")
        or SURROUNDING_BUILDING_DEFAULTS["ObjectType"],
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": quantities,
        "neighbor_specs": list(neighbor_specs),
        "project_width": project_w,
        "project_depth": project_d,
        "project_height": project_h,
        "gap": gap,
        "plot_thickness": float(
            entry.get("plot_thickness", NEIGHBOR_PLOT_THICKNESS)
        ),
    }
    return params


def map_construction_logistics_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a Baustelleneinrichtungsobjekt catalog entry into generator params.

    Vignette: fence, container, crane (mast+jib), foundation, storage + opaque building.
    """
    if not is_construction_logistics_entry(entry):
        raise ValueError(
            "unsupported element_type for construction logistics: "
            f"{entry.get('element_type')!r}"
        )

    cont_w = float(entry.get("container_width", DEFAULT_CONTAINER_WIDTH))
    cont_d = float(entry.get("container_depth", DEFAULT_CONTAINER_DEPTH))
    cont_h = float(entry.get("container_height", DEFAULT_CONTAINER_HEIGHT))
    geometry = {"area": cont_w * cont_d, "height": cont_h}

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=CONSTRUCTION_LOGISTICS_ELEMENT_SLUG,
        defaults=CONSTRUCTION_LOGISTICS_DEFAULTS,
        geometry=geometry,
    )

    quantities = resolved.get("quantities") or {}
    qto = quantities.setdefault("Qto_BuildingElementProxyBaseQuantities", {})
    qto["GrossVolume"] = round(cont_w * cont_d * cont_h, 3)

    logistics_names = entry.get("logistics_names") or [
        "Zaun",
        entry.get("name")
        or resolved.get("Name")
        or CONSTRUCTION_LOGISTICS_DEFAULTS["Name"],
        "Kran",
        "Lagerfläche",
        "Kranfundament",
    ]

    params: dict[str, Any] = {
        "project_name": entry.get("project_name")
        or entry.get("id")
        or "Baustelleneinricht",
        "name": entry.get("name")
        or resolved.get("Name")
        or CONSTRUCTION_LOGISTICS_DEFAULTS["Name"],
        "predefined_type": resolved.get("PredefinedType") or "USERDEFINED",
        "object_type": resolved.get("ObjectType")
        or CONSTRUCTION_LOGISTICS_DEFAULTS["ObjectType"],
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": quantities,
        "logistics_names": list(logistics_names),
        "building_width": float(entry.get("building_width", LOG_BUILDING_WIDTH)),
        "building_depth": float(entry.get("building_depth", LOG_BUILDING_DEPTH)),
        "building_height": float(entry.get("building_height", LOG_BUILDING_HEIGHT)),
        "yard_depth": float(entry.get("yard_depth", DEFAULT_YARD_DEPTH)),
        "yard_side": float(entry.get("yard_side", DEFAULT_YARD_SIDE)),
        "fence_height": float(entry.get("fence_height", DEFAULT_FENCE_HEIGHT)),
        "fence_thickness": float(entry.get("fence_thickness", DEFAULT_FENCE_THICKNESS)),
        "container_width": cont_w,
        "container_depth": cont_d,
        "container_height": cont_h,
        "crane_pad": float(entry.get("crane_pad", DEFAULT_CRANE_PAD)),
        "crane_pad_thickness": float(
            entry.get("crane_pad_thickness", DEFAULT_CRANE_PAD_THICKNESS)
        ),
        "crane_height": float(entry.get("crane_height", DEFAULT_CRANE_HEIGHT)),
        "crane_mast": float(entry.get("crane_mast", DEFAULT_CRANE_MAST)),
        "crane_jib_length": float(entry.get("crane_jib_length", DEFAULT_CRANE_JIB_LENGTH)),
        "crane_jib_width": float(entry.get("crane_jib_width", DEFAULT_CRANE_JIB_WIDTH)),
        "crane_jib_height": float(entry.get("crane_jib_height", DEFAULT_CRANE_JIB_HEIGHT)),
        "storage_width": float(entry.get("storage_width", DEFAULT_STORAGE_WIDTH)),
        "storage_depth": float(entry.get("storage_depth", DEFAULT_STORAGE_DEPTH)),
        "storage_height": float(entry.get("storage_height", DEFAULT_STORAGE_HEIGHT)),
        "plot_thickness": float(entry.get("plot_thickness", LOG_PLOT_THICKNESS)),
    }
    return params


def map_planning_constraint_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a Rahmenbedingung catalog entry into generator params.

    Vignette: flood zone, railway corridor, flight corridor + opaque building.
    """
    if not is_planning_constraint_entry(entry):
        raise ValueError(
            "unsupported element_type for planning constraint: "
            f"{entry.get('element_type')!r}"
        )

    flood_h = float(entry.get("flood_height", DEFAULT_FLOOD_HEIGHT))
    flight_w = float(entry.get("flight_width", CONSTRAINT_FLIGHT_WIDTH))
    flight_d = float(entry.get("flight_depth", CONSTRAINT_FLIGHT_DEPTH))
    flight_h = float(entry.get("flight_height", CONSTRAINT_FLIGHT_HEIGHT))
    geometry = {"area": flight_w * flight_d, "height": flight_h}

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=PLANNING_CONSTRAINT_ELEMENT_SLUG,
        defaults=PLANNING_CONSTRAINT_DEFAULTS,
        geometry=geometry,
    )

    quantities = resolved.get("quantities") or {}
    qto = quantities.setdefault("Qto_BuildingElementProxyBaseQuantities", {})
    qto["GrossVolume"] = round(flight_w * flight_d * flight_h, 3)

    constraint_names = entry.get("constraint_names") or [
        "Überschwemmungsgebiet",
        "Eisenbahnkorridor",
        entry.get("name")
        or resolved.get("Name")
        or PLANNING_CONSTRAINT_DEFAULTS["Name"],
    ]

    params: dict[str, Any] = {
        "project_name": entry.get("project_name")
        or entry.get("id")
        or "Rahmenbedingung",
        "name": entry.get("name")
        or resolved.get("Name")
        or PLANNING_CONSTRAINT_DEFAULTS["Name"],
        "predefined_type": resolved.get("PredefinedType") or "USERDEFINED",
        "object_type": resolved.get("ObjectType")
        or PLANNING_CONSTRAINT_DEFAULTS["ObjectType"],
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": quantities,
        "constraint_names": list(constraint_names),
        "building_width": float(
            entry.get("building_width", CONSTRAINT_BUILDING_WIDTH)
        ),
        "building_depth": float(
            entry.get("building_depth", CONSTRAINT_BUILDING_DEPTH)
        ),
        "building_height": float(
            entry.get("building_height", CONSTRAINT_BUILDING_HEIGHT)
        ),
        "yard": float(entry.get("yard", CONSTRAINT_YARD)),
        "flood_height": flood_h,
        "rail_width": float(entry.get("rail_width", DEFAULT_RAIL_WIDTH)),
        "rail_height": float(entry.get("rail_height", DEFAULT_RAIL_HEIGHT)),
        "flight_width": flight_w,
        "flight_depth": flight_d,
        "flight_height": flight_h,
        "plot_thickness": float(
            entry.get("plot_thickness", CONSTRAINT_PLOT_THICKNESS)
        ),
    }
    return params


def map_umbau_perimeter_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert an Umbauperimeter entry into the closed-storey plan vignette."""
    if not is_umbau_perimeter_entry(entry):
        raise ValueError(
            "unsupported element_type for alteration area: "
            f"{entry.get('element_type')!r}"
        )

    plan_w = float(entry.get("plan_width", entry.get("building_width", UMBAU_PLAN_WIDTH)))
    plan_d = float(entry.get("plan_depth", entry.get("building_depth", UMBAU_PLAN_DEPTH)))
    wall_t = float(entry.get("wall_thickness", UMBAU_WALL_THICKNESS))
    split_x = float(entry.get("split_x", UMBAU_SPLIT_X))
    perimeter_h = float(entry.get("perimeter_height", DEFAULT_PERIMETER_HEIGHT))
    inset = 0.12
    perimeter_w = split_x - wall_t - 2.0 * inset
    perimeter_d = plan_d - 2.0 * wall_t - 2.0 * inset
    geometry = {"area": perimeter_w * perimeter_d, "height": perimeter_h}

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=UMBAU_PERIMETER_ELEMENT_SLUG,
        defaults=UMBAU_PERIMETER_DEFAULTS,
        geometry=geometry,
    )
    quantities = resolved.get("quantities") or {}
    qto = quantities.setdefault("Qto_BuildingElementProxyBaseQuantities", {})
    qto["GrossVolume"] = round(perimeter_w * perimeter_d * perimeter_h, 3)

    return {
        "project_name": entry.get("project_name")
        or entry.get("id")
        or "Umbauperimeter",
        "name": entry.get("name")
        or resolved.get("Name")
        or UMBAU_PERIMETER_DEFAULTS["Name"],
        "predefined_type": resolved.get("PredefinedType") or "USERDEFINED",
        "object_type": resolved.get("ObjectType")
        or UMBAU_PERIMETER_DEFAULTS["ObjectType"],
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": quantities,
        "plan_width": plan_w,
        "plan_depth": plan_d,
        "wall_height": float(
            entry.get("wall_height", entry.get("building_height", UMBAU_WALL_HEIGHT))
        ),
        "wall_thickness": wall_t,
        "slab_thickness": float(entry.get("slab_thickness", UMBAU_SLAB_THICKNESS)),
        "split_x": split_x,
        "split_y": float(entry.get("split_y", 3.20)),
        "perimeter_height": perimeter_h,
    }


def map_stair_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a two-storey stair catalog entry into ``generate_stair`` params."""
    if entry.get("element_type") not in STAIR_TYPES:
        raise ValueError(
            f"unsupported element_type for stair: {entry.get('element_type')!r}"
        )

    storey_h = float(entry.get("storey_height", DEFAULT_STOREY_HEIGHT))
    flight_w = float(entry.get("flight_width", DEFAULT_FLIGHT_WIDTH))
    flight_run = float(entry.get("flight_run", DEFAULT_FLIGHT_RUN))
    landing_d = float(entry.get("landing_depth", DEFAULT_LANDING_DEPTH))
    step_count = int(entry.get("step_count", DEFAULT_STEP_COUNT))
    tread_t = float(entry.get("tread_thickness", DEFAULT_TREAD_THICKNESS))
    waist_t = float(entry.get("waist_thickness", DEFAULT_WAIST_THICKNESS))
    wall_t = float(entry.get("wall_thickness", DEFAULT_WALL_THICKNESS))
    landing_width = 2.0 * flight_w + 0.18
    plan_area = 2.0 * flight_w * flight_run + landing_width * landing_d
    geometry = {"area": plan_area, "height": storey_h}
    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=STAIR_ELEMENT_SLUG,
        defaults=STAIR_DEFAULTS,
        geometry=geometry,
    )
    quantities = resolved.get("quantities") or {}
    qto = quantities.setdefault("Qto_StairBaseQuantities", {})
    qto["GrossVolume"] = round(
        2.0 * step_count * flight_w * (flight_run / step_count) * tread_t
        + 2.0 * flight_w * flight_run * waist_t
        + landing_width * landing_d * tread_t,
        3,
    )
    resolved["quantities"] = quantities

    return {
        "project_name": entry.get("project_name") or entry.get("id") or "Treppe",
        "storey_height": storey_h,
        "flight_width": flight_w,
        "flight_run": flight_run,
        "landing_depth": landing_d,
        "step_count": step_count,
        "tread_thickness": tread_t,
        "waist_thickness": waist_t,
        "wall_thickness": wall_t,
        "resolved_attributes": resolved,
    }


def map_railing_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a simplified balcony-edge railing entry into generator params."""
    if entry.get("element_type") not in RAILING_TYPES:
        raise ValueError(
            f"unsupported element_type for railing: {entry.get('element_type')!r}"
        )

    length = float(entry.get("railing_length", DEFAULT_RAILING_LENGTH))
    height = float(entry.get("railing_height", DEFAULT_RAILING_HEIGHT))
    resolved_entry = dict(entry)
    resolved_entry["Length"] = length
    resolved_entry["Height"] = height
    resolved = build_element_attributes_from_yaml(
        entry=resolved_entry,
        element_slug=RAILING_ELEMENT_SLUG,
        defaults=RAILING_DEFAULTS,
        geometry={"height": height},
    )
    quantities = resolved.setdefault("quantities", {})
    quantities.setdefault("Qto_RailingBaseQuantities", {})["Length"] = length
    properties = resolved.setdefault("properties", {})
    properties.setdefault("Pset_RailingCommon", {})["Height"] = height

    balcony_depth = float(entry.get("balcony_depth", RAILING_BALCONY_DEPTH))
    interior_width = float(entry.get("interior_width", 2.0))
    interior_height = float(entry.get("interior_height", 2.8))
    finish_ceiling_height = float(entry.get("FinishCeilingHeight", 2.6))
    space_params = map_exterior_space_params(
        {
            "id": f"{entry.get('id') or 'railing'}-exterior-context",
            "element_type": "SPACE-EXT",
            "height": float(entry.get("exterior_space_height", 1.0)),
            "width": balcony_depth,
            "depth": length,
            "interior_width": interior_width,
            "interior_depth": length,
            "interior_height": interior_height,
            "FinishCeilingHeight": finish_ceiling_height,
        }
    )

    return {
        "project_name": entry.get("project_name")
        or entry.get("id")
        or "Absturzsicherung",
        "space_params": space_params,
        "railing_length": length,
        "railing_height": height,
        "railing_thickness": float(
            entry.get("railing_thickness", DEFAULT_RAILING_THICKNESS)
        ),
        "balcony_depth": balcony_depth,
        "resolved_attributes": resolved,
    }


def map_shading_device_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a shading-device entry into ``generate_shading`` params.

    Reuses the exterior-window vignette (no balcony) and places vertical
    lamellas on a 1 m cantilever above the opening.
    """
    if entry.get("element_type") not in SHADING_DEVICE_TYPES:
        raise ValueError(
            f"unsupported element_type for shading device: {entry.get('element_type')!r}"
        )

    cantilever = float(entry.get("cantilever", DEFAULT_CANTILEVER))
    lamella_count = int(entry.get("lamella_count", DEFAULT_LAMELLA_COUNT))
    lamella_height = float(entry.get("lamella_height", DEFAULT_LAMELLA_HEIGHT))
    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=SHADING_DEVICE_ELEMENT_SLUG,
        defaults=SHADING_DEVICE_DEFAULTS,
        geometry={"height": lamella_height, "area": cantilever * WINDOW_WIDTH},
    )
    space_params = map_exterior_space_params(_exterior_space_entry_from_fabric(entry))
    space_params["omit_primary_space"] = True
    space_params["include_interior_space"] = False
    space_params["include_balcony"] = False
    space_params["include_upper_balcony"] = False
    space_params["cladding_covers_slab"] = True

    return {
        "project_name": entry.get("project_name") or entry.get("id") or "Sonnenschutz",
        "space_params": space_params,
        "cantilever": cantilever,
        "lamella_count": lamella_count,
        "lamella_height": lamella_height,
        "resolved_attributes": resolved,
    }


def map_tree_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a Baum catalog entry into ``generate_tree`` params.

    Vignette: ground slab + root ball + trunk + crown ball (accent tree).
    """
    if not is_tree_entry(entry):
        raise ValueError(
            f"unsupported element_type for tree: {entry.get('element_type')!r}"
        )

    crown_r = float(entry.get("crown_radius", DEFAULT_CROWN_RADIUS))
    trunk_r = float(entry.get("trunk_radius", DEFAULT_TRUNK_RADIUS))
    trunk_h = float(entry.get("trunk_height", DEFAULT_TRUNK_HEIGHT))
    root_r = float(entry.get("root_radius", DEFAULT_ROOT_RADIUS))
    geometry = {
        "height": trunk_h + crown_r,
        "area": math.pi * max(crown_r, root_r) ** 2,
    }

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=TREE_ELEMENT_SLUG,
        defaults=TREE_DEFAULTS,
        geometry=geometry,
    )

    params: dict[str, Any] = {
        "project_name": entry.get("project_name") or entry.get("id") or "Baum",
        "name": entry.get("name") or resolved.get("Name") or TREE_DEFAULTS["Name"],
        "predefined_type": resolved.get("PredefinedType") or "VEGETATION",
        "object_type": resolved.get("ObjectType") or TREE_DEFAULTS["ObjectType"],
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": resolved.get("quantities") or {},
        "crown_radius": crown_r,
        "trunk_radius": trunk_r,
        "trunk_height": trunk_h,
        "root_radius": root_r,
    }
    if entry.get("with_context") is not None:
        params["with_context"] = entry["with_context"]
    if entry.get("ground_padding") is not None:
        params["ground_padding"] = float(entry["ground_padding"])
    return params


def map_humus_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a Humus catalog entry into ``generate_humus`` params."""
    if not is_humus_entry(entry):
        raise ValueError(
            f"unsupported element_type for humus: {entry.get('element_type')!r}"
        )

    length = float(entry.get("length", DEFAULT_LAYER_LENGTH))
    width = float(entry.get("width", DEFAULT_LAYER_WIDTH))
    thickness = float(entry.get("thickness", DEFAULT_LAYER_THICKNESS))
    geometry = {"area": length * width, "height": thickness}

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=HUMUS_ELEMENT_SLUG,
        defaults=HUMUS_DEFAULTS,
        geometry=geometry,
    )

    params: dict[str, Any] = {
        "project_name": entry.get("project_name") or entry.get("id") or "Humus",
        "name": entry.get("name") or resolved.get("Name") or HUMUS_DEFAULTS["Name"],
        "predefined_type": resolved.get("PredefinedType") or "USERDEFINED",
        "object_type": resolved.get("ObjectType") or HUMUS_DEFAULTS["ObjectType"],
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": resolved.get("quantities") or {},
        "length": length,
        "width": width,
        "thickness": thickness,
    }
    if entry.get("with_context") is not None:
        params["with_context"] = entry["with_context"]
    return params


def map_tree_pit_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a Baumgrube catalog entry into ``generate_tree_pit`` params."""
    if not is_tree_pit_entry(entry):
        raise ValueError(
            f"unsupported element_type for tree pit: {entry.get('element_type')!r}"
        )

    length = float(entry.get("length", DEFAULT_PIT_LENGTH))
    width = float(entry.get("width", DEFAULT_PIT_WIDTH))
    depth = float(entry.get("depth", DEFAULT_PIT_DEPTH))
    geometry = {"area": length * width, "height": depth}

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=TREE_PIT_ELEMENT_SLUG,
        defaults=TREE_PIT_DEFAULTS,
        geometry=geometry,
    )

    params: dict[str, Any] = {
        "project_name": entry.get("project_name") or entry.get("id") or "Baumgrube",
        "name": entry.get("name") or resolved.get("Name") or TREE_PIT_DEFAULTS["Name"],
        "predefined_type": resolved.get("PredefinedType") or "USERDEFINED",
        "object_type": resolved.get("ObjectType") or TREE_PIT_DEFAULTS["ObjectType"],
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": resolved.get("quantities") or {},
        "length": length,
        "width": width,
        "depth": depth,
    }
    if entry.get("with_context") is not None:
        params["with_context"] = entry["with_context"]
    return params


def map_retention_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a Retentionsvolumen catalog entry into ``generate_retention`` params."""
    if not is_retention_entry(entry):
        raise ValueError(
            f"unsupported element_type for retention: {entry.get('element_type')!r}"
        )

    length = float(entry.get("length", DEFAULT_BASIN_LENGTH))
    width = float(entry.get("width", DEFAULT_BASIN_WIDTH))
    depth = float(entry.get("depth", DEFAULT_BASIN_DEPTH))
    geometry = {"area": length * width, "height": depth}

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=RETENTION_ELEMENT_SLUG,
        defaults=RETENTION_DEFAULTS,
        geometry=geometry,
    )

    params: dict[str, Any] = {
        "project_name": entry.get("project_name")
        or entry.get("id")
        or "Retentionsvolumen",
        "name": entry.get("name") or resolved.get("Name") or RETENTION_DEFAULTS["Name"],
        "predefined_type": resolved.get("PredefinedType") or "USERDEFINED",
        "object_type": resolved.get("ObjectType") or RETENTION_DEFAULTS["ObjectType"],
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": resolved.get("quantities") or {},
        "length": length,
        "width": width,
        "depth": depth,
    }
    if entry.get("with_context") is not None:
        params["with_context"] = entry["with_context"]
    return params


def map_furniture_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a Möbel catalog entry into ``generate_furniture`` params.

    Vignette: either table + chair or a rough built-in kitchen line.
    """
    if not is_furniture_entry(entry):
        raise ValueError(
            f"unsupported element_type for furniture: {entry.get('element_type')!r}"
        )

    if entry.get("element_type") == "ARC-FURN-BUILTIN":
        unit_w = float(entry.get("unit_width", 0.60))
        tall_w = float(entry.get("tall_width", 0.60))
        depth = float(entry.get("kitchen_depth", 0.60))
        height = float(entry.get("tall_height", 2.20))
        resolved = build_element_attributes_from_yaml(
            entry=entry,
            element_slug=BUILT_IN_FURNITURE_ELEMENT_SLUG,
            defaults=BUILT_IN_FURNITURE_DEFAULTS,
            geometry={"area": (tall_w + 3.0 * unit_w) * depth, "height": height},
        )
        return {
            "project_name": entry.get("project_name")
            or entry.get("id")
            or "Einbaumoebel-Kueche",
            "predefined_type": resolved.get("PredefinedType") or "USERDEFINED",
            "object_type": resolved.get("ObjectType") or "Einbaumöbel",
            "properties": resolved.get("properties") or {},
            "property_datatypes": resolved.get("property_datatypes") or {},
            "quantities": resolved.get("quantities") or {},
            "room_width": float(entry.get("room_width", FURNITURE_ROOM_WIDTH)),
            "room_depth": float(entry.get("room_depth", FURNITURE_ROOM_DEPTH)),
            "wall_height": float(entry.get("wall_height", FURNITURE_WALL_HEIGHT)),
            "slab_thickness": float(
                entry.get("slab_thickness", FURNITURE_SLAB_THICKNESS)
            ),
            "unit_width": unit_w,
            "tall_width": tall_w,
            "kitchen_depth": depth,
            "tall_height": height,
        }

    table_w = float(entry.get("table_width", DEFAULT_TABLE_WIDTH))
    table_d = float(entry.get("table_depth", DEFAULT_TABLE_DEPTH))
    table_h = float(entry.get("table_height", DEFAULT_TABLE_HEIGHT))
    geometry = {"area": table_w * table_d, "height": table_h}

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=FURNITURE_ELEMENT_SLUG,
        defaults=FURNITURE_DEFAULTS,
        geometry=geometry,
    )

    params: dict[str, Any] = {
        "project_name": entry.get("project_name") or entry.get("id") or "Moebel",
        "name": entry.get("name") or resolved.get("Name") or FURNITURE_DEFAULTS["Name"],
        "predefined_type": resolved.get("PredefinedType") or "TABLE",
        "chair_name": entry.get("chair_name") or "Stuhl-01",
        "chair_predefined_type": entry.get("chair_predefined_type") or "CHAIR",
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": resolved.get("quantities") or {},
        "room_width": float(entry.get("room_width", FURNITURE_ROOM_WIDTH)),
        "room_depth": float(entry.get("room_depth", FURNITURE_ROOM_DEPTH)),
        "wall_height": float(entry.get("wall_height", FURNITURE_WALL_HEIGHT)),
        "slab_thickness": float(entry.get("slab_thickness", FURNITURE_SLAB_THICKNESS)),
        "table_width": table_w,
        "table_depth": table_d,
        "table_height": table_h,
        "chair_width": float(entry.get("chair_width", DEFAULT_CHAIR_WIDTH)),
        "chair_depth": float(entry.get("chair_depth", DEFAULT_CHAIR_DEPTH)),
    }
    return params


def _luftraum_entry_from_shared(entry: dict[str, Any]) -> dict[str, Any]:
    """Shared geometry for cards that reuse the Luftraum atrium vignette."""
    return {
        "id": entry.get("id"),
        "element_type": "SPACE-AIR",
        "height": entry.get("height", 2.8),
        "upper_height": entry.get("upper_height", 2.8),
        "width": entry.get("width", 4.0),
        "depth": entry.get("depth", 5.0),
        "FinishCeilingHeight": entry.get("FinishCeilingHeight", 2.6),
        "with_context": entry.get("with_context", True),
        **(
            {"boundary": entry["boundary"]}
            if entry.get("boundary") is not None
            else {}
        ),
        **(
            {"overhang": entry["overhang"]}
            if entry.get("overhang") is not None
            else {}
        ),
    }


def _luftraum_entry_from_coordination(entry: dict[str, Any]) -> dict[str, Any]:
    """Shared geometry for the Koordinationszone card (same as space-luftraum-01)."""
    return _luftraum_entry_from_shared(entry)


def map_beam_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a beam catalog entry into ``generate_beam`` params.

    Vignette: same Luftraum atrium as ``space-luftraum-01``; accent IfcBeams.
    """
    if not is_beam_entry(entry):
        raise ValueError(
            f"unsupported element_type for Beam mapping: {entry.get('element_type')!r}"
        )

    luftraum_params = map_luftraum_params(_luftraum_entry_from_shared(entry))
    luftraum_params["omit_luftraum"] = False
    luftraum_params["include_ceiling_covering"] = False
    luftraum_params["top_slab_half"] = True
    luftraum_params["project_name"] = (
        entry.get("project_name") or entry.get("id") or "Unterzug"
    )

    width = float(luftraum_params.get("width") or entry.get("width", 4.0))
    span = width + WALL_THICKNESS + NEIGHBOR_SPACE_WIDTH
    gross_volume = BEAM_WIDTH * BEAM_DEPTH * span

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=BEAM_ELEMENT_SLUG,
        defaults=BEAM_DEFAULTS,
        geometry={"area": span * BEAM_WIDTH, "height": BEAM_DEPTH},
    )
    quantities = resolved.get("quantities") or {}
    qto = quantities.setdefault("Qto_BeamBaseQuantities", {})
    qto["GrossVolume"] = round(gross_volume, 3)

    return {
        "luftraum_params": luftraum_params,
        "name": entry.get("name") or resolved.get("Name") or BEAM_DEFAULTS["Name"],
        "predefined_type": resolved.get("PredefinedType") or "BEAM",
        "object_type": resolved.get("ObjectType"),
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": quantities,
    }


def map_coordination_zone_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a Koordinationszone catalog entry into ``generate_coordination_zone`` params.

    Vignette: Luftraum roof/beam fabric (no spaces); accent one transparent
    proxy wrapping the top slab and beams (flush with beam ends by default).
    """
    if not is_coordination_zone_entry(entry):
        raise ValueError(
            "unsupported element_type for coordination zone: "
            f"{entry.get('element_type')!r}"
        )

    luftraum_params = map_luftraum_params(_luftraum_entry_from_coordination(entry))
    luftraum_params["omit_spaces"] = True
    luftraum_params["project_name"] = (
        entry.get("project_name") or entry.get("id") or "Koordinationszone"
    )

    zone_height = float(entry.get("zone_height", DEFAULT_ZONE_HEIGHT))
    zone_margin = float(entry.get("zone_margin", DEFAULT_ZONE_MARGIN))
    width = float(luftraum_params.get("width") or entry.get("width", 4.0))
    depth = float(luftraum_params.get("depth") or entry.get("depth", 5.0))
    # Bay footprint (+ optional equal margin on every side)
    footprint = (width + WALL_THICKNESS + NEIGHBOR_SPACE_WIDTH + 2 * zone_margin) * (
        depth + 2 * zone_margin
    )
    geometry = {"area": footprint, "height": zone_height}

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=COORDINATION_ZONE_ELEMENT_SLUG,
        defaults=COORDINATION_ZONE_DEFAULTS,
        geometry=geometry,
    )

    quantities = resolved.get("quantities") or {}
    qto = quantities.setdefault("Qto_BuildingElementProxyBaseQuantities", {})
    qto["GrossVolume"] = round(footprint * zone_height, 3)

    return {
        "luftraum_params": luftraum_params,
        "zone_height": zone_height,
        "zone_margin": zone_margin,
        "name": entry.get("name")
        or resolved.get("Name")
        or COORDINATION_ZONE_DEFAULTS["Name"],
        "predefined_type": resolved.get("PredefinedType") or "USERDEFINED",
        "object_type": resolved.get("ObjectType")
        or COORDINATION_ZONE_DEFAULTS["ObjectType"],
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": quantities,
    }


def map_roof_pitched_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a Steildach catalog entry into ``generate_pitched_roof`` params.

    Vignette: floor plate + attic IfcSpace following the gable underside + IfcRoof.
    """
    if not is_roof_pitched_entry(entry):
        raise ValueError(
            f"unsupported element_type for pitched roof: {entry.get('element_type')!r}"
        )

    width = float(entry.get("width", ROOF_DEFAULT_WIDTH))
    depth = float(entry.get("depth", ROOF_DEFAULT_DEPTH))
    eave_h = float(entry.get("eave_height", DEFAULT_EAVE_HEIGHT))
    rise = float(entry.get("rise", DEFAULT_RISE))
    roof_t = float(entry.get("roof_thickness", DEFAULT_ROOF_THICKNESS))
    floor_t = float(entry.get("floor_thickness", ROOF_FLOOR_THICKNESS))
    intermediate_z = float(
        entry.get(
            "intermediate_slab_elevation",
            DEFAULT_INTERMEDIATE_SLAB_ELEVATION,
        )
    )
    half_width = width * 0.5
    upper_z = intermediate_z + floor_t

    geometry = {
        "area": pitched_roof_gross_area(width, depth, rise),
        "height": roof_t,
    }
    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=ROOF_PITCHED_ELEMENT_SLUG,
        defaults=ROOF_PITCHED_DEFAULTS,
        geometry=geometry,
    )

    quantities = resolved.get("quantities") or {}
    qto = quantities.setdefault("Qto_RoofBaseQuantities", {})
    qto["GrossArea"] = round(geometry["area"], 2)

    space_geometry = {
        "height": eave_h + rise - upper_z,
        "area": half_width * depth,
        "finish_ceiling_height": eave_h + rise - upper_z,
    }
    space_defaults = roof_attic_space_defaults()
    space_defaults["FinishCeilingHeight"] = space_geometry["height"]
    space_resolved = build_space_attributes_from_yaml(
        entry=dict(entry.get("space") or {}),
        geometry=space_geometry,
        element_slug=SPACE_ELEMENT_SLUG,
        defaults=space_defaults,
    )
    space_qto = (space_resolved.get("quantities") or {}).setdefault(
        "Qto_SpaceBaseQuantities", {}
    )
    space_qto["NetFloorArea"] = round(half_width * depth, 2)
    space_qto["GrossFloorArea"] = round(half_width * depth, 2)
    space_qto["Height"] = round(space_geometry["height"], 2)
    space_qto["GrossVolume"] = round(
        (
            half_width * (eave_h - upper_z)
            + 0.5 * half_width * rise
        )
        * depth,
        2,
    )
    space_qto["FinishCeilingHeight"] = round(space_geometry["height"], 2)

    luftraum_geometry = {
        "height": eave_h + rise - intermediate_z,
        "area": half_width * depth,
        "finish_ceiling_height": eave_h + rise - intermediate_z,
    }
    luftraum_resolved = build_space_attributes_from_yaml(
        entry=dict(entry.get("luftraum") or {}),
        geometry=luftraum_geometry,
        element_slug=LUFTRAUM_ELEMENT_SLUG,
        defaults=luftraum_defaults(),
    )
    luftraum_qto = (luftraum_resolved.get("quantities") or {}).setdefault(
        "Qto_SpaceBaseQuantities", {}
    )
    luftraum_qto["NetFloorArea"] = round(half_width * depth, 2)
    luftraum_qto["GrossFloorArea"] = round(half_width * depth, 2)
    luftraum_qto["Height"] = round(luftraum_geometry["height"], 2)
    luftraum_qto["GrossVolume"] = round(
        (
            half_width * (eave_h - intermediate_z)
            + 0.5 * half_width * rise
        )
        * depth,
        2,
    )

    lower_space_geometry = {
        "height": intermediate_z,
        "area": width * depth,
        "finish_ceiling_height": intermediate_z,
    }
    lower_space_defaults = roof_attic_space_defaults()
    lower_space_defaults.update(
        {
            "Name": "201",
            "SignageRoomNumber": "201",
            "FinishCeilingHeight": intermediate_z,
        }
    )
    lower_space_resolved = build_space_attributes_from_yaml(
        entry=dict(entry.get("lower_space") or {}),
        geometry=lower_space_geometry,
        element_slug=SPACE_ELEMENT_SLUG,
        defaults=lower_space_defaults,
    )
    lower_space_qto = (
        lower_space_resolved.get("quantities") or {}
    ).setdefault("Qto_SpaceBaseQuantities", {})
    lower_space_qto["NetFloorArea"] = round(width * depth, 2)
    lower_space_qto["GrossFloorArea"] = round(width * depth, 2)
    lower_space_qto["Height"] = round(intermediate_z, 2)
    lower_space_qto["GrossVolume"] = round(
        width * depth * intermediate_z, 2
    )

    params: dict[str, Any] = {
        "project_name": entry.get("project_name") or entry.get("id") or "Steildach",
        "name": entry.get("name") or resolved.get("Name") or ROOF_PITCHED_DEFAULTS["Name"],
        "predefined_type": resolved.get("PredefinedType") or "GABLE_ROOF",
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": quantities,
        "space_attrs": space_resolved,
        "lower_space_attrs": lower_space_resolved,
        "luftraum_attrs": luftraum_resolved,
        "width": width,
        "depth": depth,
        "eave_height": eave_h,
        "rise": rise,
        "roof_thickness": roof_t,
        "floor_thickness": floor_t,
        "intermediate_slab_elevation": intermediate_z,
    }
    if resolved.get("ObjectType") is not None:
        params["ObjectType"] = resolved["ObjectType"]
    return params


def map_roofing_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a Gefälledämmung catalog entry into ``generate_roofing`` params.

    Vignette: roof slab + Attika + exterior cladding; accent tapered ROOFING.
    """
    if not is_roofing_entry(entry):
        raise ValueError(
            f"unsupported element_type for Roofing mapping: {entry.get('element_type')!r}"
        )

    slab_w = float(entry.get("slab_width", ROOFING_SLAB_WIDTH))
    slab_d = float(entry.get("slab_depth", ROOFING_SLAB_DEPTH))
    parapet_t = float(entry.get("parapet_thickness", DEFAULT_PARAPET_THICKNESS))
    inset = float(entry.get("roofing_edge_inset", DEFAULT_ROOFING_EDGE_INSET))
    roof_w = max(slab_w - 2.0 * inset, 0.01)
    roof_d = max(slab_d - parapet_t - 2.0 * inset, 0.01)
    geometry = {"area": roof_w * roof_d, "height": float(
        entry.get("roofing_thickness_start", DEFAULT_ROOFING_THICK_START)
    )}

    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=ROOFING_ELEMENT_SLUG,
        defaults=ROOFING_DEFAULTS,
        geometry=geometry,
    )

    quantities = resolved.get("quantities") or {}
    qto = quantities.setdefault("Qto_CoveringBaseQuantities", {})
    qto["NetArea"] = round(roof_w * roof_d, 2)

    params: dict[str, Any] = {
        "project_name": entry.get("project_name") or entry.get("id") or "Gefaelledaemmung",
        "name": entry.get("name") or resolved.get("Name") or ROOFING_DEFAULTS["Name"],
        "predefined_type": resolved.get("PredefinedType") or "ROOFING",
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": quantities,
        "slab_attrs": {
            "Name": "Flachdach",
            "PredefinedType": "ROOF",
        },
        "wall_attrs": {
            "Name": "Attika",
            "PredefinedType": "SOLIDWALL",
        },
        "cladding_attrs": {
            "Name": "Fassadenbekleidung",
            "PredefinedType": "CLADDING",
        },
        "slab_width": slab_w,
        "slab_depth": slab_d,
        "slab_thickness": float(
            entry.get("slab_thickness", ROOFING_SLAB_THICKNESS)
        ),
        "parapet_height": float(entry.get("parapet_height", DEFAULT_PARAPET_HEIGHT)),
        "parapet_thickness": parapet_t,
        "roofing_thickness_start": float(
            entry.get("roofing_thickness_start", DEFAULT_ROOFING_THICK_START)
        ),
        "roofing_thickness_end": float(
            entry.get("roofing_thickness_end", DEFAULT_ROOFING_THICK_END)
        ),
        "roofing_edge_inset": inset,
    }
    if resolved.get("ObjectType") is not None:
        params["ObjectType"] = resolved["ObjectType"]
    return params


def map_opening_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert an opening catalog entry into ``generate_opening`` params.

    Geometry matches the interior-space fabric (no spaces / no ceiling); opening
    attributes come from ``architecture-opening-void.yaml``.
    """
    if not is_opening_entry(entry):
        raise ValueError(
            f"unsupported element_type for Opening mapping: {entry.get('element_type')!r}"
        )

    clear_width = float(entry.get("clear_width", entry.get("Width", OPENING_DEFAULTS["Width"])))
    clear_height = float(
        entry.get("clear_height", entry.get("Height", OPENING_DEFAULTS["Height"]))
    )

    space_entry = {
        "id": entry.get("id"),
        "element_type": "IfcSpace",
        "height": entry.get("height", 2.8),
        "FinishCeilingHeight": entry.get("FinishCeilingHeight", 2.6),
        "with_context": entry.get("with_context", True),
    }
    if entry.get("boundary"):
        space_entry["boundary"] = entry["boundary"]
    else:
        space_entry["width"] = entry.get("width", 4.0)
        space_entry["depth"] = entry.get("depth", 5.0)

    space_params = map_space_params(space_entry)
    space_params["omit_primary_space"] = True
    space_params["include_neighbor_space"] = False
    space_params["include_ceiling_covering"] = False
    space_params["include_ceiling_slab"] = False
    space_params["include_floor_slab"] = False
    space_params["include_floor_covering"] = False

    geometry = {"height": clear_height, "area": clear_width * clear_height}
    defaults = {
        **OPENING_DEFAULTS,
        "Width": clear_width,
        "Height": clear_height,
    }
    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=OPENING_ELEMENT_SLUG,
        defaults=defaults,
        geometry=geometry,
    )

    quantities = resolved.get("quantities") or {}
    qto = quantities.setdefault("Qto_OpeningElementBaseQuantities", {})
    qto["Width"] = clear_width
    qto["Height"] = clear_height

    return {
        "space_params": space_params,
        "name": entry.get("name") or resolved.get("Name") or OPENING_DEFAULTS["Name"],
        "predefined_type": resolved.get("PredefinedType") or "OPENING",
        "clear_width": clear_width,
        "clear_height": clear_height,
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": quantities,
        **(
            {"sill": float(entry["sill"])}
            if entry.get("sill") is not None
            else {}
        ),
        **(
            {"duct_overhang": float(entry["duct_overhang"])}
            if entry.get("duct_overhang") is not None
            else {}
        ),
    }


def is_reference_point_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in REFERENCE_POINT_TYPES


def is_gross_volume_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in GROSS_VOLUME_TYPES


def is_spatial_structure_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in SPATIAL_STRUCTURE_TYPES


def is_slab_entry(entry: dict[str, Any]) -> bool:
    return entry.get("element_type") in SLAB_TYPES


def _slab_geometry(entry: dict[str, Any]) -> dict[str, float]:
    width = float(entry.get("building_width", DEFAULT_BUILDING_WIDTH))
    depth = float(entry.get("building_depth", DEFAULT_BUILDING_DEPTH))
    thickness = float(entry.get("slab_thickness", DEFAULT_SLAB_THICKNESS))
    return {"area": width * depth, "height": thickness}


def _build_slab_attrs_list(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Resolve attributes for Bodenplatte / Decke / Flachdach in the shared vignette."""
    geometry = _slab_geometry(entry)
    overrides = entry.get("slabs") or {}

    specs = (
        (
            SLAB_BASE_ELEMENT_SLUG,
            SLAB_BASE_DEFAULTS,
            dict(overrides.get("base") or {}),
        ),
        (
            SLAB_FLOOR_ELEMENT_SLUG,
            SLAB_FLOOR_DEFAULTS,
            dict(overrides.get("floor") or {}),
        ),
        (
            SLAB_ROOF_ELEMENT_SLUG,
            SLAB_ROOF_DEFAULTS,
            dict(overrides.get("roof") or {}),
        ),
    )
    # Top-level attribute overrides apply to the highlighted slab only.
    highlight = entry.get("highlight") or _HIGHLIGHT_BY_TYPE.get(
        entry.get("element_type", ""), "slab-floor"
    )
    highlight_key = {
        "slab-base": "base",
        "slab-floor": "floor",
        "slab-roof": "roof",
    }.get(highlight)

    result: list[dict[str, Any]] = []
    for slug, defaults, slab_entry in specs:
        if highlight_key and (
            (slug == SLAB_BASE_ELEMENT_SLUG and highlight_key == "base")
            or (slug == SLAB_FLOOR_ELEMENT_SLUG and highlight_key == "floor")
            or (slug == SLAB_ROOF_ELEMENT_SLUG and highlight_key == "roof")
        ):
            for key, value in entry.items():
                if key in {
                    "id",
                    "element_type",
                    "highlight",
                    "attach_element",
                    "slabs",
                    "project",
                    "site",
                    "building",
                    "storey_names",
                    "plot_width",
                    "plot_depth",
                    "building_width",
                    "building_depth",
                    "slab_thickness",
                    "plot_thickness",
                    "storey_spacing",
                    "balcony_width",
                    "balcony_depth",
                    "balcony",
                }:
                    continue
                if key not in slab_entry:
                    slab_entry[key] = value

        resolved = build_element_attributes_from_yaml(
            entry=slab_entry,
            element_slug=slug,
            defaults=defaults,
            geometry=geometry,
        )
        quantities = resolved.setdefault("quantities", {})
        qto = quantities.setdefault("Qto_SlabBaseQuantities", {})
        qto["GrossVolume"] = round(geometry["area"] * geometry["height"], 2)
        if slug == SLAB_ROOF_ELEMENT_SLUG:
            qto["GrossArea"] = round(geometry["area"], 2)
        result.append(resolved)
    return result


def _build_balcony_attrs(entry: dict[str, Any]) -> dict[str, Any]:
    """Resolve attributes for the projecting storey-01 balcony (IfcSlab FLOOR)."""
    thickness = float(entry.get("slab_thickness", DEFAULT_SLAB_THICKNESS))
    width = float(entry.get("balcony_width", DEFAULT_BALCONY_WIDTH))
    depth = float(entry.get("balcony_depth", DEFAULT_BALCONY_DEPTH))
    geometry = {"area": width * depth, "height": thickness}
    balcony_entry = dict(entry.get("balcony") or {})

    highlight = entry.get("highlight") or _HIGHLIGHT_BY_TYPE.get(
        entry.get("element_type", ""), ""
    )
    if highlight == "slab-balcony":
        for key, value in entry.items():
            if key in {
                "id",
                "element_type",
                "highlight",
                "attach_element",
                "slabs",
                "balcony",
                "project",
                "site",
                "building",
                "storey_names",
                "plot_width",
                "plot_depth",
                "building_width",
                "building_depth",
                "slab_thickness",
                "plot_thickness",
                "storey_spacing",
                "balcony_width",
                "balcony_depth",
            }:
                continue
            if key not in balcony_entry:
                balcony_entry[key] = value

    resolved = build_element_attributes_from_yaml(
        entry=balcony_entry,
        element_slug=SLAB_BALCONY_ELEMENT_SLUG,
        defaults=SLAB_BALCONY_DEFAULTS,
        geometry=geometry,
    )
    quantities = resolved.setdefault("quantities", {})
    qto = quantities.setdefault("Qto_SlabBaseQuantities", {})
    qto["GrossVolume"] = round(geometry["area"] * geometry["height"], 2)
    qto["GrossArea"] = round(geometry["area"], 2)
    return resolved


def map_spatial_structure_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a Project/Site/Building/Storey catalog entry into vignette params.

    Attributes come from ``elements/{project,site,building,storey}.yaml`` with
    stable defaults; nested ``project`` / ``site`` / ``building`` dicts or
    top-level Name/Phase/storey_names override.
    """
    if not is_spatial_structure_entry(entry):
        raise ValueError(
            f"unsupported element_type for spatial structure: {entry.get('element_type')!r}"
        )

    element_type = entry["element_type"]
    highlight = entry.get("highlight") or _HIGHLIGHT_BY_TYPE[element_type]

    project_entry = dict(entry.get("project") or {})
    if "Name" in entry and "Name" not in project_entry and highlight == "project":
        project_entry["Name"] = entry["Name"]
    if "Phase" in entry and "Phase" not in project_entry:
        project_entry["Phase"] = entry["Phase"]

    site_entry = dict(entry.get("site") or {})
    building_entry = dict(entry.get("building") or {})
    storey_names = tuple(entry.get("storey_names") or DEFAULT_STOREY_NAMES)

    project_attrs = build_element_attributes_from_yaml(
        entry=project_entry,
        element_slug=PROJECT_ELEMENT_SLUG,
        defaults=PROJECT_DEFAULTS,
    )
    site_attrs = build_element_attributes_from_yaml(
        entry=site_entry,
        element_slug=SITE_ELEMENT_SLUG,
        defaults=SITE_DEFAULTS,
    )
    building_attrs = build_element_attributes_from_yaml(
        entry=building_entry,
        element_slug=BUILDING_ELEMENT_SLUG,
        defaults=BUILDING_DEFAULTS,
    )
    storey_attrs = [
        build_element_attributes_from_yaml(
            entry={"Name": name},
            element_slug=STOREY_ELEMENT_SLUG,
            defaults={"Name": name},
        )
        for name in storey_names
    ]

    params: dict[str, Any] = {
        "highlight": highlight,
        "project_name": project_attrs.get("Name") or PROJECT_DEFAULTS["Name"],
        "storey_names": storey_names,
        "project_attrs": project_attrs,
        "site_attrs": site_attrs,
        "building_attrs": building_attrs,
        "storey_attrs": storey_attrs,
        # Same opaque plates as slab cards; hierarchy pictures do not need full attrs.
        "slab_attrs": _build_slab_attrs_list(entry),
        "balcony_attrs": _build_balcony_attrs(entry),
    }
    for key in (
        "plot_width",
        "plot_depth",
        "building_width",
        "building_depth",
        "slab_thickness",
        "plot_thickness",
        "storey_spacing",
        "balcony_width",
        "balcony_depth",
    ):
        if entry.get(key) is not None:
            params[key] = entry[key]
    return params


def map_slab_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a Bodenplatte / Decke / Flachdach / Balkon catalog entry into params.

    Reuses the Project/Site/Building/Storey opaque-slab model; ``highlight`` accents
    the matching plate (base / floor / roof / balcony).
    """
    if not is_slab_entry(entry):
        raise ValueError(
            f"unsupported element_type for slab mapping: {entry.get('element_type')!r}"
        )

    element_type = entry["element_type"]
    highlight = entry.get("highlight") or _HIGHLIGHT_BY_TYPE[element_type]
    storey_names = tuple(entry.get("storey_names") or DEFAULT_STOREY_NAMES)

    project_attrs = build_element_attributes_from_yaml(
        entry=dict(entry.get("project") or {}),
        element_slug=PROJECT_ELEMENT_SLUG,
        defaults=PROJECT_DEFAULTS,
    )
    site_attrs = build_element_attributes_from_yaml(
        entry=dict(entry.get("site") or {}),
        element_slug=SITE_ELEMENT_SLUG,
        defaults=SITE_DEFAULTS,
    )
    building_attrs = build_element_attributes_from_yaml(
        entry=dict(entry.get("building") or {}),
        element_slug=BUILDING_ELEMENT_SLUG,
        defaults=BUILDING_DEFAULTS,
    )
    storey_attrs = [
        build_element_attributes_from_yaml(
            entry={"Name": name},
            element_slug=STOREY_ELEMENT_SLUG,
            defaults={"Name": name},
        )
        for name in storey_names
    ]

    params: dict[str, Any] = {
        "highlight": highlight,
        "project_name": project_attrs.get("Name") or PROJECT_DEFAULTS["Name"],
        "storey_names": storey_names,
        "project_attrs": project_attrs,
        "site_attrs": site_attrs,
        "building_attrs": building_attrs,
        "storey_attrs": storey_attrs,
        "slab_attrs": _build_slab_attrs_list(entry),
        "balcony_attrs": _build_balcony_attrs(entry),
    }
    for key in (
        "plot_width",
        "plot_depth",
        "building_width",
        "building_depth",
        "slab_thickness",
        "plot_thickness",
        "storey_spacing",
        "balcony_width",
        "balcony_depth",
    ):
        if entry.get(key) is not None:
            params[key] = entry[key]
    return params

def map_gross_volume_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a Bruttovolumen catalog entry into ``generate_gross_volumes`` params."""
    if not is_gross_volume_entry(entry):
        raise ValueError(
            f"unsupported element_type for gross volume: {entry.get('element_type')!r}"
        )

    storey_names = tuple(entry.get("storey_names") or DEFAULT_STOREY_NAMES)
    height = float(entry.get("height", 3.0))
    foundation_height = float(entry.get("foundation_height", 0.50))
    unit_overrides = entry.get("units") or {}

    unit_templates: dict[str, dict[str, Any]] = {}
    for key, defaults in GROSS_VOLUME_UNIT_DEFAULTS.items():
        unit_entry = dict(unit_overrides.get(key) or {})
        geom_height = foundation_height if key == "foundation" else height
        resolved = build_element_attributes_from_yaml(
            entry=unit_entry,
            element_slug=GROSS_VOLUME_ELEMENT_SLUG,
            defaults=defaults,
            geometry={"height": geom_height},
        )
        unit_templates[key] = {
            "name": resolved.get("Name") or defaults["Name"],
            "long_name": resolved.get("LongName") or defaults["LongName"],
            "predefined_type": resolved.get("PredefinedType") or "GFA",
            "object_type": resolved.get("ObjectType"),
            "properties": resolved.get("properties") or {},
            "property_datatypes": resolved.get("property_datatypes") or {},
            "quantities": resolved.get("quantities") or {},
        }

    params: dict[str, Any] = {
        "project_name": entry.get("project_name") or entry.get("id") or "Bruttovolumen",
        "storey_names": storey_names,
        "height": height,
        "foundation_height": foundation_height,
        "unit_templates": unit_templates,
    }
    for key in (
        "building_width",
        "building_depth",
        "stair_width",
        "stair_depth",
        "plot_width",
        "plot_depth",
        "plot_thickness",
        "storey_spacing",
        "foundation_storey",
    ):
        if entry.get(key) is not None:
            params[key] = entry[key]
    return params


def map_reference_point_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a catalog Bezugspunkt instance into ``generate_reference_points`` params."""
    if not is_reference_point_entry(entry):
        raise ValueError(
            f"unsupported element_type for reference points: {entry.get('element_type')!r}"
        )

    points = entry.get("points")
    if not points or len(points) < 3:
        raise ValueError(
            f"entry {entry.get('id')!r}: at least three points are required"
        )

    origin = dict(DEFAULT_ORIGIN_LV95)
    origin.update(entry.get("origin_lv95") or {})

    params: dict[str, Any] = {
        "project_name": entry.get("project_name") or entry.get("id") or "Bezugspunkte",
        "origin_lv95": origin,
        "points": list(points),
    }
    if entry.get("marker_height") is not None:
        params["marker_height"] = entry["marker_height"]
    if entry.get("marker_half_base") is not None:
        params["marker_half_base"] = entry["marker_half_base"]
    if entry.get("with_context") is not None:
        params["with_context"] = entry["with_context"]
    return params


def map_entry_params(entry: dict[str, Any]) -> dict[str, Any]:
    """Dispatch catalog entry → generator params by element_type."""
    element_type = entry.get("element_type")
    if element_type in SPACE_TYPES:
        return map_space_params(entry)
    if element_type in EXTERIOR_SPACE_TYPES:
        return map_exterior_space_params(entry)
    if element_type in PARKING_TYPES:
        return map_parking_params(entry)
    if element_type in ELEVATOR_TYPES:
        return map_elevator_params(entry)
    if element_type in VORSATZSCHALE_TYPES:
        return map_vorsatzschale_params(entry)
    if element_type in LUFTRAUM_TYPES:
        return map_luftraum_params(entry)
    if element_type in COVERING_TYPES:
        return map_covering_params(entry)
    if element_type in GROSS_VOLUME_TYPES:
        return map_gross_volume_params(entry)
    if element_type in REFERENCE_POINT_TYPES:
        return map_reference_point_params(entry)
    if element_type in SPATIAL_STRUCTURE_TYPES:
        return map_spatial_structure_params(entry)
    if element_type in SLAB_TYPES:
        return map_slab_params(entry)
    if element_type in OPENING_TYPES:
        return map_opening_params(entry)
    if element_type in FOOTING_TYPES:
        return map_footing_params(entry)
    if element_type in COLUMN_TYPES:
        return map_column_params(entry)
    if element_type in MAINTENANCE_SPACE_TYPES:
        return map_maintenance_space_params(entry)
    if element_type in INSTALLATION_PATH_TYPES:
        return map_installation_path_params(entry)
    if element_type in TURNING_RADIUS_TYPES:
        return map_turning_radius_params(entry)
    if element_type in DECISION_VOLUME_TYPES:
        return map_decision_volume_params(entry)
    if element_type in MOVEMENT_CLEARANCE_TYPES:
        return map_movement_clearance_params(entry)
    if element_type in BUILDING_LAW_PARCEL_TYPES:
        return map_building_law_parcel_params(entry)
    if element_type in SURROUNDING_BUILDING_TYPES:
        return map_surrounding_building_params(entry)
    if element_type in CONSTRUCTION_LOGISTICS_TYPES:
        return map_construction_logistics_params(entry)
    if element_type in PLANNING_CONSTRAINT_TYPES:
        return map_planning_constraint_params(entry)
    if element_type in UMBAU_PERIMETER_TYPES:
        return map_umbau_perimeter_params(entry)
    if element_type in STAIR_TYPES:
        return map_stair_params(entry)
    if element_type in RAILING_TYPES:
        return map_railing_params(entry)
    if element_type in SHADING_DEVICE_TYPES:
        return map_shading_device_params(entry)
    if element_type in TREE_TYPES:
        return map_tree_params(entry)
    if element_type in HUMUS_TYPES:
        return map_humus_params(entry)
    if element_type in TREE_PIT_TYPES:
        return map_tree_pit_params(entry)
    if element_type in RETENTION_TYPES:
        return map_retention_params(entry)
    if element_type in FURNITURE_TYPES:
        return map_furniture_params(entry)
    if element_type in COORDINATION_ZONE_TYPES:
        return map_coordination_zone_params(entry)
    if element_type in BEAM_TYPES:
        return map_beam_params(entry)
    if element_type in ROOF_PITCHED_TYPES:
        return map_roof_pitched_params(entry)
    if element_type in ROOFING_TYPES:
        return map_roofing_params(entry)
    if element_type in EXTERIOR_FABRIC_TYPES:
        return map_exterior_fabric_params(entry)
    if element_type in INTERIOR_FABRIC_TYPES:
        return map_interior_fabric_params(entry)
    if element_type in DETAIL_REFERENCE_TYPES:
        return map_detail_reference_params(entry)
    raise ValueError(f"unsupported element_type: {element_type!r}")


def get_generator(element_type: str) -> Callable[[dict[str, Any]], tuple]:
    """Return the generator callable for ``element_type``, or raise KeyError."""
    try:
        return ELEMENT_GENERATORS[element_type]
    except KeyError as exc:
        raise KeyError(f"no generator registered for element_type={element_type!r}") from exc
