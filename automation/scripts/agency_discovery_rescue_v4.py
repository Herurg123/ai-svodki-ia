#!/usr/bin/env python3
"""Agency discovery rescue v4: gap-aware query, unchanged one-search ceiling."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable

import agency_discovery_rescue as v3
from event_freshness_contract import (
    append_event_freshness_prompt,
    apply_candidate_schema_contract,
)
from story_coverage import read_json, write_json

AGENCY_DISCOVERY_RESCUE_VERSION = 4
AGENCY_DISCOVERY_RESCUE_STRATEGY = v3.AGENCY_DISCOVERY_RESCUE_STRATEGY
AGENCY_DISCOVERY_RESCUE_DIRECTION = v3.AGENCY_DISCOVERY_RESCUE_DIRECTION
AGENCY_DISCOVERY_ALLOWED_DOMAINS = v3.AGENCY_DISCOVERY_ALLOWED_DOMAINS
AGENCY_DISCOVERY_SEARCH_CONTEXT_SIZE = v3.AGENCY_DISCOVERY_SEARCH_CONTEXT_SIZE
MAXIMUM_SEARCH_OPERATIONS = 1
PIPELINE_MAXIMUM_SEARCH_OPERATIONS = v3.PIPELINE_MAXIMUM_SEARCH_OPERATIONS
PRODUCTION_PREVIEW_ROOT = v3.PRODUCTION_PREVIEW_ROOT

apply_candidate_schema_contract(v3.AUDIT_CANDIDATE_SCHEMA)

_BASE_QUERY = v3.AGENCY_DISCOVERY_RESCUE_QUERY
_GAP_QUERIES = {
    (): _BASE_QUERY,
    ("asia",): "latest AI China Asia chips infrastructure financing earnings business deals policy security",
    ("russia",): "latest AI Russia chips infrastructure financing earnings business deals policy security",
    ("asia", "russia"): "latest AI China Russia chips infrastructure financing earnings business deals policy security",
}


def _regional_gaps(primary_report: dict[str, Any]) -> tuple[str, ...]:
    health = primary_report.get("regional_health")
    if not isinstance(health, dict):
        return ()
    result: list[str] = []
    for key in ("asia", "russia"):
        row = health.get(key)
        if isinstance(row, dict) and row.get("health_check_needed") is True:
            result.append(key)
    return tuple(result)


def gap_aware_query(primary_report: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    gaps = _regional_gaps(primary_report)
    return _GAP_QUERIES.get(gaps, _BASE_QUERY), gaps


def _primary_report(
    artifact_dir: Path, output_root: Path, publication_date: str
) -> dict[str, Any]:
    path = v3._primary_report_path(artifact_dir, output_root, publication_date)
    if path is None:
        return {}
    try:
        payload = read_json(path)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _persist_v4(
    report: dict[str, Any], *, artifact_dir: Path, output_root: Path,
    publication_date: str
) -> None:
    write_json(artifact_dir / "agency-discovery-rescue.json", report)
    output_root.mkdir(parents=True, exist_ok=True)
    write_json(output_root / f"agency-discovery-rescue-{publication_date}.json", report)


def _persist_report(
    report: dict[str, Any], *, artifact_dir: Path, output_root: Path,
    publication_date: str
) -> None:
    """Compatibility surface used by same-day recovery."""
    _persist_v4(
        report,
        artifact_dir=artifact_dir,
        output_root=output_root,
        publication_date=publication_date,
    )


def run_agency_discovery_rescue(
    *, artifact_dir: Path, archive_path: Path, publication_date: str,
    api_key: str, model: str, maximum_candidates: int = 20,
    search_runner: Callable[..., tuple[dict[str, Any], dict[str, Any]]] | None = None,
    output_root: Path = v3.PRODUCTION_PREVIEW_ROOT,
) -> dict[str, Any]:
    primary = _primary_report(artifact_dir, output_root, publication_date)
    query, gaps = gap_aware_query(primary)
    previous_query = v3.AGENCY_DISCOVERY_RESCUE_QUERY
    previous_build_prompt = v3.build_prompt

    def build_prompt_with_event_contract(**kwargs: Any) -> str:
        return append_event_freshness_prompt(previous_build_prompt(**kwargs))

    v3.AGENCY_DISCOVERY_RESCUE_QUERY = query
    v3.build_prompt = build_prompt_with_event_contract
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

    result = copy.deepcopy(report)
    result["version"] = AGENCY_DISCOVERY_RESCUE_VERSION
    result["query"] = query
    result["query_policy"] = "gap_aware_reuters_one_slot"
    result["regional_gaps_at_trigger"] = list(gaps)
    result["search_operation_limit"] = MAXIMUM_SEARCH_OPERATIONS
    result.setdefault("pipeline_search_budget", {})["maximum_total"] = PIPELINE_MAXIMUM_SEARCH_OPERATIONS
    _persist_v4(
        result,
        artifact_dir=artifact_dir,
        output_root=output_root,
        publication_date=publication_date,
    )
    return result
