#!/usr/bin/env python3
"""Hybrid Completeness v2: split regional health within the existing four calls.

No extra paid call is introduced.  When both Search-derived Russia and Asia gaps
are open, the four Hybrid slots become two broad fixed passes plus one dedicated
China/Asia pass and one dedicated Russian-language Russia pass.  With one gap,
the historical three fixed plus one regional pattern remains intact.
"""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable

_BASE_PATH = Path(__file__).with_name("hybrid_search_completeness_v1.py")
_BASE_SPEC = importlib.util.spec_from_file_location("hybrid_search_completeness_v1_for_v2", _BASE_PATH)
assert _BASE_SPEC and _BASE_SPEC.loader
base = importlib.util.module_from_spec(_BASE_SPEC)
sys.modules[_BASE_SPEC.name] = base
_BASE_SPEC.loader.exec_module(base)

for _name in dir(base):
    if not _name.startswith("_"):
        globals()[_name] = getattr(base, _name)

from agency_discovery_rescue import (
    AGENCY_DISCOVERY_RESCUE_DIRECTION,
    AGENCY_DISCOVERY_RESCUE_STRATEGY,
    PIPELINE_MAXIMUM_SEARCH_OPERATIONS,
    run_agency_discovery_rescue,
)
from source_pulse_shadow import (
    compact_shadow_report,
    refresh_post_hybrid_fusion,
    run_source_pulse_shadow,
)

HYBRID_COMPLETENESS_VERSION = 2
REGIONAL_HEALTH_VERSION = 2
DEFAULT_MAXIMUM_SEARCH_CALLS = 4
FIXED_SEARCH_CALLS = 3
SPLIT_FIXED_SEARCH_CALLS = 2

REGIONAL_QUERIES = {
    "asia": "latest China AI models products agents robotics chips investment infrastructure Qwen DeepSeek GLM Huawei",
    "russia": "последние новости ИИ Россия модели продукты агенты инвестиции облако инфраструктура кибербезопасность регулирование",
}


def __getattr__(name: str) -> Any:
    return getattr(base, name)


def _regional_gaps(research: dict[str, Any]) -> tuple[str, ...]:
    health = research.get("regional_health")
    if not isinstance(health, dict):
        return ()
    result: list[str] = []
    for key in ("asia", "russia"):
        row = health.get(key)
        if isinstance(row, dict) and row.get("health_check_needed") is True:
            result.append(key)
    return tuple(result)


def regional_health_query(gaps: tuple[str, ...]) -> str:
    if len(gaps) != 1 or gaps[0] not in REGIONAL_QUERIES:
        raise ValueError("regional_health_query v2 requires exactly one region")
    return REGIONAL_QUERIES[gaps[0]]


def _regional_prompt(
    *, publication_date: str, search_window: dict[str, Any], region: str,
    existing_candidates: list[Any], archive: dict[str, Any]
) -> str:
    query = REGIONAL_QUERIES[region]
    if region == "russia":
        guidance = (
            "Проверь крупные свежие события российского ИИ: модели, продукты и агенты, "
            "корпоративное внедрение, инвестиции, облака/инфраструктуру, безопасность и "
            "регулирование. Ищи по русскоязычной экосистеме source-neutral; ТАСС, CNews, "
            "официальные компании и другие надежные источники допустимы, но не являются whitelist."
        )
        label = "Russia recall health-check"
    else:
        guidance = (
            "Проверь крупные свежие события Китая/Азии: новые модели и AI-продукты, агенты, "
            "robotics/physical AI, chips/compute, финансирование, инфраструктуру, безопасность "
            "и регулирование. Не ограничивайся перечисленными брендами или издателями."
        )
        label = "China/Asia recall health-check"
    prompt = base.build_prompt(
        publication_date=publication_date,
        search_window=search_window,
        direction_id=base.ADAPTIVE_DIRECTION_ID,
        direction_label=label,
        direction_guidance=guidance,
        existing_candidates=existing_candidates,
        archive=archive,
        missing_clusters=(),
    )
    return prompt + f"""

Дополнительный контракт regional-health v{REGIONAL_HEALTH_VERSION}:
выполни ровно один source-neutral Web Search без API domain filter.
Фактический query должен быть ТОЧНО:
`{query}`
Это health-check полноты, а не квота публикации. При отсутствии достойной новости
верни пустой candidates. Не подменяй свежий regional recall старыми обзорными материалами.
"""


def _run_pre_hybrid_agency_rescue(
    *, artifact_dir: Path, archive_path: Path, publication_date: str,
    api_key: str, model: str, maximum_candidates: int, output_root: Path,
) -> dict[str, Any]:
    try:
        return run_agency_discovery_rescue(
            artifact_dir=artifact_dir,
            archive_path=archive_path,
            publication_date=publication_date,
            api_key=api_key,
            model=model,
            maximum_candidates=maximum_candidates,
            output_root=output_root,
        )
    except Exception as exc:
        report = {
            "version": 3,
            "search_strategy": AGENCY_DISCOVERY_RESCUE_STRATEGY,
            "publication_date": publication_date,
            "triggered": False,
            "executed": False,
            "state": "integration_error",
            "status": "complete_with_gaps",
            "search_operation_limit": 1,
            "search_operation_reserved": 0,
            "search_operation_count_contribution": 0,
            "added_count": 0,
            "rejections": [{"reason_code": "integration_error", "detail": f"{type(exc).__name__}: {exc}"}],
            "pipeline_search_budget": {
                "primary_maximum": 12,
                "agency_discovery_rescue_maximum": 1,
                "hybrid_maximum": 4,
                "coverage_maximum": 7,
                "maximum_total": PIPELINE_MAXIMUM_SEARCH_OPERATIONS,
            },
        }
        write_json(artifact_dir / "agency-discovery-rescue.json", report)
        output_root.mkdir(parents=True, exist_ok=True)
        write_json(output_root / f"agency-discovery-rescue-{publication_date}.json", report)
        return report


def _rescue_added(report: dict[str, Any]) -> bool:
    return int(report.get("added_count", 0) or 0) > 0


def _renumber(candidates: list[dict[str, Any]]) -> None:
    for index, candidate in enumerate(candidates, start=1):
        candidate["id"] = f"cand-{index:03d}"


def _pre_hybrid_source_freshness_gate(
    *, rescue: dict[str, Any], artifact_dir: Path, publication_date: str,
    output_root: Path,
    verify_fn: Callable[[dict[str, Any]], tuple[dict[str, Any], dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    if not _rescue_added(rescue):
        return rescue
    research = read_json(artifact_dir / "candidates.json")
    if not isinstance(research, dict) or not isinstance(research.get("candidates"), list):
        return rescue
    rescue_rows = [
        copy.deepcopy(item) for item in research["candidates"]
        if isinstance(item, dict)
        and item.get("audit_direction") == AGENCY_DISCOVERY_RESCUE_DIRECTION
        and item.get("recommendation") in {"include", "consider"}
    ]
    base_rows = [
        copy.deepcopy(item) for item in research["candidates"]
        if isinstance(item, dict) and item.get("audit_direction") != AGENCY_DISCOVERY_RESCUE_DIRECTION
    ]
    if not rescue_rows:
        return rescue
    result = copy.deepcopy(rescue)
    try:
        if verify_fn is None:
            from source_freshness import verify_research_payload
            verify_fn = verify_research_payload
        verified, summary = verify_fn({
            "search_window": copy.deepcopy(research.get("search_window")),
            "candidates": copy.deepcopy(rescue_rows),
        })
        survivors = [
            copy.deepcopy(item) for item in (verified.get("candidates") or [])
            if isinstance(item, dict) and item.get("recommendation") in {"include", "consider"}
        ]
        result["source_freshness_gate"] = {
            "version": 1, "status": "complete", "paid_api_calls": 0,
            "candidate_count_before": len(rescue_rows),
            "candidate_count_after": len(survivors), "summary": copy.deepcopy(summary),
        }
    except Exception as exc:
        survivors = []
        result["source_freshness_gate"] = {
            "version": 1, "status": "error_nonfatal", "paid_api_calls": 0,
            "candidate_count_before": len(rescue_rows), "candidate_count_after": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }
    rebuilt = copy.deepcopy(research)
    rebuilt_rows = base_rows + survivors
    _renumber(rebuilt_rows)
    rebuilt["candidates"] = rebuilt_rows
    write_json(artifact_dir / "candidates.json", rebuilt)
    result["freshness_verified_added_count"] = len(survivors)
    result["accepted_count"] = len(survivors)
    result["added_count"] = len(survivors)
    result["accepted_candidates"] = copy.deepcopy(survivors)
    if not survivors:
        result["state"] = "completed_no_addition"
        result["status"] = "complete_with_gaps"
        result.pop("merged_research_path", None)
        result.pop("diagnostic_merged_research_path", None)
    write_json(artifact_dir / "agency-discovery-rescue.json", result)
    output_root.mkdir(parents=True, exist_ok=True)
    write_json(output_root / f"agency-discovery-rescue-{publication_date}.json", result)
    return result


def _execute_attempt(
    *, research: dict[str, Any], collected: list[dict[str, Any]], archive: dict[str, Any],
    publication_date: str, direction_id: str, label: str, prompt: str,
    api_key: str, model: str, maximum_candidates: int,
    request_fn: Callable[..., tuple[dict[str, Any], dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload: dict[str, Any] | None = None
    metadata: dict[str, Any] = {}
    error: str | None = None
    try:
        payload, metadata = request_fn(
            api_key=api_key, model=model, prompt=prompt, direction_id=direction_id
        )
    except base.CompletenessResponseError as exc:
        metadata = exc.metadata
        error = f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    record = base._attempt_record(
        direction_id=direction_id, label=label, prompt=prompt,
        payload=payload, metadata=metadata, error=error,
    )
    additions = [copy.deepcopy(item) for item in record.get("candidates") or [] if isinstance(item, dict)]
    collected.extend(additions)
    provisional, _, _ = merge_candidates(research, collected, maximum_candidates=maximum_candidates)
    return record, provisional


def _run_split_both_regions(
    *, research: dict[str, Any], archive: dict[str, Any], publication_date: str,
    api_key: str, model: str, maximum_candidates: int,
    request_fn: Callable[..., tuple[dict[str, Any], dict[str, Any]]],
    output_root: Path,
) -> dict[str, Any]:
    search_window = research["search_window"]
    primary_candidates = [copy.deepcopy(item) for item in research.get("candidates") or [] if isinstance(item, dict)]
    attempts: list[dict[str, Any]] = []
    collected: list[dict[str, Any]] = []
    working = copy.deepcopy(research)

    # Preserve two broad independent discovery lenses.  The third historical
    # broad pass is reallocated, not added, so two regional ecosystems receive
    # one independent search each within the same four-call maximum.
    for direction in base.COMPLETENESS_DIRECTIONS[:SPLIT_FIXED_SEARCH_CALLS]:
        prompt = base.build_prompt(
            publication_date=publication_date,
            search_window=search_window,
            direction_id=direction["id"],
            direction_label=direction["label"],
            direction_guidance=direction["guidance"],
            existing_candidates=working.get("candidates") or [],
            archive=archive,
        )
        record, working = _execute_attempt(
            research=research, collected=collected, archive=archive,
            publication_date=publication_date, direction_id=direction["id"],
            label=direction["label"], prompt=prompt, api_key=api_key, model=model,
            maximum_candidates=maximum_candidates, request_fn=request_fn,
        )
        attempts.append(record)

    regional_rows: list[dict[str, Any]] = []
    for region in ("asia", "russia"):
        prompt = _regional_prompt(
            publication_date=publication_date,
            search_window=search_window,
            region=region,
            existing_candidates=working.get("candidates") or [],
            archive=archive,
        )
        label = "China/Asia recall health-check" if region == "asia" else "Russia recall health-check"
        record, working = _execute_attempt(
            research=research, collected=collected, archive=archive,
            publication_date=publication_date, direction_id=base.ADAPTIVE_DIRECTION_ID,
            label=label, prompt=prompt, api_key=api_key, model=model,
            maximum_candidates=maximum_candidates, request_fn=request_fn,
        )
        record["search_strategy"] = "regional_recall_health_split"
        record["regional_health_version"] = REGIONAL_HEALTH_VERSION
        record["regional_target"] = region
        record["required_query"] = REGIONAL_QUERIES[region]
        attempts.append(record)
        regional_rows.append(record)

    merged, accepted, rejected = merge_candidates(research, collected, maximum_candidates=maximum_candidates)
    final_candidates = [item for item in merged.get("candidates") or [] if isinstance(item, dict)]
    complete = all(item.get("status") in {"checked", "checked_with_gaps"} for item in attempts)
    completed_calls = base._searches_from_attempts(attempts)
    report: dict[str, Any] = {
        "version": HYBRID_COMPLETENESS_VERSION,
        "status": "complete" if complete else "complete_with_gaps",
        "publication_date": publication_date,
        "search_window": copy.deepcopy(search_window),
        "strategy": "primary_plus_two_fixed_plus_split_russia_asia_health",
        "search_budget": {
            "maximum_calls": DEFAULT_MAXIMUM_SEARCH_CALLS,
            "fixed_calls": SPLIT_FIXED_SEARCH_CALLS,
            "regional_calls_maximum": 2,
            "response_attempts": len(attempts),
            "completed_calls": completed_calls,
            "remaining_calls": max(0, DEFAULT_MAXIMUM_SEARCH_CALLS - completed_calls),
            "maximum_total_tool_calls_per_pass": base.HYBRID_MAX_TOOL_CALLS_PER_PASS,
            "navigation_tool_allowance_per_pass": base.HYBRID_NAVIGATION_TOOL_ALLOWANCE,
        },
        "primary_candidate_count": len(primary_candidates),
        "primary_cluster_counts": base.cluster_counts(primary_candidates),
        "cluster_counts_after_fixed": base.cluster_counts([
            item for item in working.get("candidates") or [] if isinstance(item, dict)
        ]),
        "missing_clusters_after_fixed": [],
        "adaptive_needed": True,
        "regional_health": {
            "version": REGIONAL_HEALTH_VERSION,
            "gaps": ["asia", "russia"],
            "split_when_both": True,
            "publication_quota": False,
            "domain_filter": False,
            "checks": {
                str(item.get("regional_target")): {
                    "checked": item.get("status") in {"checked", "checked_with_gaps"},
                    "query": item.get("required_query"),
                    "candidate_count": int(item.get("candidate_count", 0) or 0),
                }
                for item in regional_rows
            },
        },
        "attempts": attempts,
        "additional_candidates_returned": len(collected),
        "accepted_candidates": accepted,
        "rejected_candidates": rejected,
        "final_candidate_count": len(final_candidates),
        "final_cluster_counts": base.cluster_counts(final_candidates),
        "editorial_rerun_needed": bool(accepted),
        "merged_research_path": None,
        "diagnostic_merged_research_path": None,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    if accepted:
        diagnostic = output_root / f"hybrid-completeness-merged-{publication_date}.json"
        runtime_root = base._runtime_root_for(output_root)
        runtime_root.mkdir(parents=True, exist_ok=True)
        runtime = runtime_root / f"hybrid-completeness-merged-{publication_date}.json"
        write_json(diagnostic, merged)
        write_json(runtime, merged)
        report["diagnostic_merged_research_path"] = str(diagnostic)
        report["merged_research_path"] = str(runtime)
    return report


def _run_one_region(
    *, research: dict[str, Any], archive_path: Path, publication_date: str,
    api_key: str, model: str, maximum_candidates: int, region: str,
    request_fn: Callable[..., tuple[dict[str, Any], dict[str, Any]]], output_root: Path,
) -> dict[str, Any]:
    artifact_stub = None
    # Run exactly the historical three fixed calls first, suppressing base's
    # fourth adaptive slot.  Its accepted merged path is then the regional input.
    # A temporary call target is unnecessary because base persists to output_root.
    raise RuntimeError("internal placeholder")


def _attach_quality_layers(
    *, report: dict[str, Any], rescue: dict[str, Any], artifact_dir: Path,
    publication_date: str, output_root: Path,
) -> dict[str, Any]:
    report = copy.deepcopy(report)
    report["agency_discovery_rescue"] = copy.deepcopy(rescue)
    report["pre_hybrid_quality_search_operations"] = int(
        rescue.get("search_operation_count_contribution", 0) or 0
    )
    report["pipeline_search_budget"] = {
        "primary_maximum": 12,
        "agency_discovery_rescue_maximum": 1,
        "hybrid_maximum": 4,
        "coverage_maximum": 7,
        "maximum_total": PIPELINE_MAXIMUM_SEARCH_OPERATIONS,
    }
    try:
        fusion_research = read_json(artifact_dir / "candidates.json")
        merged_path = report.get("merged_research_path")
        if isinstance(merged_path, str) and Path(merged_path).is_file():
            candidate = read_json(Path(merged_path))
            if isinstance(candidate, dict):
                fusion_research = candidate
        if isinstance(fusion_research, dict):
            refresh_post_hybrid_fusion(
                artifact_dir=artifact_dir,
                output_root=output_root,
                publication_date=publication_date,
                research=fusion_research,
            )
    except Exception:
        pass
    pulse_path = artifact_dir / "source-pulse.json"
    if pulse_path.is_file():
        try:
            pulse = read_json(pulse_path)
            compact = compact_shadow_report(pulse)
            promotion = pulse.get("promotion") if isinstance(pulse, dict) else None
            compact["supplemental_candidate_influence"] = bool(
                isinstance(pulse, dict) and pulse.get("supplemental_candidate_influence") is True
            )
            compact["supplemental_promoted_count"] = (
                int(promotion.get("promoted_count", 0) or 0) if isinstance(promotion, dict) else 0
            )
            report["source_pulse_shadow"] = compact
        except Exception as exc:
            report["source_pulse_shadow"] = {
                "status": "diagnostic_read_error", "candidate_influence": False,
                "paid_api_calls": 0, "web_search_operations": 0,
                "error": f"{type(exc).__name__}: {exc}",
            }
    if _rescue_added(rescue):
        report["editorial_rerun_needed"] = True
        if not report.get("merged_research_path"):
            current = read_json(artifact_dir / "candidates.json")
            if isinstance(current, dict):
                diagnostic = output_root / f"hybrid-completeness-merged-{publication_date}.json"
                runtime_root = base._runtime_root_for(output_root)
                runtime_root.mkdir(parents=True, exist_ok=True)
                runtime = runtime_root / f"hybrid-completeness-merged-{publication_date}.json"
                write_json(diagnostic, current)
                write_json(runtime, current)
                report["diagnostic_merged_research_path"] = str(diagnostic)
                report["merged_research_path"] = str(runtime)
    output_root.mkdir(parents=True, exist_ok=True)
    write_json(output_root / f"hybrid-completeness-{publication_date}.json", report)
    write_json(artifact_dir / "hybrid-completeness.json", report)
    return report


def _run_three_plus_one_region(
    *, artifact_dir: Path, archive_path: Path, publication_date: str,
    api_key: str, model: str, maximum_candidates: int, region: str,
    request_fn: Callable[..., tuple[dict[str, Any], dict[str, Any]]], output_root: Path,
) -> dict[str, Any]:
    report = base.run_hybrid_completeness(
        artifact_dir=artifact_dir,
        archive_path=archive_path,
        publication_date=publication_date,
        api_key=api_key,
        model=model,
        maximum_search_calls=base.FIXED_SEARCH_CALLS,
        maximum_candidates=maximum_candidates,
        request_fn=request_fn,
        output_root=output_root,
    )
    archive = read_json(archive_path)
    research = read_json(artifact_dir / "candidates.json")
    current = research
    merged_path = report.get("merged_research_path")
    if isinstance(merged_path, str) and Path(merged_path).is_file():
        candidate = read_json(Path(merged_path))
        if isinstance(candidate, dict):
            current = candidate
    prompt = _regional_prompt(
        publication_date=publication_date,
        search_window=research["search_window"],
        region=region,
        existing_candidates=current.get("candidates") or [],
        archive=archive,
    )
    record, _ = _execute_attempt(
        research=current, collected=[], archive=archive,
        publication_date=publication_date, direction_id=base.ADAPTIVE_DIRECTION_ID,
        label="China/Asia recall health-check" if region == "asia" else "Russia recall health-check",
        prompt=prompt, api_key=api_key, model=model,
        maximum_candidates=maximum_candidates, request_fn=request_fn,
    )
    record["search_strategy"] = "regional_recall_health"
    record["regional_health_version"] = REGIONAL_HEALTH_VERSION
    record["regional_target"] = region
    record["required_query"] = REGIONAL_QUERIES[region]
    additions = [copy.deepcopy(item) for item in record.get("candidates") or [] if isinstance(item, dict)]
    merged, accepted, rejected = merge_candidates(current, additions, maximum_candidates=maximum_candidates)
    attempts = list(report.get("attempts") or []) + [record]
    completed_calls = base._searches_from_attempts(attempts)
    report.update({
        "version": HYBRID_COMPLETENESS_VERSION,
        "status": "complete" if record.get("status") in {"checked", "checked_with_gaps"} and report.get("status") == "complete" else "complete_with_gaps",
        "strategy": "primary_plus_three_fixed_plus_one_regional_health",
        "attempts": attempts,
        "adaptive_needed": True,
        "regional_health": {
            "version": REGIONAL_HEALTH_VERSION,
            "gaps": [region], "split_when_both": False,
            "publication_quota": False, "domain_filter": False,
            "checks": {region: {
                "checked": record.get("status") in {"checked", "checked_with_gaps"},
                "query": REGIONAL_QUERIES[region],
                "candidate_count": len(additions),
            }},
        },
        "additional_candidates_returned": int(report.get("additional_candidates_returned", 0) or 0) + len(additions),
        "accepted_candidates": list(report.get("accepted_candidates") or []) + accepted,
        "rejected_candidates": list(report.get("rejected_candidates") or []) + rejected,
        "final_candidate_count": len([item for item in merged.get("candidates") or [] if isinstance(item, dict)]),
        "final_cluster_counts": base.cluster_counts([item for item in merged.get("candidates") or [] if isinstance(item, dict)]),
        "editorial_rerun_needed": bool(report.get("editorial_rerun_needed") or accepted),
    })
    report["search_budget"] = {
        **dict(report.get("search_budget") or {}),
        "maximum_calls": DEFAULT_MAXIMUM_SEARCH_CALLS,
        "fixed_calls": FIXED_SEARCH_CALLS,
        "regional_calls_maximum": 1,
        "response_attempts": len(attempts),
        "completed_calls": completed_calls,
        "remaining_calls": max(0, DEFAULT_MAXIMUM_SEARCH_CALLS - completed_calls),
    }
    if accepted:
        diagnostic = output_root / f"hybrid-completeness-merged-{publication_date}.json"
        runtime_root = base._runtime_root_for(output_root)
        runtime_root.mkdir(parents=True, exist_ok=True)
        runtime = runtime_root / f"hybrid-completeness-merged-{publication_date}.json"
        write_json(diagnostic, merged)
        write_json(runtime, merged)
        report["diagnostic_merged_research_path"] = str(diagnostic)
        report["merged_research_path"] = str(runtime)
    return report


def run_hybrid_completeness(
    *, artifact_dir: Path, archive_path: Path, publication_date: str, api_key: str,
    model: str, maximum_search_calls: int = DEFAULT_MAXIMUM_SEARCH_CALLS,
    maximum_candidates: int = 20,
    request_fn: Callable[..., tuple[dict[str, Any], dict[str, Any]]] = base.run_search_request,
    output_root: Path = base.PRODUCTION_PREVIEW_ROOT,
) -> dict[str, Any]:
    if maximum_search_calls < base.FIXED_SEARCH_CALLS:
        raise ValueError(f"Hybrid completeness требует минимум {base.FIXED_SEARCH_CALLS} search operations")
    maximum_search_calls = min(maximum_search_calls, DEFAULT_MAXIMUM_SEARCH_CALLS)
    initial = read_json(artifact_dir / "candidates.json")
    if not isinstance(initial, dict) or not isinstance(initial.get("candidates"), list):
        raise RuntimeError("Hybrid completeness: candidates.json должен быть объектом")

    rescue = _run_pre_hybrid_agency_rescue(
        artifact_dir=artifact_dir, archive_path=archive_path,
        publication_date=publication_date, api_key=api_key, model=model,
        maximum_candidates=maximum_candidates, output_root=output_root,
    )
    rescue = _pre_hybrid_source_freshness_gate(
        rescue=rescue, artifact_dir=artifact_dir,
        publication_date=publication_date, output_root=output_root,
    )
    refreshed = read_json(artifact_dir / "candidates.json")
    research = refreshed if isinstance(refreshed, dict) else initial

    pulse_shadow = run_source_pulse_shadow(
        artifact_dir=artifact_dir, archive_path=archive_path,
        publication_date=publication_date, output_root=output_root,
    )
    promotion = pulse_shadow.get("promotion") if isinstance(pulse_shadow, dict) else None
    fusion = pulse_shadow.get("fusion") if isinstance(pulse_shadow, dict) else None
    summary = fusion.get("summary") if isinstance(fusion, dict) else None
    print(
        "Source Pulse shadow reuse: "
        f"state={pulse_shadow.get('state') if isinstance(pulse_shadow, dict) else 'unknown'}, "
        f"pulse_only={summary.get('pulse_only_count') if isinstance(summary, dict) else 'n/a'}, "
        f"supplemental_promoted={promotion.get('promoted_count') if isinstance(promotion, dict) else 0}; "
        "shadow_mutation=0; paid API calls=0; Web Search operations=0."
    )

    gaps = _regional_gaps(research)
    if not gaps or maximum_search_calls < DEFAULT_MAXIMUM_SEARCH_CALLS:
        report = base.run_hybrid_completeness(
            artifact_dir=artifact_dir, archive_path=archive_path,
            publication_date=publication_date, api_key=api_key, model=model,
            maximum_search_calls=maximum_search_calls,
            maximum_candidates=maximum_candidates, request_fn=request_fn,
            output_root=output_root,
        )
    elif set(gaps) == {"asia", "russia"}:
        archive = read_json(archive_path)
        if not isinstance(archive, dict) or not isinstance(research.get("search_window"), dict):
            report = base.run_hybrid_completeness(
                artifact_dir=artifact_dir, archive_path=archive_path,
                publication_date=publication_date, api_key=api_key, model=model,
                maximum_search_calls=maximum_search_calls,
                maximum_candidates=maximum_candidates, request_fn=request_fn,
                output_root=output_root,
            )
        else:
            report = _run_split_both_regions(
                research=research, archive=archive, publication_date=publication_date,
                api_key=api_key, model=model, maximum_candidates=maximum_candidates,
                request_fn=request_fn, output_root=output_root,
            )
    else:
        report = _run_three_plus_one_region(
            artifact_dir=artifact_dir, archive_path=archive_path,
            publication_date=publication_date, api_key=api_key, model=model,
            maximum_candidates=maximum_candidates, region=gaps[0],
            request_fn=request_fn, output_root=output_root,
        )
    return _attach_quality_layers(
        report=report, rescue=rescue, artifact_dir=artifact_dir,
        publication_date=publication_date, output_root=output_root,
    )


def persist_report(artifact_dir: Path, report: dict[str, Any]) -> None:
    write_json(artifact_dir / "hybrid-completeness.json", report)
    path = base.PRODUCTION_PREVIEW_ROOT / f"hybrid-completeness-{report.get('publication_date', 'unknown')}.json"
    write_json(path, report)
