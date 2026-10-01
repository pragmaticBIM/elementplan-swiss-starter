"""IfcSlab helpers for vignette / catalog context geometry."""

from __future__ import annotations

from typing import Sequence

import ifcopenshell

from generators.parts import add_extruded_product


def add_slab(
    ifc_file: ifcopenshell.file,
    *,
    name: str,
    body_context: ifcopenshell.entity_instance,
    storey: ifcopenshell.entity_instance,
    polyline: Sequence[Sequence[float]],
    thickness: float,
    z_bottom: float,
    predefined_type: str = "FLOOR",
) -> ifcopenshell.entity_instance:
    return add_extruded_product(
        ifc_file,
        ifc_class="IfcSlab",
        name=name,
        body_context=body_context,
        storey=storey,
        polyline=polyline,
        thickness=thickness,
        z_bottom=z_bottom,
        predefined_type=predefined_type,
    )
