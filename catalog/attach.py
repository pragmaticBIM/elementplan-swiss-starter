"""Attach generated PNG/IFC previews to Elementplan element YAML + media folders."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ELEMENTS_DIR = REPO_ROOT / "elements"
MEDIA_IMAGES_DIR = REPO_ROOT / "media" / "images"
MEDIA_ATTACHMENTS_DIR = REPO_ROOT / "media" / "attachments"


def _set_or_insert_link(text: str, key: str, filename: str) -> str:
    """Set ``key: filename`` in element YAML, inserting after picture/model links if missing."""
    pattern = re.compile(rf"^({re.escape(key)}\s*:\s*).*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(rf"\1{filename}", text, count=1)

    # Insert after picture/attachment/model links if present
    for anchor in ("picture_link", "picture_print_link", "attachment_link", "model_link"):
        anchor_pat = re.compile(rf"^({re.escape(anchor)}\s*:.*)$", re.MULTILINE)
        match = anchor_pat.search(text)
        if match:
            insert_at = match.end()
            return text[:insert_at] + f"\n{key}: {filename}" + text[insert_at:]

    # Fallback: after entity_ifc4_3 / entity_ifc4 line
    entity_pat = re.compile(r"^(entity_ifc4(?:_3)?\s*:.*)$", re.MULTILINE)
    matches = list(entity_pat.finditer(text))
    if matches:
        insert_at = matches[-1].end()
        return text[:insert_at] + f"\n{key}: {filename}" + text[insert_at:]

    raise ValueError(f"cannot find a place to insert {key} in element YAML")


def attach_preview_to_element(
    *,
    element_slug: str,
    png_path: Path,
    ifc_path: Path,
    print_path: Path | None = None,
) -> dict[str, Path]:
    """Copy preview assets into media/ and update the element YAML links.

    - PNG        → ``media/images/{element_slug}.png``        (``picture_link``)
    - print TIFF → ``media/images/{element_slug}-print.tif`` (``picture_print_link``)
    - IFC        → ``media/attachments/{element_slug}.ifc``    (``attachment_link`` + legacy ``model_link``)

    Returns paths of the written media files.
    """
    element_yaml = ELEMENTS_DIR / f"{element_slug}.yaml"
    if not element_yaml.is_file():
        raise FileNotFoundError(f"element YAML not found: {element_yaml}")
    if not png_path.is_file():
        raise FileNotFoundError(f"PNG not found: {png_path}")
    if not ifc_path.is_file():
        raise FileNotFoundError(f"IFC not found: {ifc_path}")

    picture_name = f"{element_slug}.png"
    picture_print_name = f"{element_slug}-print.tif"
    attachment_name = f"{element_slug}.ifc"

    MEDIA_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)

    picture_dest = MEDIA_IMAGES_DIR / picture_name
    attachment_dest = MEDIA_ATTACHMENTS_DIR / attachment_name
    shutil.copy2(png_path, picture_dest)
    shutil.copy2(ifc_path, attachment_dest)

    result: dict[str, Path] = {
        "picture": picture_dest,
        "attachment": attachment_dest,
        "yaml": element_yaml,
    }

    text = element_yaml.read_text(encoding="utf-8")
    text = _set_or_insert_link(text, "picture_link", picture_name)
    if print_path is not None:
        if not print_path.is_file():
            raise FileNotFoundError(f"print TIFF not found: {print_path}")
        picture_print_dest = MEDIA_IMAGES_DIR / picture_print_name
        shutil.copy2(print_path, picture_print_dest)
        text = _set_or_insert_link(text, "picture_print_link", picture_print_name)
        result["picture_print"] = picture_print_dest
    text = _set_or_insert_link(text, "attachment_link", attachment_name)
    # Keep legacy model_link in sync for older readers in this add-ons repo
    text = _set_or_insert_link(text, "model_link", attachment_name)
    element_yaml.write_text(text, encoding="utf-8")

    return result
