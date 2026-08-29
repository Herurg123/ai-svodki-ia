#!/usr/bin/env python3
"""Deterministic P4 regional-health viability refresh.

Primary regional health is intentionally Search-derived. This module may only
re-open a previously healthy Primary region when the exact Primary regional
candidates that survived the Primary final cap are later proven non-viable by
freshness/editorial filtering. It never closes an already-open Search gap and
never treats Pulse-only or unrelated later candidates as proof that Primary was
healthy.

No network, model, or search call is performed here.
"""
from __future__ import annotations

import copy
from typing import Any

REGIONAL_HEALTH_VIABILITY_VERSION = 1
ELIGIBLE_RECOMMENDATIONS = frozenset({"include", "consider"})
REGION_DIRECTIONS: dict[str, tuple[str, ...]] = {
    "asia": ("china_asia_models", "china_asia_integrations"),
    "russia": ("russia",),
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _title_key(candidate: Any) -> str:
    if not isinstance(candidate, dict):
        return ""
    return _clean(candidate.get("title")).casefold()


def _source_urls(candidate: Any) -> frozenset[str]:
    if not isinstance(candidate, dict):
        return frozenset()
    urls: set[str] = set()
    primary_url = candidate.get("primary_url")
    if isinstance(primary_url, str) and primary_url.strip():
        urls.add(primary_url.strip())
    rows = [candidate.get("primary_source"), *(candidate.get("supporting_sources") or [])]
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = row.get("url")
        if isinstance(url, str) and url.strip():
            urls.add(url.strip())
    return frozenset(urls)


def _same_candidate(left: Any, right: Any) -> bool:
    left_title = _title_key(left)
    right_title = _title_key(right)
    if left_title and left_title == right_title:
        return True
    left_urls = _source_urls(left)
    right_urls = _source_urls(right)
    return bool(left_urls and right_urls and left_urls.intersection(right_urls))


def candidate_viable(candidate: Any) -> bool:
    """Return post-freshness/editorial viability without inventing stricter policy."""
    if not isinstance(candidate, dict):
        return False
    if candidate.get("recommendation") not in ELIGIBLE_RECOMMENDATIONS:
        return False
    if candidate.get("event_freshness_status") == "stale":
        return False
    if candidate.get("freshness_status") == "old_reprint":
        return False
    return True


def _regional_raw_candidates(primary_report: dict[str, Any], region: str) -> list[dict[str, Any]] | None:
    direction_ids = REGION_DIRECTIONS[region]
    directions = primary_report.get("directions")
    if not isinstance(directions, list):
        return None
    by_id = {
        str(item.get("direction_id")): item
        for item in directions
        if isinstance(item, dict) and item.get("direction_id")
    }
    selected: list[dict[str, Any]] = []
    for direction_id in direction_ids:
        row = by_id.get(direction_id)
        if not isinstance(row, dict):
            return None
        raw = row.get("raw_candidates")
        if not isinstance(raw, list):
            return None
        selected.extend(copy.deepcopy(item) for item in raw if isinstance(item, dict))
    return selected


def _primary_final_candidates(primary_report: dict[str, Any]) -> list[dict[str, Any]] | None:
    rows = primary_report.get("final_candidates")
    if not isinstance(rows, list):
        return None
    return [copy.deepcopy(item) for item in rows if isinstance(item, dict)]


def _regional_final_candidates(
    primary_report: dict[str, Any], region: str
) -> list[dict[str, Any]] | None:
    raw = _regional_raw_candidates(primary_report, region)
    final = _primary_final_candidates(primary_report)
    if raw is None or final is None:
        return None
    matched: list[dict[str, Any]] = []
    for candidate in final:
        if any(_same_candidate(candidate, regional) for regional in raw):
            matched.append(candidate)
    return matched


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
            if _same_candidate(primary, current):
                found_index = index
                break
        if found_index is None:
            unmatched += 1
            continue
        used.add(found_index)
        matched.append(current_candidates[found_index])
    return matched, unmatched


def refresh_regional_health(
    *, primary_report: dict[str, Any], current_research: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Re-open false-negative regional health after deterministic filtering.

    Safety rules:
    - existing Search-derived gaps remain open;
    - a healthy region re-opens only with complete Primary provenance evidence;
    - unrelated Pulse/Hybrid/Coverage candidates cannot close or rescue the flag;
    - missing or identity-ambiguous evidence preserves the prior state.
    """
    result = copy.deepcopy(current_research)
    health = result.get("regional_health")
    if not isinstance(health, dict):
        return result, {
            "version": REGIONAL_HEALTH_VIABILITY_VERSION,
            "status": "not_available",
            "changed": False,
            "reason": "current research has no regional_health object",
            "regions": {},
            "paid_api_calls": 0,
            "web_search_operations": 0,
        }
    current_candidates = result.get("candidates")
    if not isinstance(current_candidates, list):
        return result, {
            "version": REGIONAL_HEALTH_VIABILITY_VERSION,
            "status": "not_available",
            "changed": False,
            "reason": "current research has no candidates array",
            "regions": {},
            "paid_api_calls": 0,
            "web_search_operations": 0,
        }
    current_candidates = [item for item in current_candidates if isinstance(item, dict)]

    updated_health = copy.deepcopy(health)
    changed = False
    diagnostics: dict[str, Any] = {}

    for region in ("asia", "russia"):
        prior_row = health.get(region)
        if not isinstance(prior_row, dict):
            diagnostics[region] = {
                "status": "not_available",
                "changed": False,
                "reason": "regional health row missing",
            }
            continue

        row = copy.deepcopy(prior_row)
        row["viability_version"] = REGIONAL_HEALTH_VIABILITY_VERSION
        row["viability_stage"] = "post_freshness_editorial_pre_hybrid"
        prior_gap = prior_row.get("health_check_needed") is True
        row["health_check_needed_before_viability"] = prior_gap

        if prior_gap:
            row["viability_status"] = "already_open"
            row["reopened_after_filtering"] = False
            diagnostics[region] = {
                "status": "already_open",
                "changed": False,
                "health_check_needed": True,
            }
            updated_health[region] = row
            continue

        regional_final = _regional_final_candidates(primary_report, region)
        if regional_final is None:
            row["viability_status"] = "insufficient_primary_provenance"
            row["reopened_after_filtering"] = False
            diagnostics[region] = {
                "status": "insufficient_primary_provenance",
                "changed": False,
                "health_check_needed": False,
            }
            updated_health[region] = row
            continue

        row["primary_regional_final_candidates"] = len(regional_final)
        accepted_early = int(prior_row.get("accepted_candidates", 0) or 0)

        if accepted_early > 0 and not regional_final:
            row["health_check_needed"] = True
            row["reopened_after_filtering"] = True
            row["viability_status"] = "reopened_after_primary_final_cap"
            row["post_filter_matched_candidates"] = 0
            row["viable_candidates"] = 0
            changed = True
            diagnostics[region] = {
                "status": row["viability_status"],
                "changed": True,
                "health_check_needed": True,
                "viable_candidates": 0,
            }
            updated_health[region] = row
            continue

        if not regional_final:
            row["viability_status"] = "no_primary_regional_candidate"
            row["reopened_after_filtering"] = False
            diagnostics[region] = {
                "status": row["viability_status"],
                "changed": False,
                "health_check_needed": False,
                "viable_candidates": 0,
            }
            updated_health[region] = row
            continue

        matched, unmatched = _match_current(regional_final, current_candidates)
        row["post_filter_matched_candidates"] = len(matched)
        row["post_filter_unmatched_candidates"] = unmatched
        viable = [item for item in matched if candidate_viable(item)]
        row["viable_candidates"] = len(viable)

        if unmatched:
            row["viability_status"] = "identity_incomplete_preserved"
            row["reopened_after_filtering"] = False
            diagnostics[region] = {
                "status": row["viability_status"],
                "changed": False,
                "health_check_needed": False,
                "matched": len(matched),
                "unmatched": unmatched,
                "viable_candidates": len(viable),
            }
        elif viable:
            row["viability_status"] = "viable"
            row["reopened_after_filtering"] = False
            diagnostics[region] = {
                "status": "viable",
                "changed": False,
                "health_check_needed": False,
                "viable_candidates": len(viable),
            }
        else:
            row["health_check_needed"] = True
            row["viability_status"] = "reopened_after_filtering"
            row["reopened_after_filtering"] = True
            changed = True
            diagnostics[region] = {
                "status": row["viability_status"],
                "changed": True,
                "health_check_needed": True,
                "viable_candidates": 0,
            }
        updated_health[region] = row

    updated_health["viability_version"] = REGIONAL_HEALTH_VIABILITY_VERSION
    updated_health["viability_stage"] = "post_freshness_editorial_pre_hybrid"
    updated_health["publication_quota"] = False
    result["regional_health"] = updated_health
    return result, {
        "version": REGIONAL_HEALTH_VIABILITY_VERSION,
        "status": "complete",
        "changed": changed,
        "regions": diagnostics,
        "policy": (
            "Regional health may only re-open when the Search-derived Primary "
            "regional candidates no longer have a viable post-freshness/editorial "
            "survivor. Existing Search gaps never close here and no publication "
            "quota is introduced."
        ),
        "paid_api_calls": 0,
        "web_search_operations": 0,
    }
