#!/usr/bin/env python3
"""Stable public entrypoint for zero-budget Hybrid Completeness v2.

Production behavior lives in ``hybrid_search_completeness_v2.py``. The previous
regional wrapper is retained as ``hybrid_search_completeness_regional_v1.py`` so
recovery hooks and monkeypatch-oriented offline tests keep a stable compatibility
surface. Hybrid remains capped at four Web Search operations; the pre-Hybrid
Reuters rescue remains capped at one operation.
"""
from __future__ import annotations

from typing import Any

import agency_discovery_rescue_v4 as _agency_v4
import hybrid_search_completeness_v2 as _v2

for _name in dir(_v2):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_v2, _name)

REPOSITORY_ROOT = _v2.legacy.REPOSITORY_ROOT
PRODUCTION_PREVIEW_ROOT = _v2.legacy.PRODUCTION_PREVIEW_ROOT
RUNTIME_RESEARCH_ROOT = _v2.legacy.RUNTIME_RESEARCH_ROOT
run_agency_discovery_rescue = _agency_v4.run_agency_discovery_rescue
run_source_pulse_shadow = _v2.legacy.run_source_pulse_shadow
refresh_post_hybrid_fusion = _v2.legacy.refresh_post_hybrid_fusion
run_search_request = _v2.legacy.run_search_request

DEFAULT_MAXIMUM_SEARCH_CALLS = 4
FIXED_SEARCH_CALLS = 3
PIPELINE_MAXIMUM_SEARCH_OPERATIONS = 24
HYBRID_COMPLETENESS_VERSION = 2
REGIONAL_HEALTH_VERSION = 2


def __getattr__(name: str) -> Any:
    return getattr(_v2, name)


def _sync_compatibility_hooks() -> None:
    for name in (
        "REPOSITORY_ROOT",
        "PRODUCTION_PREVIEW_ROOT",
        "RUNTIME_RESEARCH_ROOT",
        "run_agency_discovery_rescue",
        "run_source_pulse_shadow",
        "refresh_post_hybrid_fusion",
        "run_search_request",
    ):
        if name not in globals():
            continue
        value = globals()[name]
        setattr(_v2, name, value)
        setattr(_v2.legacy, name, value)
        if hasattr(_v2.legacy._base, name):
            setattr(_v2.legacy._base, name, value)


def build_prompt(**kwargs: Any) -> str:
    _sync_compatibility_hooks()
    _v2._ensure_original_prompt_hook()
    return _v2.build_prompt(**kwargs)


def regional_health_query(gaps: tuple[str, ...]) -> str:
    return _v2.regional_health_query(gaps)


def _regional_gaps(research: dict[str, Any]) -> tuple[str, ...]:
    return _v2._regional_gaps(research)


def _pre_hybrid_source_freshness_gate(**kwargs: Any) -> dict[str, Any]:
    _sync_compatibility_hooks()
    return _v2.legacy._pre_hybrid_source_freshness_gate(**kwargs)


def _run_pre_hybrid_agency_rescue(**kwargs: Any) -> dict[str, Any]:
    _sync_compatibility_hooks()
    return _v2.legacy._run_pre_hybrid_agency_rescue(**kwargs)


def _annotate_retrieval_health(report: dict[str, Any]) -> dict[str, Any]:
    regional = report.get("regional_health")
    if not isinstance(regional, dict) or not regional.get("gaps"):
        report["retrieval_health"] = {
            "status": "complete_no_regional_gap",
            "regional_gaps": [],
            "unresolved_regional_gaps": [],
            "volume_completion_independent": True,
            "coverage_paid_search_trigger_unchanged": True,
            "additional_paid_searches": 0,
            "publication_quota": False,
        }
        return report
    gaps = [str(item) for item in regional.get("gaps") or [] if str(item)]
    checks = regional.get("checks")
    if not isinstance(checks, dict):
        checked = bool(regional.get("checked"))
        candidate_count = int(regional.get("candidate_count", 0) or 0)
        checks = {
            gap: {"checked": checked, "candidate_count": candidate_count}
            for gap in gaps
        }
    incomplete = [
        gap for gap in gaps
        if not isinstance(checks.get(gap), dict) or checks[gap].get("checked") is not True
    ]
    unresolved = [
        gap for gap in gaps
        if isinstance(checks.get(gap), dict)
        and checks[gap].get("checked") is True
        and int(checks[gap].get("candidate_count", 0) or 0) == 0
    ]
    if incomplete:
        status = "incomplete_regional_health_check"
    elif unresolved:
        status = "complete_with_regional_gaps"
    else:
        status = "regional_candidate_evidence_found"
    report["retrieval_health"] = {
        "status": status,
        "regional_gaps": gaps,
        "unresolved_regional_gaps": unresolved,
        "incomplete_regional_checks": incomplete,
        "volume_completion_independent": True,
        "coverage_paid_search_trigger_unchanged": True,
        "additional_paid_searches": 0,
        "publication_quota": False,
        "policy": (
            "A full-volume digest may still carry unresolved regional retrieval gaps. "
            "Zero-budget mode records the gap but does not launch extra Coverage searches."
        ),
    }
    return report


def run_hybrid_completeness(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _sync_compatibility_hooks()
    if "request_fn" not in kwargs:
        kwargs["request_fn"] = globals().get("run_search_request", _v2.legacy.run_search_request)
    report = _v2.run_hybrid_completeness(*args, **kwargs)
    report = _annotate_retrieval_health(report)
    artifact_dir = kwargs.get("artifact_dir")
    if artifact_dir is None and args:
        artifact_dir = args[0]
    if artifact_dir is not None:
        persist_report(artifact_dir, report)
    return report


def persist_report(artifact_dir, report):
    _sync_compatibility_hooks()
    return _v2.persist_report(artifact_dir, report)
