"""IfcBuildingElementProxy Wenderadius — Lastzug Fahrkurve swept path."""

from __future__ import annotations

import math
from typing import Any, Sequence

import ifcopenshell
from shapely.geometry import Polygon
from shapely.ops import unary_union

from generators.base import assign_pset, assign_qto, create_project_shell, get_body_context
from generators.covering import add_covering
from generators.parts import add_extruded_product, rect_polyline
from generators.slab import add_slab
from generators.space import FLOOR_COVERING_THICKNESS, FLOOR_SLAB_THICKNESS

# Metres — NZ / CH traffic-study Lastzug proportions (schematic Fahrkurve).
DEFAULT_CUBE_SIZE = 4.0
DEFAULT_STREET_CLEARANCE = 1.8
DEFAULT_STREET_WIDTH = 3.5
DEFAULT_APPROACH = 5.0
DEFAULT_PROXY_HEIGHT = 4.0
DEFAULT_PROXY_OUTER = 12.5  # front outer tracking radius
DEFAULT_VEHICLE_WIDTH = 2.55
# Schematic Fahrkurve length (tip on outer arc → rear on inner cut-in).
DEFAULT_VEHICLE_LENGTH = 9.5
DEFAULT_NOSE_LENGTH = 1.6  # cab tip (home-plate point)
DEFAULT_PROXY_INNER_MID = 5.0  # deepest trailer cut-in mid-turn
DEFAULT_TURN_ANGLE_DEG = 135.0  # matches typical Fahrkurve fan
DEFAULT_POSE_COUNT = 72  # dense sampling approximates a continuous swept path
DEFAULT_ENVELOPE_SIMPLIFY = 0.20  # remove dense pose facets without changing area
DEFAULT_ARC_SEGMENTS = 32  # street curb only
DEFAULT_SLAB_PADDING = 0.50
DEFAULT_CORNER_HEIGHT = 2.80

# Inner radius (m) vs turn progress 0…1 — trailer off-tracking.
_INNER_RADIUS_PROFILE: tuple[tuple[float, float], ...] = (
    (0.00, 10.0),
    (0.25, 7.0),
    (0.40, 5.5),
    (0.55, 5.0),
    (0.75, 5.3),
    (1.00, 6.5),
)

_ENTITY_FIELD_MAP = ("Name", "LongName", "Description", "PredefinedType", "ObjectType", "Phase")


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


def _lerp_profile(t: float, profile: Sequence[tuple[float, float]]) -> float:
    if t <= profile[0][0]:
        return float(profile[0][1])
    if t >= profile[-1][0]:
        return float(profile[-1][1])
    for (a0, v0), (a1, v1) in zip(profile, profile[1:]):
        if a0 <= t <= a1:
            if a1 == a0:
                return float(v1)
            u = (t - a0) / (a1 - a0)
            return float(v0 + u * (v1 - v0))
    return float(profile[-1][1])


def _scaled_inner_profile(
    *,
    outer_radius: float,
    vehicle_width: float,
    inner_mid: float,
) -> tuple[tuple[float, float], ...]:
    """Scale the reference cut-in profile to configured outer / mid radii."""
    ref_entry = 10.0
    ref_mid = 5.0
    entry = outer_radius - vehicle_width
    scale_cut = (entry - inner_mid) / (ref_entry - ref_mid) if ref_entry != ref_mid else 1.0
    scaled: list[tuple[float, float]] = []
    for t, r_ref in _INNER_RADIUS_PROFILE:
        cut_ref = ref_entry - r_ref
        scaled.append((t, entry - cut_ref * scale_cut))
    return tuple(scaled)


def _arc_points(
    radius: float,
    angle0: float,
    angle1: float,
    segments: int,
) -> list[tuple[float, float]]:
    if segments < 4:
        raise ValueError("arc needs at least 4 segments")
    return [
        (
            radius * math.cos(angle0 + (angle1 - angle0) * i / segments),
            radius * math.sin(angle0 + (angle1 - angle0) * i / segments),
        )
        for i in range(segments + 1)
    ]


def _street_polyline(
    outer_radius: float,
    inner_radius: float,
    approach: float,
    turn_angle: float,
    segments: int,
) -> list[tuple[float, float]]:
    """Curved street with straight approaches along the turn start/end."""
    outer_arc = _arc_points(outer_radius, 0.0, turn_angle, segments)
    inner_arc = _arc_points(inner_radius, turn_angle, 0.0, segments)
    end_c = math.cos(turn_angle)
    end_s = math.sin(turn_angle)
    # Exit approach continues tangent past the arc end.
    exit_dx = -end_s
    exit_dy = end_c
    return [
        (outer_radius, -approach),
        *outer_arc,
        (
            outer_radius * end_c + exit_dx * approach,
            outer_radius * end_s + exit_dy * approach,
        ),
        (
            inner_radius * end_c + exit_dx * approach,
            inner_radius * end_s + exit_dy * approach,
        ),
        *inner_arc,
        (inner_radius, -approach),
    ]


def _home_plate_local(
    length: float,
    width: float,
    nose: float,
) -> list[tuple[float, float]]:
    """Lastzug outline in local XY: +X forward, origin at geometric mid.

    Rear flat, pointed cab tip — same silhouette as 2D Fahrkurve frames.
    """
    if nose >= length * 0.45:
        raise ValueError("nose_length must be well below half the vehicle length")
    half_w = width * 0.5
    half_l = length * 0.5
    shoulder = half_l - nose
    return [
        (-half_l, -half_w),
        (-half_l, half_w),
        (shoulder, half_w),
        (half_l, 0.0),
        (shoulder, -half_w),
    ]


def _transform_polygon(
    local: Sequence[tuple[float, float]],
    *,
    origin: tuple[float, float],
    heading: float,
) -> list[tuple[float, float]]:
    c = math.cos(heading)
    s = math.sin(heading)
    ox, oy = origin
    return [
        (ox + x * c - y * s, oy + x * s + y * c)
        for x, y in local
    ]


def _vehicle_poses(
    *,
    outer_radius: float,
    vehicle_width: float,
    vehicle_length: float,
    nose_length: float,
    inner_mid: float,
    approach: float,
    turn_angle: float,
    pose_count: int,
) -> list[list[tuple[float, float]]]:
    """Discrete Lastzug footprints through approach + turn (Fahrkurve frames).

    Cab tip sits on the outer tracking arc; rear sits on the trailer cut-in
    radius. Angular lag from the law of cosines keeps body length stable so
    each frame reads like a 2D Schleppkurve outline.
    """
    if pose_count < 4:
        raise ValueError("pose_count must be at least 4")
    inner_profile = _scaled_inner_profile(
        outer_radius=outer_radius,
        vehicle_width=vehicle_width,
        inner_mid=inner_mid,
    )
    local = _home_plate_local(vehicle_length, vehicle_width, nose_length)
    half_l = vehicle_length * 0.5
    poses: list[list[tuple[float, float]]] = []

    def _beta(r_out: float, r_in: float) -> float:
        """Angular lag between tip (outer) and rear (inner) for fixed length."""
        denom = 2.0 * r_out * r_in
        if denom <= 1e-9:
            return 0.0
        cos_b = (r_out * r_out + r_in * r_in - vehicle_length * vehicle_length) / denom
        cos_b = max(-1.0, min(1.0, cos_b))
        return math.acos(cos_b)

    def _pose_at(alpha_tip: float, r_in: float) -> list[tuple[float, float]]:
        r_out = outer_radius
        beta = _beta(r_out, r_in)
        tip = (r_out * math.cos(alpha_tip), r_out * math.sin(alpha_tip))
        alpha_rear = alpha_tip - beta
        rear = (r_in * math.cos(alpha_rear), r_in * math.sin(alpha_rear))
        heading = math.atan2(tip[1] - rear[1], tip[0] - rear[0])
        # Local origin is geometric mid; tip is at +half_l along heading.
        mid = (
            tip[0] - math.cos(heading) * half_l,
            tip[1] - math.sin(heading) * half_l,
        )
        return _transform_polygon(local, origin=mid, heading=heading)

    # Straight lead-in (heading +Y) before the arc — diagram start frame.
    r_in0 = _lerp_profile(0.0, inner_profile)
    r_mid = 0.5 * (outer_radius + r_in0)
    poses.append(
        _transform_polygon(
            local,
            origin=(r_mid, -approach * 0.65),
            heading=math.pi / 2.0,
        )
    )

    n_arc = pose_count - 1
    for i in range(n_arc):
        t = i / (n_arc - 1) if n_arc > 1 else 0.0
        alpha_tip = turn_angle * t
        r_in = _lerp_profile(t, inner_profile)
        # Keep tip↔rear distance feasible for law of cosines.
        max_span = outer_radius + r_in - 0.05
        min_span = abs(outer_radius - r_in) + 0.05
        if not (min_span < vehicle_length < max_span):
            # Fallback: tangent placement on mid-track.
            r_c = 0.5 * (outer_radius + r_in)
            heading = alpha_tip + math.pi / 2.0
            mid = (r_c * math.cos(alpha_tip), r_c * math.sin(alpha_tip))
            poses.append(_transform_polygon(local, origin=mid, heading=heading))
        else:
            poses.append(_pose_at(alpha_tip, r_in))

    return poses


def _union_polyline(
    poses: Sequence[Sequence[tuple[float, float]]],
    *,
    simplify_tolerance: float = DEFAULT_ENVELOPE_SIMPLIFY,
) -> list[tuple[float, float]]:
    """Outer ring of a dense pose union, simplified into a smooth swept envelope."""
    if simplify_tolerance < 0:
        raise ValueError("simplify_tolerance must be non-negative")
    polys = [Polygon(p) for p in poses]
    for poly in polys:
        if not poly.is_valid or poly.is_empty:
            raise ValueError("invalid vehicle pose polygon")
    merged = unary_union(polys)
    if merged.is_empty:
        raise ValueError("empty swept-path union")
    if merged.geom_type == "MultiPolygon":
        merged = max(merged.geoms, key=lambda g: g.area)
    if simplify_tolerance:
        merged = merged.simplify(simplify_tolerance, preserve_topology=True)
    if merged.geom_type != "Polygon" or not merged.is_valid or merged.is_empty:
        raise ValueError("invalid swept-path envelope")
    coords = list(merged.exterior.coords)
    # Drop duplicate closing vertex for IfcArbitraryClosedProfileDef helper.
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    return [(float(x), float(y)) for x, y in coords]


def generate_turning_radius(
    params: dict[str, Any] | None = None,
) -> tuple[ifcopenshell.file, ifcopenshell.entity_instance]:
    """Build a curved street clear of a cube; Lastzug Fahrkurve proxy hits it.

    Densely sampled home-plate poses define a continuous Fahrkurve; their
    simplified outer union is extruded as one proxy volume.

    ``params`` keys:
    - ``cube_size`` / ``street_clearance`` / ``street_width`` / ``approach``
    - ``proxy_outer`` / ``vehicle_width`` / ``vehicle_length`` / ``nose_length``
    - ``proxy_inner_mid`` / ``turn_angle_deg`` / ``pose_count``
    - ``envelope_simplify``
    - ``proxy_height`` / ``arc_segments`` / ``slab_padding`` / ``corner_height``
    - ``name`` / ``predefined_type`` / ``object_type``
    - ``properties`` / ``property_datatypes`` / ``quantities``

    Returns ``(ifc_file, turning_radius_proxy)``.
    """
    params = dict(params or {})

    cube = float(params.get("cube_size", DEFAULT_CUBE_SIZE))
    clearance = float(params.get("street_clearance", DEFAULT_STREET_CLEARANCE))
    street_w = float(params.get("street_width", DEFAULT_STREET_WIDTH))
    approach = float(params.get("approach", DEFAULT_APPROACH))
    proxy_h = float(params.get("proxy_height", DEFAULT_PROXY_HEIGHT))
    proxy_out = float(params.get("proxy_outer", DEFAULT_PROXY_OUTER))
    vehicle_w = float(params.get("vehicle_width", DEFAULT_VEHICLE_WIDTH))
    vehicle_l = float(params.get("vehicle_length", DEFAULT_VEHICLE_LENGTH))
    nose = float(params.get("nose_length", DEFAULT_NOSE_LENGTH))
    proxy_in_mid = float(params.get("proxy_inner_mid", DEFAULT_PROXY_INNER_MID))
    turn_deg = float(params.get("turn_angle_deg", DEFAULT_TURN_ANGLE_DEG))
    pose_count = int(params.get("pose_count", DEFAULT_POSE_COUNT))
    envelope_simplify = float(
        params.get("envelope_simplify", DEFAULT_ENVELOPE_SIMPLIFY)
    )
    segments = int(params.get("arc_segments", DEFAULT_ARC_SEGMENTS))
    pad = float(params.get("slab_padding", DEFAULT_SLAB_PADDING))
    slab_t = float(params.get("slab_thickness", FLOOR_SLAB_THICKNESS))
    cover_t = float(params.get("covering_thickness", FLOOR_COVERING_THICKNESS))
    corner_h = float(params.get("corner_height", DEFAULT_CORNER_HEIGHT))
    turn_angle = math.radians(turn_deg)

    street_inner = cube + clearance
    street_outer = street_inner + street_w
    proxy_in_entry = proxy_out - vehicle_w

    if min(cube, clearance, street_w, approach, proxy_h, proxy_out, vehicle_w, vehicle_l, corner_h) <= 0:
        raise ValueError("all turning-radius vignette dimensions must be positive")
    if nose <= 0 or nose >= vehicle_l * 0.45:
        raise ValueError("nose_length must be positive and well below vehicle_length")
    if vehicle_w >= proxy_out:
        raise ValueError("vehicle_width must be smaller than proxy_outer")
    if proxy_in_mid <= 0 or proxy_in_mid >= proxy_in_entry:
        raise ValueError("proxy_inner_mid must be positive and tighter than entry inner")
    if not (45.0 <= turn_deg <= 180.0):
        raise ValueError("turn_angle_deg must be between 45 and 180")
    if street_outer >= proxy_out:
        raise ValueError("street outer curb must stay inside the outer tracking radius")
    if pad < 0:
        raise ValueError("slab_padding must be non-negative")
    if envelope_simplify < 0:
        raise ValueError("envelope_simplify must be non-negative")

    name = params.get("name") or "WR-01"
    predefined_type = params.get("predefined_type") or "USERDEFINED"
    object_type = params.get("object_type") or params.get("ObjectType") or "Wenderadius"

    poses = _vehicle_poses(
        outer_radius=proxy_out,
        vehicle_width=vehicle_w,
        vehicle_length=vehicle_l,
        nose_length=nose,
        inner_mid=proxy_in_mid,
        approach=approach,
        turn_angle=turn_angle,
        pose_count=pose_count,
    )
    envelope = _union_polyline(
        poses,
        simplify_tolerance=envelope_simplify,
    )
    proxy_area = float(Polygon(envelope).area)

    street_poly = _street_polyline(
        street_outer, street_inner, approach, turn_angle, segments
    )

    xs = [p[0] for p in envelope] + [p[0] for p in street_poly] + [0.0, cube]
    ys = [p[1] for p in envelope] + [p[1] for p in street_poly] + [0.0, cube]
    slab_poly = rect_polyline(
        min(xs) - pad,
        min(ys) - pad,
        max(xs) + pad,
        max(ys) + pad,
    )

    ifc_file, _project, _site, _building, storey, body_context = create_project_shell(
        params.get("project_name") or name,
        storey_name="EG",
    )
    body_context = get_body_context(ifc_file) or body_context

    z_cover = 0.0
    z_slab = z_cover - slab_t

    add_slab(
        ifc_file,
        name="Strasse-Bodenplatte",
        body_context=body_context,
        storey=storey,
        polyline=slab_poly,
        thickness=slab_t,
        z_bottom=z_slab,
        predefined_type="FLOOR",
    )
    add_covering(
        ifc_file,
        name="Fahrbahn",
        body_context=body_context,
        storey=storey,
        polyline=street_poly,
        thickness=cover_t,
        z_bottom=z_cover,
        predefined_type="FLOORING",
    )

    corner = add_extruded_product(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name="Gebaeudeecke",
        body_context=body_context,
        storey=storey,
        polyline=rect_polyline(0.0, 0.0, cube, cube),
        thickness=corner_h,
        z_bottom=z_cover + cover_t,
        predefined_type="USERDEFINED",
    )
    corner.ObjectType = "Kontext"

    proxy = add_extruded_product(
        ifc_file,
        ifc_class="IfcBuildingElementProxy",
        name=name,
        body_context=body_context,
        storey=storey,
        polyline=envelope,
        thickness=proxy_h,
        z_bottom=z_cover + cover_t,
        predefined_type=predefined_type,
    )

    volumes = dict(params.get("quantities") or {})
    qto = dict(volumes.get("Qto_BuildingElementProxyBaseQuantities") or {})
    qto["GrossVolume"] = round(proxy_area * proxy_h, 3)
    volumes["Qto_BuildingElementProxyBaseQuantities"] = qto

    resolved = {
        "Name": name,
        "PredefinedType": predefined_type,
        "ObjectType": object_type,
        "Description": "LKW-Schleppkurve / Wenderadius als Proxy-Volumen",
        "properties": params.get("properties") or {},
        "property_datatypes": params.get("property_datatypes") or {},
        "quantities": volumes,
    }
    _apply_resolved_attributes(ifc_file, proxy, resolved)

    return ifc_file, proxy
