#!/usr/bin/env python3
"""Stable public entrypoint for Hybrid Completeness v3.

Production behavior lives in ``hybrid_search_completeness_v3.py``.  The normal
Hybrid ceiling remains four Web Search operations.  Only when Search-derived
Russia *and* China/Asia gaps are both open may v3 spend one additional fifth
Hybrid search, preserving all three broad passes plus two dedicated regional
health checks.  The pre-Hybrid agency rescue remains capped at one operation and
Source Pulse remains zero-OpenAI/zero-Web-Search.

P3 changes only routing semantics inside already-existing slots: regional health
queries carry representative company/policy anchors and the pre-Hybrid Reuters
rescue uses v5's global publisher route. P4 adds a deterministic pre-Hybrid
viability refresh: an early healthy Primary region may re-open only when its own
Primary regional candidates no longer have a viable post-freshness/editorial
survivor. Existing Search gaps never close here. The 24/25 ceilings are unchanged.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import agency_discovery_rescue_v5 as _agency_v5
import hybrid_search_completeness_v3 as _v3
from event_freshness_contract import (
    append_event_freshness_prompt,
    apply_candidate_schema_contract,
)
from regional_health_viability import refresh_regional_health
from story_coverage import read_json, write_json

_v2 = _v3.v2
legacy = _v2.legacy

for _name in dir(_v3):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_v3, _name)

apply_candidate_schema_contract(legacy.AUDIT_CANDIDATE_SCHEMA)

REPOSITORY_ROOT = legacy.REPOSITORY_ROOT
PRODUCTION_PREVIEW_ROOT = legacy.PRODUCTION_PREVIEW_ROOT
RUNTIME_RESEARCH_ROOT = legacy.RUNTIME_RESEARCH_ROOT
run_agency_discovery_rescue = _agency_v5.run_agency_discovery_rescue
run_source_pulse_shadow = legacy.run_source_pulse_shadow
refresh_post_hybrid_fusion = legacy.refresh_post_hybrid_fusion
run_search_request = legacy.run_search_request

DEFAULT_MAXIMUM_SEARCH_CALLS = 4
CONDITIONAL_DOUBLE_GAP_MAXIMUM_SEARCH_CALLS = 5
CONDITIONAL_EXTRA_HYBRID_CALLS = 1
PIPELINE_BASE_MAXIMUM_SEARCH_OPERATIONS = 24
PIPELINE_DOUBLE_GAP_MAXIMUM_SEARCH_OPERATIONS = 25
HYBRID_COMPLETENESS_VERSION = 3
REGIONAL_HEALTH_VERSION = 3

REGIONAL_QUERIES = {
    "asia": (
        "latest China AI models releases Tencent Hunyuan Qwen DeepSeek GLM "
        "Huawei products research"
    ),
    "russia": (
        "последние новости ИИ Россия Яндекс Сбер VK МТС продукты регулирование "
        "авторское право данные обучение моделей"
    ),
}


def __getattr__(name: str) -> Any:
    return getattr(_v3, name)


def _sync_regional_queries() -> None:
    """Apply P3 query text without rewriting preserved v2/v3 source modules."""
    _v2.REGIONAL_QUERIES = REGIONAL_QUERIES
    _v3.REGIONAL_QUERIES = REGIONAL_QUERIES


def _sync_compatibility_hooks() -> None:
    """Mirror public monkeypatch/recovery hooks through all preserved layers."""
    _sync_regional_queries()
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
        setattr(_v3, name, value)
        setattr(_v2, name, value)
        setattr(legacy, name, value)
        if hasattr(legacy._base, name):
            setattr(legacy._base, name, value)


def build_prompt(**kwargs: Any) -> str:
    _sync_compatibility_hooks()
    _v2._ensure_original_prompt_hook()
    return append_event_freshness_prompt(_v2.build_prompt(**kwargs))


def regional_health_query(gaps: tuple[str, ...]) -> str:
    """Preserve the historical combined-query helper without changing v3 execution.

    Production v3 executes separate regional searches on the double-gap path, but
    older diagnostics/tests still use this public helper to inspect a source-neutral
    combined Russia/China-Asia query.  Keep that stable surface rather than making a
    helper API break masquerade as retrieval architecture.
    """
    _sync_regional_queries()
    if len(gaps) == 1:
        return _v2.regional_health_query(gaps)
    return legacy.regional_health_query(gaps)


def _regional_gaps(research: dict[str, Any]) -> tuple[str, ...]:
    return _v2._regional_gaps(research)


def _pre_hybrid_source_freshness_gate(**kwargs: Any) -> dict[str, Any]:
    _sync_compatibility_hooks()
    return legacy._pre_hybrid_source_freshness_gate(**kwargs)


def _run_pre_hybrid_agency_rescue(**kwargs: Any) -> dict[str, Any]:
    _sync_compatibility_hooks()
    return legacy._run_pre_hybrid_agency_rescue(**kwargs)


def _refresh_pre_hybrid_regional_health(artifact_dir: Any) -> dict[str, Any]:
    """Refresh only false-negative regional health before any Hybrid search."""
    root = Path(artifact_dir)
    primary_path = root / "primary-recall.json"
    candidates_path = root / "candidates.json"
    try:
        primary = read_json(primary_path)
        research = read_json(candidates_path)
    except Exception as exc:
        return {
            "version": 1,
            "status": "not_available",
            "changed": False,
            "reason": f"{type(exc).__name__}: {exc}",
            "paid_api_calls": 0,
            "web_search_operations": 0,
        }
    if not isinstance(primary, dict) or not isinstance(research, dict):
        return {
            "version": 1,
            "status": "not_available",
            "changed": False,
            "reason": "primary-recall.json or candidates.json has unexpected structure",
            "paid_api_calls": 0,
            "web_search_operations": 0,
        }
    updated, diagnostics = refresh_regional_health(
        primary_report=primary,
        current_research=research,
    )
    if diagnostics.get("status") == "complete":
        # Persist metadata even when no gap changes so the artifact proves which
        # post-filter viability decision fed Hybrid routing.
        write_json(candidates_path, updated)
    return diagnostics


def _annotate_retrieval_health(report: dict[str, Any]) -> dict[str, Any]:
    extension = report.get("conditional_paid_extension")
    extension_used = bool(
        isinstance(extension, dict) and extension.get("used") is True
    )
    regional = report.get("regional_health")
    if not isinstance(regional, dict) or not regional.get("gaps"):
        report["retrieval_health"] = {
            "status": "complete_no_regional_gap",
            "regional_gaps": [],
            "unresolved_regional_gaps": [],
            "volume_completion_independent": True,
            "coverage_paid_search_trigger_unchanged": True,
            "coverage_additional_paid_searches": 0,
            "hybrid_conditional_paid_extension_used": extension_used,
            "additional_paid_searches": 1 if extension_used else 0,
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
        gap
        for gap in gaps
        if not isinstance(checks.get(gap), dict)
        or checks[gap].get("checked") is not True
    ]
    unresolved = [
        gap
        for gap in gaps
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
        "coverage_additional_paid_searches": 0,
        "hybrid_conditional_paid_extension_used": extension_used,
        "additional_paid_searches": 1 if extension_used else 0,
        "publication_quota": False,
        "policy": (
            "A full-volume digest may still carry unresolved regional retrieval gaps. "
            "The only approved paid regional extension is one fifth Hybrid search "
            "when both Russia and China/Asia gaps are open; extra Coverage searches "
            "remain disabled."
        ),
    }
    return report


def run_hybrid_completeness(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _sync_compatibility_hooks()
    if "request_fn" not in kwargs:
        kwargs["request_fn"] = globals().get("run_search_request", legacy.run_search_request)
    artifact_dir = kwargs.get("artifact_dir")
    if artifact_dir is None and args:
        artifact_dir = args[0]
    viability = (
        _refresh_pre_hybrid_regional_health(artifact_dir)
        if artifact_dir is not None
        else {
            "version": 1,
            "status": "not_available",
            "changed": False,
            "reason": "artifact_dir not supplied",
            "paid_api_calls": 0,
            "web_search_operations": 0,
        }
    )
    report = _v3.run_hybrid_completeness(*args, **kwargs)
    report["regional_health_viability"] = viability
    report = _annotate_retrieval_health(report)
    if artifact_dir is not None:
        persist_report(artifact_dir, report)
    return report


def persist_report(artifact_dir, report):
    _sync_compatibility_hooks()
    return _v3.persist_report(artifact_dir, report)
