"""Headless isometric PNG render from an IFC file (element-type agnostic)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Collection, Mapping, Sequence

# Prefer EGL for CI/Docker headless; set before PyOpenGL/pyrender import.
os.environ.setdefault("PYOPENGL_PLATFORM", "egl")

import ifcopenshell
import ifcopenshell.geom
import numpy as np
import pyrender
import trimesh
from PIL import Image, ImageDraw, ImageFont

from render.print_raster import PRINT_DPI, PRINT_RESOLUTION, save_print_tiff


DEFAULT_RESOLUTION = (1024, 1024)
# Long lens. Orthographic cover tiles match this framing at the look-at plane.
_YFOV = np.pi / 5.0
# 1200² @ 600 DPI (~4.6 cm linework). Catalog cards stay 1024² RGB PNG.
_BG_COLOR = [0.93, 0.93, 0.93, 1.0]
_WATERMARK_TEXT = "pragmaticBIM.ch"

# Main catalog element accent; context stays white; edges black.
# Volumes (IfcSpace) use transparency; solid products use opaque accent.
_ACCENT_VOLUME = [1.0, 0.45, 0.1, 0.38]
_ACCENT_SOLID = [1.0, 0.45, 0.1, 1.0]
_CONTEXT_COLOR = [0.96, 0.96, 0.96, 1.0]
_CONTEXT_VOLUME = [0.92, 0.92, 0.92, 0.12]  # faint room volume when not the primary accent
_FLOORING_COLOR = [0.78, 0.68, 0.52, 1.0]  # warm beige so covering reads vs white slab
_WALL_COLOR = [1.0, 1.0, 1.0, 1.0]  # interior walls always fully opaque
_FRAME_COLOR = [1.0, 1.0, 1.0, 1.0]  # door/window frames
_GLASS_COLOR = [0.0, 0.0, 0.0, 1.0]  # glazing shown solid black in catalog PNGs
_EDGE_COLOR = [0.05, 0.05, 0.05, 1.0]
_DOTTED_EDGE_COLOR = [0.35, 0.35, 0.35, 1.0]
_THIN_EDGE_COLOR = [0.45, 0.45, 0.45, 1.0]

# IFC classes rendered as transparent volumes when they are the primary element
_VOLUME_CLASSES = frozenset({"IfcSpace", "IfcZone", "IfcOpeningElement"})
# Context MEP shown as dotted wireframe only (no solid faces)
_OUTLINE_ONLY_CLASSES = frozenset({"IfcDuctSegment", "IfcPipeSegment", "IfcCableCarrierSegment"})


def _tessellate_product(
    settings: ifcopenshell.geom.settings,
    product: ifcopenshell.entity_instance,
) -> trimesh.Trimesh | None:
    try:
        shape = ifcopenshell.geom.create_shape(settings, product)
    except Exception:
        return None
    verts = np.array(shape.geometry.verts, dtype=np.float64).reshape(-1, 3)
    faces = np.array(shape.geometry.faces, dtype=np.int64).reshape(-1, 3)
    if not len(verts) or not len(faces):
        return None
    return trimesh.Trimesh(vertices=verts, faces=faces, process=False)


def _product_meshes(
    ifc_file: ifcopenshell.file,
    *,
    primary_guids: Collection[str] | None = None,
    disable_opening_subtractions: bool | None = None,
) -> list[tuple[str, str, trimesh.Trimesh]]:
    """Tessellate each product; return ``(guid, ifc_class, mesh)`` triples.

    When the file has door/window fillings, opening voids are subtracted from
    hosts so frames can sit flush with the facade. Otherwise hosts keep a
    continuous Body (avoids unnecessary boolean work / edge noise).
    Pass ``disable_opening_subtractions`` explicitly to override.
    ``IfcOpeningElement`` is only drawn when it is the catalog accent.
    """
    if disable_opening_subtractions is None:
        has_fillings = bool(
            ifc_file.by_type("IfcDoor") or ifc_file.by_type("IfcWindow")
        )
        disable_opening_subtractions = not has_fillings
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    settings.set(settings.DISABLE_OPENING_SUBTRACTIONS, bool(disable_opening_subtractions))
    primary = set(primary_guids or ())

    opening_guids = {o.GlobalId for o in ifc_file.by_type("IfcOpeningElement")}
    guid_to_class: dict[str, str] = {}
    for product in ifc_file.by_type("IfcProduct"):
        guid_to_class[product.GlobalId] = product.is_a()

    results: list[tuple[str, str, trimesh.Trimesh]] = []
    iterator = ifcopenshell.geom.iterator(settings, ifc_file)
    if iterator.initialize():
        while True:
            shape = iterator.get()
            guid = shape.guid
            # Never draw void solids unless they are the catalog primary accent
            if guid in opening_guids and guid not in primary:
                if not iterator.next():
                    break
                continue
            ifc_class = guid_to_class.get(guid, "IfcProduct")
            geometry = shape.geometry
            verts = np.array(geometry.verts, dtype=np.float64).reshape(-1, 3)
            faces = np.array(geometry.faces, dtype=np.int64).reshape(-1, 3)
            if len(verts) and len(faces):
                results.append(
                    (
                        guid,
                        ifc_class,
                        trimesh.Trimesh(vertices=verts, faces=faces, process=False),
                    )
                )
            if not iterator.next():
                break

    if not results:
        for product in ifc_file.by_type("IfcProduct"):
            if product.is_a("IfcOpeningElement") and product.GlobalId not in primary:
                continue
            if not product.Representation:
                continue
            mesh = _tessellate_product(settings, product)
            if mesh is not None:
                results.append((product.GlobalId, product.is_a(), mesh))

    # Opening bodies when accented (architecture-opening-void catalog card)
    if primary:
        for opening in ifc_file.by_type("IfcOpeningElement"):
            if opening.GlobalId not in primary:
                continue
            if any(guid == opening.GlobalId for guid, _, _ in results):
                continue
            mesh = _tessellate_product(settings, opening)
            if mesh is not None:
                results.append((opening.GlobalId, "IfcOpeningElement", mesh))

    if not results:
        raise ValueError("IFC file has no tessellatable geometry")
    return results


def _primary_style(ifc_class: str) -> tuple[list[float], bool]:
    """Return ``(rgba, blend)`` for the main catalog element."""
    if ifc_class in _VOLUME_CLASSES:
        return list(_ACCENT_VOLUME), True
    return list(_ACCENT_SOLID), False


def _material(rgba: Sequence[float], *, blend: bool = False) -> pyrender.MetallicRoughnessMaterial:
    return pyrender.MetallicRoughnessMaterial(
        baseColorFactor=list(rgba),
        metallicFactor=0.0,
        roughnessFactor=1.0,
        alphaMode="BLEND" if blend else "OPAQUE",
    )


def _glass_material(rgba: Sequence[float]) -> pyrender.MetallicRoughnessMaterial:
    """Flat black glass — avoid lit grey shading that reads as hatching."""
    return pyrender.MetallicRoughnessMaterial(
        baseColorFactor=list(rgba),
        metallicFactor=0.0,
        roughnessFactor=1.0,
        emissiveFactor=[rgba[0], rgba[1], rgba[2]],
        alphaMode="OPAQUE",
    )


def _feature_edges(mesh: trimesh.Trimesh) -> np.ndarray:
    """Return ``(N, 2)`` vertex-index pairs for sharp feature edges."""
    edges, _normals = _feature_edges_with_outward(mesh)
    return edges


def _feature_edges_with_outward(
    mesh: trimesh.Trimesh,
) -> tuple[np.ndarray, np.ndarray]:
    """Sharp feature edges plus a unit outward bias direction per edge.

    Outward is the normalized sum of the two adjacent face normals — used to
    lift strokes off coplanar white tops so they are not depth-rejected.
    """
    if len(mesh.faces) == 0 or len(mesh.vertices) == 0:
        return (
            np.zeros((0, 2), dtype=np.int64),
            np.zeros((0, 3), dtype=np.float64),
        )
    try:
        adj_edges = np.asarray(mesh.face_adjacency_edges, dtype=np.int64)
        adj_angles = np.asarray(mesh.face_adjacency_angles, dtype=np.float64)
        adj_faces = np.asarray(mesh.face_adjacency, dtype=np.int64)
        mask = adj_angles > np.deg2rad(15.0)
        feature = adj_edges[mask]
        pairs = adj_faces[mask]
        face_normals = np.asarray(mesh.face_normals, dtype=np.float64)
        if len(feature) == 0:
            return (
                np.zeros((0, 2), dtype=np.int64),
                np.zeros((0, 3), dtype=np.float64),
            )
        outward = face_normals[pairs[:, 0]] + face_normals[pairs[:, 1]]
        norms = np.linalg.norm(outward, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-9)
        outward = outward / norms
        return feature, outward
    except Exception:
        feature = np.asarray(mesh.edges_unique, dtype=np.int64)
        return feature, np.zeros((len(feature), 3), dtype=np.float64)


def _view_radius_distance(bounds: np.ndarray, padding: float) -> tuple[float, float]:
    """AABB half-diagonal and the eye distance used by ``_isometric_camera_pose``."""
    extents = bounds[1] - bounds[0]
    radius = float(np.linalg.norm(extents)) * 0.5
    if radius < 1e-6:
        radius = 1.0
    return radius, radius * float(padding) * 2.5


def _stroke_world_half_width(
    bounds: np.ndarray,
    *,
    height_px: int,
    target_px: float = 2.0,
    world_height: float | None = None,
) -> float:
    """World-space half-width so strokes land near ``target_px`` after projection."""
    if world_height is None:
        # Match ``_isometric_camera_pose`` distance + PerspectiveCamera yfov.
        _radius, distance = _view_radius_distance(bounds, 1.6)
        world_height = 2.0 * distance * float(np.tan(_YFOV * 0.5))
    meters_per_px = world_height / max(float(height_px), 1.0)
    return max(0.5 * meters_per_px * target_px, 1e-4)


def _ribbon_from_segments(
    segments: Sequence[tuple[np.ndarray, np.ndarray]],
    *,
    eye: np.ndarray,
    half_width: float,
    toward_bias: float,
    rgba: Sequence[float],
    outward: Sequence[np.ndarray] | None = None,
    normal_bias: float = 0.0,
) -> pyrender.Mesh | None:
    """Build camera-facing ribbon triangles from open line segments."""
    eye = np.asarray(eye, dtype=np.float64).reshape(3)
    ribbon_positions: list[list[float]] = []
    ribbon_indices: list[int] = []
    for idx, (p0, p1) in enumerate(segments):
        p0 = np.asarray(p0, dtype=np.float64).reshape(3)
        p1 = np.asarray(p1, dtype=np.float64).reshape(3)
        along = p1 - p0
        length = float(np.linalg.norm(along))
        if length < 1e-9:
            continue
        along /= length
        mid = 0.5 * (p0 + p1)
        to_eye = eye - mid
        to_eye_norm = float(np.linalg.norm(to_eye))
        if to_eye_norm < 1e-9:
            continue
        view = to_eye / to_eye_norm
        side = np.cross(along, view)
        side_norm = float(np.linalg.norm(side))
        if side_norm < 1e-9:
            helper = np.array([0.0, 0.0, 1.0], dtype=np.float64)
            if abs(float(along @ helper)) > 0.9:
                helper = np.array([0.0, 1.0, 0.0], dtype=np.float64)
            side = np.cross(along, helper)
            side_norm = float(np.linalg.norm(side))
            if side_norm < 1e-9:
                continue
        side /= side_norm
        bias = view * toward_bias
        if outward is not None and idx < len(outward) and normal_bias:
            n = np.asarray(outward[idx], dtype=np.float64).reshape(3)
            n_norm = float(np.linalg.norm(n))
            if n_norm > 1e-9:
                bias = bias + (n / n_norm) * float(normal_bias)
        a = p0 + side * half_width + bias
        b = p0 - side * half_width + bias
        c = p1 - side * half_width + bias
        d = p1 + side * half_width + bias
        base = len(ribbon_positions)
        ribbon_positions.extend([a.tolist(), b.tolist(), c.tolist(), d.tolist()])
        ribbon_indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])

    if not ribbon_indices:
        return None

    primitive = pyrender.Primitive(
        positions=np.ascontiguousarray(ribbon_positions, dtype=np.float32),
        indices=np.ascontiguousarray(ribbon_indices, dtype=np.int32),
        mode=pyrender.GLTF.TRIANGLES,
        material=_material(rgba),
        color_0=None,
    )
    return pyrender.Mesh(primitives=[primitive])


def _edge_stroke_mesh(
    mesh: trimesh.Trimesh,
    *,
    eye: np.ndarray,
    half_width: float,
    toward_bias: float,
    normal_bias: float = 0.0,
    rgba: Sequence[float] | None = None,
) -> pyrender.Mesh | None:
    """Camera-facing ribbon strokes for sharp feature edges.

    GL_LINES sit on solid faces and z-fight away on white–white abutments.
    Thin ribbons biased toward the camera (and slightly along face normals)
    keep a continuous black seam.
    """
    feature, outward = _feature_edges_with_outward(mesh)
    if len(feature) == 0:
        return None
    verts = np.asarray(mesh.vertices, dtype=np.float64)
    segments = [(verts[int(i0)], verts[int(i1)]) for i0, i1 in feature]
    return _ribbon_from_segments(
        segments,
        eye=eye,
        half_width=half_width,
        toward_bias=toward_bias,
        rgba=list(rgba or _EDGE_COLOR),
        outward=list(outward),
        normal_bias=normal_bias,
    )


def _dotted_edge_mesh(
    mesh: trimesh.Trimesh,
    *,
    eye: np.ndarray,
    half_width: float,
    toward_bias: float,
    normal_bias: float = 0.0,
    dash: float = 0.06,
    gap: float = 0.05,
    rgba: Sequence[float] | None = None,
) -> pyrender.Mesh | None:
    """Dotted wireframe from sharp edges (short dashes with gaps; no faces)."""
    feature, outward = _feature_edges_with_outward(mesh)
    if len(feature) == 0:
        return None

    verts = np.asarray(mesh.vertices, dtype=np.float64)
    dash_segments: list[tuple[np.ndarray, np.ndarray]] = []
    dash_outward: list[np.ndarray] = []
    for (i0, i1), n in zip(feature, outward):
        p0 = verts[int(i0)]
        p1 = verts[int(i1)]
        length = float(np.linalg.norm(p1 - p0))
        if length < 1e-9:
            continue
        direction = (p1 - p0) / length
        t = 0.0
        while t < length - 1e-9:
            a = p0 + direction * t
            b = p0 + direction * min(t + dash, length)
            dash_segments.append((a, b))
            dash_outward.append(n)
            t += dash + gap

    return _ribbon_from_segments(
        dash_segments,
        eye=eye,
        half_width=half_width,
        toward_bias=toward_bias,
        rgba=list(rgba or _DOTTED_EDGE_COLOR),
        outward=dash_outward,
        normal_bias=normal_bias,
    )


def _bias_triangle_mesh_along_view(
    mesh: pyrender.Mesh,
    eye: np.ndarray,
    amount: float,
) -> pyrender.Mesh:
    """Clone triangle primitives with vertices shifted along (eye - v).

    Positive ``amount`` moves toward the camera; negative pushes depth occluders
    back so coplanar strokes win the depth test.
    """
    eye = np.asarray(eye, dtype=np.float64).reshape(3)
    primitives: list[pyrender.Primitive] = []
    for prim in mesh.primitives:
        if prim.mode != pyrender.GLTF.TRIANGLES:
            primitives.append(prim)
            continue
        positions = np.asarray(prim.positions, dtype=np.float64)
        to_eye = eye.reshape(1, 3) - positions
        norms = np.linalg.norm(to_eye, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-9)
        shifted = positions + (to_eye / norms) * float(amount)
        primitives.append(
            pyrender.Primitive(
                positions=np.ascontiguousarray(shifted, dtype=np.float32),
                normals=prim.normals,
                indices=prim.indices,
                mode=prim.mode,
                material=prim.material,
                color_0=None,
            )
        )
    return pyrender.Mesh(primitives=primitives)


def _isometric_camera_pose(
    bounds: np.ndarray,
    padding: float = 1.6,
    *,
    direction: Sequence[float] | None = None,
) -> np.ndarray:
    """Build a camera pose looking at the mesh AABB centre from an isometric direction."""
    center = (bounds[0] + bounds[1]) * 0.5
    extents = bounds[1] - bounds[0]
    radius = float(np.linalg.norm(extents)) * 0.5
    if radius < 1e-6:
        radius = 1.0

    direction_vec = np.array(
        list(direction) if direction is not None else [1.0, 1.0, 1.0],
        dtype=np.float64,
    )
    if direction_vec.shape != (3,) or float(np.linalg.norm(direction_vec)) < 1e-8:
        raise ValueError("camera direction must be a non-zero 3-vector")
    direction_vec /= np.linalg.norm(direction_vec)
    eye = center + direction_vec * (radius * padding * 2.5)

    forward = center - eye
    forward /= np.linalg.norm(forward)
    world_up = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    right = np.cross(forward, world_up)
    if np.linalg.norm(right) < 1e-8:
        world_up = np.array([0.0, 1.0, 0.0], dtype=np.float64)
        right = np.cross(forward, world_up)
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)

    pose = np.eye(4, dtype=np.float64)
    pose[:3, 0] = right
    pose[:3, 1] = up
    pose[:3, 2] = -forward
    pose[:3, 3] = eye
    return pose


def _product_material(
    guid: str,
    ifc_class: str,
    *,
    primary: set[str],
    colors: Mapping[str, list[float]],
    flooring_guids: Collection[str] | None = None,
) -> tuple[pyrender.MetallicRoughnessMaterial, bool]:
    """Return ``(material, is_transparent)`` for a product mesh."""
    if guid in primary and guid in colors:
        rgba = list(colors[guid])
        if len(rgba) == 3:
            rgba.append(1.0)
        blend = rgba[3] < 0.999
        return _material(rgba, blend=blend), blend
    if guid in primary:
        rgba, blend = _primary_style(ifc_class)
        return _material(rgba, blend=blend), blend
    if flooring_guids and guid in flooring_guids:
        return _material(_FLOORING_COLOR, blend=False), False
    if ifc_class in _VOLUME_CLASSES:
        # Keep room volumes see-through so solid accents (e.g. ceiling) stay visible
        return _material(_CONTEXT_VOLUME, blend=True), True
    if ifc_class in {"IfcWall", "IfcWallStandardCase"}:
        return _material(_WALL_COLOR, blend=False), False
    if ifc_class in {"IfcDoor", "IfcWindow"}:
        return _material(_FRAME_COLOR, blend=False), False
    if ifc_class == "IfcPlate":
        # Opening glazing: solid black in PNG; IFC keeps transparent Glass material
        return _glass_material(_GLASS_COLOR), False
    return _material(_CONTEXT_COLOR, blend=False), False


def _depth_only_material() -> pyrender.MetallicRoughnessMaterial:
    """Background-coloured opaque material for depth occluders (use with RenderFlags.FLAT)."""
    return pyrender.MetallicRoughnessMaterial(
        baseColorFactor=list(_BG_COLOR),
        metallicFactor=0.0,
        roughnessFactor=1.0,
        alphaMode="OPAQUE",
    )


def _as_depth_occluders(meshes: Sequence[pyrender.Mesh]) -> list[pyrender.Mesh]:
    """Clone triangle meshes with a background-coloured material for invisible depth writes."""
    occluders: list[pyrender.Mesh] = []
    material = _depth_only_material()
    for mesh in meshes:
        primitives = []
        for prim in mesh.primitives:
            if prim.mode != pyrender.GLTF.TRIANGLES:
                continue
            primitives.append(
                pyrender.Primitive(
                    positions=prim.positions,
                    normals=prim.normals,
                    indices=prim.indices,
                    mode=pyrender.GLTF.TRIANGLES,
                    material=material,
                    color_0=None,
                )
            )
        if primitives:
            occluders.append(pyrender.Mesh(primitives=primitives))
    return occluders


def _add_camera_and_lights(
    scene: pyrender.Scene,
    *,
    bounds: np.ndarray,
    camera_pose: np.ndarray,
    width: int,
    height: int,
    orthographic: bool = False,
    camera_padding: float = 1.6,
) -> None:
    if orthographic:
        # Same size at the look-at plane as the perspective lens; parallel edges stay parallel.
        radius, distance = _view_radius_distance(bounds, camera_padding)
        ymag = distance * float(np.tan(_YFOV * 0.5))
        znear = max(0.01, distance - radius * 2.0)
        zfar = distance + radius * 2.0
        camera = pyrender.OrthographicCamera(
            xmag=ymag, ymag=ymag, znear=znear, zfar=zfar
        )
    else:
        camera = pyrender.PerspectiveCamera(yfov=_YFOV, aspectRatio=width / height)
    scene.add(camera, pose=camera_pose)
    scene.add(pyrender.DirectionalLight(color=np.ones(3), intensity=3.0), pose=camera_pose)
    fill_pose = camera_pose.copy()
    fill_pose[:3, 3] = ((bounds[0] + bounds[1]) * 0.5) + np.array([-1.0, 0.5, 0.8]) * float(
        np.linalg.norm(bounds[1] - bounds[0])
    )
    scene.add(
        pyrender.DirectionalLight(color=np.array([0.95, 0.95, 1.0]), intensity=1.0),
        pose=fill_pose,
    )


def _render_scene(
    renderer: pyrender.OffscreenRenderer,
    scene: pyrender.Scene,
    *,
    flat: bool = False,
) -> np.ndarray:
    flags = pyrender.RenderFlags.RGBA | pyrender.RenderFlags.SKIP_CULL_FACES
    if flat:
        flags |= pyrender.RenderFlags.FLAT
    try:
        color, _depth = renderer.render(scene, flags=flags)
    except TypeError:
        color, _depth = renderer.render(scene)
        if color.shape[2] == 3:
            alpha = np.full((*color.shape[:2], 1), 255, dtype=np.uint8)
            color = np.concatenate([color, alpha], axis=2)
    return color


def _load_font(size: int) -> ImageFont.ImageFont:
    """Prefer a common system sans; fall back to Pillow default."""
    candidates = (
        "/usr/share/fonts/adwaita-sans-fonts/AdwaitaSans-Regular.ttf",
        "/usr/share/fonts/google-carlito-fonts/Carlito-Regular.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _primary_bounds(
    product_meshes: Sequence[tuple[str, str, trimesh.Trimesh]],
    primary: set[str],
) -> np.ndarray:
    """Return AABB ``(2, 3)`` of primary product meshes (fallback: all meshes)."""
    bounds_list = [mesh.bounds for guid, _cls, mesh in product_meshes if guid in primary]
    if not bounds_list:
        bounds_list = [mesh.bounds for _guid, _cls, mesh in product_meshes]
    return np.array(
        [
            np.min([b[0] for b in bounds_list], axis=0),
            np.max([b[1] for b in bounds_list], axis=0),
        ]
    )


def _stamp_texture_rgba(text: str = _WATERMARK_TEXT) -> np.ndarray:
    """Greyscale ink mask used to build extruded 3D letter geometry."""
    font = _load_font(120)
    probe = Image.new("L", (8, 8), 0)
    draw = ImageDraw.Draw(probe)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = 16
    img = Image.new("L", (tw + 2 * pad, th + 2 * pad), 0)
    draw = ImageDraw.Draw(img)
    draw.text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=255)
    return np.asarray(img, dtype=np.uint8)


def _mask_to_polygons(mask: np.ndarray) -> list:
    """Convert a binary text mask into shapely polygons (with holes)."""
    from shapely.geometry import Polygon

    try:
        import cv2
    except ImportError:
        return []

    _, bw = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    contours, hierarchy = cv2.findContours(bw, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return []
    hier = hierarchy[0]
    polygons: list = []
    for i, contour in enumerate(contours):
        if hier[i][3] != -1:
            continue
        if len(contour) < 3:
            continue
        exterior = contour.reshape(-1, 2).astype(np.float64)
        holes: list[list[list[float]]] = []
        child = hier[i][2]
        while child != -1:
            hole = contours[child].reshape(-1, 2).astype(np.float64)
            if len(hole) >= 3:
                holes.append(hole.tolist())
            child = hier[child][0]
        try:
            poly = Polygon(exterior, holes)
        except Exception:
            continue
        if poly.is_valid and poly.area > 4.0:
            polygons.append(poly)
    return polygons


def _robust_mesh_bounds(mesh: trimesh.Trimesh) -> np.ndarray:
    """Axis-aligned bounds ignoring non-finite / extreme tessellation outliers."""
    verts = np.asarray(mesh.vertices, dtype=np.float64)
    if verts.size == 0:
        return np.asarray(mesh.bounds, dtype=np.float64)
    finite = np.isfinite(verts).all(axis=1)
    verts = verts[finite]
    if len(verts) < 3:
        return np.asarray(mesh.bounds, dtype=np.float64)
    median = np.median(verts, axis=0)
    dist = np.linalg.norm(verts - median, axis=1)
    limit = max(50.0, float(np.median(dist)) * 20.0 + 1.0)
    verts = verts[dist <= limit]
    if len(verts) < 3:
        return np.asarray(mesh.bounds, dtype=np.float64)
    return np.vstack([verts.min(axis=0), verts.max(axis=0)])


def _horizontal_top_suitable(surface_bounds: np.ndarray) -> bool:
    """True when bounds describe a flat, wide-enough top face for engraving."""
    extents = surface_bounds[1] - surface_bounds[0]
    xy_min = float(min(extents[0], extents[1]))
    xy_max = float(max(extents[0], extents[1]))
    z = float(extents[2])
    if xy_min < 0.55:
        return False
    # Must be plate-like (slab/covering), not a wall/column/tree AABB
    if z > max(0.6, 0.35 * xy_min):
        return False
    if xy_min < 0.35 * xy_max and z > xy_min:
        return False
    return True


def _horizontal_hosts(
    product_meshes: list[tuple[str, str, trimesh.Trimesh]],
    primary_bounds: np.ndarray,
    *,
    prefer_lowest: bool = False,
    camera_direction: Sequence[float] | None = None,
) -> list[tuple[int, float, np.ndarray]]:
    """Flat opaque tops overlapping the primary XY.

    Default: highest first. ``prefer_lowest`` picks the visible top of the
    bottom plate (floor covering over slab) instead of the roof.

    At equal height, prefer the plate closer to the camera (e.g. balcony in
    front of an exterior wall rather than the interior slab behind it).
    """
    direction = np.array(
        list(camera_direction) if camera_direction is not None else [1.0, 1.0, 1.0],
        dtype=np.float64,
    )
    direction = direction / max(float(np.linalg.norm(direction)), 1e-8)
    cam_xy = direction[:2].copy()
    if float(np.linalg.norm(cam_xy)) < 1e-8:
        cam_xy = np.array([1.0, 1.0], dtype=np.float64)
    cam_xy /= np.linalg.norm(cam_xy)

    pad = 0.35
    x0 = float(primary_bounds[0][0]) - pad
    y0 = float(primary_bounds[0][1]) - pad
    x1 = float(primary_bounds[1][0]) + pad
    y1 = float(primary_bounds[1][1]) + pad
    candidates: list[tuple[int, float, np.ndarray, float]] = []
    for i, (_guid, ifc_class, mesh) in enumerate(product_meshes):
        if ifc_class in _OUTLINE_ONLY_CLASSES or ifc_class in _VOLUME_CLASSES:
            continue
        # Skip glass and transparent accent proxies (carve white context only)
        if ifc_class in {"IfcPlate", "IfcBuildingElementProxy"}:
            continue
        b = _robust_mesh_bounds(mesh)
        if b[1][0] < x0 or b[0][0] > x1 or b[1][1] < y0 or b[0][1] > y1:
            continue
        if not _horizontal_top_suitable(b):
            continue
        top = float(b[1][2])
        # Prefer slabs slightly over coverings at similar height
        class_bias = 0.05 if ifc_class == "IfcSlab" else 0.0
        center_xy = (b[0][:2] + b[1][:2]) * 0.5
        # Small bias: break ties toward the camera-near plate without beating height
        cam_bias = float(center_xy @ cam_xy) * 0.02
        score = top + class_bias + cam_bias
        candidates.append((i, top, b.copy(), score))
    if not candidates:
        return []
    if prefer_lowest:
        # Visible top of the bottom build-up (covering above slab), not buried slab
        z_min = min(item[1] for item in candidates)
        bottom = [item for item in candidates if item[1] <= z_min + 0.30]
        rest = [item for item in candidates if item[1] > z_min + 0.30]
        bottom.sort(key=lambda item: item[3], reverse=True)
        rest.sort(key=lambda item: item[3], reverse=True)
        ordered = bottom + rest
    else:
        ordered = sorted(candidates, key=lambda item: item[3], reverse=True)
    return [(i, top, bounds) for i, top, bounds, _score in ordered]


def _extrude_brand_glyphs(
    stamp_w: float,
    extrude_h: float,
    *,
    y_scale: float = 0.70,
) -> trimesh.Trimesh | None:
    """Build a local +Z extruded text mesh centred at the origin."""
    mask = _stamp_texture_rgba()
    polygons = _mask_to_polygons(mask)
    meshes: list[trimesh.Trimesh] = []
    if polygons:
        from shapely.geometry import Polygon
        from shapely.ops import unary_union

        union = unary_union(polygons)
        minx, miny, maxx, maxy = union.bounds
        sx = stamp_w / max(maxx - minx, 1e-6)
        for poly in polygons:
            coords = [
                ((x - minx) * sx - stamp_w * 0.5, (maxy - y) * sx)
                for x, y in poly.exterior.coords
            ]
            holes = [
                [((x - minx) * sx - stamp_w * 0.5, (maxy - y) * sx) for x, y in ring.coords]
                for ring in poly.interiors
            ]
            try:
                shaped = Polygon(coords, holes)
                if not shaped.is_valid or shaped.area < 1e-8:
                    continue
                meshes.append(trimesh.creation.extrude_polygon(shaped, height=extrude_h))
            except Exception:
                continue
    if not meshes:
        return None
    mesh = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
    mesh.apply_translation(
        [-float(np.mean(mesh.bounds[:, 0])), -float(np.mean(mesh.bounds[:, 1])), 0.0]
    )
    mesh.apply_scale([1.0, float(y_scale), 1.0])
    return mesh


def _brand_cutter_horizontal(
    surface_bounds: np.ndarray,
    *,
    camera_direction: Sequence[float] | None = None,
    far_corner: bool = False,
    side_corner: bool = False,
    scale: float = 1.0,
    stamp_width: float | None = None,
) -> trimesh.Trimesh | None:
    """Letter cutter into a horizontal top face (corner, parallel to an edge).

    By default places at the camera-near corner; ``far_corner`` uses the opposite
    (back) corner — useful when the near corner is occupied (e.g. footing pad).
    ``side_corner`` picks a laterally offset tip (max |cross| with the camera XY)
    so a centred subject (e.g. tree crown) does not hide the brand behind it.
    ``stamp_width`` (metres) sets an absolute letter-run length when given;
    otherwise ``scale`` multiplies the procedural size from the host AABB.
    """
    scale = max(float(scale), 0.25)
    surf_ext = surface_bounds[1] - surface_bounds[0]
    surf_xy_min = float(max(min(surf_ext[0], surf_ext[1]), 1e-3))
    max_fit = 0.94 * float(min(surf_ext[0], surf_ext[1]))
    if stamp_width is not None:
        stamp_w = min(max(float(stamp_width), 0.25), max_fit)
        # Absolute width: keep default letter aspect (do not inflate via scale).
        size_factor = 1.0
    else:
        stamp_w = min(0.55 * surf_xy_min, 0.65 * float(max(surf_ext[0], 1e-3))) * scale
        stamp_w = min(stamp_w, max_fit)
        size_factor = scale
    cut_depth = max(0.025, 0.08 * float(max(surf_ext[2], 0.05)))
    extrude_h = cut_depth + 0.01
    # Larger size also pulls the brand toward the chosen edge
    edge_margin = max(0.03, max(0.06 * surf_xy_min, 0.10) / size_factor)
    # Taller letters when scaled (default 0.70 keeps other cards unchanged).
    # Cap allows high-scale horizontal stamps (slab cards) to counteract
    # isometric foreshortening of letter height on flat tops.
    y_scale = min(3.5, 0.70 * max(size_factor, 1.0))

    mesh = _extrude_brand_glyphs(stamp_w, extrude_h, y_scale=y_scale)
    if mesh is None:
        return None
    mesh_extents = mesh.bounds[1] - mesh.bounds[0]
    text_half_w = float(mesh_extents[0]) * 0.5
    text_half_h = float(mesh_extents[1]) * 0.5

    direction = np.array(
        list(camera_direction) if camera_direction is not None else [1.0, 1.0, 1.0],
        dtype=np.float64,
    )
    direction = direction / max(float(np.linalg.norm(direction)), 1e-8)
    outward = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    z_top = float(surface_bounds[1][2])
    center = (surface_bounds[0] + surface_bounds[1]) * 0.5
    corners = np.array(
        [
            [surface_bounds[0][0], surface_bounds[0][1]],
            [surface_bounds[1][0], surface_bounds[0][1]],
            [surface_bounds[0][0], surface_bounds[1][1]],
            [surface_bounds[1][0], surface_bounds[1][1]],
        ],
        dtype=np.float64,
    )
    cam_xy = direction[:2].copy()
    if float(np.linalg.norm(cam_xy)) < 1e-8:
        cam_xy = np.array([1.0, 1.0], dtype=np.float64)
    cam_xy /= np.linalg.norm(cam_xy)
    # Near = max projection onto camera XY; far = opposite; side = lateral tip
    if side_corner:
        # 2D cross with camera XY → left/right tips of the plate (not front/back).
        lateral = corners[:, 0] * cam_xy[1] - corners[:, 1] * cam_xy[0]
        pick = int(np.argmax(np.abs(lateral)))
    else:
        pick = int(
            np.argmin(corners @ cam_xy) if far_corner else np.argmax(corners @ cam_xy)
        )
    corner = corners[pick]
    sign_x = 1.0 if corner[0] >= center[0] else -1.0
    sign_y = 1.0 if corner[1] >= center[1] else -1.0

    # Prefer world-X baseline (reads better in the default isometric). Only use Y
    # when the surface is a narrow strip along Y (X too short for the stamp).
    prefer_x = float(surf_ext[0]) >= max(0.9, 0.35 * float(surf_ext[1]))
    if prefer_x:
        x_axis = np.array([-sign_x, 0.0, 0.0], dtype=np.float64)
        pos = np.array(
            [
                corner[0] - sign_x * (edge_margin + text_half_w),
                corner[1] - sign_y * (edge_margin + text_half_h),
                z_top - cut_depth,
            ],
            dtype=np.float64,
        )
    else:
        x_axis = np.array([0.0, -sign_y, 0.0], dtype=np.float64)
        pos = np.array(
            [
                corner[0] - sign_x * (edge_margin + text_half_h),
                corner[1] - sign_y * (edge_margin + text_half_w),
                z_top - cut_depth,
            ],
            dtype=np.float64,
        )
    pad = edge_margin + max(text_half_w, text_half_h) * 0.15
    pos[0] = float(np.clip(pos[0], surface_bounds[0][0] + pad, surface_bounds[1][0] - pad))
    pos[1] = float(np.clip(pos[1], surface_bounds[0][1] + pad, surface_bounds[1][1] - pad))

    y_axis = np.cross(outward, x_axis)
    y_axis /= max(float(np.linalg.norm(y_axis)), 1e-8)
    away = np.array([-cam_xy[0], -cam_xy[1], 0.0], dtype=np.float64)
    away /= max(float(np.linalg.norm(away)), 1e-8)
    if float(y_axis @ away) < 0.0:
        x_axis = -x_axis
        y_axis = -y_axis
    x_axis = np.cross(y_axis, outward)
    x_axis /= max(float(np.linalg.norm(x_axis)), 1e-8)

    rot = np.eye(4, dtype=np.float64)
    rot[:3, 0] = x_axis
    rot[:3, 1] = y_axis
    rot[:3, 2] = outward
    mesh.apply_transform(rot)
    mesh.apply_translation(pos)
    return mesh


_WHITE_VERTICAL_CLASSES = frozenset(
    {"IfcWall", "IfcWallStandardCase", "IfcCovering"}
)


def _white_vertical_host(
    product_meshes: list[tuple[str, str, trimesh.Trimesh]],
    primary: set[str],
    *,
    camera_direction: Sequence[float] | None = None,
    prefer_longest: bool = False,
    wall_name: str | None = None,
    wall_name_by_guid: dict[str, str] | None = None,
) -> tuple[int, np.ndarray, np.ndarray] | None:
    """Pick a white vertical host for engraving: ``(index, outward_normal, bounds)``.

    Prefers walls; also accepts tall facade cladding (IfcCovering) so roofing
    vignettes can brand the outer panel.
    ``wall_name`` restricts the host to that IfcWall.Name when provided.
    """
    direction = np.array(
        list(camera_direction) if camera_direction is not None else [1.0, 1.0, 1.0],
        dtype=np.float64,
    )
    direction = direction / max(float(np.linalg.norm(direction)), 1e-8)
    cam_xy = direction[:2].copy()
    if float(np.linalg.norm(cam_xy)) < 1e-8:
        cam_xy = np.array([1.0, 1.0], dtype=np.float64)
    cam_xy /= np.linalg.norm(cam_xy)

    best: tuple[int, np.ndarray, np.ndarray] | None = None
    best_score = -1.0
    face_normals = (
        np.array([1.0, 0.0, 0.0]),
        np.array([-1.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
        np.array([0.0, -1.0, 0.0]),
    )
    for i, (guid, ifc_class, mesh) in enumerate(product_meshes):
        if guid in primary:
            continue  # keep orange accent faces clean
        if ifc_class not in _WHITE_VERTICAL_CLASSES:
            continue
        if wall_name is not None:
            name = (wall_name_by_guid or {}).get(guid)
            if name != wall_name:
                continue
        b = np.asarray(mesh.bounds, dtype=np.float64)
        extents = b[1] - b[0]
        # Walls need ~door height; cladding on a parapet can be shorter (~slab+Attika).
        min_height = 0.55 if ifc_class == "IfcCovering" else 0.7
        if float(extents[2]) < min_height:
            continue
        # Skip plate-like coverings (flooring / roofing tops): need a thin depth axis.
        if ifc_class == "IfcCovering":
            xy_min = float(min(extents[0], extents[1]))
            if xy_min > 0.25:
                continue
        for normal in face_normals:
            face_dot = float(normal[:2] @ cam_xy)
            if face_dot < 0.25:
                continue
            # Face area facing the camera
            if abs(normal[0]) > 0.5:
                face_area = float(extents[1] * extents[2])
                face_width = float(extents[1])
            else:
                face_area = float(extents[0] * extents[2])
                face_width = float(extents[0])
            if face_width < 0.6:
                continue
            # Prefer walls slightly over cladding when both qualify.
            class_bonus = 1.05 if ifc_class != "IfcCovering" else 1.0
            score = face_dot * face_area * class_bonus
            if prefer_longest:
                score += face_width * 1_000_000.0
            if score > best_score:
                best_score = score
                best = (i, normal.copy(), b)
    return best


def _brand_cutter_vertical(
    surface_bounds: np.ndarray,
    outward: np.ndarray,
    *,
    camera_direction: Sequence[float] | None = None,
    wall_top: bool = False,
    rotate_90: bool = False,
    center_along_wall: bool = False,
    scale: float = 1.0,
    stamp_width: float | None = None,
) -> trimesh.Trimesh | None:
    """Letter cutter into a vertical white face (corner, upright).

    Default: bottom corner. ``wall_top`` places at the top corner instead.
    ``rotate_90`` turns the letter-run upright on the wall face.
    ``center_along_wall`` places mid-face along the wall length (avoids the tip).
    ``stamp_width`` (metres) sets an absolute letter-run length when given;
    otherwise ``scale`` multiplies the procedural size from the face width.
    """
    extents = surface_bounds[1] - surface_bounds[0]
    if abs(outward[0]) > 0.5:
        face_width = float(extents[1])
        wall_thickness = float(extents[0])
    else:
        face_width = float(extents[0])
        wall_thickness = float(extents[1])
    face_height = float(extents[2])
    scale = max(float(scale), 0.25)
    run_limit = face_height if rotate_90 else face_width
    max_fit = 0.90 * run_limit
    if stamp_width is not None:
        stamp_w = min(max(float(stamp_width), 0.25), max_fit)
        size_factor = 1.0
    else:
        stamp_w = min(0.55 * run_limit, 0.70 * run_limit) * scale
        stamp_w = min(stamp_w, max_fit)
        size_factor = scale
    cut_depth = max(0.02, min(0.45 * wall_thickness, 0.08))
    extrude_h = cut_depth + 0.01
    edge_margin = max(0.06 * min(face_width, face_height) / size_factor, 0.08)

    mesh = _extrude_brand_glyphs(stamp_w, extrude_h)
    if mesh is None:
        return None
    if rotate_90:
        mesh.apply_transform(
            trimesh.transformations.rotation_matrix(
                np.pi * 0.5,
                [0.0, 0.0, 1.0],
            )
        )
    mesh_extents = mesh.bounds[1] - mesh.bounds[0]
    text_half_w = float(mesh_extents[0]) * 0.5
    text_half_h = float(mesh_extents[1]) * 0.5

    direction = np.array(
        list(camera_direction) if camera_direction is not None else [1.0, 1.0, 1.0],
        dtype=np.float64,
    )
    direction = direction / max(float(np.linalg.norm(direction)), 1e-8)
    outward = np.asarray(outward, dtype=np.float64)
    outward = outward / max(float(np.linalg.norm(outward)), 1e-8)
    center = (surface_bounds[0] + surface_bounds[1]) * 0.5

    # Letter tops always world +Z. Prefer reading against the camera tangent, then
    # re-assert upright (flipping the reading axis alone used to invert the glyphs).
    world_up = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    x_axis = np.cross(world_up, outward)
    if float(np.linalg.norm(x_axis)) < 1e-8:
        x_axis = np.array([1.0, 0.0, 0.0], dtype=np.float64)
    x_axis /= np.linalg.norm(x_axis)
    if float(x_axis[:2] @ direction[:2]) > 0.0:
        x_axis = -x_axis
    y_axis = np.cross(outward, x_axis)
    if float(y_axis[2]) < 0.0:
        x_axis = -x_axis
        y_axis = -y_axis
    y_axis /= max(float(np.linalg.norm(y_axis)), 1e-8)

    # Corner of the camera-facing face closest to the eye (bottom or top)
    face_center = center + outward * (extents * 0.5)
    anchor_z = (
        float(surface_bounds[1][2]) if wall_top else float(surface_bounds[0][2])
    )
    # Bottom: lift up from edge; top: drop down from edge so glyphs stay on the face
    vertical_offset = (
        -world_up * (edge_margin + text_half_h)
        if wall_top
        else world_up * (edge_margin + text_half_h)
    )
    if center_along_wall:
        # Mid-face along the wall run so the brand reads on the long elevation.
        pos = face_center.copy()
        pos[2] = anchor_z
        pos = pos + vertical_offset - outward * cut_depth
    else:
        c0 = face_center + x_axis * (face_width * 0.5)
        c1 = face_center - x_axis * (face_width * 0.5)
        c0[2] = anchor_z
        c1[2] = anchor_z
        eye = center + direction
        corner = (
            c0
            if float(np.linalg.norm(c0 - eye)) < float(np.linalg.norm(c1 - eye))
            else c1
        )
        # Inset from the corner into the face (keep upright x_axis; do not reassign it)
        inset = face_center - corner
        inset[2] = 0.0
        inset_len = float(np.linalg.norm(inset))
        if inset_len < 1e-8:
            inset = x_axis.copy()
        else:
            inset /= inset_len
        pos = (
            corner
            + inset * (edge_margin + text_half_w)
            + vertical_offset
            - outward * cut_depth
        )

    rot = np.eye(4, dtype=np.float64)
    rot[:3, 0] = x_axis
    rot[:3, 1] = y_axis
    rot[:3, 2] = outward
    mesh.apply_transform(rot)
    mesh.apply_translation(pos)
    return mesh


def _apply_boolean_engrave(
    product_meshes: list[tuple[str, str, trimesh.Trimesh]],
    idx: int,
    cutter: trimesh.Trimesh,
) -> bool:
    guid, ifc_class, host = product_meshes[idx]
    try:
        engraved = host.difference(cutter, engine="manifold")
    except Exception:
        return False
    if engraved is None:
        return False
    if not isinstance(engraved, trimesh.Trimesh):
        try:
            engraved = engraved.dump(concatenate=True)
        except Exception:
            return False
    if not isinstance(engraved, trimesh.Trimesh):
        return False
    faces = getattr(engraved, "faces", None)
    if faces is None or len(faces) == 0:
        return False
    product_meshes[idx] = (guid, ifc_class, engraved)
    return True


def _engrave_brand_into_meshes(
    product_meshes: list[tuple[str, str, trimesh.Trimesh]],
    primary: set[str],
    *,
    camera_direction: Sequence[float] | None = None,
    prefer_lowest: bool = False,
    far_corner: bool = False,
    side_corner: bool = False,
    prefer_wall: bool = False,
    longest_wall: bool = False,
    wall_top: bool = False,
    rotate_90: bool = False,
    center_along_wall: bool = False,
    wall_name: str | None = None,
    wall_name_by_guid: dict[str, str] | None = None,
    scale: float = 1.0,
    stamp_width: float | None = None,
) -> None:
    """Boolean-subtract brand letters (render-only).

    Prefer a flat horizontal top; otherwise carve a white vertical wall (bottom, upright).
    As a last resort, carve the primary wall itself when it is the only vertical.
    ``prefer_lowest`` engraves the bottom plate (floor) instead of the highest.
    ``far_corner`` places the horizontal brand at the camera-far corner.
    ``side_corner`` places it on a lateral tip (beside a centred subject).
    ``prefer_wall`` skips horizontal hosts and carves a white vertical wall first
    (used when flooring would otherwise steal the brand, e.g. parking).
    ``longest_wall`` selects the longest visible wall instead of weighting by area.
    ``wall_name`` forces a specific IfcWall.Name host when provided.
    ``wall_top`` places the vertical brand at the top of the wall face.
    ``rotate_90`` turns lettering by 90 degrees within the wall face.
    ``center_along_wall`` places mid-face along the wall length.
    ``scale`` multiplies procedural stamp size; ``stamp_width`` (metres) overrides
    with an absolute letter-run length (per-picture fixed size).
    """
    primary_bounds = _primary_bounds(product_meshes, primary)
    if not prefer_wall:
        for idx, _z_top, surface_bounds in _horizontal_hosts(
            product_meshes,
            primary_bounds,
            prefer_lowest=prefer_lowest,
            camera_direction=camera_direction,
        ):
            cutter = _brand_cutter_horizontal(
                surface_bounds,
                camera_direction=camera_direction,
                far_corner=far_corner,
                side_corner=side_corner,
                scale=scale,
                stamp_width=stamp_width,
            )
            if cutter is not None and _apply_boolean_engrave(product_meshes, idx, cutter):
                return

    host_kwargs = dict(
        camera_direction=camera_direction,
        prefer_longest=longest_wall,
        wall_name=wall_name,
        wall_name_by_guid=wall_name_by_guid,
    )
    vertical = _white_vertical_host(product_meshes, primary, **host_kwargs)
    if vertical is None:
        # Last resort: primary wall when no white context wall exists
        vertical = _white_vertical_host(product_meshes, primary=set(), **host_kwargs)
        if vertical is not None:
            idx, outward, surface_bounds = vertical
            guid, ifc_class, _mesh = product_meshes[idx]
            if ifc_class not in _WHITE_VERTICAL_CLASSES or guid not in primary:
                vertical = None
    if vertical is None:
        return
    idx, outward, surface_bounds = vertical
    cutter = _brand_cutter_vertical(
        surface_bounds,
        outward,
        camera_direction=camera_direction,
        wall_top=wall_top,
        rotate_90=rotate_90,
        center_along_wall=center_along_wall,
        scale=scale,
        stamp_width=stamp_width,
    )
    if cutter is None:
        return
    _apply_boolean_engrave(product_meshes, idx, cutter)


def _apply_corner_watermark(img: Image.Image, text: str = _WATERMARK_TEXT) -> Image.Image:
    """Small brand label in the bottom-right corner (2D overlay)."""
    out = img.convert("RGBA")
    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font_size = max(14, int(out.width * 0.025))
    font = _load_font(font_size)
    margin = max(12, int(out.width * 0.02))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = out.width - tw - margin - bbox[0]
    y = out.height - th - margin - bbox[1]
    draw.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0, 90))
    draw.text((x, y), text, font=font, fill=(40, 40, 40, 155))
    return Image.alpha_composite(out, overlay)


def _composite_edges_through_transparency(
    faces: np.ndarray,
    edge_layer: np.ndarray,
    *,
    threshold: float = 4.0,
    dilate: int = 2,
) -> np.ndarray:
    """Overlay edge strokes onto face colours.

    ``edge_layer`` is rendered with invisible opaque depth occluders (no transparent
    volumes) plus edge ribbons, so strokes remain visible where only see-through
    geometry would have hidden them. Pyrender always depth-writes blended surfaces,
    which is why a single-pass render drops those lines.
    """
    # Sample clear colour from a corner (occluders match this under flat ambient lighting)
    bg = edge_layer[0, 0, :3].astype(np.float32)
    delta = np.max(np.abs(edge_layer[..., :3].astype(np.float32) - bg), axis=2)
    edge_mask = delta > threshold
    # Dilate so anti-aliased ribbon edges stay continuous after compositing
    dil = edge_mask.copy()
    for _ in range(max(int(dilate), 0)):
        nxt = dil.copy()
        nxt[1:, :] |= dil[:-1, :]
        nxt[:-1, :] |= dil[1:, :]
        nxt[:, 1:] |= dil[:, :-1]
        nxt[:, :-1] |= dil[:, 1:]
        dil = nxt
    result = faces.copy()
    result[dil] = np.minimum(faces[dil], edge_layer[dil])
    return result


def _fit_content_square(
    image: Image.Image,
    *,
    margin_frac: float = 0.06,
    bg_rgb: tuple[int, int, int] = (237, 237, 237),
    bg_tol: int = 6,
) -> Image.Image:
    """Recenter geometry in a square with a tight grey border.

    Camera framing often leaves uneven empty bands (especially above flat
    vignettes). Crop to content, pad by ``margin_frac`` of the longer side,
    and letterbox onto a square of the original size.
    """
    rgb = image.convert("RGB")
    arr = np.asarray(rgb)
    diff = np.abs(arr.astype(np.int16) - np.asarray(bg_rgb, dtype=np.int16))
    mask = diff.max(axis=2) > bg_tol
    if not bool(mask.any()):
        return rgb

    ys, xs = np.where(mask)
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    content = rgb.crop((x0, y0, x1 + 1, y1 + 1))
    bw, bh = content.size
    pad = max(1, int(round(max(bw, bh) * margin_frac)))
    side = max(bw + 2 * pad, bh + 2 * pad)
    canvas = Image.new("RGB", (side, side), bg_rgb)
    canvas.paste(content, ((side - bw) // 2, (side - bh) // 2))

    if canvas.size != rgb.size:
        canvas = canvas.resize(rgb.size, Image.Resampling.LANCZOS)
    return canvas


def render_isometric(
    ifc_file: ifcopenshell.file,
    output_path: str | os.PathLike[str],
    *,
    primary_guids: Collection[str] | None = None,
    primary_colors: Mapping[str, Sequence[float]] | None = None,
    dotted_guids: Collection[str] | None = None,
    thin_edge_guids: Collection[str] | None = None,
    camera_focus_guids: Collection[str] | None = None,
    camera_padding: float = 1.6,
    resolution: Sequence[int] = DEFAULT_RESOLUTION,
    camera_direction: Sequence[float] | None = None,
    orthographic: bool = False,
    color_flooring: bool = True,
    show_context_volumes: bool = True,
    disable_opening_subtractions: bool | None = None,
    engrave: bool = True,
    watermark: bool = True,
    dpi: Sequence[int] | None = None,
    engrave_prefer_lowest: bool = False,
    engrave_far_corner: bool = False,
    engrave_side_corner: bool = False,
    engrave_prefer_wall: bool = False,
    engrave_longest_wall: bool = False,
    engrave_wall_top: bool = False,
    engrave_rotate_90: bool = False,
    engrave_center_along_wall: bool = False,
    engrave_wall_name: str | None = None,
    engrave_scale: float = 1.0,
    engrave_stamp_width: float | None = None,
    camera_bounds: np.ndarray | None = None,
    fit_content: bool = True,
) -> Path:
    """Render all geometry in ``ifc_file`` to a fixed-angle isometric image.

    ``primary_guids`` marks the catalog main element(s): accent colour
    (transparent for volumes, opaque for solids). Everything else is white context.
    ``primary_colors`` optionally maps GUID → opaque RGBA to override the default
    accent for specific primaries (e.g. graded storey slabs).
    ``dotted_guids`` renders selected products as dashed outlines without faces.
    ``thin_edge_guids`` renders selected product edges lighter and thinner.
    ``camera_focus_guids`` limits camera framing to selected products while still
    rendering the surrounding model.
    ``camera_padding`` controls the margin around the framed geometry.
    ``camera_direction`` optional eye offset from the AABB centre (default ``+X+Y+Z``);
    use ``(-1, -1, 1)`` for a 180° yaw of the isometric view.
    ``orthographic`` uses a parallel projection with the same framing at the
    look-at plane (cover tiles). Default stays the long perspective lens.
    ``color_flooring`` when True, tints IfcCovering FLOORING beige so it reads
    against white slabs; set False for white context flooring.
    ``show_context_volumes`` when False, skips face fill for non-primary IfcSpace
    volumes (edges remain) so only the accented void reads as coloured.
    ``disable_opening_subtractions`` overrides the automatic opening-rendering
    heuristic when a vignette has unfilled openings that must remain visible.
    ``engrave`` / ``watermark`` control the 3D brand carve and corner label
    (disable both for clean print assets).
    ``dpi`` optional PNG metadata; TIFF print masters use ``PRINT_DPI``.
    Engraving placement/size should come from ``render.engrave_specs`` (per picture).
    ``engrave_prefer_lowest`` / ``engrave_far_corner`` / ``engrave_side_corner`` /
    ``engrave_prefer_wall`` / ``engrave_longest_wall`` / ``engrave_wall_name``
    select the wall host; ``engrave_wall_top`` selects its corner,
    ``engrave_rotate_90`` turns lettering, and ``engrave_center_along_wall``
    places mid-face along the wall length.
    ``engrave_scale`` multiplies procedural stamp size; ``engrave_stamp_width``
    (metres) sets a fixed letter-run length for that picture.
    ``camera_bounds`` optional world AABB ``(2, 3)`` used for the camera pose,
    orthographic magnification, and stroke width instead of the mesh bounds.
    ``fit_content`` when False, skips the crop-and-rescale pass so a shared
    camera stays identical across pictures.
    If omitted, the first IfcSpace (else first product with geometry) is treated as primary.
    """
    product_meshes = _product_meshes(
        ifc_file,
        primary_guids=primary_guids,
        disable_opening_subtractions=disable_opening_subtractions,
    )
    if not isinstance(product_meshes, list):
        product_meshes = list(product_meshes)
    primary = set(primary_guids or ())
    dotted = set(dotted_guids or ())
    thin_edges = set(thin_edge_guids or ())
    colors = {g: list(c) for g, c in (primary_colors or {}).items()}
    flooring_guids = (
        {
            c.GlobalId
            for c in ifc_file.by_type("IfcCovering")
            if getattr(c, "PredefinedType", None) == "FLOORING"
        }
        if color_flooring
        else set()
    )
    if not primary:
        for guid, ifc_class, _mesh in product_meshes:
            if ifc_class in _VOLUME_CLASSES:
                primary.add(guid)
                break
        if not primary and product_meshes:
            primary.add(product_meshes[0][0])

    # Render-only: carve brand into top horizontal surface, else white vertical wall.
    if engrave:
        wall_name_by_guid = {
            w.GlobalId: str(w.Name or "")
            for w in ifc_file.by_type("IfcWall")
        }
        _engrave_brand_into_meshes(
            product_meshes,
            primary,
            camera_direction=camera_direction,
            prefer_lowest=engrave_prefer_lowest,
            far_corner=engrave_far_corner,
            side_corner=engrave_side_corner,
            prefer_wall=engrave_prefer_wall,
            longest_wall=engrave_longest_wall,
            wall_top=engrave_wall_top,
            rotate_90=engrave_rotate_90,
            center_along_wall=engrave_center_along_wall,
            wall_name=engrave_wall_name,
            wall_name_by_guid=wall_name_by_guid,
            scale=engrave_scale,
            stamp_width=engrave_stamp_width,
        )

    width, height = int(resolution[0]), int(resolution[1])
    all_bounds: list[np.ndarray] = []
    focus = set(camera_focus_guids or ())
    focus_bounds: list[np.ndarray] = []

    # Opaque context first, then glass, then frames, then transparent volumes
    def sort_key(item: tuple[str, str, trimesh.Trimesh]) -> int:
        guid, ifc_class, _ = item
        if ifc_class in _VOLUME_CLASSES:
            return 4
        if guid in primary:
            return 3
        if ifc_class in {"IfcDoor", "IfcWindow"}:
            return 2  # frames in front of glass
        if ifc_class == "IfcPlate":
            return 1  # glass panes after walls, before frames
        return 0

    opaque_face_meshes: list[pyrender.Mesh] = []
    transparent_face_meshes: list[pyrender.Mesh] = []
    solid_edge_sources: list[trimesh.Trimesh] = []
    thin_edge_sources: list[trimesh.Trimesh] = []
    dotted_edge_sources: list[trimesh.Trimesh] = []
    has_accent_opening = False

    for guid, ifc_class, mesh in sorted(product_meshes, key=sort_key):
        all_bounds.append(mesh.bounds)
        if guid in focus:
            focus_bounds.append(mesh.bounds)
        if ifc_class in _OUTLINE_ONLY_CLASSES or guid in dotted:
            dotted_edge_sources.append(mesh)
            continue
        # Optional: wireframe-only context rooms (Luftraum card — only void is filled)
        skip_faces = (
            not show_context_volumes
            and ifc_class in _VOLUME_CLASSES
            and guid not in primary
        )
        if not skip_faces:
            material, is_transparent = _product_material(
                guid,
                ifc_class,
                primary=primary,
                colors=colors,
                flooring_guids=flooring_guids,
            )
            face_mesh = pyrender.Mesh.from_trimesh(mesh, material=material, smooth=False)
            if is_transparent:
                transparent_face_meshes.append(face_mesh)
                if ifc_class == "IfcOpeningElement":
                    has_accent_opening = True
            else:
                opaque_face_meshes.append(face_mesh)
        # Skip edge overlay on glass — triangulation edges read as grey hatching
        if ifc_class != "IfcPlate":
            if guid in thin_edges:
                thin_edge_sources.append(mesh)
            else:
                solid_edge_sources.append(mesh)

    # Depth occluders for edge compositing: punch voids when an opening is accented so
    # MEP outlines remain visible through the transparent Durchbruch (faces stay continuous).
    opaque_occluder_meshes = opaque_face_meshes
    if has_accent_opening:
        voided = _product_meshes(
            ifc_file,
            primary_guids=primary,
            disable_opening_subtractions=False,
        )
        occluders: list[pyrender.Mesh] = []
        for guid, ifc_class, mesh in voided:
            if ifc_class in _OUTLINE_ONLY_CLASSES or ifc_class in _VOLUME_CLASSES:
                continue
            material, is_transparent = _product_material(
                guid,
                ifc_class,
                primary=primary,
                colors=colors,
                flooring_guids=flooring_guids,
            )
            if is_transparent:
                continue
            occluders.append(
                pyrender.Mesh.from_trimesh(mesh, material=material, smooth=False)
            )
        if occluders:
            opaque_occluder_meshes = occluders

    framing = focus_bounds or all_bounds
    bounds = (
        np.asarray(camera_bounds, dtype=np.float64)
        if camera_bounds is not None
        else np.array(
            [
                np.min([b[0] for b in framing], axis=0),
                np.max([b[1] for b in framing], axis=0),
            ]
        )
    )
    camera_pose = _isometric_camera_pose(
        bounds,
        padding=float(camera_padding),
        direction=camera_direction,
    )
    eye = np.asarray(camera_pose[:3, 3], dtype=np.float64)
    scene_radius = float(np.linalg.norm(bounds[1] - bounds[0])) * 0.5
    stroke_height = None
    if orthographic:
        _radius, distance = _view_radius_distance(bounds, float(camera_padding))
        stroke_height = 2.0 * distance * float(np.tan(_YFOV * 0.5))
    half_width = _stroke_world_half_width(
        bounds, height_px=height, world_height=stroke_height
    )
    # Pull strokes toward the camera and push occluders back so coplanar white
    # abutments keep a continuous black seam (GL_LINES used to z-fight away).
    # Bias scales with scene size; keep well below typical wall thickness (~0.15 m)
    # so hidden edges do not bleed through solids.
    toward_bias = max(0.012, 0.006 * max(scene_radius, 1e-3))
    occluder_away = max(0.006, 0.003 * max(scene_radius, 1e-3))
    normal_bias = max(0.004, 0.002 * max(scene_radius, 1e-3))

    edge_meshes: list[pyrender.Mesh] = []
    for mesh in solid_edge_sources:
        strokes = _edge_stroke_mesh(
            mesh,
            eye=eye,
            half_width=half_width,
            toward_bias=toward_bias,
            normal_bias=normal_bias,
        )
        if strokes is not None:
            edge_meshes.append(strokes)
    for mesh in thin_edge_sources:
        strokes = _edge_stroke_mesh(
            mesh,
            eye=eye,
            half_width=half_width * 0.45,
            toward_bias=toward_bias,
            normal_bias=normal_bias,
            rgba=_THIN_EDGE_COLOR,
        )
        if strokes is not None:
            edge_meshes.append(strokes)
    for mesh in dotted_edge_sources:
        dotted = _dotted_edge_mesh(
            mesh,
            eye=eye,
            half_width=half_width,
            toward_bias=toward_bias,
            normal_bias=normal_bias,
        )
        if dotted is not None:
            edge_meshes.append(dotted)

    def make_scene(meshes: Sequence[pyrender.Mesh]) -> pyrender.Scene:
        scene = pyrender.Scene(bg_color=_BG_COLOR, ambient_light=[0.55, 0.55, 0.55])
        for item in meshes:
            scene.add(item)
        _add_camera_and_lights(
            scene,
            bounds=bounds,
            camera_pose=camera_pose,
            width=width,
            height=height,
            orthographic=orthographic,
            camera_padding=float(camera_padding),
        )
        return scene

    # Faces pass (incl. transparent). Edge pass uses invisible depth occluders so strokes
    # are not hidden by blended volumes, then composited onto the face colours.
    # Engraved brand letters pick up thin outlines from the edge pass.
    scene_faces = make_scene([*opaque_face_meshes, *transparent_face_meshes])
    depth_occluders = [
        _bias_triangle_mesh_along_view(mesh, eye, -occluder_away)
        for mesh in _as_depth_occluders(opaque_occluder_meshes)
    ]
    scene_edges = make_scene([*depth_occluders, *edge_meshes])

    renderer = pyrender.OffscreenRenderer(viewport_width=width, viewport_height=height)
    try:
        color_faces = _render_scene(renderer, scene_faces)
        if edge_meshes:
            # FLAT keeps occluders exactly background-coloured for a clean edge mask
            color_edges = _render_scene(renderer, scene_edges, flat=True)
            color = _composite_edges_through_transparency(color_faces, color_edges)
        else:
            color = color_faces
    finally:
        renderer.delete()

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    image = Image.fromarray(color)
    if fit_content:
        image = _fit_content_square(image)
    if watermark:
        image = _apply_corner_watermark(image)
    if out.suffix.lower() in {".tif", ".tiff"}:
        return save_print_tiff(image, out)
    save_kwargs: dict = {}
    if dpi is not None:
        save_kwargs["dpi"] = (int(dpi[0]), int(dpi[1]))
    image.save(out, **save_kwargs)
    return out
