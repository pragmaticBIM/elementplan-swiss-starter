"""Building-law parcel proxy volumes intersecting a schematic terrain surface."""

from __future__ import annotations

from typing import Any, Sequence

import ifcopenshell
from ifcopenshell.api.geometry import assign_representation, edit_object_placement
from ifcopenshell.api.root import create_entity
from ifcopenshell.api.spatial import assign_container

from generators.base import assign_pset, assign_qto, create_project_shell, get_body_context
from generators.parts import (
    create_brep_body_representation,
    create_body_representation,
    create_extruded_area_solid,
    create_faceted_brep,
    rect_polyline,
    translation_matrix,
)

# Metres — three cadastral parcel volumes extending from -10 m to +10 m
DEFAULT_PARCEL_BOTTOM = -10.0
DEFAULT_PARCEL_TOP = 10.0
DEFAULT_PARCEL_HEIGHT = DEFAULT_PARCEL_TOP - DEFAULT_PARCEL_BOTTOM
DEFAULT_PLOT_THICKNESS = 0.30
DEFAULT_PARCEL_DEPTH = 30.0
DEFAULT_PARCEL_A_WIDTH = 15.0
DEFAULT_PARCEL_B_WIDTH = 15.0
DEFAULT_PARCEL_C_WIDTH = 15.0
DEFAULT_SURFACE_MARGIN = 5.0

_ENTITY_FIELD_MAP = ("Name", "LongName", "Description", "PredefinedType", "ObjectType", "Phase")

# Default catalog Names = sample cadastral numbers
_DEFAULT_PARCEL_NAMES: tuple[str, ...] = ("1234", "1235", "1236")


def _apply_resolved_attributes(
    ifc_file: ifcopenshell.file,
    product: ifcopenshell.entity_instance,
    resolved: dict[str, Any] | None,
) -> None:
    if not resolved:
        return
    for field in _ENTITY_FIELD_MAP:
        if field in resolved and hasattr(product, field):
            setattr(product, field, resolved[field])
    property_datatypes = resolved.get("property_datatypes") or {}
    for pset_name, props in (resolved.get("properties") or {}).items():
        assign_pset(
            ifc_file,
            product,
            pset_name,
            props,
            datatypes=property_datatypes.get(pset_name),
        )
    for qto_name, quantities in (resolved.get("quantities") or {}).items():
        assign_qto(ifc_file, product, qto_name, quantities)


def _shoelace_area(polyline: Sequence[Sequence[float]]) -> float:
    pts = [(float(p[0]), float(p[1])) for p in polyline]
    if pts[0] != pts[-1]:
        pts = pts + [pts[0]]
    area = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        area += x0 * y1 - x1 * y0
    return abs(area) * 0.5


def _add_extruded_on_site(
    ifc_file: ifcopenshell.file,
    *,
    ifc_class: str,
    name: str,
    body_context: ifcopenshell.entity_instance,
    site: ifcopenshell.entity_instance,
    polyline: Sequence[Sequence[float]],
    thickness: float,
    z_bottom: float = 0.0,
    predefined_type: str | None = None,
) -> ifcopenshell.entity_instance:
    """Create a site-contained product with a horizontal extruded Body."""
    product = create_entity(
        ifc_file,
        ifc_class=ifc_class,
        name=name,
        predefined_type=predefined_type,
    )
    assign_container(ifc_file, relating_structure=site, products=[product])
    edit_object_placement(
        ifc_file,
        product=product,
        matrix=translation_matrix(z=z_bottom),
    )
    solid = create_extruded_area_solid(
        ifc_file,
        [(float(p[0]), float(p[1])) for p in polyline],
        float(thickness),
    )
    representation = create_body_representation(ifc_file, body_context, solid)
    assign_representation(ifc_file, product=product, representation=representation)
    return product


def _add_terrain_surface(
    ifc_file: ifcopenshell.file,
    *,
    body_context: ifcopenshell.entity_instance,
    site: ifcopenshell.entity_instance,
    width: float,
    depth: float,
    thickness: float,
) -> None:
    """Give the site a shallow, triangulated terrain plate."""
    xs = (0.0, width * 0.25, width * 0.5, width * 0.75, width)
    ys = (0.0, depth / 3.0, depth * 2.0 / 3.0, depth)
    heights = (
        (0.00, 0.35, 0.90, 1.45, 1.85),
        (-0.35, 0.25, 1.15, 2.15, 2.75),
        (-0.60, -0.05, 0.90, 1.90, 2.50),
        (-0.25, 0.20, 0.70, 1.25, 1.65),
    )
    vertices: list[tuple[float, float, float]] = []
    for row, y in enumerate(ys):
        for col, x in enumerate(xs):
            vertices.append((x, y, heights[row][col]))
    vertices.extend(
        (x, y, heights[row][col] - thickness)
        for row, y in enumerate(ys)
        for col, x in enumerate(xs)
    )

    cols = len(xs)
    rows = len(ys)
    top_count = cols * rows
    faces: list[tuple[int, ...]] = []
    for row in range(rows - 1):
        for col in range(cols - 1):
            a = row * cols + col
            b = a + 1
            d = (row + 1) * cols + col
            c = d + 1
            faces.extend(((a, b, c), (a, c, d)))
            faces.extend(
                (
                    (a + top_count, c + top_count, b + top_count),
                    (a + top_count, d + top_count, c + top_count),
                )
            )
    for edge in (
        tuple(range(cols)),
        tuple(row * cols + cols - 1 for row in range(rows)),
        tuple((rows - 1) * cols + col for col in reversed(range(cols))),
        tuple(row * cols for row in reversed(range(rows))),
    ):
        for a, b in zip(edge, edge[1:]):
            faces.append((a, a + top_count, b + top_count, b))

    terrain = create_faceted_brep(ifc_file, vertices, faces)
    representation = create_brep_body_representation(ifc_file, body_context, terrain)
    assign_representation(ifc_file, product=site, representation=representation)


def generate_building_law_parcel(
    params: dict[str, Any],
) -> tuple[ifcopenshell.file, list[ifcopenshell.entity_instance]]:
    """Build three adjoining parcel proxies through a terrain surface.

    ``params`` keys:
    - ``parcel_bottom`` / ``parcel_top`` / ``parcel_depth``
    - ``parcel_a_width`` / ``parcel_b_width`` / ``parcel_c_width``
    - ``surface_margin``: terrain visible around the parcel group
    - ``parcel_names``: sequence of Name tokens (cadastral numbers)
    - ``name`` / ``predefined_type`` / ``object_type`` (defaults for all parcels)
    - ``properties`` / ``property_datatypes`` / ``quantities``
    - ``parcel_attrs``: optional per-parcel resolved attribute dicts

    Returns ``(ifc_file, parcel_proxies)``.
    """
    parcel_bottom = float(params.get("parcel_bottom", DEFAULT_PARCEL_BOTTOM))
    parcel_top = float(params.get("parcel_top", DEFAULT_PARCEL_TOP))
    parcel_h = parcel_top - parcel_bottom
    parcel_d = float(params.get("parcel_depth", DEFAULT_PARCEL_DEPTH))
    width_a = float(params.get("parcel_a_width", DEFAULT_PARCEL_A_WIDTH))
    width_b = float(params.get("parcel_b_width", DEFAULT_PARCEL_B_WIDTH))
    width_c = float(params.get("parcel_c_width", DEFAULT_PARCEL_C_WIDTH))
    surface_margin = float(params.get("surface_margin", DEFAULT_SURFACE_MARGIN))
    plot_t = float(params.get("plot_thickness", DEFAULT_PLOT_THICKNESS))
    if parcel_h <= 0 or parcel_d <= 0 or min(width_a, width_b, width_c) <= 0:
        raise ValueError("parcel dimensions must be positive")
    if surface_margin <= 0:
        raise ValueError("surface_margin must be positive")

    parcel_w = width_a + width_b + width_c
    surface_w = parcel_w + surface_margin * 2.0
    surface_d = parcel_d + surface_margin * 2.0
    project_name = params.get("project_name") or "Baurechtliche Parzellen"
    ifc_file, _project, site, _building, storey, body_context = create_project_shell(
        project_name
    )
    # Storey kept for hierarchy; parcels and plot live on the site.
    _ = storey
    body_context = get_body_context(ifc_file) or body_context

    edit_object_placement(
        ifc_file,
        product=site,
        matrix=translation_matrix(),
    )
    _add_terrain_surface(
        ifc_file,
        body_context=body_context,
        site=site,
        width=surface_w,
        depth=surface_d,
        thickness=plot_t,
    )

    x0 = surface_margin
    x_ab = x0 + width_a
    x_bc = x_ab + width_b
    x3 = x_bc + width_c
    y0 = surface_margin
    y3 = y0 + parcel_d

    # Shared boundaries change direction; outer boundaries are also skewed so
    # none of the three cadastral footprints reads as a parallel-sided strip.
    boundary_ab = (
        (x_ab, y0),
        (x_ab - 1.8, y0 + parcel_d * 0.34),
        (x_ab + 1.2, y0 + parcel_d * 0.67),
        (x_ab + 0.8, y3),
    )
    boundary_bc = (
        (x_bc, y0 + 1.8),
        (x_bc - 1.1, y0 + parcel_d * 0.31),
        (x_bc + 1.6, y0 + parcel_d * 0.71),
        (x_bc - 1.0, y3 - 1.5),
    )
    parcel_a_poly = [
        (x0, y0 + 2.2),
        *boundary_ab,
        (x0 + 2.0, y3 - 1.7),
    ]
    parcel_b_poly = [
        boundary_ab[0],
        boundary_bc[0],
        *boundary_bc[1:],
        *reversed(boundary_ab[1:]),
    ]
    parcel_c_poly = [
        boundary_bc[0],
        (x3 - 0.8, y0 + 0.5),
        (x3 - 2.2, y3),
        *reversed(boundary_bc[1:]),
    ]

    names = list(params.get("parcel_names") or _DEFAULT_PARCEL_NAMES)
    if len(names) < 3:
        names = list(_DEFAULT_PARCEL_NAMES)
    polys = (parcel_a_poly, parcel_b_poly, parcel_c_poly)
    parcel_attrs_list = list(params.get("parcel_attrs") or [])
    object_type = params.get("object_type") or "Baurechtliche Parzelle"
    predefined_type = params.get("predefined_type") or "USERDEFINED"

    parcels: list[ifcopenshell.entity_instance] = []
    for index, (poly, name) in enumerate(zip(polys, names)):
        proxy = _add_extruded_on_site(
            ifc_file,
            ifc_class="IfcBuildingElementProxy",
            name=str(name),
            body_context=body_context,
            site=site,
            polyline=poly,
            thickness=parcel_h,
            z_bottom=parcel_bottom,
            predefined_type=predefined_type,
        )
        proxy.ObjectType = object_type
        attrs = parcel_attrs_list[index] if index < len(parcel_attrs_list) else None
        if attrs:
            _apply_resolved_attributes(ifc_file, proxy, attrs)
        else:
            # Shared YAML defaults without overwriting the per-parcel Name
            shared = {
                "PredefinedType": predefined_type,
                "ObjectType": object_type,
                "properties": params.get("properties") or {},
                "property_datatypes": params.get("property_datatypes") or {},
                "quantities": {},
            }
            area = _shoelace_area(poly)
            shared["quantities"] = {
                "Qto_BuildingElementProxyBaseQuantities": {
                    "GrossVolume": round(area * parcel_h, 3),
                }
            }
            _apply_resolved_attributes(ifc_file, proxy, shared)
            proxy.Name = str(name)
        parcels.append(proxy)

    return ifc_file, parcels
