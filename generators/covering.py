"""IfcCovering helpers and suspended-ceiling catalog generator."""

from __future__ import annotations

from typing import Any, Sequence

import ifcopenshell
from ifcopenshell.api.geometry import assign_representation, edit_object_placement
from ifcopenshell.api.root import create_entity
from ifcopenshell.api.spatial import assign_container

from generators.base import assign_pset, assign_qto
from generators.parts import (
    add_extruded_product,
    axis_placement_matrix,
    create_body_representation,
    create_extruded_area_solid,
)


def add_covering(
    ifc_file: ifcopenshell.file,
    *,
    name: str,
    body_context: ifcopenshell.entity_instance,
    storey: ifcopenshell.entity_instance,
    polyline: Sequence[Sequence[float]],
    thickness: float,
    z_bottom: float,
    predefined_type: str,
) -> ifcopenshell.entity_instance:
    return add_extruded_product(
        ifc_file,
        ifc_class="IfcCovering",
        name=name,
        body_context=body_context,
        storey=storey,
        polyline=polyline,
        thickness=thickness,
        z_bottom=z_bottom,
        predefined_type=predefined_type,
    )


def add_vertical_covering(
    ifc_file: ifcopenshell.file,
    *,
    name: str,
    body_context: ifcopenshell.entity_instance,
    storey: ifcopenshell.entity_instance,
    origin: Sequence[float],
    length: float,
    height: float,
    thickness: float = 0.05,
    direction_xy: Sequence[float] = (1.0, 0.0),
    predefined_type: str = "CLADDING",
    openings: Sequence[dict] | None = None,
) -> ifcopenshell.entity_instance:
    """Vertical facade cladding strip (same local frame as ``add_wall``)."""
    from generators.wall import vertical_body_solids_with_openings

    covering = create_entity(
        ifc_file,
        ifc_class="IfcCovering",
        name=name,
        predefined_type=predefined_type,
    )
    assign_container(ifc_file, relating_structure=storey, products=[covering])
    dx, dy = float(direction_xy[0]), float(direction_xy[1])
    edit_object_placement(
        ifc_file,
        product=covering,
        matrix=axis_placement_matrix(
            (
                float(origin[0]),
                float(origin[1]),
                float(origin[2]) if len(origin) > 2 else 0.0,
            ),
            local_x=(dx, dy, 0.0),
            local_z=(0.0, 0.0, 1.0),
        ),
    )
    solids = vertical_body_solids_with_openings(
        ifc_file,
        length=length,
        height=height,
        thickness=thickness,
        openings=openings,
    )
    representation = create_body_representation(ifc_file, body_context, solids)
    assign_representation(ifc_file, product=covering, representation=representation)
    return covering


def _find_covering_by_type(
    ifc_file: ifcopenshell.file,
    predefined_type: str,
    *,
    prefer_name_contains: str | None = None,
) -> ifcopenshell.entity_instance:
    """Return an IfcCovering with the given PredefinedType from the vignette."""
    matches = [
        covering
        for covering in ifc_file.by_type("IfcCovering")
        if getattr(covering, "PredefinedType", None) == predefined_type
    ]
    if not matches:
        raise ValueError(
            f"no IfcCovering with PredefinedType={predefined_type!r} in vignette"
        )

    def _is_primary_room(covering: ifcopenshell.entity_instance) -> bool:
        name = covering.Name or ""
        # Neighbour suffix, and never pick a ceiling when asking for flooring by name
        if "-N-" in name:
            return False
        if predefined_type == "FLOORING" and "Ceiling" in name:
            return False
        if predefined_type == "CEILING" and "Floor" in name:
            return False
        return True

    if prefer_name_contains:
        for covering in matches:
            name = covering.Name or ""
            if prefer_name_contains in name and _is_primary_room(covering):
                return covering
    for covering in matches:
        if _is_primary_room(covering):
            return covering
    return matches[0]


def generate_covering(
    params: dict[str, Any],
) -> tuple[ifcopenshell.file, ifcopenshell.entity_instance]:
    """Build a vignette and return the target covering as primary.

    - ``CEILING``: Luftraum atrium (same as ``space-luftraum-01``); accents the
      suspended ceiling spanning through the void under the beams.
    - ``FLOORING``: interior-space vignette (same as Innenräume).

    ``params`` keys:
    - ``luftraum_params`` (CEILING) or ``space_params`` (FLOORING)
    - ``name`` / ``predefined_type``
    - ``properties`` / ``property_datatypes`` / ``quantities``
    """
    predefined_type = (
        params.get("predefined_type") or params.get("PredefinedType") or "CEILING"
    )
    predefined_type = str(predefined_type)

    if predefined_type == "CEILING":
        from generators.luftraum import generate_luftraum

        luftraum_params = dict(params.get("luftraum_params") or {})
        if not luftraum_params:
            raise ValueError(
                "luftraum_params is required for CEILING (reuse the Luftraum vignette)"
            )
        luftraum_params.setdefault("with_context", True)
        luftraum_params["omit_luftraum"] = False
        luftraum_params["include_ceiling_covering"] = True
        ifc_file, _context = generate_luftraum(luftraum_params)
        prefer_name = "CeilingCovering"
    else:
        # Late import: space.py imports add_covering from this module
        from generators.space import generate_space

        space_params = dict(params.get("space_params") or {})
        if not space_params:
            raise ValueError(
                "space_params is required for FLOORING (reuse the interior-space vignette)"
            )
        space_params.setdefault("with_context", True)
        ifc_file, _space = generate_space(space_params)
        prefer_name = "FloorCovering"

    covering = _find_covering_by_type(
        ifc_file,
        predefined_type,
        prefer_name_contains=prefer_name,
    )

    name = params.get("name") or params.get("Name")
    if name:
        covering.Name = str(name)

    covering.PredefinedType = predefined_type

    quantities = params.get("quantities") or {}
    for qto_name, props in quantities.items():
        assign_qto(ifc_file, covering, qto_name, props)

    property_datatypes = params.get("property_datatypes") or {}
    for pset_name, props in (params.get("properties") or {}).items():
        assign_pset(
            ifc_file,
            covering,
            pset_name,
            props,
            datatypes=property_datatypes.get(pset_name),
        )

    return ifc_file, covering
