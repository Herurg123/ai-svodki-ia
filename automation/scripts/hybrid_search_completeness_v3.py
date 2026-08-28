#!/usr/bin/env python3
"""Hybrid Completeness v3: one paid fifth search only for a double regional gap.

The stable Hybrid baseline remains four Web Search operations.  When Primary
Search health reports *both* China/Asia and Russia gaps, and the caller has not
lowered the baseline below four, v3 preserves all three broad Hybrid passes and
adds two dedicated regional health passes.  That one exceptional path therefore
uses five Hybrid searches: 3 broad + China/Asia + Russia.

No-gap and single-gap behavior stays on v2 (three broad normal passes, or three
broad + one regional). Source Pulse remains zero-OpenAI/zero-Web-Search and the
pre-Hybrid agency rescue remains capped at one operation.  The whole-pipeline
ceiling is therefore 24 normally and 25 only when the double-gap extension is
actually used.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable

import hybrid_search_completeness_v2 as v2
from story_coverage import merge_candidates, read_json, write_json

for _name in dir(v2):
    if not _name.startswith("_"):
        globals()[_name] = getattr(v2, _name)

HYBRID_COMPLETENESS_VERSION = 3
REGIONAL_HEALTH_VERSION = 3
BASE_MAXIMUM_SEARCH_CALLS = 4
CONDITIONAL_DOUBLE_GAP_MAXIMUM_SEARCH_CALLS = 5
CONDITIONAL_EXTRA_HYBRID_CALLS = 1
PIPELINE_BASE_MAXIMUM_SEARCH_OPERATIONS = 24
PIPELINE_DOUBLE_GAP_MAXIMUM_SEARCH_OPERATIONS = 25


def __getattr__(name: str) -> Any:
    return getattr(v2, name)


def _double_regional_gap(gaps: tuple[str, ...]) -> bool:
    return set(gaps) == {"asia", "russia"}


def _extension_metadata(*, used: bool, completed_hybrid_calls: int) -> dict[str, Any]:
    return {
        "version": 1,
        "trigger": "both_search_derived_regional_gaps",
        "triggered": used,
        "used": used,
        "regional_gaps_required": ["asia", "russia"],
        "base_hybrid_maximum": BASE_MAXIMUM_SEARCH_CALLS,
        "conditional_extra_hybrid_calls_maximum": CONDITIONAL_EXTRA_HYBRID_CALLS,
        "effective_hybrid_maximum": (
            CONDITIONAL_DOUBLE_GAP_MAXIMUM_SEARCH_CALLS if used
            else BASE_MAXIMUM_SEARCH_CALLS
        ),
        "completed_hybrid_calls": completed_hybrid_calls,
        "publication_quota": False,
        "coverage_extra_searches_enabled": False,
        "semantic_llm_dedupe_enabled": False,
    }


def _annotate_pipeline_budget(report: dict[str, Any], *, used: bool) -> dict[str, Any]:
    result = report
    completed = int((result.get("search_budget") or {}).get("completed_calls", 0) or 0)
    result["conditional_paid_extension"] = _extension_metadata(
        used=used,
        completed_hybrid_calls=completed,
    )
    result["pipeline_search_budget"] = {
        "primary_maximum": 12,
        "agency_discovery_rescue_maximum": 1,
        "hybrid_base_maximum": BASE_MAXIMUM_SEARCH_CALLS,
        "hybrid_conditional_extra_maximum": CONDITIONAL_EXTRA_HYBRID_CALLS,
        "hybrid_effective_maximum": (
            CONDITIONAL_DOUBLE_GAP_MAXIMUM_SEARCH_CALLS if used
            else BASE_MAXIMUM_SEARCH_CALLS
        ),
        "coverage_maximum": 7,
        "base_maximum_total": PIPELINE_BASE_MAXIMUM_SEARCH_OPERATIONS,
        "maximum_total": (
            PIPELINE_DOUBLE_GAP_MAXIMUM_SEARCH_OPERATIONS if used
            else PIPELINE_BASE_MAXIMUM_SEARCH_OPERATIONS
        ),
        "conditional_double_gap_maximum_total": PIPELINE_DOUBLE_GAP_MAXIMUM_SEARCH_OPERATIONS,
    }
    rescue = result.get("agency_discovery_rescue")
    if isinstance(rescue, dict):
        rescue_budget = dict(rescue.get("pipeline_search_budget") or {})
        rescue_budget.update({
            "hybrid_base_maximum": BASE_MAXIMUM_SEARCH_CALLS,
            "hybrid_conditional_extra_maximum": CONDITIONAL_EXTRA_HYBRID_CALLS,
            "base_maximum_total": PIPELINE_BASE_MAXIMUM_SEARCH_OPERATIONS,
            "conditional_double_gap_maximum_total": PIPELINE_DOUBLE_GAP_MAXIMUM_SEARCH_OPERATIONS,
        })
        rescue["pipeline_search_budget"] = rescue_budget
    return result


def _run_double_gap_with_fifth(
    *,
    research: dict[str, Any],
    archive: dict[str, Any],
    publication_date: str,
    api_key: str,
    model: str,
    maximum_candidates: int,
    request_fn: Callable[..., tuple[dict[str, Any], dict[str, Any]]],
    output_root: Path,
) -> dict[str, Any]:
    """Run 3 broad + 2 dedicated regional passes, exactly five at most."""
    search_window = research.get("search_window")
    if not isinstance(search_window, dict):
        raise RuntimeError("Hybrid v3: missing search_window")

    primary = [
        copy.deepcopy(item)
        for item in research.get("candidates") or []
        if isinstance(item, dict)
    ]
    attempts: list[dict[str, Any]] = []
    collected: list[dict[str, Any]] = []
    working = copy.deepcopy(research)

    # Preserve every normal broad Hybrid pass. The paid extension exists solely
    # to avoid stealing one of these broad slots when both regional gaps are red.
    for direction in v2.legacy.COMPLETENESS_DIRECTIONS:
        prompt = v2.build_prompt(
            publication_date=publication_date,
            search_window=search_window,
            direction_id=direction["id"],
            direction_label=direction["label"],
            direction_guidance=direction["guidance"],
            existing_candidates=working.get("candidates") or [],
            archive=archive,
        )
        record, working = v2._attempt(
            research=research,
            collected=collected,
            archive=archive,
            publication_date=publication_date,
            direction_id=direction["id"],
            label=direction["label"],
            prompt=prompt,
            api_key=api_key,
            model=model,
            maximum_candidates=maximum_candidates,
            request_fn=request_fn,
        )
        attempts.append(record)

    counts_after_fixed = v2.legacy.cluster_counts([
        item for item in working.get("candidates") or [] if isinstance(item, dict)
    ])
    missing_after_fixed = [
        item["id"]
        for item in v2.legacy.COMPLETENESS_DIRECTIONS
        if counts_after_fixed.get(item["id"], 0) == 0
    ]

    regional_checks: dict[str, Any] = {}
    for region in ("asia", "russia"):
        label = (
            "China/Asia recall health-check"
            if region == "asia"
            else "Russia recall health-check"
        )
        prompt = v2._regional_prompt(
            publication_date=publication_date,
            search_window=search_window,
            region=region,
            existing_candidates=working.get("candidates") or [],
            archive=archive,
        )
        record, working = v2._attempt(
            research=research,
            collected=collected,
            archive=archive,
            publication_date=publication_date,
            direction_id=v2.legacy.ADAPTIVE_DIRECTION_ID,
            label=label,
            prompt=prompt,
            api_key=api_key,
            model=model,
            maximum_candidates=maximum_candidates,
            request_fn=request_fn,
        )
        record["search_strategy"] = "regional_recall_health_split_paid_extension"
        record["regional_health_version"] = REGIONAL_HEALTH_VERSION
        record["regional_target"] = region
        record["required_query"] = v2.REGIONAL_QUERIES[region]
        attempts.append(record)
        regional_checks[region] = {
            "checked": record.get("status") in {"checked", "checked_with_gaps"},
            "query": v2.REGIONAL_QUERIES[region],
            "candidate_count": int(record.get("candidate_count", 0) or 0),
        }

    # Defensive invariant: no code path may turn the conditional extension into
    # an unbounded loop or a sixth Hybrid search.
    if len(attempts) > CONDITIONAL_DOUBLE_GAP_MAXIMUM_SEARCH_CALLS:
        raise RuntimeError("Hybrid v3 exceeded conditional five-search ceiling")

    merged, accepted, rejected = merge_candidates(
        research, collected, maximum_candidates=maximum_candidates
    )
    final = [
        item for item in merged.get("candidates") or [] if isinstance(item, dict)
    ]
    completed = v2.legacy._base._searches_from_attempts(attempts)
    complete = (
        len(attempts) == CONDITIONAL_DOUBLE_GAP_MAXIMUM_SEARCH_CALLS
        and completed == CONDITIONAL_DOUBLE_GAP_MAXIMUM_SEARCH_CALLS
        and all(
            item.get("status") in {"checked", "checked_with_gaps"}
            for item in attempts
        )
    )

    report: dict[str, Any] = {
        "version": HYBRID_COMPLETENESS_VERSION,
        "status": "complete" if complete else "complete_with_gaps",
        "publication_date": publication_date,
        "search_window": copy.deepcopy(search_window),
        "strategy": "primary_plus_three_fixed_plus_split_russia_asia_paid_extension",
        "search_budget": {
            "base_maximum_calls": BASE_MAXIMUM_SEARCH_CALLS,
            "conditional_extra_calls_maximum": CONDITIONAL_EXTRA_HYBRID_CALLS,
            "maximum_calls": CONDITIONAL_DOUBLE_GAP_MAXIMUM_SEARCH_CALLS,
            "fixed_calls": 3,
            "regional_calls_maximum": 2,
            "response_attempts": len(attempts),
            "completed_calls": completed,
            "remaining_calls": max(
                0, CONDITIONAL_DOUBLE_GAP_MAXIMUM_SEARCH_CALLS - completed
            ),
            "maximum_total_tool_calls_per_pass": v2.legacy.HYBRID_MAX_TOOL_CALLS_PER_PASS,
            "navigation_tool_allowance_per_pass": v2.legacy.HYBRID_NAVIGATION_TOOL_ALLOWANCE,
        },
        "primary_candidate_count": len(primary),
        "primary_cluster_counts": v2.legacy.cluster_counts(primary),
        "cluster_counts_after_fixed": counts_after_fixed,
        "missing_clusters_after_fixed": missing_after_fixed,
        "adaptive_needed": True,
        "regional_health": {
            "version": REGIONAL_HEALTH_VERSION,
            "gaps": ["asia", "russia"],
            "checked": all(row["checked"] for row in regional_checks.values()),
            "split_when_both": True,
            "checks": regional_checks,
            "publication_quota": False,
            "domain_filter": False,
        },
        "attempts": attempts,
        "additional_candidates_returned": len(collected),
        "accepted_candidates": accepted,
        "rejected_candidates": rejected,
        "final_candidate_count": len(final),
        "final_cluster_counts": v2.legacy.cluster_counts(final),
        "editorial_rerun_needed": bool(accepted),
        "merged_research_path": None,
        "diagnostic_merged_research_path": None,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    v2._persist_merged_if_needed(
        report=report,
        merged=merged,
        accepted=accepted,
        publication_date=publication_date,
        output_root=output_root,
    )
    return report


def run_hybrid_completeness(
    *,
    artifact_dir: Path,
    archive_path: Path,
    publication_date: str,
    api_key: str,
    model: str,
    maximum_search_calls: int = BASE_MAXIMUM_SEARCH_CALLS,
    maximum_candidates: int = 20,
    request_fn: Callable[..., tuple[dict[str, Any], dict[str, Any]]] = v2.legacy.run_search_request,
    output_root: Path = v2.legacy.PRODUCTION_PREVIEW_ROOT,
) -> dict[str, Any]:
    if maximum_search_calls < v2.FIXED_SEARCH_CALLS:
        raise ValueError(
            f"Hybrid completeness требует минимум {v2.FIXED_SEARCH_CALLS} search operations"
        )

    # `maximum_search_calls` remains the historical *baseline* cap. The fifth
    # operation is an explicit conditional extension, not a new everyday default.
    baseline_limit = min(maximum_search_calls, BASE_MAXIMUM_SEARCH_CALLS)
    research = read_json(artifact_dir / "candidates.json")
    if not isinstance(research, dict) or not isinstance(research.get("candidates"), list):
        raise RuntimeError("Hybrid completeness: candidates.json имеет неожиданную структуру")
    gaps = v2._regional_gaps(research)

    if not (_double_regional_gap(gaps) and baseline_limit == BASE_MAXIMUM_SEARCH_CALLS):
        report = v2.run_hybrid_completeness(
            artifact_dir=artifact_dir,
            archive_path=archive_path,
            publication_date=publication_date,
            api_key=api_key,
            model=model,
            maximum_search_calls=baseline_limit,
            maximum_candidates=maximum_candidates,
            request_fn=request_fn,
            output_root=output_root,
        )
        report["version"] = HYBRID_COMPLETENESS_VERSION
        report = _annotate_pipeline_budget(report, used=False)
        write_json(artifact_dir / "hybrid-completeness.json", report)
        write_json(output_root / f"hybrid-completeness-{publication_date}.json", report)
        return report

    # Double-gap paid path: reproduce v2's quality preflight once, then execute
    # five Hybrid searches. Do not call v2.run_hybrid_completeness here because
    # that would repeat rescue/Pulse orchestration.
    rescue = v2.legacy._run_pre_hybrid_agency_rescue(
        artifact_dir=artifact_dir,
        archive_path=archive_path,
        publication_date=publication_date,
        api_key=api_key,
        model=model,
        maximum_candidates=maximum_candidates,
        output_root=output_root,
    )
    rescue = v2.legacy._pre_hybrid_source_freshness_gate(
        rescue=rescue,
        artifact_dir=artifact_dir,
        publication_date=publication_date,
        output_root=output_root,
    )
    refreshed = read_json(artifact_dir / "candidates.json")
    if isinstance(refreshed, dict):
        research = refreshed

    pulse = v2.legacy.run_source_pulse_shadow(
        artifact_dir=artifact_dir,
        archive_path=archive_path,
        publication_date=publication_date,
        output_root=output_root,
    )
    fusion = pulse.get("fusion") if isinstance(pulse, dict) else None
    summary = fusion.get("summary") if isinstance(fusion, dict) else None
    promotion = pulse.get("promotion") if isinstance(pulse, dict) else None
    print(
        "Source Pulse shadow reuse: "
        f"state={pulse.get('state') if isinstance(pulse, dict) else 'unknown'}, "
        f"pulse_only={summary.get('pulse_only_count') if isinstance(summary, dict) else 'n/a'}, "
        f"supplemental_promoted={promotion.get('promoted_count') if isinstance(promotion, dict) else 0}; "
        "shadow_mutation=0; paid API calls=0; Web Search operations=0."
    )

    archive = read_json(archive_path)
    if not isinstance(archive, dict) or not isinstance(research.get("search_window"), dict):
        # Fail safely to the bounded v2 path if the saved artifact cannot support
        # the explicit paid branch. Never spend a fifth search on malformed state.
        report = v2.run_hybrid_completeness(
            artifact_dir=artifact_dir,
            archive_path=archive_path,
            publication_date=publication_date,
            api_key=api_key,
            model=model,
            maximum_search_calls=BASE_MAXIMUM_SEARCH_CALLS,
            maximum_candidates=maximum_candidates,
            request_fn=request_fn,
            output_root=output_root,
        )
        report["version"] = HYBRID_COMPLETENESS_VERSION
        report = _annotate_pipeline_budget(report, used=False)
        write_json(artifact_dir / "hybrid-completeness.json", report)
        write_json(output_root / f"hybrid-completeness-{publication_date}.json", report)
        return report

    report = _run_double_gap_with_fifth(
        research=research,
        archive=archive,
        publication_date=publication_date,
        api_key=api_key,
        model=model,
        maximum_candidates=maximum_candidates,
        request_fn=request_fn,
        output_root=output_root,
    )
    report = v2._attach_quality_layers(
        report=report,
        rescue=rescue,
        artifact_dir=artifact_dir,
        publication_date=publication_date,
        output_root=output_root,
    )
    report["version"] = HYBRID_COMPLETENESS_VERSION
    report = _annotate_pipeline_budget(report, used=True)
    write_json(artifact_dir / "hybrid-completeness.json", report)
    write_json(output_root / f"hybrid-completeness-{publication_date}.json", report)
    return report


def persist_report(artifact_dir: Path, report: dict[str, Any]) -> None:
    write_json(artifact_dir / "hybrid-completeness.json", report)
    path = v2.legacy.PRODUCTION_PREVIEW_ROOT / (
        f"hybrid-completeness-{report.get('publication_date', 'unknown')}.json"
    )
    write_json(path, report)
