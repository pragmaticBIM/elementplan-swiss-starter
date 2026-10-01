"""Print masters: opaque Device CMYK TIFF, Typst ingest via 1-page PDF."""

from __future__ import annotations

import zlib
from pathlib import Path

from PIL import Image

# 4.6 cm at 600 dpi is ~1087 px; 1200² is a small even oversample for the GPU.
PRINT_RESOLUTION = (1200, 1200)
PRINT_DPI = (600, 600)
# Matches render.isometric._BG_COLOR (0.93, 0.93, 0.93).
PRINT_BG_RGB = (237, 237, 237)


def flatten_opaque(
    image: Image.Image,
    background: tuple[int, int, int] = PRINT_BG_RGB,
) -> Image.Image:
    """Composite any alpha onto the print background (no PDF smask)."""
    if image.mode == "RGBA":
        bg = Image.new("RGB", image.size, background)
        bg.paste(image, mask=image.getchannel("A"))
        return bg
    if image.mode == "CMYK":
        return image
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def to_print_cmyk(image: Image.Image) -> Image.Image:
    """Flatten, size to the print square, and convert to Device CMYK."""
    rgb = flatten_opaque(image)
    if rgb.mode == "CMYK":
        rgb = rgb.convert("RGB")
    if rgb.size != PRINT_RESOLUTION:
        rgb = rgb.resize(PRINT_RESOLUTION, Image.Resampling.LANCZOS)
    return rgb.convert("CMYK")


def save_print_tiff(image: Image.Image, path: str | Path) -> Path:
    """Write a ZIP-compressed CMYK TIFF at ``PRINT_DPI`` (no JPEG)."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    to_print_cmyk(image).save(
        dest,
        format="TIFF",
        compression="tiff_deflate",
        dpi=PRINT_DPI,
    )
    return dest


def raster_to_print_tiff(src: str | Path, dest: str | Path) -> Path:
    """Convert an existing RGB/RGBA raster to the print TIFF master."""
    with Image.open(src) as im:
        return save_print_tiff(im, dest)


def cmyk_tiff_to_pdf(tif_path: str | Path, pdf_path: str | Path) -> Path:
    """Wrap a CMYK TIFF as a 1-page DeviceCMYK PDF (Flate) for Typst ``#image``."""
    src = Path(tif_path)
    dest = Path(pdf_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        cmyk = im if im.mode == "CMYK" else to_print_cmyk(im)
        dpi_info = im.info.get("dpi") or PRINT_DPI
        dpi_x = float(dpi_info[0]) if isinstance(dpi_info, tuple) else float(PRINT_DPI[0])
        width, height = cmyk.size
        raw = cmyk.tobytes()
    compressed = zlib.compress(raw, 9)
    dpi = dpi_x if dpi_x > 0 else float(PRINT_DPI[0])
    w_pt = width / dpi * 72.0
    h_pt = height / dpi * 72.0
    contents = (
        f"q\n{w_pt:.4f} 0 0 {h_pt:.4f} 0 0 cm\n/Im0 Do\nQ\n"
    ).encode("ascii")
    image_dict = (
        f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} "
        f"/ColorSpace /DeviceCMYK /BitsPerComponent 8 /Interpolate false "
        f"/Filter /FlateDecode /Length {len(compressed)} >>\n"
        f"stream\n"
    ).encode("ascii") + compressed + b"\nendstream"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w_pt:.4f} {h_pt:.4f}] "
            f"/Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>"
        ).encode("ascii"),
        image_dict,
        (
            f"<< /Length {len(contents)} >>\nstream\n".encode("ascii")
            + contents
            + b"endstream"
        ),
    ]
    _write_pdf(objects, dest)
    return dest


def _write_pdf(objects: list[bytes], path: Path) -> None:
    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    parts: list[bytes] = [header]
    offsets: list[int] = []
    pos = len(header)
    for i, body in enumerate(objects, start=1):
        offsets.append(pos)
        obj = f"{i} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
        parts.append(obj)
        pos += len(obj)
    xref_items = [
        f"xref\n0 {len(objects) + 1}\n".encode("ascii"),
        b"0000000000 65535 f \n",
    ]
    for off in offsets:
        xref_items.append(f"{off:010d} 00000 n \n".encode("ascii"))
    xref = b"".join(xref_items)
    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{pos}\n%%EOF\n"
    ).encode("ascii")
    path.write_bytes(b"".join(parts) + xref + trailer)
