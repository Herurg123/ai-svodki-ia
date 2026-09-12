#!/usr/bin/env python3
"""Agency discovery rescue v5: one Reuters slot with post-filter health.

v4 is preserved for replay. v5 keeps the single Reuters-only high-context
publisher route global, but no longer treats an early Primary accepted count as
permanent proof that the ``major_agencies`` lane is healthy. Immediately before
rescue, a zero-paid deterministic bridge checks whether the exact Search-derived
Primary agency candidates still have a viable post-freshness/editorial survivor.

A zero-spend saved ``not_triggered`` report may be deterministically re-evaluated
on recovery. Any state that reserved, started, completed, failed, or left an
indeterminate search remains at-most-once and can never authorize a second
Reuters search.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable

import agency_discovery_rescue_v4 as v4
from agency_health_viability import (
    AGENCY_HEALTH_TRIGGER_VERSION,
    evaluate_agency_health,
    prior_not_triggered_recheck_allowed,
)
from event_freshness_contract import append_event_freshness_prompt
from story_coverage import read_json

v3 = v4.v3

AGENCY_DISCOVERY_RESCUE_VERSION = 5
AGENCY_DISCOVERY_RESCUE_STRATEGY = v4.AGENCY_DISCOVERY_RESCUE_STRATEGY
AGENCY_DISCOVERY_RESCUE_DIRECTION = v4.AGENCY_DISCOVERY_RESCUE_DIRECTION
AGENCY_DISCOVERY_ALLOWED_DOMAINS = v4.AGENCY_DISCOVERY_ALLOWED_DOMAINS
AGENCY_DISCOVERY_SEARCH_CONTEXT_SIZE = v4.AGENCY_DISCOVERY_SEARCH_CONTEXT_SIZE
AUDIT_CANDIDATE_SCHEMA = v3.AUDIT_CANDIDATE_SCHEMA
MAXIMUM_SEARCH_OPERATIONS = 1
PIPELINE_MAXIMUM_SEARCH_OPERATIONS = v4.PIPELINE_MAXIMUM_SEARCH_OPERATIONS
PRODUCTION_PREVIEW_ROOT = v4.PRODUCTION_PREVIEW_ROOT

AGENCY_DISCOVERY_RESCUE_QUERY = (
    "latest AI models research chips infrastructure financing earnings business "
    "deals policy security"
)


def neutral_query(primary_report: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    """Return one global publisher-route query; gaps are diagnostic only."""
    return AGENCY_DISCOVERY_RESCUE_QUERY, v4._regional_gaps(primary_report)


def source_metadata_state(api: Any) -> dict[str, Any]:
    """Distinguish missing provider source metadata from a real empty source list."""
    if not isinstance(api, dict):
        return {
            "source_metadata_available": False,
            "search_actions_with_source_metadata": 0,
            "search_actions_missing_source_metadata": 0,
        }
    with_metadata = 0
    missing_metadata = 0
    for item in api.get("web_search_call_items") or []:
        if not isinstance(item, dict) or item.get("action_type") != "search":
            continue
        action = item.get("action")
        sources = action.get("sources") if isinstance(action, dict) else None
        if isinstance(sources, list):
            with_metadata += 1
        else:
            missing_metadata += 1
    total = with_metadata + missing_metadata
    return {
        "source_metadata_available": bool(total and missing_metadata == 0),
        "search_actions_with_source_metadata": with_metadata,
        "search_actions_missing_source_metadata": missing_metadata,
    }


def _persist_report(
    report: dict[str, Any], *, artifact_dir: Path, output_root: Path,
    publication_date: str
) -> None:
    v4._persist_report(
        report,
        artifact_dir=artifact_dir,
        output_root=output_root,
        publication_date=publication_date,
    )


def _current_research(artifact_dir: Path) -> dict[str, Any]:
    try:
        payload = read_json(artifact_dir / "candidates.json")
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def run_agency_discovery_rescue(
    *, artifact_dir: Path, archive_path: Path, publication_date: str,
    api_key: str, model: str, maximum_candidates: int = 20,
    search_runner: Callable[..., tuple[dict[str, Any], dict[str, Any]]] | None = None,
    output_root: Path = PRODUCTION_PREVIEW_ROOT,
) -> dict[str, Any]:
    primary = v4._primary_report(artifact_dir, output_root, publication_date)
    current_research = _current_research(artifact_dir)
    query, gaps = neutral_query(primary)
    previous_query = v3.AGENCY_DISCOVERY_RESCUE_QUERY
    previous_build_prompt = v3.build_prompt
    previous_trigger = v3.trigger_from_primary
    previous_load_prior = v3._load_prior_report
    health_diagnostics: dict[str, Any] = {
        "version": AGENCY_HEALTH_TRIGGER_VERSION,
        "status": "not_evaluated",
        "paid_api_calls": 0,
        "web_search_operations": 0,
    }
    prior_not_triggered_rechecked = False

    def build_prompt_with_event_contract(**kwargs: Any) -> str:
        return append_event_freshness_prompt(previous_build_prompt(**kwargs))

    def trigger_with_post_filter_health(
        primary_report: dict[str, Any],
    ) -> tuple[bool, str | None, dict[str, int | str | None]]:
        nonlocal health_diagnostics
        triggered, reason, facts, diagnostics = evaluate_agency_health(
            primary_report=primary_report,
            current_research=current_research,
        )
        health_diagnostics = copy.deepcopy(diagnostics)
        return triggered, reason, facts

    def load_prior_with_zero_spend_recheck(
        prior_artifact_dir: Path, prior_output_root: Path, prior_publication_date: str
    ) -> dict[str, Any] | None:
        nonlocal prior_not_triggered_rechecked
        prior = previous_load_prior(
            prior_artifact_dir, prior_output_root, prior_publication_date
        )
        if prior_not_triggered_recheck_allowed(prior):
            prior_not_triggered_rechecked = True
            return None
        return prior

    v3.AGENCY_DISCOVERY_RESCUE_QUERY = query
    v3.build_prompt = build_prompt_with_event_contract
    v3.trigger_from_primary = trigger_with_post_filter_health
    v3._load_prior_report = load_prior_with_zero_spend_recheck
    try:
        kwargs: dict[str, Any] = {
            "artifact_dir": artifact_dir,
            "archive_path": archive_path,
            "publication_date": publication_date,
            "api_key": api_key,
            "model": model,
            "maximum_candidates": maximum_candidates,
            "output_root": output_root,
        }
        if search_runner is not None:
            kwargs["search_runner"] = search_runner
        report = v3.run_agency_discovery_rescue(**kwargs)
    finally:
        v3.AGENCY_DISCOVERY_RESCUE_QUERY = previous_query
        v3.build_prompt = previous_build_prompt
        v3.trigger_from_primary = previous_trigger
        v3._load_prior_report = previous_load_prior

    result = copy.deepcopy(report)
    result["version"] = AGENCY_DISCOVERY_RESCUE_VERSION
    result["query"] = query
    result["query_policy"] = "global_reuters_one_slot"
    result["regional_gaps_at_trigger"] = list(gaps)
    result["regional_gaps_affect_query"] = False
    result["search_operation_limit"] = MAXIMUM_SEARCH_OPERATIONS
    result["agency_health_trigger_version"] = AGENCY_HEALTH_TRIGGER_VERSION
    result["agency_health"] = health_diagnostics
    result["prior_not_triggered_rechecked"] = prior_not_triggered_rechecked
    result.setdefault("pipeline_search_budget", {})["maximum_total"] = (
        PIPELINE_MAXIMUM_SEARCH_OPERATIONS
    )
    diagnostics = source_metadata_state(result.get("api"))
    result["source_metadata_available"] = diagnostics["source_metadata_available"]
    result["source_metadata_diagnostics"] = diagnostics
    _persist_report(
        result,
        artifact_dir=artifact_dir,
        output_root=output_root,
        publication_date=publication_date,
    )
    return result
