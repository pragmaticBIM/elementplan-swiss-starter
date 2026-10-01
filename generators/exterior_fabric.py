"""Exterior wall / cladding / door / window catalog generators.

Reuse the exterior-space vignette (balcony + facade) without IfcSpace volumes.
"""

from __future__ import annotations

from typing import Any

import ifcopenshell

from generators.base import assign_pset, assign_qto


def _find_exterior_wall(ifc_file: ifcopenshell.file) -> ifcopenshell.entity_instance:
    walls = [
        wall
        for wall in ifc_file.by_type("IfcWall")
        if getattr(wall, "PredefinedType", None) == "SOLIDWALL"
        or (wall.Name or "").endswith("-ExteriorWall")
    ]
    if not walls:
        raise ValueError("no exterior IfcWall in vignette")
    return walls[0]


def _find_cladding(ifc_file: ifcopenshell.file) -> ifcopenshell.entity_instance:
    coverings = [
        covering
        for covering in ifc_file.by_type("IfcCovering")
        if getattr(covering, "PredefinedType", None) == "CLADDING"
        or (covering.Name or "").endswith("-Cladding")
    ]
    if not coverings:
        raise ValueError("no exterior cladding IfcCovering in vignette")
    return coverings[0]


def _find_door(ifc_file: ifcopenshell.file) -> ifcopenshell.entity_instance:
    doors = list(ifc_file.by_type("IfcDoor"))
    if not doors:
        raise ValueError("no IfcDoor in vignette")
    return doors[0]


def _find_window(ifc_file: ifcopenshell.file) -> ifcopenshell.entity_instance:
    windows = list(ifc_file.by_type("IfcWindow"))
    if not windows:
        raise ValueError("no IfcWindow in vignette")
    return windows[0]


_FINDERS = {
    "wall": _find_exterior_wall,
    "cladding": _find_cladding,
    "door": _find_door,
    "window": _find_window,
}


def generate_exterior_fabric(
    params: dict[str, Any],
) -> tuple[ifcopenshell.file, ifcopenshell.entity_instance]:
    """Build the exterior-space fabric without spaces; accent one facade product.

    ``accent`` is one of ``wall``, ``cladding``, ``door``, ``window``.
    Geometry matches ``space-exterior-01``; attributes come from the element YAML.
    """
    from generators.space import generate_space

    space_params = dict(params.get("space_params") or {})
    if not space_params:
        raise ValueError("space_params is required (reuse the exterior-space vignette)")
    space_params.setdefault("with_context", True)
    space_params.setdefault("vignette", "exterior")
    space_params["omit_primary_space"] = True
    space_params["include_interior_space"] = False

    accent = str(params.get("accent") or "wall").lower()
    finder = _FINDERS.get(accent)
    if finder is None:
        raise ValueError(
            f"unsupported accent={accent!r}; expected one of {sorted(_FINDERS)}"
        )

    ifc_file, _handle = generate_space(space_params)
    primary = finder(ifc_file)

    name = params.get("name") or params.get("Name")
    if name:
        primary.Name = str(name)

    predefined_type = params.get("predefined_type") or params.get("PredefinedType")
    if predefined_type is not None and hasattr(primary, "PredefinedType"):
        primary.PredefinedType = str(predefined_type)

    object_type = params.get("object_type") or params.get("ObjectType")
    if object_type is not None and hasattr(primary, "ObjectType"):
        primary.ObjectType = str(object_type)

    quantities = params.get("quantities") or {}
    for qto_name, props in quantities.items():
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

    return ifc_file, primary
