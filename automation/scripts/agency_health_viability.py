#!/usr/bin/env python3
"""Deterministic post-freshness viability for the Primary major-agency lane.

The early Primary ``major_agencies`` accepted count is not sufficient evidence
that the lane is still healthy by the time pre-Hybrid rescue runs. A candidate
may have been removed by the Primary final cap or may have become non-viable
through Event/Source Freshness and first-editorial filtering.

This module reconstructs only Search-derived Primary agency provenance and asks
whether at least one of those exact candidates still has a viable
``include|consider`` survivor. Pulse-only or unrelated later candidates cannot
impersonate Primary agency health. Ambiguous identity preserves the old
no-rescue state rather than spending the reserved Reuters slot.

No network, model, OpenAI, or Web Search call is performed here.
"""
from __future__ import annotations

import copy
from typing import Any

from story_coverage import normalize_url

AGENCY_HEALTH_TRIGGER_VERSION = 2
ELIGIBLE_RECOMMENDATIONS = frozenset({"include", "consider"})
POST_FILTER_TRIGGER_REASON = "major_agencies_no_viable_survivor_after_filtering"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _title_key(candidate: Any) -> str:
    if not isinstance(candidate, dict):
        return ""
    return _clean(candidate.get("title")).casefold()


def _normalized_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        return normalize_url(raw)
    except ValueError:
        return raw


def _source_urls(candidate: Any) -> frozenset[str]:
    if not isinstance(candidate, dict):
        return frozenset()
    urls: set[str] = set()
    for raw in (candidate.get("primary_url"),):
        normalized = _normalized_url(raw)
        if normalized:
            urls.add(normalized)
    rows = [candidate.get("primary_source"), *(candidate.get("supporting_sources") or [])]
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = _normalized_url(row.get("url"))
        if normalized:
            urls.add(normalized)
    return frozenset(urls)


def same_candidate(left: Any, right: Any) -> bool:
    """Match provenance conservatively, preferring source URL identity.

    If both rows expose source URLs, at least one URL must overlap. Same-title
    rows on different sources are not equivalent because a Pulse/later candidate
    must not masquerade as the Primary candidate whose survival is being tested.
    Title equality is used only when at least one side lacks source identity.
    """
    left_urls = _source_urls(left)
    right_urls = _source_urls(right)
    if left_urls and right_urls:
        return bool(left_urls.intersection(right_urls))
    left_title = _title_key(left)
    right_title = _title_key(right)
    return bool(left_title and left_title == right_title)


def candidate_viable(candidate: Any) -> bool:
    """Use the same conservative post-filter viability semantics as regional P4."""
    if not isinstance(candidate, dict):
        return False
    if candidate.get("recommendation") not in ELIGIBLE_RECOMMENDATIONS:
        return False
    if candidate.get("event_freshness_status") == "stale":
        return False
    if candidate.get("freshness_status") == "old_reprint":
        return False
    return True


def _major_agencies_row(primary_report: dict[str, Any]) -> dict[str, Any] | None:
    rows = primary_report.get("directions")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, dict) and row.get("direction_id") == "major_agencies":
            return row
    return None


def _primary_final_candidates(primary_report: dict[str, Any]) -> list[dict[str, Any]] | None:
    rows = primary_report.get("final_candidates")
    if not isinstance(rows, list):
        return None
    return [copy.deepcopy(item) for item in rows if isinstance(item, dict)]


def _major_final_candidates(
    primary_report: dict[str, Any], raw_candidates: list[dict[str, Any]]
) -> list[dict[str, Any]] | None:
    final = _primary_final_candidates(primary_report)
    if final is None:
        return None
    return [
        candidate
        for candidate in final
        if any(same_candidate(candidate, raw) for raw in raw_candidates)
    ]


def _match_current(
    primary_candidates: list[dict[str, Any]], current_candidates: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int]:
    matched: list[dict[str, Any]] = []
    unmatched = 0
    used: set[int] = set()
    for primary in primary_candidates:
        found_index: int | None = None
        for index, current in enumerate(current_candidates):
            if index in used:
                continue
            if same_candidate(primary, current):
                found_index = index
                break
        if found_index is None:
            unmatched += 1
            continue
        used.add(found_index)
        matched.append(current_candidates[found_index])
    return matched, unmatched


def evaluate_agency_health(
    *, primary_report: dict[str, Any], current_research: dict[str, Any]
) -> tuple[bool, str | None, dict[str, int | str | None], dict[str, Any]]:
    """Return the current rescue trigger and zero-paid diagnostics.

    Early raw/accepted gaps preserve their historical trigger reasons. When the
    early lane was healthy, rescue is newly allowed only if complete provenance
    proves that no Primary major-agency survivor remains viable after filtering.
    Missing/ambiguous provenance never creates a paid trigger.
    """
    row = _major_agencies_row(primary_report)
    base_facts: dict[str, int | str | None] = {
        "major_agencies_status": None,
        "major_agencies_raw_count": 0,
        "major_agencies_accepted_count": 0,
        "agency_health_trigger_version": AGENCY_HEALTH_TRIGGER_VERSION,
        "major_agencies_primary_final_count": 0,
        "major_agencies_post_filter_matched_count": 0,
        "major_agencies_post_filter_unmatched_count": 0,
        "major_agencies_post_filter_viable_count": 0,
    }
    diagnostics: dict[str, Any] = {
        "version": AGENCY_HEALTH_TRIGGER_VERSION,
        "stage": "post_freshness_editorial_pre_hybrid",
        "status": "not_available",
        "triggered": False,
        "trigger_reason": None,
        "paid_api_calls": 0,
        "web_search_operations": 0,
        "policy": (
            "Only Search-derived Primary major-agency candidates may prove lane health. "
            "Ambiguous identity preserves the prior state and never spends the Reuters slot."
        ),
    }
    if not isinstance(row, dict):
        diagnostics["reason"] = "major_agencies direction missing"
        return False, None, base_facts, diagnostics

    status = _clean(row.get("status"))
    raw = row.get("raw_candidates")
    raw_candidates = [copy.deepcopy(item) for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    raw_count = len(raw) if isinstance(raw, list) else 0
    accepted_count = int(row.get("accepted_count", 0) or 0)
    base_facts.update(
        {
            "major_agencies_status": status or None,
            "major_agencies_raw_count": raw_count,
            "major_agencies_accepted_count": accepted_count,
        }
    )
    diagnostics.update(
        {
            "major_agencies_status": status or None,
            "raw_count": raw_count,
            "accepted_count": accepted_count,
        }
    )
    if status not in {"complete", "complete_with_gaps"}:
        diagnostics["status"] = "primary_direction_incomplete_preserved"
        return False, None, base_facts, diagnostics
    if raw_count == 0:
        diagnostics.update(
            {"status": "early_gap", "triggered": True, "trigger_reason": "major_agencies_raw_zero"}
        )
        return True, "major_agencies_raw_zero", base_facts, diagnostics
    if accepted_count == 0:
        diagnostics.update(
            {"status": "early_gap", "triggered": True, "trigger_reason": "major_agencies_accepted_zero"}
        )
        return True, "major_agencies_accepted_zero", base_facts, diagnostics

    current = current_research.get("candidates")
    if not isinstance(current, list):
        diagnostics["status"] = "current_candidates_missing_preserved"
        return False, None, base_facts, diagnostics
    current_candidates = [item for item in current if isinstance(item, dict)]

    major_final = _major_final_candidates(primary_report, raw_candidates)
    if major_final is None:
        diagnostics["status"] = "insufficient_primary_provenance_preserved"
        return False, None, base_facts, diagnostics

    base_facts["major_agencies_primary_final_count"] = len(major_final)
    diagnostics["primary_final_count"] = len(major_final)
    if accepted_count > 0 and not major_final:
        diagnostics.update(
            {
                "status": "no_viable_survivor_after_primary_final_cap",
                "triggered": True,
                "trigger_reason": POST_FILTER_TRIGGER_REASON,
                "matched_count": 0,
                "unmatched_count": 0,
                "viable_count": 0,
            }
        )
        return True, POST_FILTER_TRIGGER_REASON, base_facts, diagnostics

    matched, unmatched = _match_current(major_final, current_candidates)
    viable = [item for item in matched if candidate_viable(item)]
    base_facts.update(
        {
            "major_agencies_post_filter_matched_count": len(matched),
            "major_agencies_post_filter_unmatched_count": unmatched,
            "major_agencies_post_filter_viable_count": len(viable),
        }
    )
    diagnostics.update(
        {
            "matched_count": len(matched),
            "unmatched_count": unmatched,
            "viable_count": len(viable),
        }
    )
    if unmatched:
        diagnostics["status"] = "identity_incomplete_preserved"
        return False, None, base_facts, diagnostics
    if viable:
        diagnostics["status"] = "viable_primary_agency_survivor"
        return False, None, base_facts, diagnostics

    diagnostics.update(
        {
            "status": "no_viable_survivor_after_filtering",
            "triggered": True,
            "trigger_reason": POST_FILTER_TRIGGER_REASON,
        }
    )
    return True, POST_FILTER_TRIGGER_REASON, base_facts, diagnostics


def prior_not_triggered_recheck_allowed(prior: Any) -> bool:
    """A zero-spend not-triggered report may be deterministically reconsidered."""
    if not isinstance(prior, dict) or prior.get("state") != "not_triggered":
        return False
    if bool(prior.get("executed")):
        return False
    if int(prior.get("search_operation_reserved", 0) or 0) != 0:
        return False
    return int(prior.get("search_operation_count_contribution", 0) or 0) == 0
