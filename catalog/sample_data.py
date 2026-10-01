"""Hardcoded sample catalog instances for end-to-end testing.

Geometry is explicit; IFC attributes/properties are filled from element YAML
with stable defaults unless overridden.
"""

from __future__ import annotations

SAMPLE_CATALOG: list[dict] = [
    {
        "id": "space-office-01",
        "element_type": "IfcSpace",
        "height": 2.8,
        "width": 4.0,
        "depth": 5.0,
        "FinishCeilingHeight": 2.6,
        "include_ceiling_covering": False,
        "include_ceiling_slab": False,
        "include_exterior_envelope": True,
        "include_partition_openings": True,
        "omit_camera_facing_envelope": True,
        "camera_padding": 2.0,
        "attach_element": "spaces-interior",
    },
    {
        # Interior-space fabric + smaller mid slab + top slab; accent Luftraum void.
        "id": "space-luftraum-01",
        "element_type": "SPACE-AIR",
        "height": 2.8,
        "upper_height": 2.8,
        "width": 4.0,
        "depth": 5.0,
        "FinishCeilingHeight": 2.6,
        "attach_element": "spaces-luftraum",
    },
    {
        # Same Luftraum atrium; half top slab; accent IfcBeams under the remaining half.
        "id": "beam-01",
        "element_type": "ARC-BEAM",
        "height": 2.8,
        "upper_height": 2.8,
        "width": 4.0,
        "depth": 5.0,
        "FinishCeilingHeight": 2.6,
        "attach_element": "architecture-beam",
    },
    {
        # Half interior room + exterior wall/cladding/openings + 1 m balcony space.
        "id": "space-exterior-01",
        "element_type": "SPACE-EXT",
        "height": 1.0,
        "width": 1.5,
        "depth": 5.0,
        "interior_width": 2.0,
        "interior_depth": 5.0,
        "interior_height": 2.8,
        "FinishCeilingHeight": 2.6,
        "attach_element": "spaces-exterior",
    },
    {
        # Three 2.7×5 m PARKING bays; flooring inset by wall_t; 3 m street.
        "id": "space-parking-01",
        "element_type": "SPACE-PARK",
        "height": 2.2,
        "width": 2.7,
        "depth": 5.0,
        "bay_count": 3,
        "names": ["P0001", "P0002", "P0003"],
        "attach_element": "spaces-parking",
    },
    {
        # Open-front shaft: slab + storey-separated U-walls; accent elevator IfcSpace.
        "id": "space-elevator-01",
        "element_type": "SPACE-ELEVATOR",
        "height": 2.8,
        "width": 1.6,
        "depth": 2.0,
        "attach_element": "spaces-elevator",
    },
    {
        # Bathroom: slab + Tragwand + 7 cm facing wall, 20 cm clear Vorsatzschale + WC.
        "id": "space-vorsatzschale-01",
        "element_type": "SPACE-VORSATZ",
        "height": 2.5,
        "width": 2.2,
        "room_depth": 1.2,
        "gap": 0.20,
        "facing_thickness": 0.07,
        "attach_element": "spaces-vorsatzschale",
    },
    {
        # Interior partition fabric (no spaces / no ceiling); accent PARTITIONING wall.
        "id": "wall-interior-01",
        "element_type": "ARC-WALL-INT",
        "height": 2.8,
        "width": 4.0,
        "depth": 5.0,
        "attach_element": "architecture-wall-interior",
    },
    {
        # Same interior fabric; accent load-bearing SOLIDWALL (LoadBearing=TRUE).
        "id": "wall-interior-lb-01",
        "element_type": "ARC-WALL-INT-LB",
        "height": 2.8,
        "width": 4.0,
        "depth": 5.0,
        "attach_element": "architecture-wall-interior-loadbearing",
    },
    {
        # Tile splashback on the camera-facing partition face, with a schematic washbasin.
        "id": "wall-cladding-interior-01",
        "element_type": "ARC-WALL-CLAD",
        "height": 2.8,
        "width": 4.0,
        "depth": 5.0,
        "attach_element": "architecture-wall-cladding-interior",
    },
    {
        # Same interior-wall vignette; accent one backing panel inside the wall.
        "id": "drywall-reinforcement-01",
        "element_type": "ARC-DRYWALL-REINF",
        "height": 2.8,
        "width": 4.0,
        "depth": 5.0,
        "attach_element": "architecture-drywall-reinforcement",
    },
    {
        # Exterior fabric without spaces/cladding; open top (no slab/ceiling); accent wall.
        "id": "wall-exterior-01",
        "element_type": "ARC-WALL-EXT",
        "height": 1.0,
        "width": 1.5,
        "depth": 5.0,
        "interior_width": 2.0,
        "interior_depth": 5.0,
        "interior_height": 2.8,
        "FinishCeilingHeight": 2.6,
        "attach_element": "architecture-wall-exterior",
    },
    {
        # Same exterior wall as wall-exterior-01; two orange Detailverweis volumes.
        "id": "detail-reference-01",
        "element_type": "ARC-DET-REF",
        "height": 1.0,
        "width": 1.5,
        "depth": 5.0,
        "interior_width": 2.0,
        "interior_depth": 5.0,
        "interior_height": 2.8,
        "FinishCeilingHeight": 2.6,
        "volume_names": ["AW-Balkon", "AW-Türschwelle"],
        "attach_element": "architecture-detail-reference",
    },
    {
        # Same exterior fabric; no spaces; open top (no slab); accent cladding.
        "id": "cladding-exterior-01",
        "element_type": "ARC-WALL-CLAD-EXT",
        "height": 1.0,
        "width": 1.5,
        "depth": 5.0,
        "interior_width": 2.0,
        "interior_depth": 5.0,
        "interior_height": 2.8,
        "FinishCeilingHeight": 2.6,
        "attach_element": "architecture-wall-cladding-exterior",
    },
    {
        # Exterior facade fabric; no spaces; accent exterior door.
        "id": "door-exterior-01",
        "element_type": "ARC-DOOR-EXT",
        "height": 1.0,
        "width": 1.5,
        "depth": 5.0,
        "interior_width": 2.0,
        "interior_depth": 5.0,
        "interior_height": 2.8,
        "FinishCeilingHeight": 2.6,
        "attach_element": "architecture-door-exterior",
    },
    {
        # Exterior facade fabric; no spaces; accent exterior window.
        "id": "window-exterior-01",
        "element_type": "ARC-WINDOW-EXT",
        "height": 1.0,
        "width": 1.5,
        "depth": 5.0,
        "interior_width": 2.0,
        "interior_depth": 5.0,
        "interior_height": 2.8,
        "FinishCeilingHeight": 2.6,
        "attach_element": "architecture-window-exterior",
    },
    {
        # Exterior window vignette; accent vertical lamellas, 1 m cantilever.
        "id": "shading-device-01",
        "element_type": "ARC-SHADING",
        "height": 1.0,
        "width": 1.5,
        "depth": 5.0,
        "interior_width": 2.0,
        "interior_depth": 5.0,
        "interior_height": 2.8,
        "FinishCeilingHeight": 2.6,
        "PredefinedType": "JALOUSIE",
        "attach_element": "architecture-shading-device",
    },
    {
        # Two-room interior fabric with envelope; accent interior door in partition.
        "id": "door-interior-01",
        "element_type": "ARC-DOOR-INT",
        "height": 2.8,
        "width": 4.0,
        "depth": 5.0,
        "FinishCeilingHeight": 2.6,
        "attach_element": "architecture-door-interior",
    },
    {
        # Two-room interior fabric with envelope; accent interior window in partition.
        "id": "window-interior-01",
        "element_type": "ARC-WINDOW-INT",
        "height": 2.8,
        "width": 4.0,
        "depth": 5.0,
        "FinishCeilingHeight": 2.6,
        "attach_element": "architecture-window-interior",
    },
    {
        # Same Luftraum atrium vignette; PNG accents the suspended ceiling through the void.
        "id": "ceiling-suspended-01",
        "element_type": "IfcCovering",
        "height": 2.8,
        "upper_height": 2.8,
        "width": 4.0,
        "depth": 5.0,
        "FinishCeilingHeight": 2.6,
        "attach_element": "architecture-ceiling-suspended",
    },
    {
        # Same room vignette as space-office-01; PNG accents both floor build-ups.
        "id": "floor-covering-01",
        "element_type": "ARC-FLOOR-COV",
        "height": 2.8,
        "width": 4.0,
        "depth": 5.0,
        "FinishCeilingHeight": 2.6,
        "attach_element": "architecture-floor-covering",
    },
    {
        # Exterior terrace vignette; accents balcony FLOORING covering (AOF finish).
        "id": "floor-covering-exterior-01",
        "element_type": "ARC-FLOOR-COV-EXT",
        "height": 1.0,
        "width": 2.0,
        "depth": 4.0,
        "FinishCeilingHeight": 2.6,
        "attach_element": "architecture-floor-covering-exterior",
    },
    {
        # Interior-space fabric without ceilings/spaces; orange Durchbruch in partition.
        "id": "opening-void-01",
        "element_type": "ARC-OPENING-VOID",
        "height": 2.8,
        "width": 4.0,
        "depth": 5.0,
        "clear_width": 0.60,
        "clear_height": 0.40,
        "attach_element": "architecture-opening-void",
    },
    {
        # Three LV95 Bezugspunkte near the geographic centre of Switzerland (Älggi-Alp).
        # Local engineering coords; origin maps to EPSG:2056 via IfcMapConversion.
        "id": "survey-ref-points-01",
        "element_type": "Bezugspunkt",
        "origin_lv95": {
            "easting": 2660156.235,
            "northing": 1183629.331,
            "height": 1645.0,
        },
        "points": [
            {"name": "BP-01", "Reference": "1001", "x": 0.0, "y": 0.0, "z": 0.0},
            {"name": "BP-02", "Reference": "1002", "x": 30.0, "y": 4.0, "z": 0.15},
            {"name": "BP-03", "Reference": "1003", "x": 10.0, "y": 26.0, "z": -0.10},
        ],
        "with_context": False,
        "attach_element": "survey-reference-point",
    },
    {
        "id": "spatial-project-01",
        "element_type": "IfcProject",
        "highlight": "project",
    },
    {
        "id": "spatial-site-01",
        "element_type": "IfcSite",
        "highlight": "site",
        "attach_element": "site",
    },
    {
        "id": "spatial-building-01",
        "element_type": "IfcBuilding",
        "highlight": "building",
    },
    {
        "id": "spatial-storey-01",
        "element_type": "IfcBuildingStorey",
        "highlight": "storey",
        "attach_element": "storey",
    },
    {
        # Same opaque plates as spatial-*; accent Bodenplatte (bottom).
        "id": "slab-base-01",
        "element_type": "ARC-SLAB-BASE",
        "highlight": "slab-base",
        "attach_element": "architecture-slab-base",
    },
    {
        # Same opaque plates as spatial-*; accent Decke (middle).
        "id": "slab-floor-01",
        "element_type": "ARC-SLAB-FLOOR",
        "highlight": "slab-floor",
        "attach_element": "architecture-slab-floor",
    },
    {
        # Same vignette as slab-floor; accent only the projecting balcony.
        "id": "slab-balcony-01",
        "element_type": "ARC-SLAB-BALCONY",
        "highlight": "slab-balcony",
        "attach_element": "architecture-slab-balcony",
    },
    {
        # Same opaque plates as spatial-*; accent Flachdach (top).
        "id": "slab-roof-01",
        "element_type": "ARC-ROOF-FLAT",
        "highlight": "slab-roof",
        "attach_element": "architecture-slab-flat-roof",
    },
    {
        # Pad footing under a base slab corner + one column; accent the footing.
        "id": "footing-pad-01",
        "element_type": "ARC-FOOTING",
        "camera_padding": 1.8,
        "attach_element": "architecture-footing",
    },
    {
        # Same vignette with closed slab; accent the column (no footing).
        "id": "column-01",
        "element_type": "ARC-COLUMN",
        "attach_element": "architecture-column",
    },
    {
        # Long multi-part monoblock; 90 cm Wartungsraum at Filter; accent clearance.
        "id": "maintenance-space-01",
        "element_type": "ARC-MAINT-SPACE",
        "maintenance_depth": 0.90,
        "attach_element": "architecture-maintenance-space",
    },
    {
        # L-corridor + door partition; Einbringweg matches the door clear opening.
        "id": "installation-path-01",
        "element_type": "ARC-INSTALL-PATH",
        "corridor_width": 2.50,
        "attach_element": "architecture-installation-path",
    },
    {
        # Lastzug Fahrkurve: smooth swept envelope; street clear of cube.
        "id": "turning-radius-01",
        "element_type": "ARC-TURN-RAD",
        "cube_size": 4.0,
        "street_clearance": 1.8,
        "street_width": 3.5,
        "approach": 5.0,
        "proxy_outer": 12.5,
        "vehicle_width": 2.55,
        "vehicle_length": 9.5,
        "nose_length": 1.6,
        "proxy_inner_mid": 5.0,
        "turn_angle_deg": 135.0,
        "pose_count": 72,
        "envelope_simplify": 0.20,
        "proxy_height": 4.0,
        "camera_padding": 3.5,
        "attach_element": "architecture-turning-radius",
    },
    {
        # One storey; several Entscheidungskörper in different rooms.
        "id": "decision-volume-01",
        "element_type": "ARC-DEC-VOL",
        "attach_element": "architecture-decision-volume",
        "camera_padding": 1.35,
    },
    {
        # Accessible wet room with sanitary fixtures and one Wendefläche.
        "id": "movement-clearance-01",
        "element_type": "ARC-MOVEMENT-CLEARANCE",
        "attach_element": "architecture-movement-clearance",
    },
    {
        # Three cadastral parcel volumes from -10 m to +10 m through terrain.
        "id": "building-law-parcel-01",
        "element_type": "ARC-PARCEL",
        "parcel_names": ["1234", "1235", "1236"],
        "parcel_bottom": -10.0,
        "parcel_top": 10.0,
        "parcel_depth": 30.0,
        "parcel_a_width": 15.0,
        "parcel_b_width": 15.0,
        "parcel_c_width": 15.0,
        "camera_padding": 2.0,
        "attach_element": "architecture-building-law-parcel",
    },
    {
        # Opaque project mass + three neighbour gross volumes (N001–N003).
        "id": "surrounding-building-01",
        "element_type": "ARC-UMG-NEIGHBOR",
        "neighbor_specs": [
            ("N001", 10.0, 7.0, 12.0, "HOCH"),
            ("N002", 8.0, 6.0, 8.0, "MITTEL"),
            ("N003", 7.0, 5.5, 6.0, "TIEF"),
        ],
        "project_width": 8.0,
        "project_depth": 7.0,
        "project_height": 9.0,
        "gap": 4.0,
        "camera_padding": 2.5,
        "attach_element": "architecture-surrounding-building",
    },
    {
        # Site yard: fence, container, crane mast+jib, foundation, storage; opaque building.
        "id": "construction-logistics-01",
        "element_type": "ARC-SITE-LOG",
        "logistics_names": [
            "Zaun",
            "Container",
            "Kran",
            "Lagerfläche",
            "Kranfundament",
        ],
        "building_width": 8.0,
        "building_depth": 6.0,
        "building_height": 7.0,
        "yard_depth": 10.0,
        "yard_side": 6.0,
        "camera_padding": 2.5,
        "attach_element": "architecture-construction-logistics",
    },
    {
        # Flood zone, railway corridor, flight corridor; opaque building on plot.
        "id": "planning-constraint-01",
        "element_type": "ARC-CONSTRAINT",
        "constraint_names": [
            "Überschwemmungsgebiet",
            "Eisenbahnkorridor",
            "Flugschneise",
        ],
        "building_width": 8.0,
        "building_depth": 6.0,
        "building_height": 7.0,
        "camera_padding": 2.5,
        "attach_element": "architecture-planning-constraint",
    },
    {
        # Same closed storey plan as Entscheidungskörper; one Umbauperimeter on the left rooms.
        "id": "umbau-perimeter-01",
        "element_type": "ARC-UMBAU-PER",
        "name": "P-2026-014",
        "StartDate": "2026-04-01",
        "EndDate": "2026-10-31",
        "AlterationStatus": "PLANNED",
        "camera_padding": 1.35,
        "attach_element": "architecture-umbau-perimeter",
    },
    {
        # Two flights across EG/1.OG; upper flight dashed, with room and door below.
        "id": "stair-01",
        "element_type": "ARC-STAIR",
        "storey_height": 3.0,
        "flight_width": 1.1,
        "flight_run": 3.0,
        "landing_depth": 1.0,
        "step_count": 9,
        "IsExternal": False,
        "camera_padding": 1.8,
        "attach_element": "architecture-stair",
    },
    {
        # Exterior-space balcony vignette with a temporary railing at its outer edge.
        "id": "railing-01",
        "element_type": "ARC-RAILING",
        "railing_length": 5.0,
        "railing_height": 1.10,
        "railing_thickness": 0.08,
        "balcony_depth": 1.5,
        "interior_width": 2.0,
        "interior_height": 2.8,
        "FinishCeilingHeight": 2.6,
        "Status": "TEMPORARY",
        "PredefinedType": "GUARDRAIL",
        "camera_padding": 1.8,
        "attach_element": "architecture-railing",
    },
    {
        # Luftraum roof + beams; one oversized transparent Koordinationszone wrapping top.
        "id": "coordination-zone-01",
        "element_type": "ARC-COORD-ZONE",
        "height": 2.8,
        "upper_height": 2.8,
        "width": 4.0,
        "depth": 5.0,
        "FinishCeilingHeight": 2.6,
        "zone_height": 1.70,
        "zone_margin": 0.0,
        "attach_element": "architecture-coordination-zone",
    },
    {
        # Gable Steildach + attic IfcSpace following the roof inclination.
        "id": "roof-pitched-01",
        "element_type": "ARC-ROOF-PITCH",
        "attach_element": "architecture-roof-pitched",
    },
    {
        # Flat roof + Attika + flush cladding + Attika-top insulation; accent ROOFING.
        "id": "roofing-insulation-01",
        "element_type": "ARC-ROOF-DRAIN",
        "attach_element": "architecture-roof-drainage",
    },
    {
        # Schematic tree: crown sphere + trunk + root sphere on ground.
        "id": "tree-01",
        "element_type": "LAN-TREE",
        "attach_element": "landscape-tree",
    },
    {
        # Thin humus layer on a ground plate.
        "id": "humus-01",
        "element_type": "LAN-HUMUS",
        "attach_element": "landscape-humus",
    },
    {
        # Shallow retention basin on terrain.
        "id": "retention-01",
        "element_type": "LAN-RETENTION",
        "attach_element": "landscape-retention",
    },
    {
        # Floor slab + back wall; schematic table + chair (orange accents).
        "id": "furniture-01",
        "element_type": "FURN",
        "attach_element": "furniture",
    },
    {
        # Floor slab + back wall; rough kitchen line made from separate blocks.
        "id": "built-in-furniture-kitchen-01",
        "element_type": "ARC-FURN-BUILTIN",
        "room_width": 3.2,
        "attach_element": "architecture-built-in-furniture",
    },
    {
        "id": "spaces-gross-volume-01",
        "element_type": "SPACE-GROSS",
        "height": 3.0,
        "foundation_height": 0.50,
        "storey_names": ["EG", "01", "02"],
        "attach_element": "spaces-gross-volume",
    },
]
