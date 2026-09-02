#!/usr/bin/env python3
"""Deterministic Primary Recall outcome diagnostics.

This module classifies already-saved per-direction evidence. It performs no
network access, OpenAI calls, Web Search operations, ranking, filtering, or
publication decisions. In particular, ``raw_candidates == []`` is split into
separate observable outcomes instead of being treated as one generic zero.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

PRIMARY_ZERO_OUTCOME_VERSION = 1

_COMPLETE_STATUSES = {"complete", "complete_with_gaps"}


def _items(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _search_items(api: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in _items(api.get("web_search_call_items"))
        if str(item.get("action_type") or "") == "search"
    ]


def source_metadata_state(api: Any) -> tuple[str, int]:
    """Return ``present|empty|unavailable`` plus distinct consulted-source count.

    ``action.sources=[]`` is evidence that source metadata was returned and the
    provider pool was empty. Missing/``null`` sources are not equivalent: they
    mean the provider did not expose source-pool metadata for that search action.
    """
    if not isinstance(api, dict):
        return "unavailable", 0

    consulted = _items(api.get("consulted_sources"))
    if consulted:
        return "present", len(consulted)

    saw_explicit_list = False
    explicit_sources: list[dict[str, Any]] = []
    for item in _search_items(api):
        action = item.get("action")
        if not isinstance(action, dict) or "sources" not in action:
            continue
        raw = action.get("sources")
        if isinstance(raw, list):
            saw_explicit_list = True
            explicit_sources.extend(_items(raw))

    if explicit_sources:
        return "present", len(explicit_sources)
    if saw_explicit_list:
        return "empty", 0
    return "unavailable", 0


def classify_direction(report: Any) -> dict[str, Any]:
    """Classify one saved Primary direction without changing its semantics."""
    row = report if isinstance(report, dict) else {}
    direction_id = str(row.get("direction_id") or "unknown")
    status = str(row.get("status") or "")
    raw = _items(row.get("raw_candidates"))
    model_rejections = _items(row.get("model_rejections"))
    validator_rejections = _items(row.get("validator_rejections"))
    accepted_count = int(row.get("accepted_count", 0) or 0)
    api = row.get("api") if isinstance(row.get("api"), dict) else {}
    completed_searches = int(
        row.get("web_search_calls_completed", api.get("web_search_calls_completed", 0)) or 0
    )
    metadata_state, consulted_count = source_metadata_state(api)

    if status not in _COMPLETE_STATUSES or completed_searches != 1:
        outcome = "technical_incomplete"
    elif raw:
        if accepted_count > 0:
            outcome = "candidate_accepted"
        elif validator_rejections:
            outcome = "validator_rejected_all"
        else:
            outcome = "raw_candidate_not_accepted"
    elif model_rejections:
        # This means the model emitted rejection rows and no candidate rows. It
        # does NOT prove that a particular independently missed event appeared in
        # the provider pool or that the model inspected that exact event.
        outcome = "model_rejections_only"
    elif metadata_state == "present":
        outcome = "provider_sources_present_no_candidate_or_rejection"
    elif metadata_state == "empty":
        outcome = "provider_source_pool_empty"
    else:
        outcome = "provider_source_metadata_unavailable"

    return {
        "direction_id": direction_id,
        "status": status or None,
        "raw_count": len(raw),
        "accepted_count": accepted_count,
        "model_rejection_count": len(model_rejections),
        "validator_rejection_count": len(validator_rejections),
        "web_search_calls_completed": completed_searches,
        "source_metadata_state": metadata_state,
        "consulted_source_count": consulted_count,
        "raw_zero": len(raw) == 0,
        "outcome": outcome,
    }


def build_primary_outcome_diagnostics(direction_reports: Any) -> dict[str, Any]:
    rows = [classify_direction(row) for row in _items(direction_reports)]
    zero_rows = [row for row in rows if row["raw_zero"]]
    counts = Counter(str(row["outcome"]) for row in rows)
    zero_counts = Counter(str(row["outcome"]) for row in zero_rows)
    return {
        "version": PRIMARY_ZERO_OUTCOME_VERSION,
        "status": "complete",
        "network_calls": 0,
        "openai_calls": 0,
        "web_search_operations": 0,
        "direction_count": len(rows),
        "raw_zero_direction_count": len(zero_rows),
        "outcome_counts": dict(sorted(counts.items())),
        "raw_zero_outcome_counts": dict(sorted(zero_counts.items())),
        "raw_zero_directions": [str(row["direction_id"]) for row in zero_rows],
        "directions": rows,
        "policy": (
            "diagnostic only: story volume and raw=0 never imply that a specific missed event "
            "was absent from the provider pool or rejected by the model without exact saved evidence"
        ),
    }
