"""IfcBeam catalog generator — accents beams in the Luftraum atrium vignette."""

from __future__ import annotations

from typing import Any

import ifcopenshell

from generators.base import assign_pset, assign_qto


def generate_beam(
    params: dict[str, Any],
) -> tuple[ifcopenshell.file, list[ifcopenshell.entity_instance]]:
    """Build the Luftraum vignette and return the IfcBeams as primary products.

    Geometry matches ``space-luftraum-01`` (including the Luftraum void as
    context). The suspended ceiling is omitted and the top slab is halved over
    the gallery so beams hanging into the atrium stay visible from above.

    ``params`` keys:
    - ``luftraum_params``: geometry passed to ``generate_luftraum``
    - ``name`` / ``predefined_type``
    - ``properties`` / ``property_datatypes`` / ``quantities``

    Returns ``(ifc_file, beams)``.
    """
    from generators.luftraum import generate_luftraum

    luftraum_params = dict(params.get("luftraum_params") or {})
    if not luftraum_params:
        raise ValueError("luftraum_params is required (reuse the Luftraum vignette)")
    luftraum_params.setdefault("with_context", True)
    # Keep the void; no ceiling plate; half top slab so beam tops read clearly
    luftraum_params["omit_luftraum"] = False
    luftraum_params["include_ceiling_covering"] = False
    luftraum_params["top_slab_half"] = True

    ifc_file, _context = generate_luftraum(luftraum_params)
    beams = list(ifc_file.by_type("IfcBeam"))
    if not beams:
        raise ValueError("no IfcBeam in Luftraum vignette")

    name = params.get("name") or params.get("Name")
    predefined_type = params.get("predefined_type") or params.get("PredefinedType")
    object_type = params.get("object_type") or params.get("ObjectType")
    quantities = params.get("quantities") or {}
    properties = params.get("properties") or {}
    property_datatypes = params.get("property_datatypes") or {}

    for index, beam in enumerate(beams):
        if name:
            beam.Name = str(name) if len(beams) == 1 else f"{name}-{index + 1:02d}"
        if predefined_type is not None and hasattr(beam, "PredefinedType"):
            beam.PredefinedType = str(predefined_type)
        if object_type is not None and hasattr(beam, "ObjectType"):
            beam.ObjectType = str(object_type)
        for qto_name, props in quantities.items():
            assign_qto(ifc_file, beam, qto_name, props)
        for pset_name, props in properties.items():
            assign_pset(
                ifc_file,
                beam,
                pset_name,
                props,
                datatypes=property_datatypes.get(pset_name),
            )

    return ifc_file, beams
