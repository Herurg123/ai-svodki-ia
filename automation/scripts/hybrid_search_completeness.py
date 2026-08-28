#!/usr/bin/env python3
"""Stable public entrypoint for zero-budget Hybrid Completeness v2.

Production behavior lives in ``hybrid_search_completeness_v2.py``.  The previous
regional wrapper is retained as ``hybrid_search_completeness_regional_v1.py`` so
recovery hooks and monkeypatch-oriented offline tests keep a stable compatibility
surface.  Hybrid remains capped at four Web Search operations.
"""
from __future__ import annotations

from typing import Any

import hybrid_search_completeness_v2 as _v2

for _name in dir(_v2):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_v2, _name)

# Mutable compatibility hooks used by existing tests/recovery code.
REPOSITORY_ROOT = _v2.legacy.REPOSITORY_ROOT
PRODUCTION_PREVIEW_ROOT = _v2.legacy.PRODUCTION_PREVIEW_ROOT
RUNTIME_RESEARCH_ROOT = _v2.legacy.RUNTIME_RESEARCH_ROOT
run_agency_discovery_rescue = _v2.legacy.run_agency_discovery_rescue
run_source_pulse_shadow = _v2.legacy.run_source_pulse_shadow
refresh_post_hybrid_fusion = _v2.legacy.refresh_post_hybrid_fusion
run_search_request = _v2.legacy.run_search_request

# Contract literals intentionally remain visible at the stable entrypoint.
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


def run_hybrid_completeness(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _sync_compatibility_hooks()
    if "request_fn" not in kwargs:
        kwargs["request_fn"] = globals().get("run_search_request", _v2.legacy.run_search_request)
    return _v2.run_hybrid_completeness(*args, **kwargs)


def persist_report(artifact_dir, report):
    _sync_compatibility_hooks()
    return _v2.persist_report(artifact_dir, report)
