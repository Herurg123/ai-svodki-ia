#!/usr/bin/env python3
"""Offline P3 audit for provider/source-routing recall failures.

This module consumes a saved production-derived fixture. It never calls OpenAI,
Web Search, Terra, or mutable external sources. The goal is deliberately modest:
separate provider source-pool misses from post-retrieval rejection and from cases
where the provider did not expose source metadata, then verify that proposed
query contracts cover the fixed control themes without increasing search count.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _fold(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def classify_observation(row: dict[str, Any]) -> str:
    if row.get("search_completed") is not True:
        return "search_not_completed"
    if row.get("source_metadata_available") is not True:
        return "source_metadata_unavailable"
    if row.get("control_source_pool_hit") is not True:
        return "provider_source_pool_miss"
    if int(row.get("candidate_count", 0) or 0) < 1:
        return "candidate_omission_after_retrieval"
    return "candidate_retrieved"


def query_covers_control(query: str, control: dict[str, Any]) -> bool:
    folded = _fold(query)
    groups = control.get("required_anchor_groups")
    if not isinstance(groups, list) or not groups:
        return False
    for group in groups:
        if not isinstance(group, list) or not group:
            return False
        if not any(_fold(anchor) in folded for anchor in group if _fold(anchor)):
            return False
    return True


def audit_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    controls = payload.get("controls")
    observations = payload.get("production_observations")
    queries = payload.get("proposed_query_contract")
    control_routes = payload.get("query_control_routes")
    budget = payload.get("search_budget")
    if not isinstance(controls, dict):
        raise ValueError("controls must be an object")
    if not isinstance(observations, list):
        raise ValueError("production_observations must be an array")
    if not isinstance(queries, dict) or not isinstance(control_routes, dict):
        raise ValueError("query contract is incomplete")
    if not isinstance(budget, dict):
        raise ValueError("search_budget must be an object")

    classified: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for raw in observations:
        if not isinstance(raw, dict):
            continue
        classification = classify_observation(raw)
        counts[classification] = counts.get(classification, 0) + 1
        classified.append(
            {
                "route": raw.get("route"),
                "control_id": raw.get("control_id"),
                "query": raw.get("query"),
                "consulted_sources_count": int(raw.get("consulted_sources_count", 0) or 0),
                "candidate_count": int(raw.get("candidate_count", 0) or 0),
                "classification": classification,
            }
        )

    coverage: dict[str, Any] = {}
    uncovered: list[str] = []
    for control_id, control in controls.items():
        routes = control_routes.get(control_id)
        route_rows: list[dict[str, Any]] = []
        if not isinstance(routes, list):
            routes = []
        for route in routes:
            query = queries.get(str(route))
            covered = isinstance(query, str) and query_covers_control(query, control)
            route_rows.append({"route": route, "query": query, "covered": covered})
        control_covered = any(item["covered"] for item in route_rows)
        coverage[control_id] = {
            "covered": control_covered,
            "routes": route_rows,
        }
        if not control_covered:
            uncovered.append(str(control_id))

    ordinary = int(budget.get("ordinary_pipeline_maximum", 0) or 0)
    double_gap = int(budget.get("double_regional_gap_maximum", 0) or 0)
    added = int(budget.get("p3_additional_searches", 0) or 0)
    budget_ok = ordinary == 24 and double_gap == 25 and added == 0

    return {
        "version": 1,
        "status": "pass" if not uncovered and budget_ok else "fail",
        "classification_counts": counts,
        "observations": classified,
        "query_control_coverage": coverage,
        "uncovered_controls": uncovered,
        "budget_unchanged": budget_ok,
        "ordinary_pipeline_maximum": ordinary,
        "double_regional_gap_maximum": double_gap,
        "p3_additional_searches": added,
        "interpretation": (
            "A completed search with source metadata and no control source in the pool is a "
            "provider/ranking miss, not a post-retrieval normalization failure. A completed "
            "search with sources metadata missing is diagnostically unknown and must not be "
            "reported as proof that the provider consulted zero sources."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.fixture.read_text(encoding="utf-8"))
    report = audit_fixture(payload)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
