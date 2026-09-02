#!/usr/bin/env python3
"""Volume-independent deterministic health summary for digest discovery lanes.

This module only interprets already-saved retrieval diagnostics. It performs no
network access, OpenAI call, Web Search operation, editorial mutation, or
publication gating. Story count is deliberately excluded from health scoring: a
full-volume digest can still be retrieval-degraded.
"""
from __future__ import annotations

import copy
from typing import Any

DISCOVERY_HEALTH_VERSION = 1
HEALTHY = "healthy"
DEGRADED = "degraded"
INDETERMINATE = "indeterminate"


def _lane(status: str, reasons: list[str], **details: Any) -> dict[str, Any]:
    return {
        "status": status,
        "reasons": reasons,
        "details": details,
    }


def _primary_health(primary: Any) -> dict[str, Any]:
    if not isinstance(primary, dict):
        return _lane(INDETERMINATE, ["primary_report_missing"])
    budget = primary.get("search_budget") if isinstance(primary.get("search_budget"), dict) else {}
    completed = int(budget.get("completed_calls", 0) or 0)
    maximum = int(budget.get("maximum_calls", 12) or 12)
    directions = [row for row in primary.get("directions") or [] if isinstance(row, dict)]
    incomplete = [
        str(row.get("direction_id") or "unknown")
        for row in directions
        if row.get("status") not in {"complete", "complete_with_gaps"}
    ]
    zero_raw = [
        str(row.get("direction_id") or "unknown")
        for row in directions
        if isinstance(row.get("raw_candidates"), list) and len(row.get("raw_candidates") or []) == 0
    ]
    reasons: list[str] = []
    if primary.get("status") != "complete":
        reasons.append(f"primary_status:{primary.get('status') or 'missing'}")
    if completed < maximum:
        reasons.append(f"mandatory_searches_incomplete:{completed}/{maximum}")
    if incomplete:
        reasons.append("incomplete_directions:" + ",".join(incomplete))
    return _lane(
        DEGRADED if reasons else HEALTHY,
        reasons,
        completed_searches=completed,
        maximum_searches=maximum,
        direction_count=len(directions),
        zero_raw_directions=zero_raw,
        zero_raw_alone_is_not_degradation=True,
    )


def _pulse_health(pulse: Any) -> dict[str, Any]:
    if not isinstance(pulse, dict):
        return _lane(INDETERMINATE, ["source_pulse_report_missing"])
    snapshot = pulse.get("snapshot") if isinstance(pulse.get("snapshot"), dict) else {}
    summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}
    report_status = str(pulse.get("status") or "missing")
    source_status = str(summary.get("source_health_status") or "missing")
    degraded_ids = sorted({str(item) for item in summary.get("degraded_source_ids") or [] if str(item)})
    reasons: list[str] = []
    if report_status != "complete":
        reasons.append(f"source_pulse_status:{report_status}")
    if source_status != "complete":
        reasons.append(f"source_health_status:{source_status}")
    if degraded_ids:
        reasons.append("degraded_sources:" + ",".join(degraded_ids))
    promotion = pulse.get("promotion") if isinstance(pulse.get("promotion"), dict) else {}
    return _lane(
        DEGRADED if reasons else HEALTHY,
        reasons,
        configured_sources=int(summary.get("configured_sources", 0) or 0),
        sources_ok=int(summary.get("sources_ok", 0) or 0),
        sources_unavailable=int(summary.get("sources_unavailable", 0) or 0),
        sources_parse_error=int(summary.get("sources_parse_error", 0) or 0),
        degraded_source_ids=degraded_ids,
        lead_count=int(summary.get("lead_count", 0) or 0),
        promoted_count=int(promotion.get("promoted_count", 0) or 0),
    )


def _agency_health(agency: Any) -> dict[str, Any]:
    if not isinstance(agency, dict):
        return _lane(INDETERMINATE, ["agency_rescue_report_missing"])
    state = str(agency.get("state") or "missing")
    executed = bool(agency.get("executed"))
    reasons: list[str] = []
    if state in {"search_failed", "diagnostics_missing"}:
        reasons.append(f"agency_state:{state}")
        status = DEGRADED
    elif state in {"search_started", "indeterminate_after_interruption", "missing"}:
        reasons.append(f"agency_state:{state}")
        status = INDETERMINATE
    else:
        status = HEALTHY

    health = agency.get("agency_health") if isinstance(agency.get("agency_health"), dict) else {}
    if str(health.get("status") or "") in {
        "identity_incomplete_preserved",
        "insufficient_primary_provenance_preserved",
        "current_candidates_missing_preserved",
    }:
        reasons.append(f"agency_health:{health.get('status')}")
        status = INDETERMINATE if status != DEGRADED else status

    metadata_available = agency.get("source_metadata_available")
    if executed and metadata_available is False:
        reasons.append("search_source_metadata_unavailable")
        status = INDETERMINATE if status != DEGRADED else status
    return _lane(
        status,
        reasons,
        triggered=bool(agency.get("triggered")),
        trigger_reason=agency.get("trigger_reason"),
        executed=executed,
        state=state,
        search_operations=int(agency.get("search_operation_count_contribution", 0) or 0),
        source_metadata_available=metadata_available,
        accepted_count=int(agency.get("accepted_count", 0) or 0),
    )


def _hybrid_health(hybrid: Any) -> dict[str, Any]:
    if not isinstance(hybrid, dict):
        return _lane(INDETERMINATE, ["hybrid_report_missing"])
    retrieval = hybrid.get("retrieval_health") if isinstance(hybrid.get("retrieval_health"), dict) else {}
    retrieval_status = str(retrieval.get("status") or "missing")
    reasons: list[str] = []
    if hybrid.get("status") not in {"complete", "complete_with_gaps"}:
        reasons.append(f"hybrid_status:{hybrid.get('status') or 'missing'}")
    if retrieval_status != "complete":
        reasons.append(f"retrieval_health:{retrieval_status}")
    unresolved = [str(item) for item in retrieval.get("unresolved_regional_gaps") or [] if str(item)]
    if unresolved:
        reasons.append("unresolved_regional_gaps:" + ",".join(unresolved))
    status = DEGRADED if reasons else HEALTHY
    return _lane(
        status,
        reasons,
        retrieval_status=retrieval_status,
        regional_gaps=[str(item) for item in retrieval.get("regional_gaps") or []],
        unresolved_regional_gaps=unresolved,
        conditional_paid_extension_used=bool(
            retrieval.get("hybrid_conditional_paid_extension_used")
        ),
        completed_searches=int((hybrid.get("search_budget") or {}).get("completed_calls", 0) or 0),
    )


def _coverage_health(coverage: Any) -> dict[str, Any]:
    if not isinstance(coverage, dict):
        return _lane(INDETERMINATE, ["coverage_report_missing"])
    required = [str(item) for item in coverage.get("required_directions") or []]
    checked = [str(item) for item in coverage.get("checked_directions") or []]
    partial = [str(item) for item in coverage.get("partial_directions") or []]
    unchecked = [str(item) for item in coverage.get("unchecked_directions") or []]
    quality = coverage.get("retrieval_quality") if isinstance(coverage.get("retrieval_quality"), dict) else {}
    quality_status = str(quality.get("status") or "missing")
    reasons: list[str] = []
    if coverage.get("status") not in {"ok", "editorial_stop"}:
        reasons.append(f"coverage_status:{coverage.get('status') or 'missing'}")
    if coverage.get("audit_state") != "completed_usable":
        reasons.append(f"audit_state:{coverage.get('audit_state') or 'missing'}")
    if partial:
        reasons.append("partial_directions:" + ",".join(partial))
    if unchecked or (required and set(checked) != set(required)):
        reasons.append("mandatory_coverage_incomplete")
    if quality_status not in {"complete", "missing"}:
        reasons.append(f"retrieval_quality:{quality_status}")
    status = DEGRADED if reasons else HEALTHY
    return _lane(
        status,
        reasons,
        audit_status=coverage.get("audit_status"),
        checked_directions=len(checked),
        required_directions=len(required),
        retrieval_quality_status=quality_status,
        completed_searches=int((coverage.get("search_budget") or {}).get("completed_calls", 0) or 0),
        bounded_gaps_usable=bool(
            coverage.get("audit_status") == "complete_with_gaps" and not reasons
        ),
    )


def evaluate_discovery_health(
    *, primary: Any, pulse: Any, agency: Any, hybrid: Any, coverage: Any
) -> dict[str, Any]:
    """Aggregate existing lane diagnostics without using story volume as evidence."""
    lanes = {
        "primary": _primary_health(primary),
        "source_pulse": _pulse_health(pulse),
        "major_agencies": _agency_health(agency),
        "hybrid": _hybrid_health(hybrid),
        "coverage": _coverage_health(coverage),
    }
    degraded = [name for name, lane in lanes.items() if lane["status"] == DEGRADED]
    indeterminate = [name for name, lane in lanes.items() if lane["status"] == INDETERMINATE]
    if degraded:
        overall = DEGRADED
    elif indeterminate:
        overall = INDETERMINATE
    else:
        overall = HEALTHY
    return {
        "version": DISCOVERY_HEALTH_VERSION,
        "status": overall,
        "story_volume_independent": True,
        "publication_gate": False,
        "paid_api_calls": 0,
        "web_search_operations": 0,
        "degraded_lanes": degraded,
        "indeterminate_lanes": indeterminate,
        "lanes": copy.deepcopy(lanes),
        "policy": (
            "Story count never proves retrieval health. Explicit degraded diagnostics win; "
            "missing or provenance-ambiguous diagnostics remain indeterminate."
        ),
    }
