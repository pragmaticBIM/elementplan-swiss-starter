"""Shared IFC helpers: project shell, placement, Pset/Qto assignment."""

from __future__ import annotations

from typing import Any

import ifcopenshell
import ifcopenshell.api.owner.settings as owner_settings
from ifcopenshell.api.aggregate import assign_object
from ifcopenshell.api.context import add_context
from ifcopenshell.api.geometry import edit_object_placement
from ifcopenshell.api.owner import (
    add_application,
    add_organisation,
    add_person,
    add_person_and_organisation,
)
from ifcopenshell.api.project import create_file
from ifcopenshell.api.pset import add_pset, add_qto, edit_pset, edit_qto
from ifcopenshell.api.root import create_entity
from ifcopenshell.api.type import assign_type
from ifcopenshell.api.unit import add_si_unit, assign_unit
from ifcopenshell.util.element import get_type
from ifcopenshell.util.type import get_applicable_types

from generators.parts import translation_matrix


def _ensure_owner_history_factories() -> None:
    """Configure ifcopenshell owner factories so entities get IfcOwnerHistory."""

    def get_user(ifc: ifcopenshell.file) -> ifcopenshell.entity_instance | None:
        existing = next(iter(ifc.by_type("IfcPersonAndOrganization")), None)
        if existing:
            return existing
        person = add_person(
            ifc,
            identification="catalog-pipeline",
            family_name="Pipeline",
            given_name="Catalog",
        )
        organisation = add_organisation(
            ifc, identification="pragmaticBIM", name="pragmaticBIM"
        )
        return add_person_and_organisation(
            ifc, person=person, organisation=organisation
        )

    def get_application(ifc: ifcopenshell.file) -> ifcopenshell.entity_instance | None:
        existing = next(iter(ifc.by_type("IfcApplication")), None)
        if existing:
            return existing
        organisation = next(iter(ifc.by_type("IfcOrganization")), None)
        if organisation is None:
            organisation = add_organisation(
                ifc, identification="pragmaticBIM", name="pragmaticBIM"
            )
        return add_application(
            ifc,
            application_developer=organisation,
            version="0.1.0",
            application_full_name="Catalog IFC Pipeline",
            application_identifier="catalog-ifc-pipeline",
        )

    owner_settings.get_user = get_user
    owner_settings.get_application = get_application


def create_project_shell(
    name: str = "Catalog Element",
    *,
    storey_name: str = "Level 0",
    version: str = "IFC4",
) -> tuple[
    ifcopenshell.file,
    ifcopenshell.entity_instance,
    ifcopenshell.entity_instance,
    ifcopenshell.entity_instance,
    ifcopenshell.entity_instance,
    ifcopenshell.entity_instance,
]:
    """Create a minimal valid Project → Site → Building → Storey hierarchy.

    Returns ``(file, project, site, building, storey, body_context)``.
    SI length units and Model/Body geometric contexts are assigned.
    """
    ifc_file, project, site, building, storeys, body_context = create_multi_storey_shell(
        name,
        storey_names=(storey_name,),
        storey_elevations=(0.0,),
        version=version,
    )
    return ifc_file, project, site, building, storeys[0], body_context


def create_multi_storey_shell(
    name: str = "Catalog Element",
    *,
    storey_names: tuple[str, ...] = ("EG", "1.OG", "2.OG"),
    storey_elevations: tuple[float, ...] | None = None,
    version: str = "IFC4",
) -> tuple[
    ifcopenshell.file,
    ifcopenshell.entity_instance,
    ifcopenshell.entity_instance,
    ifcopenshell.entity_instance,
    list[ifcopenshell.entity_instance],
    ifcopenshell.entity_instance,
]:
    """Create Project → Site → Building → N Storeys.

    Returns ``(file, project, site, building, storeys, body_context)``.
    """
    if not storey_names:
        raise ValueError("storey_names must not be empty")
    elevations = storey_elevations
    if elevations is None:
        elevations = tuple(float(i) * 3.0 for i in range(len(storey_names)))
    if len(elevations) != len(storey_names):
        raise ValueError("storey_names and storey_elevations must have the same length")

    _ensure_owner_history_factories()
    ifc_file = create_file(version=version)
    project = create_entity(ifc_file, ifc_class="IfcProject", name=name)
    length = add_si_unit(ifc_file, unit_type="LENGTHUNIT")
    area = add_si_unit(ifc_file, unit_type="AREAUNIT")
    volume = add_si_unit(ifc_file, unit_type="VOLUMEUNIT")
    assign_unit(ifc_file, units=[length, area, volume])

    model_context = add_context(ifc_file, context_type="Model")
    body_context = add_context(
        ifc_file,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=model_context,
    )

    site = create_entity(ifc_file, ifc_class="IfcSite", name="Site")
    building = create_entity(ifc_file, ifc_class="IfcBuilding", name="Building")
    assign_object(ifc_file, relating_object=project, products=[site])
    assign_object(ifc_file, relating_object=site, products=[building])
    edit_object_placement(ifc_file, product=site)
    edit_object_placement(ifc_file, product=building)

    storeys: list[ifcopenshell.entity_instance] = []
    for storey_name, elevation in zip(storey_names, elevations):
        storey = create_entity(
            ifc_file, ifc_class="IfcBuildingStorey", name=storey_name
        )
        if hasattr(storey, "Elevation"):
            storey.Elevation = float(elevation)
        assign_object(ifc_file, relating_object=building, products=[storey])
        edit_object_placement(
            ifc_file,
            product=storey,
            matrix=translation_matrix(z=float(elevation)),
        )
        storeys.append(storey)

    return ifc_file, project, site, building, storeys, body_context


def place_product(
    ifc_file: ifcopenshell.file,
    product: ifcopenshell.entity_instance,
) -> ifcopenshell.entity_instance:
    """Assign a default local object placement to ``product``."""
    return edit_object_placement(ifc_file, product=product)


def assign_pset(
    ifc_file: ifcopenshell.file,
    product: ifcopenshell.entity_instance,
    pset_name: str,
    properties: dict[str, Any],
    *,
    datatypes: dict[str, str] | None = None,
) -> ifcopenshell.entity_instance | None:
    """Create/edit an IfcPropertySet on ``product``. Skips empty property dicts.

    ``datatypes`` maps property name → IFC datatype (e.g. IfcIdentifier) so
    values match the Elementplan / IFC definitions instead of defaulting to IfcLabel.
    """
    if not properties:
        return None
    pset_product = product
    if pset_name == "Pset_ManufacturerTypeInformation" and not product.is_a(
        "IfcTypeObject"
    ):
        pset_product = get_type(product)
        if pset_product is None:
            applicable_types = get_applicable_types(product.is_a(), ifc_file.schema)
            if not applicable_types:
                raise ValueError(
                    f"{product.is_a()} has no applicable IFC type for {pset_name}"
                )
            pset_product = create_entity(
                ifc_file,
                ifc_class=applicable_types[0],
                name=f"{product.Name or product.is_a()} Type",
            )
            assign_type(
                ifc_file,
                related_objects=[product],
                relating_type=pset_product,
            )
    typed: dict[str, Any] = {}
    for key, value in properties.items():
        datatype = (datatypes or {}).get(key)
        typed[key] = _typed_ifc_value(ifc_file, value, datatype) if datatype else value
    pset = add_pset(ifc_file, product=pset_product, name=pset_name)
    edit_pset(ifc_file, pset=pset, properties=typed)
    return pset


def _typed_ifc_value(
    ifc_file: ifcopenshell.file, value: Any, datatype: str
) -> Any:
    """Wrap a Python value in the given IFC simple type entity."""
    dt = datatype.strip()
    if dt == "IfcBoolean":
        return ifc_file.create_entity("IfcBoolean", bool(value))
    if dt == "IfcInteger":
        return ifc_file.create_entity("IfcInteger", int(value))
    if dt == "IfcReal":
        return ifc_file.create_entity("IfcReal", float(value))
    if dt == "IfcIdentifier":
        return ifc_file.create_entity("IfcIdentifier", str(value))
    if dt == "IfcText":
        return ifc_file.create_entity("IfcText", str(value))
    if dt == "IfcLabel":
        return ifc_file.create_entity("IfcLabel", str(value))
    # Length/area/etc. as property single values still use measure types
    if dt in {
        "IfcLengthMeasure",
        "IfcAreaMeasure",
        "IfcVolumeMeasure",
        "IfcPositiveLengthMeasure",
        "IfcThermalTransmittanceMeasure",
    }:
        return ifc_file.create_entity(dt, float(value))
    return value


def assign_qto(
    ifc_file: ifcopenshell.file,
    product: ifcopenshell.entity_instance,
    qto_name: str,
    quantities: dict[str, Any],
) -> ifcopenshell.entity_instance | None:
    """Create/edit an IfcElementQuantity on ``product``. Skips empty quantity dicts."""
    if not quantities:
        return None
    qto = add_qto(ifc_file, product=product, name=qto_name)
    edit_qto(ifc_file, qto=qto, properties=quantities)
    return qto


def get_body_context(ifc_file: ifcopenshell.file) -> ifcopenshell.entity_instance:
    """Return the Model/Body/MODEL_VIEW context, creating it if missing."""
    for context in ifc_file.by_type("IfcGeometricRepresentationSubContext"):
        if (
            context.ContextType == "Model"
            and context.ContextIdentifier == "Body"
            and context.TargetView == "MODEL_VIEW"
        ):
            return context

    model_context = None
    for context in ifc_file.by_type("IfcGeometricRepresentationContext"):
        if context.ContextType == "Model" and not context.is_a(
            "IfcGeometricRepresentationSubContext"
        ):
            model_context = context
            break
    if model_context is None:
        model_context = add_context(ifc_file, context_type="Model")
    return add_context(
        ifc_file,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=model_context,
    )
