#!/usr/bin/env python3
"""Batch-generate IFC + isometric PNG previews for catalog entries."""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from catalog.attach import attach_preview_to_element
from catalog.mapping import (
    BEAM_TYPES,
    CEILING_COVERING_TYPES,
    COORDINATION_ZONE_TYPES,
    COVERING_TYPES,
    DETAIL_REFERENCE_TYPES,
    EXTERIOR_FABRIC_TYPES,
    EXTERIOR_SPACE_TYPES,
    FLOOR_COVERING_TYPES,
    FLOOR_COVERING_EXTERIOR_TYPES,
    FOOTING_TYPES,
    COLUMN_TYPES,
    FURNITURE_TYPES,
    GROSS_VOLUME_TYPES,
    INTERIOR_CLADDING_TYPES,
    INTERIOR_FABRIC_TYPES,
    INTERIOR_WALL_TYPES,
    LUFTRAUM_TYPES,
    MAINTENANCE_SPACE_TYPES,
    INSTALLATION_PATH_TYPES,
    TURNING_RADIUS_TYPES,
    DECISION_VOLUME_TYPES,
    MOVEMENT_CLEARANCE_TYPES,
    BUILDING_LAW_PARCEL_TYPES,
    SURROUNDING_BUILDING_TYPES,
    CONSTRUCTION_LOGISTICS_TYPES,
    PLANNING_CONSTRAINT_TYPES,
    UMBAU_PERIMETER_TYPES,
    OPENING_TYPES,
    PARKING_TYPES,
    ELEVATOR_TYPES,
    REFERENCE_POINT_TYPES,
    ROOF_PITCHED_TYPES,
    ROOFING_TYPES,
    SLAB_TYPES,
    SPACE_TYPES,
    SPATIAL_STRUCTURE_TYPES,
    STAIR_TYPES,
    RAILING_TYPES,
    SHADING_DEVICE_TYPES,
    TREE_TYPES,
    HUMUS_TYPES,
    TREE_PIT_TYPES,
    RETENTION_TYPES,
    VORSATZSCHALE_TYPES,
    get_generator,
    map_entry_params,
)
from catalog.sample_data import SAMPLE_CATALOG
from render.engrave_specs import engrave_kwargs_for
from render.isometric import PRINT_DPI, PRINT_RESOLUTION, render_isometric
import ifcopenshell.util.element as element_util

# Title-grid slugs. Orthographic copies live beside the perspective pictures
# and do not replace ``picture_link`` (book pages keep the perspective lens).
COVER_ISO_SLUGS = (
    "spaces-interior",
    "spaces-exterior",
    "spaces-parking",
    "architecture-door-exterior",
    "furniture",
    "architecture-stair",
    "architecture-window-interior",
    "spaces-elevator",
    "architecture-beam",
    "architecture-ceiling-suspended",
    "architecture-floor-covering",
    "architecture-slab-floor",
    "architecture-slab-balcony",
    "architecture-roof-pitched",
    "architecture-detail-reference",
    "architecture-opening-void",
)

# Graded opaque oranges for the Storey catalog picture (bottom → top).
_STOREY_GRADE_COLORS: list[list[float]] = [
    [1.0, 0.72, 0.45, 1.0],
    [1.0, 0.55, 0.22, 1.0],
    [1.0, 0.40, 0.08, 1.0],
]

# Opaque orange tones for Bruttovolumen: foundation + (flat A, stair, flat B) × storey.
_GROSS_VOLUME_COLORS: list[list[float]] = [
    # FD foundation
    [0.78, 0.32, 0.06, 1.0],
    # EG
    [1.00, 0.78, 0.38, 1.0],
    [1.00, 0.55, 0.12, 1.0],
    [1.00, 0.42, 0.05, 1.0],
    # 01
    [1.00, 0.68, 0.26, 1.0],
    [0.98, 0.46, 0.08, 1.0],
    [0.95, 0.34, 0.02, 1.0],
    # 02
    [1.00, 0.58, 0.16, 1.0],
    [0.95, 0.38, 0.04, 1.0],
    [0.90, 0.26, 0.00, 1.0],
]

# Translucent oranges for Detailverweis volumes (balcony–wall, balcony–door).
_DETAIL_REFERENCE_COLORS: list[list[float]] = [
    [1.00, 0.62, 0.22, 0.42],  # lighter — wall junction
    [0.95, 0.32, 0.04, 0.48],  # deeper — door threshold
]

# Transparent orange for Koordinationszone proxy (IfcBuildingElementProxy is otherwise opaque).
_COORDINATION_ZONE_COLOR: list[float] = [1.0, 0.45, 0.1, 0.38]
_UMBAU_PERIMETER_COLOR: list[float] = [1.0, 0.45, 0.1, 0.38]
_INSTALLATION_PATH_COLOR: list[float] = [1.0, 0.45, 0.1, 0.38]
_TURNING_RADIUS_COLOR: list[float] = [1.0, 0.45, 0.1, 0.38]
_HUMUS_COLOR: list[float] = [1.0, 0.45, 0.1, 0.55]

# Graded translucent oranges for Entscheidungskörper (open, approved, superseded).
_DECISION_VOLUME_COLORS: list[list[float]] = [
    [1.00, 0.55, 0.12, 0.42],
    [0.95, 0.32, 0.04, 0.48],
    [0.72, 0.48, 0.32, 0.36],
]

# Graded translucent oranges for overlapping Bewegungsflächen.
_MOVEMENT_CLEARANCE_COLORS: list[list[float]] = [
    [1.00, 0.62, 0.18, 0.40],
    [1.00, 0.42, 0.06, 0.46],
    [0.92, 0.28, 0.02, 0.42],
]
_BUILDING_LAW_PARCEL_COLORS: list[list[float]] = [
    [1.00, 0.62, 0.22, 0.40],
    [1.00, 0.48, 0.12, 0.42],
    [0.95, 0.32, 0.04, 0.42],
]
_SURROUNDING_BUILDING_COLORS: list[list[float]] = [
    [1.00, 0.62, 0.22, 0.42],
    [1.00, 0.48, 0.12, 0.44],
    [0.95, 0.32, 0.04, 0.42],
]

# Graded translucent oranges for Baustelleneinrichtungsobjekte
# (fence, container, crane, storage, crane foundation).
_CONSTRUCTION_LOGISTICS_COLORS: list[list[float]] = [
    [1.00, 0.68, 0.28, 0.40],
    [1.00, 0.52, 0.14, 0.44],
    [0.95, 0.32, 0.04, 0.46],
    [0.90, 0.22, 0.00, 0.42],
    [0.85, 0.18, 0.00, 0.44],
]

# Graded translucent oranges for Rahmenbedingungen (flood, rail, flight).
_PLANNING_CONSTRAINT_COLORS: list[list[float]] = [
    [1.00, 0.68, 0.28, 0.38],
    [1.00, 0.48, 0.12, 0.42],
    [0.95, 0.30, 0.04, 0.40],
]


def _print_element_properties(element) -> None:
    """Print psets/qtos so they are visible in the generation log."""
    psets = element_util.get_psets(element, psets_only=True)
    qtos = element_util.get_psets(element, qtos_only=True)
    predefined = getattr(element, "PredefinedType", None)
    object_type = getattr(element, "ObjectType", None)
    long_name = getattr(element, "LongName", None)
    phase = getattr(element, "Phase", None)
    print(
        f"    entity: Name={element.Name!r} LongName={long_name!r} "
        f"PredefinedType={predefined} ObjectType={object_type!r}"
        + (f" Phase={phase!r}" if phase is not None else "")
    )
    for pset_name, props in psets.items():
        clean = {k: v for k, v in props.items() if k != "id"}
        print(f"    {pset_name}: {clean}")
    for qto_name, props in qtos.items():
        clean = {k: v for k, v in props.items() if k != "id"}
        print(f"    {qto_name}: {clean}")


def _primary_guids(ifc_file, element_type: str, primary) -> set[str]:
    """GUIDs to accent in the isometric preview."""
    if element_type in FLOOR_COVERING_TYPES:
        # Accent both primary and neighbour floor build-ups
        flooring = {
            c.GlobalId
            for c in ifc_file.by_type("IfcCovering")
            if getattr(c, "PredefinedType", None) == "FLOORING"
        }
        return flooring or {primary.GlobalId}
    if element_type in COVERING_TYPES:
        # Accent only the covering (CEILING: Luftraum atrium; FLOORING: Innenräume)
        if isinstance(primary, list):
            return {p.GlobalId for p in primary}
        return {primary.GlobalId}
    if element_type in OPENING_TYPES:
        if isinstance(primary, list):
            return {p.GlobalId for p in primary}
        return {primary.GlobalId}
    if element_type in EXTERIOR_FABRIC_TYPES:
        if isinstance(primary, list):
            return {p.GlobalId for p in primary}
        return {primary.GlobalId}
    if element_type in INTERIOR_WALL_TYPES:
        # The non-load-bearing card shows two parallel partitions: the original
        # wall below the flooring and a second wall based on finished floor.
        return {
            wall.GlobalId
            for wall in ifc_file.by_type("IfcWall")
            if getattr(wall, "PredefinedType", None) == "PARTITIONING"
        } or {primary.GlobalId}
    if element_type in EXTERIOR_SPACE_TYPES:
        # Accent only EXTERNAL spaces (balcony); interior half stays context
        return {
            s.GlobalId
            for s in ifc_file.by_type("IfcSpace")
            if getattr(s, "PredefinedType", None) == "EXTERNAL"
        } or {primary.GlobalId}
    if element_type in LUFTRAUM_TYPES:
        # Accent only the Luftraum void; office / Flur / Galerie stay context
        return {
            s.GlobalId
            for s in ifc_file.by_type("IfcSpace")
            if getattr(s, "ObjectType", None) == "Luftraum"
        } or {primary.GlobalId}
    if element_type in COORDINATION_ZONE_TYPES:
        # Accent Koordinationszone + keep Luftraum void visible
        guids = {
            p.GlobalId for p in (primary if isinstance(primary, list) else [primary])
        }
        guids.update(
            s.GlobalId
            for s in ifc_file.by_type("IfcSpace")
            if getattr(s, "ObjectType", None) == "Luftraum"
        )
        return guids
    if element_type in BEAM_TYPES:
        return {b.GlobalId for b in ifc_file.by_type("IfcBeam")} or {
            p.GlobalId for p in (primary if isinstance(primary, list) else [primary])
        }
    if element_type in PARKING_TYPES:
        # Accent only PARKING bays; street aisle stays context
        if isinstance(primary, list):
            return {p.GlobalId for p in primary}
        return {primary.GlobalId}
    if element_type in ELEVATOR_TYPES:
        if isinstance(primary, list):
            return {p.GlobalId for p in primary}
        return {primary.GlobalId}
    if element_type in VORSATZSCHALE_TYPES:
        # Accent only the Vorsatzschale gap; bathroom fabric stays context
        return {
            s.GlobalId
            for s in ifc_file.by_type("IfcSpace")
            if getattr(s, "ObjectType", None) == "Vorsatzschale"
        } or {primary.GlobalId}
    if element_type in SPACE_TYPES | GROSS_VOLUME_TYPES:
        return {s.GlobalId for s in ifc_file.by_type("IfcSpace")}
    if element_type in REFERENCE_POINT_TYPES:
        return {p.GlobalId for p in ifc_file.by_type("IfcBuildingElementProxy")}
    if element_type in DETAIL_REFERENCE_TYPES:
        if isinstance(primary, list):
            return {p.GlobalId for p in primary}
        return {primary.GlobalId}
    if isinstance(primary, list):
        return {p.GlobalId for p in primary}
    return {primary.GlobalId}


def _primary_colors(element_type: str, primary) -> dict[str, list[float]] | None:
    """Optional per-GUID accent colours (Storey / Bruttovolumen oranges)."""
    if element_type in UMBAU_PERIMETER_TYPES:
        proxies = primary if isinstance(primary, list) else [primary]
        return {
            proxy.GlobalId: list(_UMBAU_PERIMETER_COLOR)
            for proxy in proxies
            if proxy.is_a("IfcBuildingElementProxy")
        } or None
    if element_type in COORDINATION_ZONE_TYPES:
        colors: dict[str, list[float]] = {}
        proxies = primary if isinstance(primary, list) else [primary]
        for proxy in proxies:
            if proxy.is_a("IfcBuildingElementProxy"):
                colors[proxy.GlobalId] = list(_COORDINATION_ZONE_COLOR)
        return colors or None
    if element_type in INSTALLATION_PATH_TYPES:
        colors = {}
        proxies = primary if isinstance(primary, list) else [primary]
        for proxy in proxies:
            if proxy.is_a("IfcBuildingElementProxy"):
                colors[proxy.GlobalId] = list(_INSTALLATION_PATH_COLOR)
        return colors or None
    if element_type in TURNING_RADIUS_TYPES:
        colors = {}
        proxies = primary if isinstance(primary, list) else [primary]
        for proxy in proxies:
            if proxy.is_a("IfcBuildingElementProxy") and str(
                getattr(proxy, "ObjectType", "") or ""
            ) in {"Wenderadius", "Rayon de braquage", "Raggio di manovra", "Turning radius"}:
                colors[proxy.GlobalId] = list(_TURNING_RADIUS_COLOR)
        return colors or None
    if element_type in DECISION_VOLUME_TYPES:
        proxies = primary if isinstance(primary, list) else [primary]
        colors: dict[str, list[float]] = {}
        for index, proxy in enumerate(proxies):
            if not proxy.is_a("IfcBuildingElementProxy"):
                continue
            colors[proxy.GlobalId] = list(
                _DECISION_VOLUME_COLORS[min(index, len(_DECISION_VOLUME_COLORS) - 1)]
            )
        return colors or None
    if element_type in MOVEMENT_CLEARANCE_TYPES:
        proxies = primary if isinstance(primary, list) else [primary]
        colors = {}
        for index, proxy in enumerate(proxies):
            if not proxy.is_a("IfcBuildingElementProxy"):
                continue
            colors[proxy.GlobalId] = list(
                _MOVEMENT_CLEARANCE_COLORS[
                    min(index, len(_MOVEMENT_CLEARANCE_COLORS) - 1)
                ]
            )
        return colors or None
    if element_type in BUILDING_LAW_PARCEL_TYPES:
        if not isinstance(primary, list):
            return None
        colors: dict[str, list[float]] = {}
        next_index = 0
        for proxy in primary:
            if not proxy.is_a("IfcBuildingElementProxy"):
                continue
            colors[proxy.GlobalId] = list(
                _BUILDING_LAW_PARCEL_COLORS[
                    min(next_index, len(_BUILDING_LAW_PARCEL_COLORS) - 1)
                ]
            )
            next_index += 1
        return colors or None
    if element_type in SURROUNDING_BUILDING_TYPES:
        if not isinstance(primary, list):
            return None
        colors = {}
        next_index = 0
        for proxy in primary:
            if not proxy.is_a("IfcBuildingElementProxy"):
                continue
            colors[proxy.GlobalId] = list(
                _SURROUNDING_BUILDING_COLORS[
                    min(next_index, len(_SURROUNDING_BUILDING_COLORS) - 1)
                ]
            )
            next_index += 1
        return colors or None
    if element_type in CONSTRUCTION_LOGISTICS_TYPES:
        if not isinstance(primary, list):
            return None
        # Same Name shares one orange (crane mast + jib)

        colors: dict[str, list[float]] = {}
        name_color: dict[str, list[float]] = {}
        next_index = 0
        for proxy in primary:
            if not proxy.is_a("IfcBuildingElementProxy"):
                continue
            name = str(proxy.Name or proxy.GlobalId)
            if name not in name_color:
                name_color[name] = list(
                    _CONSTRUCTION_LOGISTICS_COLORS[
                        min(next_index, len(_CONSTRUCTION_LOGISTICS_COLORS) - 1)
                    ]
                )
                next_index += 1
            colors[proxy.GlobalId] = name_color[name]
        return colors or None
    if element_type in PLANNING_CONSTRAINT_TYPES:
        if not isinstance(primary, list):
            return None
        colors: dict[str, list[float]] = {}
        next_index = 0
        for proxy in primary:
            if not proxy.is_a("IfcBuildingElementProxy"):
                continue
            colors[proxy.GlobalId] = list(
                _PLANNING_CONSTRAINT_COLORS[
                    min(next_index, len(_PLANNING_CONSTRAINT_COLORS) - 1)
                ]
            )
            next_index += 1
        return colors or None
    if element_type in DETAIL_REFERENCE_TYPES:
        if not isinstance(primary, list):
            return None
        # Same Name shares one orange (door detail may be split around the opening)
        colors: dict[str, list[float]] = {}
        name_color: dict[str, list[float]] = {}
        next_index = 0
        for proxy in primary:
            name = str(proxy.Name or proxy.GlobalId)
            if name not in name_color:
                name_color[name] = list(
                    _DETAIL_REFERENCE_COLORS[
                        min(next_index, len(_DETAIL_REFERENCE_COLORS) - 1)
                    ]
                )
                next_index += 1
            colors[proxy.GlobalId] = name_color[name]
        return colors
    if element_type in GROSS_VOLUME_TYPES:
        if not isinstance(primary, list):
            return None
        spaces = [p for p in primary if p.is_a("IfcSpace")]
        if not spaces:
            return None
        colors: dict[str, list[float]] = {}
        for index, space in enumerate(spaces):
            colors[space.GlobalId] = list(
                _GROSS_VOLUME_COLORS[min(index, len(_GROSS_VOLUME_COLORS) - 1)]
            )
        return colors
    if element_type in ELEVATOR_TYPES:
        # Default translucent accent orange (_ACCENT_VOLUME) for both spaces.
        return None
    if element_type in HUMUS_TYPES:
        if not hasattr(primary, "GlobalId"):
            return None
        return {primary.GlobalId: list(_HUMUS_COLOR)}
    if element_type in TREE_PIT_TYPES | RETENTION_TYPES:
        if not hasattr(primary, "GlobalId"):
            return None
        return {primary.GlobalId: list(_HUMUS_COLOR)}
    if element_type not in {"IfcBuildingStorey", "STOREY"}:
        return None
    if not isinstance(primary, list):
        return None
    # Storey card: grade by storey (bottom→top). Balcony shares its floor's colour.
    slabs = [p for p in primary if p.is_a("IfcSlab")]
    if not slabs:
        return None
    storey_order: list[str] = []
    storey_by_guid: dict[str, str] = {}
    for slab in slabs:
        storey = element_util.get_container(slab)
        storey_id = storey.GlobalId if storey is not None else slab.GlobalId
        storey_by_guid[slab.GlobalId] = storey_id
        if storey_id not in storey_order:
            storey_order.append(storey_id)
    colors: dict[str, list[float]] = {}
    for slab in slabs:
        storey_index = storey_order.index(storey_by_guid[slab.GlobalId])
        colors[slab.GlobalId] = list(
            _STOREY_GRADE_COLORS[min(storey_index, len(_STOREY_GRADE_COLORS) - 1)]
        )
    return colors


def run_catalog(
    catalog: list[dict],
    output_dir: Path,
    *,
    cover_iso: bool = False,
) -> tuple[int, int, list[str]]:
    """Process known catalog types. Returns (succeeded, failed, failed_ids)."""
    output_dir.mkdir(parents=True, exist_ok=True)

    succeeded = 0
    failed = 0
    failed_ids: list[str] = []

    supported = (
        SPACE_TYPES
        | EXTERIOR_SPACE_TYPES
        | PARKING_TYPES
        | ELEVATOR_TYPES
        | VORSATZSCHALE_TYPES
        | LUFTRAUM_TYPES
        | COVERING_TYPES
        | GROSS_VOLUME_TYPES
        | REFERENCE_POINT_TYPES
        | SPATIAL_STRUCTURE_TYPES
        | SLAB_TYPES
        | OPENING_TYPES
        | FOOTING_TYPES
        | COLUMN_TYPES
        | MAINTENANCE_SPACE_TYPES
        | INSTALLATION_PATH_TYPES
        | TURNING_RADIUS_TYPES
        | DECISION_VOLUME_TYPES
        | MOVEMENT_CLEARANCE_TYPES
        | BUILDING_LAW_PARCEL_TYPES
        | SURROUNDING_BUILDING_TYPES
        | CONSTRUCTION_LOGISTICS_TYPES
        | PLANNING_CONSTRAINT_TYPES
        | UMBAU_PERIMETER_TYPES
        | STAIR_TYPES
        | RAILING_TYPES
        | SHADING_DEVICE_TYPES
        | TREE_TYPES
        | HUMUS_TYPES
        | TREE_PIT_TYPES
        | RETENTION_TYPES
        | FURNITURE_TYPES
        | COORDINATION_ZONE_TYPES
        | BEAM_TYPES
        | ROOF_PITCHED_TYPES
        | ROOFING_TYPES
        | EXTERIOR_FABRIC_TYPES
        | INTERIOR_FABRIC_TYPES
        | DETAIL_REFERENCE_TYPES
    )
    entries = [e for e in catalog if e.get("element_type") in supported]
    skipped = len(catalog) - len(entries)
    if skipped:
        print(f"Skipping {skipped} unsupported catalog entr(y/ies)")

    for entry in entries:
        element_id = str(entry.get("id") or "unknown")
        try:
            element_type = entry["element_type"]
            params = map_entry_params(entry)
            generator = get_generator(element_type)
            result = generator(params)
            ifc_file, primary = result[0], result[1]
            dotted_guids = (
                {product.GlobalId for product in result[2]}
                if len(result) > 2 and result[2]
                else None
            )
            thin_edge_guids = (
                {product.GlobalId for product in result[3]}
                if len(result) > 3 and result[3]
                else None
            )

            ifc_path = output_dir / f"{element_id}.ifc"
            attach_slug = str(entry.get("attach_element") or "")
            if cover_iso and attach_slug:
                media_dir = Path(__file__).resolve().parent / "media" / "images"
                media_dir.mkdir(parents=True, exist_ok=True)
                png_path = media_dir / f"{attach_slug}-iso.png"
                print_path = media_dir / f"{attach_slug}-iso-print.tif"
            else:
                png_path = output_dir / f"{element_id}.png"
                print_path = output_dir / f"{element_id}-print.tif"
            ifc_file.write(str(ifc_path))
            camera_direction = entry.get("camera_direction")
            if camera_direction is None and element_type in (
                LUFTRAUM_TYPES | BEAM_TYPES | COORDINATION_ZONE_TYPES
            ):
                camera_direction = (-1.0, -1.0, 1.0)
            elif camera_direction is None and element_type in (
                DECISION_VOLUME_TYPES | UMBAU_PERIMETER_TYPES
            ):
                # Steeper than the default isometric so the storey reads as a plan.
                camera_direction = (0.42, 0.55, 1.25)
            primary_guids = _primary_guids(ifc_file, element_type, primary)
            primary_colors = _primary_colors(element_type, primary)
            camera_focus_guids = (
                {primary[0].GlobalId}
                if element_type in REFERENCE_POINT_TYPES
                and isinstance(primary, list)
                and primary
                else None
            )
            # Beige flooring only when it helps read the subject (Bodenbelag).
            # Interior spaces / Luftraum / beam / Abhangdecke / Koordinationszone /
            # parking: keep floors white context. Wandbekleidung Innen keeps the
            # beige floor so the splash reads as sitting on the flooring.
            color_flooring = element_type not in (
                SPACE_TYPES
                | LUFTRAUM_TYPES
                | COORDINATION_ZONE_TYPES
                | BEAM_TYPES
                | CEILING_COVERING_TYPES
                | PARKING_TYPES
                | ELEVATOR_TYPES
                | VORSATZSCHALE_TYPES
                | (INTERIOR_FABRIC_TYPES - INTERIOR_CLADDING_TYPES)
            )
            # Luftraum card: only the void is filled; office / Flur / Galerie stay wireframe.
            show_context_volumes = element_type not in LUFTRAUM_TYPES
            render_kwargs = dict(
                primary_guids=primary_guids,
                primary_colors=primary_colors,
                dotted_guids=dotted_guids,
                thin_edge_guids=thin_edge_guids,
                camera_focus_guids=camera_focus_guids,
                camera_padding=float(entry.get("camera_padding", 1.6)),
                camera_direction=camera_direction,
                color_flooring=color_flooring,
                show_context_volumes=show_context_volumes,
                disable_opening_subtractions=(
                    False
                    if element_type in ELEVATOR_TYPES | DECISION_VOLUME_TYPES
                    else None
                ),
                orthographic=cover_iso,
            )
            # Catalog card: 1024² with brand engraving + corner watermark.
            render_isometric(
                ifc_file,
                png_path,
                **render_kwargs,
                **engrave_kwargs_for(element_id),
            )
            # Print asset: 1200² @ 600 DPI CMYK TIFF, clean (no engraving / watermark).
            render_isometric(
                ifc_file,
                print_path,
                resolution=PRINT_RESOLUTION,
                engrave=False,
                watermark=False,
                dpi=PRINT_DPI,
                **render_kwargs,
            )

            assets = f"{ifc_path.name}, {png_path.name}, {print_path.name}"
            if element_type in SPATIAL_STRUCTURE_TYPES:
                print(f"OK  {element_id} -> {assets}")
                for ifc_class in (
                    "IfcProject",
                    "IfcSite",
                    "IfcBuilding",
                    "IfcBuildingStorey",
                    "IfcSlab",
                ):
                    for product in ifc_file.by_type(ifc_class):
                        print(f"    [{ifc_class}]")
                        _print_element_properties(product)
            elif element_type in SLAB_TYPES:
                print(f"OK  {element_id} -> {assets}")
                for product in ifc_file.by_type("IfcSlab"):
                    mark = " *" if product in (
                        primary if isinstance(primary, list) else [primary]
                    ) else ""
                    print(f"    [IfcSlab]{mark}")
                    _print_element_properties(product)
            elif element_type in FOOTING_TYPES | COLUMN_TYPES:
                print(f"OK  {element_id} -> {assets}")
                for ifc_class in ("IfcFooting", "IfcSlab", "IfcColumn"):
                    for product in ifc_file.by_type(ifc_class):
                        mark = " *" if product == primary else ""
                        print(f"    [{ifc_class}]{mark}")
                        _print_element_properties(product)
            elif element_type in MAINTENANCE_SPACE_TYPES:
                print(f"OK  {element_id} -> {assets}")
                for ifc_class in ("IfcBuildingElementProxy", "IfcSlab"):
                    for product in ifc_file.by_type(ifc_class):
                        mark = " *" if product == primary else ""
                        print(f"    [{ifc_class}]{mark}")
                        _print_element_properties(product)
            elif element_type in INSTALLATION_PATH_TYPES:
                print(f"OK  {element_id} -> {assets}")
                for ifc_class in (
                    "IfcBuildingElementProxy",
                    "IfcColumn",
                    "IfcDoor",
                    "IfcWall",
                    "IfcSlab",
                ):
                    for product in ifc_file.by_type(ifc_class):
                        mark = " *" if product == primary else ""
                        print(f"    [{ifc_class}]{mark}")
                        _print_element_properties(product)
            elif element_type in TURNING_RADIUS_TYPES:
                print(f"OK  {element_id} -> {assets}")
                for ifc_class in (
                    "IfcBuildingElementProxy",
                    "IfcCovering",
                    "IfcSlab",
                ):
                    for product in ifc_file.by_type(ifc_class):
                        mark = " *" if product == primary else ""
                        print(f"    [{ifc_class}]{mark}")
                        _print_element_properties(product)
            elif element_type in BUILDING_LAW_PARCEL_TYPES:
                print(f"OK  {element_id} -> {assets}")
                primaries = primary if isinstance(primary, list) else [primary]
                primary_ids = {p.GlobalId for p in primaries}
                for ifc_class in ("IfcBuildingElementProxy", "IfcSlab", "IfcSite"):
                    for product in ifc_file.by_type(ifc_class):
                        mark = " *" if product.GlobalId in primary_ids else ""
                        print(f"    [{ifc_class}]{mark}")
                        _print_element_properties(product)
            elif element_type in SURROUNDING_BUILDING_TYPES:
                print(f"OK  {element_id} -> {assets}")
                primaries = primary if isinstance(primary, list) else [primary]
                primary_ids = {p.GlobalId for p in primaries}
                for ifc_class in ("IfcBuildingElementProxy", "IfcSlab", "IfcSite"):
                    for product in ifc_file.by_type(ifc_class):
                        mark = " *" if product.GlobalId in primary_ids else ""
                        print(f"    [{ifc_class}]{mark}")
                        _print_element_properties(product)
            elif element_type in CONSTRUCTION_LOGISTICS_TYPES:
                print(f"OK  {element_id} -> {assets}")
                primaries = primary if isinstance(primary, list) else [primary]
                primary_ids = {p.GlobalId for p in primaries}
                for ifc_class in ("IfcBuildingElementProxy", "IfcSlab", "IfcSite"):
                    for product in ifc_file.by_type(ifc_class):
                        mark = " *" if product.GlobalId in primary_ids else ""
                        print(f"    [{ifc_class}]{mark}")
                        _print_element_properties(product)
            elif element_type in PLANNING_CONSTRAINT_TYPES:
                print(f"OK  {element_id} -> {assets}")
                primaries = primary if isinstance(primary, list) else [primary]
                primary_ids = {p.GlobalId for p in primaries}
                for ifc_class in ("IfcBuildingElementProxy", "IfcSlab", "IfcSite"):
                    for product in ifc_file.by_type(ifc_class):
                        mark = " *" if product.GlobalId in primary_ids else ""
                        print(f"    [{ifc_class}]{mark}")
                        _print_element_properties(product)
            elif element_type in UMBAU_PERIMETER_TYPES:
                print(f"OK  {element_id} -> {assets}")
                for ifc_class in ("IfcBuildingElementProxy", "IfcSlab"):
                    for product in ifc_file.by_type(ifc_class):
                        mark = " *" if product == primary else ""
                        print(f"    [{ifc_class}]{mark}")
                        _print_element_properties(product)
            elif element_type in TREE_TYPES:
                print(f"OK  {element_id} -> {assets}")
                for ifc_class in ("IfcGeographicElement", "IfcSlab"):
                    for product in ifc_file.by_type(ifc_class):
                        mark = " *" if product == primary else ""
                        print(f"    [{ifc_class}]{mark}")
                        _print_element_properties(product)
            elif element_type in HUMUS_TYPES:
                print(f"OK  {element_id} -> {assets}")
                for ifc_class in ("IfcGeographicElement", "IfcSlab"):
                    for product in ifc_file.by_type(ifc_class):
                        mark = " *" if product == primary else ""
                        print(f"    [{ifc_class}]{mark}")
                        _print_element_properties(product)
            elif element_type in TREE_PIT_TYPES | RETENTION_TYPES:
                print(f"OK  {element_id} -> {assets}")
                for ifc_class in ("IfcGeographicElement", "IfcSlab", "IfcBuildingElementProxy"):
                    for product in ifc_file.by_type(ifc_class):
                        mark = " *" if product == primary else ""
                        print(f"    [{ifc_class}]{mark}")
                        _print_element_properties(product)
            elif element_type in FURNITURE_TYPES:
                print(f"OK  {element_id} -> {assets}")
                primaries = primary if isinstance(primary, list) else [primary]
                primary_ids = {p.GlobalId for p in primaries}
                for ifc_class in ("IfcFurniture", "IfcSlab", "IfcWall"):
                    for product in ifc_file.by_type(ifc_class):
                        mark = " *" if product.GlobalId in primary_ids else ""
                        print(f"    [{ifc_class}]{mark}")
                        _print_element_properties(product)
            elif element_type in ROOF_PITCHED_TYPES:
                print(f"OK  {element_id} -> {assets}")
                for ifc_class in ("IfcRoof", "IfcSpace", "IfcSlab"):
                    for product in ifc_file.by_type(ifc_class):
                        mark = " *" if product == primary else ""
                        print(f"    [{ifc_class}]{mark}")
                        _print_element_properties(product)
            elif element_type in ROOFING_TYPES:
                print(f"OK  {element_id} -> {assets}")
                primaries = primary if isinstance(primary, list) else [primary]
                primary_ids = {p.GlobalId for p in primaries}
                for ifc_class in ("IfcCovering", "IfcSlab", "IfcWall"):
                    for product in ifc_file.by_type(ifc_class):
                        mark = " *" if product.GlobalId in primary_ids else ""
                        print(f"    [{ifc_class}]{mark}")
                        _print_element_properties(product)
            elif isinstance(primary, list):
                label = ", ".join(f"{p.Name}" for p in primary)
                print(f"OK  {element_id} -> {assets}  [{label}]")
                for p in primary:
                    _print_element_properties(p)
            else:
                print(
                    f"OK  {element_id} -> {assets}"
                    f"  [{primary.Name} / {getattr(primary, 'LongName', None)}]"
                )
                _print_element_properties(primary)

            attach_slug = entry.get("attach_element")
            if attach_slug and not cover_iso:
                attached = attach_preview_to_element(
                    element_slug=str(attach_slug),
                    png_path=png_path,
                    ifc_path=ifc_path,
                    print_path=print_path,
                )
                print(
                    f"    attached -> {attached['picture'].name}, "
                    f"{attached['attachment'].name}"
                    + (
                        f", {attached['picture_print'].name}"
                        if attached.get("picture_print")
                        else ""
                    )
                )

            succeeded += 1
        except Exception as exc:
            failed += 1
            failed_ids.append(element_id)
            print(f"FAIL {element_id}: {exc}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

    return succeeded, failed, failed_ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate IFC + isometric PNG for catalog elements."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for {id}.ifc, {id}.png, and {id}-print.tif (default: ./output)",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Optional catalog id to generate (e.g. survey-ref-points-01)",
    )
    parser.add_argument(
        "--cover-iso",
        action="store_true",
        help="Render orthographic title tiles into media/images/{slug}-iso.*",
    )
    args = parser.parse_args(argv)

    catalog = SAMPLE_CATALOG
    if args.cover_iso:
        wanted = set(COVER_ISO_SLUGS)
        catalog = [e for e in catalog if e.get("attach_element") in wanted]
        missing = wanted - {e.get("attach_element") for e in catalog}
        if missing:
            print(
                f"No catalog entry for cover slug(s): {', '.join(sorted(missing))}",
                file=sys.stderr,
            )
            return 1
    if args.only:
        catalog = [e for e in catalog if e.get("id") == args.only]
        if not catalog:
            print(f"No catalog entry with id={args.only!r}", file=sys.stderr)
            return 1

    print(f"Processing {len(catalog)} catalog entr(y/ies)…")
    succeeded, failed, failed_ids = run_catalog(
        catalog, args.output_dir, cover_iso=args.cover_iso
    )

    print()
    print("=== Summary ===")
    print(f"Succeeded: {succeeded}")
    print(f"Failed:    {failed}")
    if failed_ids:
        print(f"Failed ids: {', '.join(failed_ids)}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
