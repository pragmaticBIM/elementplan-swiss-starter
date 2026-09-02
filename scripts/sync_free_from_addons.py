#!/usr/bin/env python3
"""Sync the free Elementplan baseline from the add-ons source-of-truth repo.

Reads ../elementplan_pragmaticbim_swiss_data_add_ons/distribution.yaml (or
--addons-dir), slices free.workflows (+ parents), copies free.include folders
wholesale, and rewrites this template's entity folders.

Does not touch project.yaml, README.md, LICENSE, or .github/.

Usage:
  python scripts/sync_free_from_addons.py
  python scripts/sync_free_from_addons.py --addons-dir /path/to/add_ons
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TEMPLATE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ADDONS = TEMPLATE_ROOT.parent / "elementplan_pragmaticbim_swiss_data_add_ons"

# Folders rewritten from the free workflow slice (attribute-level).
SLICED_FOLDERS = ("domains", "workflows", "elements", "values", "models")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--addons-dir",
        type=Path,
        default=DEFAULT_ADDONS,
        help="Path to elementplan_pragmaticbim_swiss_data_add_ons",
    )
    p.add_argument(
        "--template-dir",
        type=Path,
        default=TEMPLATE_ROOT,
        help="Template repo root (default: parent of scripts/)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Load and slice only; do not write files",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    addons = args.addons_dir.resolve()
    template = args.template_dir.resolve()

    cfg_path = addons / "distribution.yaml"
    if not cfg_path.is_file():
        print(f"Missing distribution.yaml at {cfg_path}", file=sys.stderr)
        return 1

    scripts_dir = addons / "scripts"
    sys.path.insert(0, str(scripts_dir))
    from lib.slice_data import (  # noqa: E402
        copy_include_folders,
        load_distribution,
        load_entity_tree,
        normalize_include,
        resolve_free_workflow_ids,
        slice_for_workflows,
        write_entity_tree,
    )

    cfg = load_distribution(cfg_path)
    free = cfg.get("free") or {}
    if not isinstance(free, dict):
        print("distribution.yaml: free must be a mapping", file=sys.stderr)
        return 1
    try:
        workflow_ids = resolve_free_workflow_ids(free, addons)
    except (ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    includes = normalize_include(free.get("include") or [])

    data = load_entity_tree(addons)
    sliced = slice_for_workflows(data, workflow_ids)

    # When free.include copies phases wholesale, drop sliced phases to avoid dual write.
    write_folders = list(SLICED_FOLDERS)
    include_names = {str(x).strip().strip("/") for x in includes}
    if "phases" not in include_names:
        write_folders.append("phases")

    print(f"Add-ons:  {addons}")
    print(f"Template: {template}")
    print(f"Free workflows: {len(workflow_ids)} (+ parents → {len(sliced.get('workflows') or [])})")
    for folder in write_folders:
        print(f"  slice {folder}: {len(sliced.get(folder) or [])}")
    if includes:
        print(f"  include: {', '.join(includes)}")

    if args.dry_run:
        print("Dry run — no files written.")
        return 0

    written = write_entity_tree(template, sliced, folders=write_folders, wipe=True)
    # Keep models/.gitkeep if models slice is empty
    models_dir = template / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    gitkeep = models_dir / ".gitkeep"
    if not any(models_dir.glob("*.yaml")) and not gitkeep.exists():
        gitkeep.write_text("", encoding="utf-8")
        written.append("models/.gitkeep")

    included = copy_include_folders(addons, template, includes)
    written.extend(included)

    print(f"Wrote {len(written)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
