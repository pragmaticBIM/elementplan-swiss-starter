"""IfcBuildingElementProxy Detailverweis volumes on the exterior-wall vignette."""

from __future__ import annotations

from typing import Any, Sequence

import ifcopenshell
import ifcopenshell.util.element as element_util
from ifcopenshell.api.geometry import assign_representation, edit_object_placement
from ifcopenshell.api.root import create_entity
from ifcopenshell.api.spatial import assign_container

from generators.base import assign_pset, get_body_context
from generators.parts import (
    create_body_representation,
    create_extruded_area_solid,
    rect_polyline,
    translation_matrix,
)
from generators.space import DOOR_WIDTH

# Shared cross-section for balcony-junction Detailverweis boxes (metres)
DEFAULT_JUNCTION = {
    "depth_into_wall": 0.15,
    "depth_onto_balcony": 0.70,
    "z_below": 0.20,
    "height": 0.85,
}


def _add_detail_volume(
    ifc_file: ifcopenshell.file,
    *,
    storey: ifcopenshell.entity_instance,
    body_context: ifcopenshell.entity_instance,
    name: str,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    z0: float,
    height: float,
) -> ifcopenshell.entity_instance:
    """Simplified IfcBuildingElementProxy volume (ObjectType=Detailverweis)."""
    proxy = create_entity(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name=str(name),
        predefined_type="USERDEFINED",
    )
    proxy.ObjectType = "Detailverweis"
    assign_container(ifc_file, relating_structure=storey, products=[proxy])
    edit_object_placement(
        ifc_file,
        product=proxy,
        matrix=translation_matrix(z=float(z0)),
    )
    solid = create_extruded_area_solid(
        ifc_file,
        rect_polyline(float(x0), float(y0), float(x1), float(y1)),
        float(height),
    )
    representation = create_body_representation(ifc_file, body_context, solid)
    assign_representation(ifc_file, product=proxy, representation=representation)
    return proxy


def _wall_outer_face_x(wall: ifcopenshell.entity_instance) -> float:
    """World X of the exterior face (balcony side) for a +Y-running facade wall."""
    origin = wall.ObjectPlacement.RelativePlacement.Location.Coordinates
    return float(origin[0])


def _place_volumes(
    ifc_file: ifcopenshell.file,
    *,
    wall: ifcopenshell.entity_instance,
    interior_depth: float,
    balcony_depth: float,
    junction: dict[str, float],
    wall_name: str,
    door_name: str,
) -> list[ifcopenshell.entity_instance]:
    """Place detail volumes along the balcony–wall line.

    Layout along the facade (+Y)::

        [ first: wall start → door ]  [ second: door ]  [ first again → wall end ]
    """
    storey = element_util.get_container(wall)
    if storey is None:
        raise ValueError("exterior wall has no storey container")
    body_context = get_body_context(ifc_file)

    facade_x = _wall_outer_face_x(wall)
    door_along = interior_depth - DOOR_WIDTH - 0.40
    door_end = door_along + DOOR_WIDTH

    x0 = facade_x - float(junction["depth_into_wall"])
    x1 = min(
        facade_x + float(junction["depth_onto_balcony"]),
        facade_x + balcony_depth,
    )
    z0 = -float(junction["z_below"])
    height = float(junction["height"])

    def box(name: str, y0: float, y1: float) -> ifcopenshell.entity_instance:
        return _add_detail_volume(
            ifc_file,
            storey=storey,
            body_context=body_context,
            name=name,
            x0=x0,
            y0=y0,
            x1=x1,
            y1=y1,
            z0=z0,
            height=height,
        )

    proxies: list[ifcopenshell.entity_instance] = []
    # First detail: wall start → door
    if door_along > 1e-6:
        proxies.append(box(wall_name, 0.0, door_along))
    # Second detail: at the door
    if door_end > door_along + 1e-6:
        proxies.append(box(door_name, door_along, door_end))
    # First detail again: door → wall end
    if interior_depth > door_end + 1e-6:
        proxies.append(box(wall_name, door_end, interior_depth))

    return proxies


def generate_detail_references(
    params: dict[str, Any],
) -> tuple[ifcopenshell.file, list[ifcopenshell.entity_instance]]:
    """Exterior-wall fabric plus Detailverweis volumes at balcony junctions.

    Reuses ``generate_exterior_fabric`` (wall accent, no cladding/spaces). No top
    slab or ceiling covering. Returns proxies ordered along the facade:
    ``[wall→door, door, door→wall-end]`` (first name flanks the door).
    """
    from generators.exterior_fabric import generate_exterior_fabric

    fabric_params = dict(params.get("fabric_params") or {})
    if not fabric_params:
        raise ValueError("fabric_params is required (reuse the exterior-wall vignette)")

    # Detail-reference card only: open top (no ceiling slab / covering)
    space_params = fabric_params.setdefault("space_params", {})
    space_params["include_ceiling_covering"] = False
    space_params["include_ceiling_slab"] = False

    ifc_file, wall = generate_exterior_fabric(fabric_params)

    interior_depth = float(
        params.get("interior_depth")
        or (fabric_params.get("space_params") or {}).get("depth")
        or 5.0
    )
    balcony_depth = float(params.get("balcony_depth") or params.get("width") or 1.5)

    volumes = params.get("volumes") or []
    wall_name = "AW-Balkon"
    door_name = "AW-Türschwelle"
    if len(volumes) >= 1 and volumes[0].get("name"):
        wall_name = str(volumes[0]["name"])
    if len(volumes) >= 2 and volumes[1].get("name"):
        door_name = str(volumes[1]["name"])

    proxies = _place_volumes(
        ifc_file,
        wall=wall,
        interior_depth=interior_depth,
        balcony_depth=balcony_depth,
        junction=dict(DEFAULT_JUNCTION),
        wall_name=wall_name,
        door_name=door_name,
    )

    # volume_attrs[0] → flanking (first) detail; volume_attrs[1] → door detail
    attrs_list: Sequence[dict[str, Any]] = params.get("volume_attrs") or []
    wall_attrs = attrs_list[0] if len(attrs_list) >= 1 else {}
    door_attrs = attrs_list[1] if len(attrs_list) >= 2 else wall_attrs

    def _apply(proxy: ifcopenshell.entity_instance, attrs: dict[str, Any]) -> None:
        if not attrs:
            return
        if attrs.get("Name"):
            proxy.Name = str(attrs["Name"])
        if attrs.get("PredefinedType") is not None:
            proxy.PredefinedType = str(attrs["PredefinedType"])
        if attrs.get("ObjectType") is not None:
            proxy.ObjectType = str(attrs["ObjectType"])
        property_datatypes = attrs.get("property_datatypes") or {}
        for pset_name, props in (attrs.get("properties") or {}).items():
            assign_pset(
                ifc_file,
                proxy,
                pset_name,
                props,
                datatypes=property_datatypes.get(pset_name),
            )

    for proxy in proxies:
        attrs = door_attrs if proxy.Name == door_name else wall_attrs
        _apply(proxy, attrs)

    return ifc_file, proxies
