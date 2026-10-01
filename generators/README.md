# IFC catalog sample generators

Python tools that build small IFC vignettes and isometric PNG previews for Elementplan catalog cards (`picture_link` / `attachment_link` under `media/`).

## Setup

From the repository root (this template, or the add-ons source repo):

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

OpenGL / OSMesa may be required for `pyrender` isometric renders (exact packages depend on your OS).

## Generate previews

```bash
# All sample catalog entries → output/{id}.ifc + {id}.png + {id}-print.tif
# Entries with attach_element also update media/ and element YAML links
python runner.py --output-dir output

# One entry only
python runner.py --output-dir output --only space-office-01
```

Each entry writes:

| File | Use |
| --- | --- |
| `{id}.png` | Catalog card (1024², brand engraving + watermark) |
| `{id}-print.tif` | Print asset (1200² @ 600 DPI, Device CMYK, no engraving/watermark) |

## Layout

| Path | Role |
| --- | --- |
| `catalog/sample_data.py` | Sample geometry + which element to attach |
| `catalog/mapping.py` | Catalog entry → generator params |
| `catalog/schema.py` | Defaults from `elements/*.yaml` |
| `catalog/attach.py` | Copy PNG/IFC into `media/` and set YAML links |
| `generators/` | IFC builders (space, slab, covering, …) |
| `render/isometric.py` | PNG isometric render |
| `runner.py` | Batch CLI |
| `media/images/` | Published rasters (`picture_link` PNG / `picture_print_link` TIFF) |
| `media/attachments/` | Published IFCs referenced by `attachment_link` |

## Notes

- Units are metres; Body representation uses Model/Body/MODEL_VIEW.
- Prefer ifcopenshell API helpers over raw entity construction.
- Attribute names and property datatypes come from the element YAML — do not invent IFC fields.
