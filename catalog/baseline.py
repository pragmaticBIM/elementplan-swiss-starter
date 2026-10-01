"""Shared spatial-structure baseline for models, attributes, and the book.

Project, Site, Building, Storey, and the survey reference point are required in
every IFC model deliverable and every use case. Declare them once here; models
opt in with ``includes_spatial_baseline: true``. Their attributes list every
active concrete workflow, because the editor resolves each
``needed_for_workflows`` entry and rejects the ``*`` token. The book still
treats that full list like ``*``: it omits these rows from per-use-case tables
and shows a short shared note.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = Path(__file__).resolve().parent / "baseline-spatial-structure.yaml"

ALL_WORKFLOWS_TOKEN = "*"
INCLUDES_SPATIAL_BASELINE_KEY = "includes_spatial_baseline"


@lru_cache(maxsize=1)
def load_spatial_baseline() -> dict[str, Any]:
    data = yaml.safe_load(BASELINE_PATH.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid baseline file: {BASELINE_PATH}")
    return data


def spatial_baseline_element_ids() -> tuple[str, ...]:
    raw = load_spatial_baseline().get("elements") or []
    return tuple(str(item) for item in raw if str(item).strip())


def is_all_workflows_token(value: Any) -> bool:
    return str(value or "").strip() == ALL_WORKFLOWS_TOKEN


def workflow_refs(attr: dict[str, Any] | None) -> list[str]:
    refs = (attr or {}).get("needed_for_workflows") or []
    if not isinstance(refs, list):
        return []
    return [str(item) for item in refs if str(item).strip()]


def attribute_applies_to_all_workflows(
    attr: dict[str, Any] | None,
    workflows: Iterable[dict[str, Any]] | None = None,
) -> bool:
    """True for the ``*`` token or a list that covers every active concrete workflow."""
    refs = workflow_refs(attr)
    if any(is_all_workflows_token(ref) for ref in refs):
        return True
    if workflows is None:
        return False
    expected = active_concrete_workflow_ids(workflows)
    if not expected:
        return False
    return set(expected) <= set(refs)


def attribute_applies_to_workflow(
    attr: dict[str, Any] | None,
    workflow_id: str,
) -> bool:
    """True if the attribute is required for ``workflow_id`` (incl. ``*``)."""
    wf_id = str(workflow_id or "").strip()
    if not wf_id:
        return False
    refs = workflow_refs(attr)
    if any(is_all_workflows_token(ref) for ref in refs):
        return True
    return wf_id in refs


def resolve_needed_for_workflows(
    attr: dict[str, Any] | None,
    all_workflow_ids: Iterable[str],
) -> list[str]:
    """Expand ``*`` to ``all_workflow_ids``; otherwise return the listed IDs."""
    refs = workflow_refs(attr)
    if any(is_all_workflows_token(ref) for ref in refs):
        return sorted({str(item) for item in all_workflow_ids if str(item).strip()})
    return list(refs)


def expand_included_elements(container: dict[str, Any] | None) -> list[str]:
    """Effective ``included_elements``, prepending the spatial baseline when opted in."""
    item = container or {}
    listed = [str(x) for x in (item.get("included_elements") or []) if str(x).strip()]
    if not item.get(INCLUDES_SPATIAL_BASELINE_KEY):
        return listed
    baseline = list(spatial_baseline_element_ids())
    seen = set(baseline)
    return baseline + [eid for eid in listed if eid not in seen]


def active_concrete_workflow_ids(workflows: Iterable[dict[str, Any]]) -> list[str]:
    """Active child workflows (have a parent) — the expansion target for ``*``."""
    ids: list[str] = []
    for workflow in workflows:
        if not isinstance(workflow, dict):
            continue
        wf_id = str(workflow.get("id") or "").strip()
        if not wf_id:
            continue
        if workflow.get("status") not in (None, "active"):
            continue
        if not workflow.get("parent_workflow"):
            continue
        ids.append(wf_id)
    ids.sort()
    return ids
