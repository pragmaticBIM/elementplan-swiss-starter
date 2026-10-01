"""Load Elementplan YAML element/value definitions and resolve attribute values."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
ELEMENTS_DIR = REPO_ROOT / "elements"
VALUES_DIR = REPO_ROOT / "values"

# Catalog element slug used for Space generators
SPACE_ELEMENT_SLUG = "spaces-interior"
EXTERIOR_SPACE_ELEMENT_SLUG = "spaces-exterior"
PARKING_ELEMENT_SLUG = "spaces-parking"
ELEVATOR_ELEMENT_SLUG = "spaces-elevator"
VORSATZSCHALE_ELEMENT_SLUG = "spaces-vorsatzschale"
CEILING_ELEMENT_SLUG = "architecture-ceiling-suspended"
FLOOR_COVERING_ELEMENT_SLUG = "architecture-floor-covering"
FLOOR_COVERING_EXTERIOR_ELEMENT_SLUG = "architecture-floor-covering-exterior"
GROSS_VOLUME_ELEMENT_SLUG = "spaces-gross-volume"
LUFTRAUM_ELEMENT_SLUG = "spaces-luftraum"
PROJECT_ELEMENT_SLUG = "project"
SITE_ELEMENT_SLUG = "site"
BUILDING_ELEMENT_SLUG = "building"
STOREY_ELEMENT_SLUG = "storey"
SLAB_BASE_ELEMENT_SLUG = "architecture-slab-base"
SLAB_FLOOR_ELEMENT_SLUG = "architecture-slab-floor"
SLAB_ROOF_ELEMENT_SLUG = "architecture-slab-flat-roof"
SLAB_BALCONY_ELEMENT_SLUG = "architecture-slab-balcony"
OPENING_ELEMENT_SLUG = "architecture-opening-void"
FOOTING_ELEMENT_SLUG = "architecture-footing"
COLUMN_ELEMENT_SLUG = "architecture-column"
MAINTENANCE_SPACE_ELEMENT_SLUG = "architecture-maintenance-space"
INSTALLATION_PATH_ELEMENT_SLUG = "architecture-installation-path"
TURNING_RADIUS_ELEMENT_SLUG = "architecture-turning-radius"
DECISION_VOLUME_ELEMENT_SLUG = "architecture-decision-volume"
MOVEMENT_CLEARANCE_ELEMENT_SLUG = "architecture-movement-clearance"
BUILDING_LAW_PARCEL_ELEMENT_SLUG = "architecture-building-law-parcel"
SURROUNDING_BUILDING_ELEMENT_SLUG = "architecture-surrounding-building"
CONSTRUCTION_LOGISTICS_ELEMENT_SLUG = "architecture-construction-logistics"
PLANNING_CONSTRAINT_ELEMENT_SLUG = "architecture-planning-constraint"
UMBAU_PERIMETER_ELEMENT_SLUG = "architecture-umbau-perimeter"
STAIR_ELEMENT_SLUG = "architecture-stair"
RAILING_ELEMENT_SLUG = "architecture-railing"
SHADING_DEVICE_ELEMENT_SLUG = "architecture-shading-device"
COORDINATION_ZONE_ELEMENT_SLUG = "architecture-coordination-zone"
ROOF_PITCHED_ELEMENT_SLUG = "architecture-roof-pitched"
ROOFING_ELEMENT_SLUG = "architecture-roof-drainage"
WALL_EXTERIOR_ELEMENT_SLUG = "architecture-wall-exterior"
CLADDING_EXTERIOR_ELEMENT_SLUG = "architecture-wall-cladding-exterior"
WALL_INTERIOR_ELEMENT_SLUG = "architecture-wall-interior"
WALL_INTERIOR_LB_ELEMENT_SLUG = "architecture-wall-interior-loadbearing"
DRYWALL_REINFORCEMENT_ELEMENT_SLUG = "architecture-drywall-reinforcement"
CLADDING_INTERIOR_ELEMENT_SLUG = "architecture-wall-cladding-interior"
DOOR_EXTERIOR_ELEMENT_SLUG = "architecture-door-exterior"
DOOR_INTERIOR_ELEMENT_SLUG = "architecture-door-interior"
WINDOW_EXTERIOR_ELEMENT_SLUG = "architecture-window-exterior"
WINDOW_INTERIOR_ELEMENT_SLUG = "architecture-window-interior"
DETAIL_REFERENCE_ELEMENT_SLUG = "architecture-detail-reference"
BEAM_ELEMENT_SLUG = "architecture-beam"
TREE_ELEMENT_SLUG = "landscape-tree"
HUMUS_ELEMENT_SLUG = "landscape-humus"
TREE_PIT_ELEMENT_SLUG = "landscape-tree-pit"
RETENTION_ELEMENT_SLUG = "landscape-retention"
FURNITURE_ELEMENT_SLUG = "furniture"
BUILT_IN_FURNITURE_ELEMENT_SLUG = "architecture-built-in-furniture"

# Entity-level attributes (pset is null) applied as IFC fields, not Psets
_ENTITY_ATTRS = frozenset({"Name", "LongName", "PredefinedType", "ObjectType", "Phase"})

# Stable, reasonable defaults for a typical interior office space preview.
# Value-list attributes must use a token that exists in the corresponding list.
_SPACE_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "INTERNAL",
    "LongName": "Buero",
    "Name": "101",
    "SignageRoomNumber": "101",
    "Reference": "HNF",
    "IsExternal": False,
    "FloorCovering": "Teppich",
    "VibrationRequirements": "ISO Office",
    "DesignAreaLoad": 3.0,
    "DesignPointLoad": 2.0,
    "Checkliste": "Bodenbelag; Elektro; Beleuchtung",
    "FinishCeilingHeight": 2.6,
}

# Adjacent corridor/circulation space in the vignette (no suspended ceiling)
_NEIGHBOR_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "INTERNAL",
    "LongName": "Flur",
    "Name": "102",
    "SignageRoomNumber": "102",
    "Reference": "VF",
    "IsExternal": False,
    "FloorCovering": "PVC",
    "VibrationRequirements": "ISO Workshop",
    "DesignAreaLoad": 2.0,
    "DesignPointLoad": 1.5,
    "Checkliste": "Bodenbelag; Beleuchtung",
}

# Exterior balcony / terrace space (1 m high volume; tokens from spaces-exterior.yaml)
_EXTERIOR_SPACE_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "EXTERNAL",
    "LongName": "Balkon",
    "Name": "201",
    "SignageRoomNumber": "201",
    "Reference": "AGF",
    "IsExternal": True,
    "FloorCovering": "Beton",
    "VibrationRequirements": "ISO Residential (Night)",
    "DesignAreaLoad": 3.0,
    "DesignPointLoad": 2.0,
}

# Parking bay (tokens from spaces-parking.yaml — Name = P####)
_PARKING_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "PARKING",
    "Name": "P0001",
    "ParkingUse": "CAR",
}

# Elevator shaft space (LongName = Aufzug; Reference = VF per SIA 416)
_ELEVATOR_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "INTERNAL",
    "LongName": "Aufzug",
    "Name": "A-01",
    "Reference": "VF",
    "IsExternal": False,
}

# Facing-shell usable volume (Vorsatzschale) — bathroom lining gap
_VORSATZSCHALE_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "USERDEFINED",
    "ObjectType": "Vorsatzschale",
    "Name": "VS-01",
}

# Interior suspended ceiling in the office-space vignette (IfcCovering CEILING)
CEILING_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "CEILING",
    "IsExternal": False,
    "Status": "NEW",
    "CostInterface": "GAB",
    "AwardInterface": "273",
    "PlanningInterface": "092",
    "BelowTerrain": "FALSE",
    "eBKP": "G04.02",
}

# Floor build-up in the office-space vignette (IfcCovering FLOORING)
FLOOR_COVERING_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "FLOORING",
    "Finish": "Teppich",
    "SubfloorType": "Zement-UB",
    "Status": "NEW",
    "CostInterface": "GAB",
    "AwardInterface": "273",
    "PlanningInterface": "092",
    "BelowTerrain": "FALSE",
    "eBKP": "G02.02",
}

# Exterior floor covering on balcony / outdoor vignette (AOF finish)
FLOOR_COVERING_EXTERIOR_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "FLOORING",
    "IsExternal": True,
    "Finish": "Beton",
    "Status": "NEW",
    "AwardInterface": "421",
    "PlanningInterface": "092",
}

# Spatial-structure catalog defaults (tokens must match YAML / value lists / storey regex)
PROJECT_DEFAULTS: dict[str, Any] = {
    "Name": "Musterprojekt",
    "Phase": "32",
}
SITE_DEFAULTS: dict[str, Any] = {
    "Name": "Planungsperimeter",
}
BUILDING_DEFAULTS: dict[str, Any] = {
    "Name": "Gebaeude A",
}
DEFAULT_STOREY_NAMES: tuple[str, ...] = ("EG", "01", "02")

# Architectural slab plates in the spatial-structure vignette (bottom → top)
SLAB_BASE_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "BASESLAB",
    "LoadBearing": True,
    "Status": "NEW",
    "CostInterface": "GAB",
    "AwardInterface": "211",
    "PlanningInterface": "092",
    # Value-list tokens (boolean YAML uses TRUE/FALSE strings).
    "BelowTerrain": "TRUE",
    "eBKP": "C01.03",
    "ThermalTransmittance": 0.17,
    "CalculatedType": "Bodenplatte_Beton_0.17",
}
SLAB_FLOOR_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "FLOOR",
    "Name": "D-01",
    "Reference": "D-01",
    "LoadBearing": True,
    "Status": "NEW",
    "FireRating": "REI 90",
    "AcousticRating": "53",
    "CostInterface": "GAB",
    "AwardInterface": "211",
    "PlanningInterface": "092",
    "BelowTerrain": "FALSE",
    "eBKP": "C04.01",
    "CalculatedType": "Decke_Beton_REI90_53",
}
SLAB_ROOF_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "ROOF",
    "Name": "FD-01",
    "Reference": "FD-01",
    "IsExternal": True,
    "LoadBearing": True,
    "Status": "NEW",
    "CostInterface": "GAB",
    "AwardInterface": "211",
    "PlanningInterface": "092",
    "BelowTerrain": "FALSE",
    "eBKP": "C04.04",
    "ThermalTransmittance": 0.17,
    "CalculatedType": "Dach_Beton_0.17",
}
# Projecting balcony on storey 01 (IfcSlab FLOOR + IsExternal)
SLAB_BALCONY_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "FLOOR",
    "Name": "Balkon",
    "Reference": "BK-01",
    "IsExternal": True,
    "LoadBearing": True,
    "Status": "NEW",
    "FireRating": "REI 90",
    "CostInterface": "GAB",
    "AwardInterface": "211",
    "PlanningInterface": "092",
    "BelowTerrain": "FALSE",
    "eBKP": "C04.07",
    "CalculatedType": "Balkon_Beton_REI90",
}

# Architectural opening (Durchbruch) in the interior-space partition vignette
OPENING_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "OPENING",
    "Name": "D-01",
    "Reference": "D-01",
    "Width": 0.60,
    "Height": 0.40,
    "Status": "NEW",
}

# Architectural beam / Unterzug in the Luftraum atrium vignette
BEAM_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "BEAM",
    "Name": "U-01",
    "Reference": "U-01",
    "LoadBearing": True,
    "Status": "NEW",
    "FireRating": "R 90",
    "CostInterface": "GAB",
    "AwardInterface": "211",
    "PlanningInterface": "092",
    "CalculatedType": "Träger_Stahl_HEA200",
}

# Architectural pad footing under a base slab + column vignette
FOOTING_DEFAULTS: dict[str, Any] = {
    "Name": "F-01",
    "LoadBearing": True,
    "Status": "NEW",
    "CostInterface": "GAB",
    "AwardInterface": "211",
    "PlanningInterface": "092",
    "BelowTerrain": "TRUE",
    "eBKP": "C01.02",
    "CalculatedType": "Fundament_Punkt_Beton",
}

# Same vignette with closed slab; accent IfcColumn
COLUMN_DEFAULTS: dict[str, Any] = {
    "Name": "S-01",
    "PredefinedType": "COLUMN",
    "LoadBearing": True,
    "Status": "NEW",
    "CostInterface": "GAB",
    "AwardInterface": "211",
    "PlanningInterface": "092",
    "IsExternal": False,
    "BelowTerrain": "FALSE",
    "eBKP": "C03.02",
    "CalculatedType": "Stütze_Beton",
}

# Maintenance clearance (Wartungsraum) at the filter of a monoblock — German ObjectType token
MAINTENANCE_SPACE_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "USERDEFINED",
    "ObjectType": "Wartungsraum",
    "Name": "WR-01",
}

# Installation access path (Einbringweg) — German ObjectType token
INSTALLATION_PATH_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "USERDEFINED",
    "ObjectType": "Einbringweg",
    "Name": "EW-01",
}

# Turning radius (Wenderadius) LKW envelope on a curved street — German ObjectType
TURNING_RADIUS_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "USERDEFINED",
    "ObjectType": "Wenderadius",
    "Name": "WR-01",
}

# Decision volume (Entscheidungskörper) — spatial validity of a sampling decision
DECISION_VOLUME_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "USERDEFINED",
    "ObjectType": "Entscheidungskörper",
    "Name": "Wandfarbe",
    "DecisionReference": "E-014",
    "DecisionStatus": "OPEN",
}

# Movement clearance (Bewegungsfläche) — rectangular SIA 500 clear area
MOVEMENT_CLEARANCE_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "USERDEFINED",
    "ObjectType": "Bewegungsfläche",
    "Name": "Wendefläche",
}

# Building-law parcel (Baurechtliche Parzelle) — Name = cadastral number
BUILDING_LAW_PARCEL_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "USERDEFINED",
    "ObjectType": "Baurechtliche Parzelle",
    "Name": "1234",
}

# Surrounding neighbour building — Name = N###; EinspracheRisiko on Pset_UmgebungCommon
SURROUNDING_BUILDING_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "USERDEFINED",
    "ObjectType": "Umgebungsbau",
    "Name": "N001",
    "EinspracheRisiko": "HOCH",
}

# Construction logistics (Baustelleneinrichtungsobjekt) — Name = setup kind from value list
CONSTRUCTION_LOGISTICS_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "USERDEFINED",
    "ObjectType": "Baustelleneinricht",
    "Name": "Container",
    "LogisticsPhase": "1",
}

# Planning constraint (Rahmenbedingung) — Name = constraint kind from value list
PLANNING_CONSTRAINT_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "USERDEFINED",
    "ObjectType": "Rahmenbedingung",
    "Name": "Flugschneise",
}

# Alteration area retained in the overall model as a spatial project history
UMBAU_PERIMETER_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "USERDEFINED",
    "ObjectType": "Umbauperimeter",
    "Name": "P-2026-014",
    "StartDate": "2026-04-01",
    "EndDate": "2026-10-31",
    "AlterationStatus": "PLANNED",
}

# Interior half-turn stair shown across two storeys.
STAIR_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "HALF_TURN_STAIR",
    "Name": "TR-01",
    "IsExternal": False,
    "Status": "NEW",
    "eBKP": "C04.02",
    "CalculatedType": "Treppe_U-Treppe",
}

# Simplified temporary guardrail at a balcony edge.
RAILING_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "GUARDRAIL",
    "Name": "G-01",
    "Status": "TEMPORARY",
    "Height": 1.10,
}

# Exterior shading device — vertical lamellas above a window.
SHADING_DEVICE_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "JALOUSIE",
    "Name": "SS-01",
    "IsExternal": True,
    "Status": "NEW",
    "eBKP": "E03.04",
}

# Landscape tree (Baumbestand) — preserved stock defaults
TREE_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "VEGETATION",
    "ObjectType": "Baum",
    "Name": "B0001",
    "Reference": "B0001",
    "Status": "EXISTING",
    "Species": "Acer platanoides",
}

# Humus layer — reinstatement sample; stockpile lives on site setup
HUMUS_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "USERDEFINED",
    "ObjectType": "Humus",
    "Name": "Humus-01",
    "ElementStatus": "NEW",
}

# Tree pit — substrate volume linked to a tree
TREE_PIT_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "USERDEFINED",
    "ObjectType": "Baumgrube",
    "Name": "BG0001",
    "TreeReference": "B0001",
}

# Retention volume — stormwater storage
RETENTION_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "USERDEFINED",
    "ObjectType": "Retentionsvolumen",
    "Name": "RET-01",
    "DesignEvent": "T=10a",
    "CatchmentReference": "Aussenraum Nord",
}

# Furniture (Möbel) — schematic table accent; chair is companion geometry
FURNITURE_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "TABLE",
    "Name": "Tisch-01",
    "CostInterface": "GAB",
    "AwardInterface": "271",
    "PlanningInterface": "091",
}

# Built-in furniture (Einbaumöbel / Küche) — rough black-box kitchen blocks
BUILT_IN_FURNITURE_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "USERDEFINED",
    "ObjectType": "Einbaumöbel",
    "Name": "Küche-01",
    "CostInterface": "GAB",
    "AwardInterface": "258",
    "PlanningInterface": "091",
}

# Coordination meeting volume (Koordinationszone) on the Luftraum roof vignette
COORDINATION_ZONE_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "USERDEFINED",
    "ObjectType": "Koordinationszone",
    "Name": "KOORD-Dach",
}

# Pitched roof (Steildach / Satteldach) with attic space under the slopes
ROOF_PITCHED_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "GABLE_ROOF",
    "Name": "SD-01",
    "Reference": "SD-01",
    "LoadBearing": True,
    "Status": "NEW",
    "CostInterface": "GAB",
    "AwardInterface": "211",
    "PlanningInterface": "092",
    "BelowTerrain": "FALSE",
    "eBKP": "C04.05",
    "ThermalTransmittance": 0.17,
}

# Attic space under the pitched roof (context volume; LongName from room-name list)
_ROOF_ATTIC_SPACE_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "INTERNAL",
    "LongName": "Abstellraum Wohnen",
    "Name": "301",
    "SignageRoomNumber": "301",
    "Reference": "HNF",
    "IsExternal": False,
    "FloorCovering": "Parkett",
    "VibrationRequirements": "ISO Residential (Night)",
    "DesignAreaLoad": 2.0,
    "DesignPointLoad": 1.5,
    "Checkliste": "Bodenbelag; Beleuchtung",
}

# Tapered insulation (Gefälledämmung) on flat roof + Attika vignette
ROOFING_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "ROOFING",
    "Name": "GD-01",
    "Reference": "GD-01",
    "IsExternal": True,
    "Status": "NEW",
    "CostInterface": "GAB",
    "AwardInterface": "273",
    "PlanningInterface": "092",
}

# Detail reference volumes (Detailverweis) on the exterior-wall vignette
DETAIL_REFERENCE_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "USERDEFINED",
    "ObjectType": "Detailverweis",
    "Name": "AW-Balkon",
}

# Exterior facade products in the exterior-space vignette (no IfcSpace volumes)
WALL_EXTERIOR_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "SOLIDWALL",
    "Name": "AW-01",
    "Reference": "AW-01",
    "IsExternal": True,
    "Status": "NEW",
    "CostInterface": "GAB",
    "AwardInterface": "211",
    "PlanningInterface": "092",
    "BelowTerrain": "FALSE",
    "eBKP": "C02.01",
    "ThermalTransmittance": 0.17,
    "CalculatedType": "Wand_Aussen_Oberirdisch_Beton_0.17",
}
CLADDING_EXTERIOR_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "CLADDING",
    "Name": "FB-01",
    "Reference": "FB-01",
    "IsExternal": True,
    "Status": "NEW",
    "CostInterface": "GAB",
    "AwardInterface": "273",
    "PlanningInterface": "092",
    "BelowTerrain": "FALSE",
    "eBKP": "E02",
}
# Interior partition / load-bearing wall / wall cladding (Innenräume vignette)
WALL_INTERIOR_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "PARTITIONING",
    "Name": "IW-01",
    "Reference": "IW-01",
    "IsExternal": False,
    "LoadBearing": False,
    "Status": "NEW",
    "CostInterface": "GAB",
    "AwardInterface": "211",
    "PlanningInterface": "092",
    "BelowTerrain": "FALSE",
    "eBKP": "G01.01",
    "CalculatedType": "Wand_Innen_Oberirdisch_Beton",
}
WALL_INTERIOR_LB_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "SOLIDWALL",
    "Name": "TW-01",
    "Reference": "TW-01",
    "IsExternal": False,
    "LoadBearing": True,
    "Status": "NEW",
    "CostInterface": "GAB",
    "AwardInterface": "211",
    "PlanningInterface": "092",
    "BelowTerrain": "FALSE",
    "eBKP": "C02.02",
    "CalculatedType": "Wand_Innen_Oberirdisch_Beton",
}
DRYWALL_REINFORCEMENT_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "USERDEFINED",
    "ObjectType": "Trockenbauverstärkung",
    "Name": "TV-01",
    "Reference": "TV-01",
}
CLADDING_INTERIOR_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "CLADDING",
    "Name": "WB-01",
    "Reference": "WB-01",
    "IsExternal": False,
    "Status": "NEW",
    "CostInterface": "GAB",
    "AwardInterface": "273",
    "PlanningInterface": "092",
    "BelowTerrain": "FALSE",
    "eBKP": "G03.02",
}
DOOR_EXTERIOR_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "DOOR",
    "Name": "AT-01",
    "Reference": "AT-01",
    "IsExternal": True,
    "Status": "NEW",
    "OverallWidth": 0.90,
    "OverallHeight": 2.10,
    "ThermalTransmittance": 1.2,
    "eBKP": "E03.02",
    "CalculatedType": "Tür_Aussen_1F_B=0.90m_H=2.10m_1.2",
}
DOOR_INTERIOR_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "DOOR",
    "Name": "IT-01",
    "Reference": "IT-01",
    "IsExternal": False,
    "Status": "NEW",
    "OverallWidth": 0.90,
    "OverallHeight": 2.10,
    "eBKP": "G01.05",
    "CalculatedType": "Tür_Innen_1F_B=0.90m_H=2.10m",
}
WINDOW_EXTERIOR_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "WINDOW",
    "Name": "AF-01",
    "IsExternal": True,
    "Status": "NEW",
    "ThermalTransmittance": 0.9,
    "SunProtection": "NONE",
    "eBKP": "E03.01",
    "CalculatedType": "Fenster_Aussen_B=1.20m_H=1.40m_0.9",
}
WINDOW_INTERIOR_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "WINDOW",
    "Name": "IF-01",
    "IsExternal": False,
    "Status": "NEW",
    "eBKP": "G01.04",
    "CalculatedType": "Fenster_Innen_B=1.20m_H=1.40m",
}

_GROSS_VOLUME_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "GFA",
}

# Non-occupiable air space / atrium void (spaces-luftraum.yaml)
_LUFTRAUM_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "USERDEFINED",
    "ObjectType": "Luftraum",
    "Name": "LR-01",
    "LongName": "Luftraum",
}

# Upper gallery room in the Luftraum vignette (neighbour bay, upper storey)
_LUFTRAUM_UPPER_DEFAULTS: dict[str, Any] = {
    "PredefinedType": "INTERNAL",
    "LongName": "Buero",
    "Name": "201",
    "SignageRoomNumber": "201",
    "Reference": "HNF",
    "IsExternal": False,
    "FloorCovering": "PVC",
    "VibrationRequirements": "ISO Office",
    "DesignAreaLoad": 2.0,
    "DesignPointLoad": 1.5,
    "Checkliste": "Bodenbelag; Beleuchtung",
}

GROSS_VOLUME_UNIT_DEFAULTS: dict[str, dict[str, Any]] = {
    "foundation": {
        **_GROSS_VOLUME_DEFAULTS,
        "Name": "FD-BR",
        "LongName": "Gruendung",
    },
    "flat_a": {**_GROSS_VOLUME_DEFAULTS, "Name": "{storey}-WA", "LongName": "Wohnung A"},
    "stair": {**_GROSS_VOLUME_DEFAULTS, "Name": "{storey}-TR", "LongName": "Treppe"},
    "flat_b": {**_GROSS_VOLUME_DEFAULTS, "Name": "{storey}-WB", "LongName": "Wohnung B"},
}

_PLACEHOLDER_TOKENS = frozenset(
    {
        "nicht definiert",
        "nicht definiert / n.d.",
        "n.d.",
        "undefined",
        "n/a",
        "-",
        "",
    }
)


@lru_cache(maxsize=64)
def load_element(slug: str) -> dict[str, Any]:
    path = ELEMENTS_DIR / f"{slug}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"element definition not found: {path}")
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"invalid element YAML: {path}")
    return data


@lru_cache(maxsize=128)
def load_value_list(value_id: str) -> list[Any]:
    """Resolve ``pragmaticbim:value/...`` to the ``values.de`` token list."""
    slug = value_id.rsplit("/", 1)[-1]
    path = VALUES_DIR / f"{slug}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"value list not found for {value_id!r}: {path}")
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    values = (data or {}).get("values") or {}
    # Catalog authoring language is German; enum tokens are usually identical across langs
    for lang in ("de", "en", "fr", "it"):
        if values.get(lang):
            return list(values[lang])
    raise ValueError(f"value list {value_id!r} has no values")


def active_ifc4_attributes(element: dict[str, Any]) -> list[dict[str, Any]]:
    """Return active attributes applicable to IFC4 / IFC4X3."""
    result: list[dict[str, Any]] = []
    for attr in element.get("attributes") or []:
        if attr.get("status") != "active":
            continue
        versions = attr.get("ifc_versions") or []
        if "ifc4" not in versions and "ifc4x3" not in versions:
            continue
        result.append(attr)
    return result


def _coerce_datatype(raw: Any, datatype: str | None) -> Any:
    """Coerce catalog values to Python types suitable for ifcopenshell."""
    if raw is None:
        return None
    dt = (datatype or "").lower()
    if dt == "ifcboolean":
        if isinstance(raw, bool):
            return raw
        text = str(raw).strip().upper()
        if text in {"TRUE", "1", "YES"}:
            return True
        if text in {"FALSE", "0", "NO"}:
            return False
        raise ValueError(f"cannot coerce {raw!r} to IfcBoolean")
    if dt in {
        "ifcreal",
        "ifcareameasure",
        "ifclengthmeasure",
        "ifcpositivelengthmeasure",
        "ifcpowermeasure",
        "ifcthermaltransmittancemeasure",
        "ifcvolumemeasure",
    }:
        return float(raw)
    if dt in {"ifcinteger", "ifccountmeasure"}:
        return int(raw)
    return str(raw)


def _pick_from_value_list(
    attr_name: str,
    choices: list[Any],
    *,
    defaults: dict[str, Any] | None = None,
) -> Any:
    """Pick a consistent reasonable token from an allowed-values list."""
    preferred = (defaults or _SPACE_DEFAULTS).get(attr_name)
    if preferred is not None:
        preferred_str = str(preferred)
        for choice in choices:
            if str(choice) == preferred_str:
                return choice

    for choice in choices:
        if str(choice).strip().lower() not in _PLACEHOLDER_TOKENS:
            return choice
    return choices[0]


def _default_free_value(
    attr: dict[str, Any],
    *,
    geometry: dict[str, float] | None = None,
    defaults: dict[str, Any] | None = None,
) -> Any:
    """Stable default when no allowed_values list exists."""
    name = attr["name"]
    datatype = attr.get("datatype") or ""
    geometry = geometry or {}
    defaults = defaults or _SPACE_DEFAULTS

    if name in defaults:
        return defaults[name]
    if name.endswith("Actual") and name[: -len("Actual")] in defaults:
        return defaults[name[: -len("Actual")]]
    if name in {"NetFloorArea", "NetArea"}:
        area = geometry.get("area")
        if area is not None:
            return round(float(area), 2)
        return 20.0
    if name in {"GrossFloorArea", "GrossArea"}:
        area = geometry.get("area")
        if area is not None:
            return round(float(area), 2)
        return 20.0
    if name == "GrossVolume" or name == "NetVolume":
        area = geometry.get("area")
        height = geometry.get("height")
        if area is not None and height is not None:
            return round(float(area) * float(height), 2)
        return 1.0
    if name == "Height":
        return float(geometry.get("height") or 2.8)
    if name == "FinishCeilingHeight":
        # Default: suspended ceiling; neighbour overrides to full height (no ceiling)
        if "FinishCeilingHeight" in defaults:
            return defaults["FinishCeilingHeight"]
        height = float(geometry.get("height") or 2.8)
        return round(height - 0.20, 2)
    if name == "GlobalTradeItemNumber":
        return "07612345000015"
    if name == "SerialNumber":
        return "SN-000001"
    if datatype == "IfcBoolean":
        return False
    if datatype in {
        "IfcReal",
        "IfcAreaMeasure",
        "IfcLengthMeasure",
        "IfcPowerMeasure",
        "IfcThermalTransmittanceMeasure",
    }:
        return 1.0
    return f"{name}"


def resolve_attribute_value(
    attr: dict[str, Any],
    *,
    geometry: dict[str, float] | None = None,
    override: Any = None,
    defaults: dict[str, Any] | None = None,
) -> Any:
    """Resolve a value: explicit override, else curated default / value-list pick."""
    datatype = attr.get("datatype")
    defaults = defaults or _SPACE_DEFAULTS
    if override is not None:
        return _coerce_datatype(override, datatype)

    # Prefer curated default when it is a valid value-list token
    if attr["name"] in defaults and attr.get("allowed_values"):
        preferred = defaults[attr["name"]]
        choices = load_value_list(str(attr["allowed_values"]))
        preferred_str = str(preferred)
        if any(str(c) == preferred_str for c in choices):
            return _coerce_datatype(preferred, datatype)

    allowed_id = attr.get("allowed_values")
    if allowed_id:
        choices = load_value_list(str(allowed_id))
        if not choices:
            raise ValueError(f"empty value list for {attr.get('name')}: {allowed_id}")
        return _coerce_datatype(
            _pick_from_value_list(str(attr["name"]), choices, defaults=defaults),
            datatype,
        )

    return _coerce_datatype(
        _default_free_value(attr, geometry=geometry, defaults=defaults), datatype
    )


def build_element_attributes_from_yaml(
    *,
    entry: dict[str, Any],
    element_slug: str,
    defaults: dict[str, Any] | None = None,
    geometry: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Build entity fields, psets and qtos from an element YAML definition.

    Returns entity attributes plus ``properties`` / ``property_datatypes`` / ``quantities``.
    """
    element = load_element(element_slug)
    defaults = defaults or {}

    entity: dict[str, Any] = {}
    properties: dict[str, dict[str, Any]] = {}
    property_datatypes: dict[str, dict[str, str]] = {}
    quantities: dict[str, dict[str, Any]] = {}

    for attr in active_ifc4_attributes(element):
        name = attr["name"]
        value = resolve_attribute_value(
            attr,
            geometry=geometry,
            override=entry.get(name),
            defaults=defaults,
        )
        pset = attr.get("pset")
        if pset is None:
            if name in _ENTITY_ATTRS:
                entity[name] = value
            continue
        if str(pset).startswith("Qto_"):
            quantities.setdefault(pset, {})[name] = value
        else:
            properties.setdefault(pset, {})[name] = value
            if attr.get("datatype"):
                property_datatypes.setdefault(pset, {})[name] = str(attr["datatype"])

    return {
        **entity,
        "properties": properties,
        "property_datatypes": property_datatypes,
        "quantities": quantities,
    }


def build_space_attributes_from_yaml(
    *,
    entry: dict[str, Any],
    geometry: dict[str, float],
    element_slug: str = SPACE_ELEMENT_SLUG,
    defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build entity fields, psets and qtos from ``spaces-interior.yaml``.

    Returns::
        {
          "Name": ...,
          "LongName": ...,
          "PredefinedType": ...,
          "properties": {pset: {prop: value}},
          "quantities": {qto: {qty: value}},
        }
    """
    resolved = build_element_attributes_from_yaml(
        entry=entry,
        element_slug=element_slug,
        defaults=defaults or _SPACE_DEFAULTS,
        geometry=geometry,
    )
    quantities = resolved.setdefault("quantities", {})

    # Geometry-derived quantities always win for Height when computed
    if "height" in geometry:
        quantities.setdefault("Qto_SpaceBaseQuantities", {})["Height"] = float(
            geometry["height"]
        )
    if "area" in geometry:
        qto = quantities.setdefault("Qto_SpaceBaseQuantities", {})
        qto["NetFloorArea"] = round(float(geometry["area"]), 2)
        qto["GrossFloorArea"] = round(float(geometry["area"]), 2)
        qto["GrossVolume"] = round(
            float(geometry["area"]) * float(geometry.get("height") or 0.0), 2
        )

    return resolved


def build_neighbor_space_attributes(
    *,
    geometry: dict[str, float],
    element_slug: str = SPACE_ELEMENT_SLUG,
) -> dict[str, Any]:
    """Attributes for the vignette neighbour (corridor) — no suspended ceiling."""
    defaults = dict(_NEIGHBOR_DEFAULTS)
    # No ceiling covering → clear height equals structural space height
    defaults["FinishCeilingHeight"] = float(geometry["height"])
    resolved = build_space_attributes_from_yaml(
        entry={},
        geometry=geometry,
        element_slug=element_slug,
        defaults=defaults,
    )
    qto = resolved.setdefault("quantities", {}).setdefault(
        "Qto_SpaceBaseQuantities", {}
    )
    qto["FinishCeilingHeight"] = float(geometry["height"])
    return {
        "name": resolved.get("Name"),
        "long_name": resolved.get("LongName"),
        "predefined_type": resolved.get("PredefinedType") or "INTERNAL",
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": qto,
    }


def build_interior_context_attributes(
    *,
    geometry: dict[str, float],
) -> dict[str, Any]:
    """Attributes for the half interior room in the exterior-space vignette."""
    defaults = dict(_SPACE_DEFAULTS)
    defaults["FinishCeilingHeight"] = float(
        geometry.get("finish_ceiling_height")
        or defaults.get("FinishCeilingHeight")
        or 2.6
    )
    resolved = build_space_attributes_from_yaml(
        entry={},
        geometry=geometry,
        element_slug=SPACE_ELEMENT_SLUG,
        defaults=defaults,
    )
    qto = resolved.setdefault("quantities", {}).setdefault(
        "Qto_SpaceBaseQuantities", {}
    )
    return {
        "name": resolved.get("Name"),
        "long_name": resolved.get("LongName"),
        "predefined_type": resolved.get("PredefinedType") or "INTERNAL",
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": qto,
    }


def exterior_space_defaults() -> dict[str, Any]:
    """Stable defaults for ``spaces-exterior`` catalog samples."""
    return dict(_EXTERIOR_SPACE_DEFAULTS)


def parking_defaults() -> dict[str, Any]:
    """Stable defaults for ``spaces-parking`` catalog samples."""
    return dict(_PARKING_DEFAULTS)


def elevator_defaults() -> dict[str, Any]:
    """Stable defaults for ``spaces-elevator`` catalog samples."""
    return dict(_ELEVATOR_DEFAULTS)


def vorsatzschale_defaults() -> dict[str, Any]:
    """Stable defaults for ``spaces-vorsatzschale`` catalog samples."""
    return dict(_VORSATZSCHALE_DEFAULTS)


def luftraum_defaults() -> dict[str, Any]:
    """Stable defaults for ``spaces-luftraum`` catalog samples."""
    return dict(_LUFTRAUM_DEFAULTS)


def roof_attic_space_defaults() -> dict[str, Any]:
    """Stable defaults for the attic IfcSpace under a pitched roof."""
    return dict(_ROOF_ATTIC_SPACE_DEFAULTS)


def build_luftraum_upper_attributes(
    *,
    geometry: dict[str, float],
) -> dict[str, Any]:
    """Attributes for the upper gallery space in the Luftraum vignette."""
    defaults = dict(_LUFTRAUM_UPPER_DEFAULTS)
    defaults["FinishCeilingHeight"] = float(geometry["height"])
    resolved = build_space_attributes_from_yaml(
        entry={},
        geometry=geometry,
        element_slug=SPACE_ELEMENT_SLUG,
        defaults=defaults,
    )
    qto = resolved.setdefault("quantities", {}).setdefault(
        "Qto_SpaceBaseQuantities", {}
    )
    qto["FinishCeilingHeight"] = float(geometry["height"])
    return {
        "name": resolved.get("Name"),
        "long_name": resolved.get("LongName"),
        "predefined_type": resolved.get("PredefinedType") or "INTERNAL",
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": qto,
    }


def build_luftraum_lower_attributes(
    *,
    geometry: dict[str, float],
) -> dict[str, Any]:
    """Attributes for the lower primary office under the Luftraum void."""
    defaults = dict(_SPACE_DEFAULTS)
    defaults["FinishCeilingHeight"] = float(
        geometry.get("finish_ceiling_height")
        or defaults.get("FinishCeilingHeight")
        or 2.6
    )
    resolved = build_space_attributes_from_yaml(
        entry={},
        geometry=geometry,
        element_slug=SPACE_ELEMENT_SLUG,
        defaults=defaults,
    )
    qto = resolved.setdefault("quantities", {}).setdefault(
        "Qto_SpaceBaseQuantities", {}
    )
    return {
        "name": resolved.get("Name"),
        "long_name": resolved.get("LongName"),
        "predefined_type": resolved.get("PredefinedType") or "INTERNAL",
        "properties": resolved.get("properties") or {},
        "property_datatypes": resolved.get("property_datatypes") or {},
        "quantities": qto,
    }
