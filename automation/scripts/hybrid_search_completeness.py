#!/usr/bin/env python3
"""Regional-health wrapper over Hybrid Completeness v1.

Before Hybrid spends its own search budget, a separate bounded quality layer may
spend at most one agency-discovery search when the mandatory ``major_agencies``
Primary route completed with raw=0 or accepted=0.  The rescue is independent of
candidate count and remains distinct from Coverage's same-event
``fresh_agency_rescue`` corroboration.

The first three independent Hybrid completeness searches are unchanged.  The
existing optional fourth Hybrid slot is redirected to a source-neutral
Russia/Asia health-check when Primary Recall completed those regional beats with
zero accepted candidates.  Hybrid itself remains capped at four searches; the
explicit whole-pipeline ceiling is 24 = 12 Primary + 1 agency discovery rescue
+ 4 Hybrid + 7 Coverage.
"""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable

_BASE_PATH = Path(__file__).with_name("hybrid_search_completeness_v1.py")
_BASE_SPEC = importlib.util.spec_from_file_location("hybrid_search_completeness_v1", _BASE_PATH)
assert _BASE_SPEC and _BASE_SPEC.loader
_base = importlib.util.module_from_spec(_BASE_SPEC)
sys.modules[_BASE_SPEC.name] = _base
_BASE_SPEC.loader.exec_module(_base)

for _name in dir(_base):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_base, _name)

from agency_discovery_rescue import (
    AGENCY_DISCOVERY_RESCUE_STRATEGY,
    PIPELINE_MAXIMUM_SEARCH_OPERATIONS,
    run_agency_discovery_rescue,
)


def __getattr__(name: str) -> Any:
    """Preserve the historical module surface for tests and recovery hooks."""
    return getattr(_base, name)


_BASE_RUN = _base.run_hybrid_completeness
REGIONAL_HEALTH_VERSION = 1


def _regional_gaps(research: dict[str, Any]) -> tuple[str, ...]:
    health = research.get("regional_health")
    if not isinstance(health, dict):
        return ()
    result: list[str] = []
    for key in ("asia", "russia"):
        item = health.get(key)
        if isinstance(item, dict) and item.get("health_check_needed") is True:
            result.append(key)
    return tuple(result)


def regional_health_query(gaps: tuple[str, ...]) -> str:
    selected = set(gaps)
    if selected == {"asia", "russia"}:
        return "latest major AI Russia China Asia models products partnerships infrastructure"
    if "asia" in selected:
        return "latest major AI China Asia models products partnerships infrastructure"
    if "russia" in selected:
        return "latest major AI Russia models products business infrastructure"
    raise ValueError("regional health query requires at least one regional gap")


def _regional_prompt(
    *, publication_date: str, search_window: dict[str, Any], gaps: tuple[str, ...],
    existing_candidates: list[Any], archive: dict[str, Any]
) -> str:
    query = regional_health_query(gaps)
    labels = ", ".join(gaps)
    prompt = _base.build_prompt(
        publication_date=publication_date,
        search_window=search_window,
        direction_id=_base.ADAPTIVE_DIRECTION_ID,
        direction_label="Regional recall health-check",
        direction_guidance=(
            "Проверь, не пропущено ли крупное ИИ-событие в регионах с нулевым "
            f"Primary recall: {labels}. Это проверка полноты поиска, а не квота на публикацию. "
            "Не ограничивайся перечисленными компаниями и не предпочитай конкретного издателя."
        ),
        existing_candidates=existing_candidates,
        archive=archive,
        missing_clusters=(),
    )
    return prompt + f"""

Дополнительный контракт regional-health v{REGIONAL_HEALTH_VERSION}:
выполни ровно один source-neutral Web Search без API domain filter. Чтобы результат
был воспроизводимым, фактический query должен быть ТОЧНО:
`{query}`
Слова в query являются retrieval hints, а не обязательными AND-фильтрами для
кандидата. При отсутствии достойной новости верни пустой candidates: это нормальный
результат и не требует искусственно заполнять региональную квоту.
"""


def _run_pre_hybrid_agency_rescue(
    *,
    artifact_dir: Path,
    archive_path: Path,
    publication_date: str,
    api_key: str,
    model: str,
    maximum_candidates: int,
    output_root: Path,
) -> dict[str, Any]:
    """Quality-gap rescue is non-fatal; Hybrid remains available on failure."""
    try:
        report = run_agency_discovery_rescue(
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
            "version": 1,
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
            "duplicate_count": 0,
            "rejections": [
                {
                    "reason_code": "integration_error",
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            ],
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
        write_json(
            output_root / f"agency-discovery-rescue-{publication_date}.json",
            report,
        )
    return report


def _rescue_added(report: dict[str, Any]) -> bool:
    return int(report.get("added_count", 0) or 0) > 0


def _attach_rescue_to_hybrid_report(
    *,
    report: dict[str, Any],
    rescue: dict[str, Any],
    artifact_dir: Path,
    publication_date: str,
    output_root: Path,
) -> dict[str, Any]:
    report = copy.deepcopy(report)
    report["agency_discovery_rescue"] = copy.deepcopy(rescue)
    report["pre_hybrid_quality_search_operations"] = int(
        rescue.get("search_operation_count_contribution", 0) or 0
    )
    report["pipeline_search_budget"] = {
        "primary_maximum": 12,
        "agency_discovery_rescue_maximum": 1,
        "hybrid_maximum": DEFAULT_MAXIMUM_SEARCH_CALLS,
        "coverage_maximum": 7,
        "maximum_total": PIPELINE_MAXIMUM_SEARCH_OPERATIONS,
    }

    if _rescue_added(rescue):
        report["editorial_rerun_needed"] = True
        merged_path = report.get("merged_research_path")
        if not isinstance(merged_path, str) or not Path(merged_path).is_file():
            current = read_json(artifact_dir / "candidates.json")
            if isinstance(current, dict) and isinstance(current.get("candidates"), list):
                output_root.mkdir(parents=True, exist_ok=True)
                diagnostic = (
                    output_root / f"hybrid-completeness-merged-{publication_date}.json"
                )
                runtime_root = _base._runtime_root_for(output_root)
                runtime_root.mkdir(parents=True, exist_ok=True)
                runtime = (
                    runtime_root / f"hybrid-completeness-merged-{publication_date}.json"
                )
                write_json(diagnostic, current)
                write_json(runtime, current)
                report["diagnostic_merged_research_path"] = str(diagnostic)
                report["merged_research_path"] = str(runtime)

    output_root.mkdir(parents=True, exist_ok=True)
    write_json(output_root / f"hybrid-completeness-{publication_date}.json", report)
    write_json(artifact_dir / "hybrid-completeness.json", report)
    return report


def run_hybrid_completeness(
    *, artifact_dir: Path, archive_path: Path, publication_date: str, api_key: str,
    model: str, maximum_search_calls: int = DEFAULT_MAXIMUM_SEARCH_CALLS,
    maximum_candidates: int = 20,
    request_fn: Callable[..., tuple[dict[str, Any], dict[str, Any]]] = run_search_request,
    output_root: Path = PRODUCTION_PREVIEW_ROOT,
) -> dict[str, Any]:
    research = read_json(artifact_dir / "candidates.json")
    if not isinstance(research, dict):
        raise RuntimeError("Hybrid completeness: candidates.json должен быть объектом")

    rescue = _run_pre_hybrid_agency_rescue(
        artifact_dir=artifact_dir,
        archive_path=archive_path,
        publication_date=publication_date,
        api_key=api_key,
        model=model,
        maximum_candidates=maximum_candidates,
        output_root=output_root,
    )
    # Rescue may have added a candidate to the persisted pool. Hybrid must see
    # that event so it does not spend its own searches rediscovering it.
    refreshed = read_json(artifact_dir / "candidates.json")
    if isinstance(refreshed, dict):
        research = refreshed

    gaps = _regional_gaps(research)
    if not gaps or maximum_search_calls < DEFAULT_MAXIMUM_SEARCH_CALLS:
        report = _BASE_RUN(
            artifact_dir=artifact_dir,
            archive_path=archive_path,
            publication_date=publication_date,
            api_key=api_key,
            model=model,
            maximum_search_calls=maximum_search_calls,
            maximum_candidates=maximum_candidates,
            request_fn=request_fn,
            output_root=output_root,
        )
        return _attach_rescue_to_hybrid_report(
            report=report,
            rescue=rescue,
            artifact_dir=artifact_dir,
            publication_date=publication_date,
            output_root=output_root,
        )

    # Reserve the already-existing fourth Hybrid slot for regional recall health.
    report = _BASE_RUN(
        artifact_dir=artifact_dir,
        archive_path=archive_path,
        publication_date=publication_date,
        api_key=api_key,
        model=model,
        maximum_search_calls=FIXED_SEARCH_CALLS,
        maximum_candidates=maximum_candidates,
        request_fn=request_fn,
        output_root=output_root,
    )
    archive = read_json(archive_path)
    search_window = research.get("search_window")
    if not isinstance(archive, dict) or not isinstance(search_window, dict):
        return _attach_rescue_to_hybrid_report(
            report=report,
            rescue=rescue,
            artifact_dir=artifact_dir,
            publication_date=publication_date,
            output_root=output_root,
        )

    current_research = research
    merged_path = report.get("merged_research_path")
    if isinstance(merged_path, str) and Path(merged_path).is_file():
        candidate = read_json(Path(merged_path))
        if isinstance(candidate, dict):
            current_research = candidate
    existing = [
        copy.deepcopy(item)
        for item in current_research.get("candidates", [])
        if isinstance(item, dict)
    ]
    prompt = _regional_prompt(
        publication_date=publication_date,
        search_window=search_window,
        gaps=gaps,
        existing_candidates=existing,
        archive=archive,
    )
    payload: dict[str, Any] | None = None
    metadata: dict[str, Any] = {}
    error: str | None = None
    try:
        payload, metadata = request_fn(
            api_key=api_key, model=model, prompt=prompt, direction_id=ADAPTIVE_DIRECTION_ID
        )
    except CompletenessResponseError as exc:
        metadata = exc.metadata
        error = f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    record = _base._attempt_record(
        direction_id=ADAPTIVE_DIRECTION_ID,
        label="Regional recall health-check",
        prompt=prompt,
        payload=payload,
        metadata=metadata,
        error=error,
    )
    record["search_strategy"] = "regional_recall_health"
    record["regional_health_version"] = REGIONAL_HEALTH_VERSION
    record["regional_gaps"] = list(gaps)
    record["required_query"] = regional_health_query(gaps)

    additions = [
        copy.deepcopy(item)
        for item in record.get("candidates", [])
        if isinstance(item, dict)
    ]
    merged, accepted, rejected = merge_candidates(
        current_research, additions, maximum_candidates=maximum_candidates
    )
    attempts = list(report.get("attempts") or []) + [record]
    completed_calls = _base._searches_from_attempts(attempts)
    checked = record.get("status") in {"checked", "checked_with_gaps"}

    report.update(
        {
            "version": HYBRID_COMPLETENESS_VERSION,
            "status": "complete" if checked else "complete_with_gaps",
            "strategy": "primary_plus_three_fixed_plus_regional_health_when_needed",
            "attempts": attempts,
            "adaptive_needed": True,
            "regional_health": {
                "version": REGIONAL_HEALTH_VERSION,
                "gaps": list(gaps),
                "checked": checked,
                "query": regional_health_query(gaps),
                "candidate_count": len(additions),
                "publication_quota": False,
                "domain_filter": False,
            },
            "additional_candidates_returned": int(
                report.get("additional_candidates_returned", 0) or 0
            )
            + len(additions),
            "accepted_candidates": list(report.get("accepted_candidates") or [])
            + accepted,
            "rejected_candidates": list(report.get("rejected_candidates") or [])
            + rejected,
            "final_candidate_count": len(
                [
                    item
                    for item in merged.get("candidates", [])
                    if isinstance(item, dict)
                ]
            ),
            "final_cluster_counts": cluster_counts(
                [
                    item
                    for item in merged.get("candidates", [])
                    if isinstance(item, dict)
                ]
            ),
            "editorial_rerun_needed": bool(
                report.get("editorial_rerun_needed") or accepted
            ),
        }
    )
    budget = dict(report.get("search_budget") or {})
    budget.update(
        {
            "maximum_calls": min(maximum_search_calls, DEFAULT_MAXIMUM_SEARCH_CALLS),
            "fixed_calls": FIXED_SEARCH_CALLS,
            "adaptive_calls_maximum": 1,
            "response_attempts": len(attempts),
            "completed_calls": completed_calls,
            "remaining_calls": max(
                0,
                min(maximum_search_calls, DEFAULT_MAXIMUM_SEARCH_CALLS)
                - completed_calls,
            ),
        }
    )
    report["search_budget"] = budget

    output_root.mkdir(parents=True, exist_ok=True)
    if accepted:
        diagnostic_merged = (
            output_root / f"hybrid-completeness-merged-{publication_date}.json"
        )
        runtime_root = _base._runtime_root_for(output_root)
        runtime_root.mkdir(parents=True, exist_ok=True)
        runtime_merged = (
            runtime_root / f"hybrid-completeness-merged-{publication_date}.json"
        )
        write_json(diagnostic_merged, merged)
        write_json(runtime_merged, merged)
        report["diagnostic_merged_research_path"] = str(diagnostic_merged)
        report["merged_research_path"] = str(runtime_merged)

    return _attach_rescue_to_hybrid_report(
        report=report,
        rescue=rescue,
        artifact_dir=artifact_dir,
        publication_date=publication_date,
        output_root=output_root,
    )
