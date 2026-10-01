"""Explicit per-picture brand-engraving specs for catalog PNGs.

Placement and size are keyed by catalog entry ``id`` so tuning one card does
not change another. Host selection remains geometric; only the flags and
stamp size below are fixed per picture.

``stamp_width`` (metres) is absolute letter-run length on the host face.
When omitted, ``scale`` multiplies the procedural size from the host AABB.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class EngraveSpec:
    """Render-only brand carve options for one catalog picture."""

    prefer_lowest: bool = False
    far_corner: bool = False
    side_corner: bool = False
    prefer_wall: bool = False
    longest_wall: bool = False
    wall_top: bool = False
    rotate_90: bool = False
    # Place mid-face along the wall length (not at the tip corner).
    center_along_wall: bool = False
    # Optional exact IfcWall.Name host for this picture.
    wall_name: str | None = None
    scale: float = 1.0
    # Absolute horizontal/vertical stamp width in metres; wins over ``scale``.
    stamp_width: float | None = None


# Defaults: highest horizontal plate, procedural size (scale 1.0).
_DEFAULT = EngraveSpec()

# Fixed per catalog picture id (see catalog/sample_data.py).
ENGRAVE_BY_ID: dict[str, EngraveSpec] = {
    # Horizontal plates -------------------------------------------------
    "coordination-zone-01": EngraveSpec(prefer_lowest=True),
    "stair-01": EngraveSpec(prefer_lowest=True),
    "railing-01": EngraveSpec(prefer_wall=True, wall_top=True),
    "installation-path-01": EngraveSpec(
        prefer_wall=True,
        wall_name="Flur-Wand-Unten",
        wall_top=True,
        rotate_90=True,
        center_along_wall=True,
    ),
    "turning-radius-01": EngraveSpec(prefer_lowest=True, stamp_width=3.5),
    "decision-volume-01": EngraveSpec(
        prefer_lowest=True,
        stamp_width=1.6,
    ),
    "movement-clearance-01": EngraveSpec(
        prefer_wall=True,
        wall_name="Rueckwand",
        wall_top=True,
    ),
    "building-law-parcel-01": EngraveSpec(prefer_lowest=True, stamp_width=4.0),
    "surrounding-building-01": EngraveSpec(prefer_lowest=True, stamp_width=4.0),
    "construction-logistics-01": EngraveSpec(prefer_lowest=True, stamp_width=4.0),
    "planning-constraint-01": EngraveSpec(prefer_lowest=True, stamp_width=4.0),
    "umbau-perimeter-01": EngraveSpec(
        prefer_lowest=True,
        stamp_width=1.6,
    ),
    "cladding-exterior-01": EngraveSpec(prefer_lowest=True, scale=2.5),
    "footing-pad-01": EngraveSpec(far_corner=True),
    # Column: near-corner brand so text sits in front of the centred column.
    "column-01": EngraveSpec(),
    # Slab hierarchy cards: wide roof plate + isometric foreshortening —
    # high scale fills the plate and tallens glyphs on the flat top.
    "slab-base-01": EngraveSpec(scale=5.0),
    "slab-floor-01": EngraveSpec(scale=5.0),
    "slab-roof-01": EngraveSpec(scale=5.0),
    "slab-balcony-01": EngraveSpec(scale=5.0),
    # Tree: lateral terrain tip; absolute width so other cards stay untouched.
    "tree-01": EngraveSpec(side_corner=True, stamp_width=2.8),
    "tree-pit-01": EngraveSpec(side_corner=True, stamp_width=2.8),
    "retention-01": EngraveSpec(side_corner=True, stamp_width=2.8),
    # Furniture: brand on the back wall (same as other interior wall cards).
    "furniture-01": EngraveSpec(prefer_wall=True, wall_top=True),
    "built-in-furniture-kitchen-01": EngraveSpec(prefer_wall=True, wall_top=True),
    # Vertical facades --------------------------------------------------
    "space-parking-01": EngraveSpec(prefer_wall=True),
    "space-elevator-01": EngraveSpec(prefer_wall=True, wall_top=True),
    "space-vorsatzschale-01": EngraveSpec(prefer_wall=True, wall_top=True),
    "detail-reference-01": EngraveSpec(prefer_wall=True, wall_top=True, scale=0.8),
    "wall-exterior-01": EngraveSpec(prefer_wall=True, wall_top=True),
    "wall-interior-01": EngraveSpec(prefer_wall=True, wall_top=True),
    "wall-interior-lb-01": EngraveSpec(prefer_wall=True, wall_top=True),
    "drywall-reinforcement-01": EngraveSpec(prefer_wall=True, wall_top=True),
    "wall-cladding-interior-01": EngraveSpec(prefer_wall=True, wall_top=True),
    "door-exterior-01": EngraveSpec(prefer_wall=True, wall_top=True),
    "window-exterior-01": EngraveSpec(prefer_wall=True, wall_top=True),
    "shading-device-01": EngraveSpec(prefer_wall=True, wall_top=True),
    "door-interior-01": EngraveSpec(prefer_wall=True, wall_top=True),
    "window-interior-01": EngraveSpec(prefer_wall=True, wall_top=True),
    "roofing-insulation-01": EngraveSpec(prefer_wall=True, wall_top=True),
}


def engrave_spec_for(entry_id: str) -> EngraveSpec:
    """Return the fixed engraving spec for a catalog entry id."""
    return ENGRAVE_BY_ID.get(str(entry_id), _DEFAULT)


def engrave_kwargs_for(entry_id: str) -> dict[str, Any]:
    """Keyword args for ``render_isometric`` (``engrave_*`` parameters)."""
    spec = engrave_spec_for(entry_id)
    return {
        "engrave_prefer_lowest": spec.prefer_lowest,
        "engrave_far_corner": spec.far_corner,
        "engrave_side_corner": spec.side_corner,
        "engrave_prefer_wall": spec.prefer_wall,
        "engrave_longest_wall": spec.longest_wall,
        "engrave_wall_top": spec.wall_top,
        "engrave_rotate_90": spec.rotate_90,
        "engrave_center_along_wall": spec.center_along_wall,
        "engrave_wall_name": spec.wall_name,
        "engrave_scale": spec.scale,
        "engrave_stamp_width": spec.stamp_width,
    }


def engrave_spec_as_dict(entry_id: str) -> dict[str, Any]:
    """Plain dict of the EngraveSpec fields (debug / logging)."""
    return asdict(engrave_spec_for(entry_id))
