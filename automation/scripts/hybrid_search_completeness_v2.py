#!/usr/bin/env python3
"""Hybrid Completeness v2: split regional recall inside the existing four calls.

The quality preflight (agency rescue, rescue freshness, Source Pulse snapshot
reuse) is inherited from the prior regional wrapper.  Only Hybrid slot
allocation changes: with both Primary Russia and Asia gaps open, four calls are
2 broad + 1 China/Asia + 1 Russia.  With one gap the historical 3 broad + 1
regional pattern remains.  The global ceiling stays 24 search operations.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable

import hybrid_search_completeness_regional_v1 as legacy
from story_coverage import merge_candidates, read_json, write_json

# Re-export the stable surface used by runtime/tests.
for _name in dir(legacy):
    if not _name.startswith("_"):
        globals()[_name] = getattr(legacy, _name)

HYBRID_COMPLETENESS_VERSION = 2
REGIONAL_HEALTH_VERSION = 2
DEFAULT_MAXIMUM_SEARCH_CALLS = 4
FIXED_SEARCH_CALLS = 3
SPLIT_FIXED_SEARCH_CALLS = 2
PIPELINE_MAXIMUM_SEARCH_OPERATIONS = 24

REGIONAL_QUERIES = {
    "asia": (
        "latest China AI models products agents robotics chips investment "
        "infrastructure security regulation Qwen DeepSeek GLM Huawei"
    ),
    "russia": (
        "последние новости ИИ Россия модели продукты агенты инвестиции облако "
        "инфраструктура кибербезопасность регулирование"
    ),
}

_LIFECYCLE_DEDUPE_RULE = """
Правило дедупликации жизненного цикла события:
не считай дубликатами разные материальные стадии только из-за общей компании,
модели или календарного дня. В частности, раскрытие автора анонимного preview !=
финальный именованный релиз; анонс финансирования != закрытие сделки; preview !=
публикация весов/production availability. Дубликат требует одного и того же
материального события, а не просто общей сущности. Если новая стадия добавляет
самостоятельные проверяемые факты и имеет собственный свежий источник, оцени её
как отдельный new_event/material_update.
""".strip()


def __getattr__(name: str) -> Any:
    return getattr(legacy, name)


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
        raise ValueError("Hybrid v2 regional query requires exactly one region")
    return REGIONAL_QUERIES[gaps[0]]


def build_prompt(**kwargs: Any) -> str:
    """Stable Hybrid prompt plus a deterministic lifecycle-dedupe clarification."""
    return legacy._base.build_prompt_original(**kwargs) + "\n\n" + _LIFECYCLE_DEDUPE_RULE


def _ensure_original_prompt_hook() -> None:
    if not hasattr(legacy._base, "build_prompt_original"):
        legacy._base.build_prompt_original = legacy._base.build_prompt


def _regional_prompt(
    *, publication_date: str, search_window: dict[str, Any], region: str,
    existing_candidates: list[Any], archive: dict[str, Any],
) -> str:
    query = REGIONAL_QUERIES[region]
    if region == "russia":
        label = "Russia recall health-check"
        guidance = (
            "Проверь крупные свежие события российского ИИ: модели, продукты и агенты, "
            "корпоративное внедрение, инвестиции, облака/инфраструктуру, безопасность и "
            "регулирование. Ищи по русскоязычной экосистеме source-neutral. ТАСС, CNews, "
            "официальные компании и другие надежные источники допустимы, но не являются whitelist."
        )
    else:
        label = "China/Asia recall health-check"
        guidance = (
            "Проверь крупные свежие события Китая/Азии: новые модели и AI-продукты, агенты, "
            "robotics/physical AI, chips/compute, финансирование, инфраструктуру, безопасность "
            "и регулирование. Не ограничивайся перечисленными брендами или издателями."
        )
    prompt = build_prompt(
        publication_date=publication_date,
        search_window=search_window,
        direction_id=legacy.ADAPTIVE_DIRECTION_ID,
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
Это retrieval health-check, а не квота публикации. При отсутствии достойной
новости верни пустой candidates. Не подменяй fresh regional recall старыми
обзорными материалами.
"""


def _attempt(
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
    except legacy.CompletenessResponseError as exc:
        metadata = exc.metadata
        error = f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    record = legacy._base._attempt_record(
        direction_id=direction_id,
        label=label,
        prompt=prompt,
        payload=payload,
        metadata=metadata,
        error=error,
    )
    collected.extend(
        copy.deepcopy(item)
        for item in record.get("candidates") or []
        if isinstance(item, dict)
    )
    provisional, _, _ = merge_candidates(
        research, collected, maximum_candidates=maximum_candidates
    )
    return record, provisional


def _persist_merged_if_needed(
    *, report: dict[str, Any], merged: dict[str, Any], accepted: list[dict[str, Any]],
    publication_date: str, output_root: Path,
) -> None:
    if not accepted:
        return
    diagnostic = output_root / f"hybrid-completeness-merged-{publication_date}.json"
    runtime_root = legacy._base._runtime_root_for(output_root)
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime = runtime_root / f"hybrid-completeness-merged-{publication_date}.json"
    write_json(diagnostic, merged)
    write_json(runtime, merged)
    report["diagnostic_merged_research_path"] = str(diagnostic)
    report["merged_research_path"] = str(runtime)


def _run_base_with_dedupe_rule(**kwargs: Any) -> dict[str, Any]:
    _ensure_original_prompt_hook()
    original = legacy._base.build_prompt
    legacy._base.build_prompt = build_prompt
    try:
        return legacy._BASE_RUN(**kwargs)
    finally:
        legacy._base.build_prompt = original


def _run_split_both(
    *, research: dict[str, Any], archive: dict[str, Any], publication_date: str,
    api_key: str, model: str, maximum_candidates: int,
    request_fn: Callable[..., tuple[dict[str, Any], dict[str, Any]]], output_root: Path,
) -> dict[str, Any]:
    search_window = research["search_window"]
    primary = [
        copy.deepcopy(item) for item in research.get("candidates") or []
        if isinstance(item, dict)
    ]
    attempts: list[dict[str, Any]] = []
    collected: list[dict[str, Any]] = []
    working = copy.deepcopy(research)

    for direction in legacy.COMPLETENESS_DIRECTIONS[:SPLIT_FIXED_SEARCH_CALLS]:
        prompt = build_prompt(
            publication_date=publication_date,
            search_window=search_window,
            direction_id=direction["id"],
            direction_label=direction["label"],
            direction_guidance=direction["guidance"],
            existing_candidates=working.get("candidates") or [],
            archive=archive,
        )
        record, working = _attempt(
            research=research, collected=collected, archive=archive,
            publication_date=publication_date, direction_id=direction["id"],
            label=direction["label"], prompt=prompt, api_key=api_key, model=model,
            maximum_candidates=maximum_candidates, request_fn=request_fn,
        )
        attempts.append(record)

    counts_after_fixed = legacy.cluster_counts([
        item for item in working.get("candidates") or [] if isinstance(item, dict)
    ])
    missing_after_fixed = [
        item["id"] for item in legacy.COMPLETENESS_DIRECTIONS
        if counts_after_fixed.get(item["id"], 0) == 0
    ]

    regional_checks: dict[str, Any] = {}
    for region in ("asia", "russia"):
        label = "China/Asia recall health-check" if region == "asia" else "Russia recall health-check"
        prompt = _regional_prompt(
            publication_date=publication_date,
            search_window=search_window,
            region=region,
            existing_candidates=working.get("candidates") or [],
            archive=archive,
        )
        record, working = _attempt(
            research=research, collected=collected, archive=archive,
            publication_date=publication_date,
            direction_id=legacy.ADAPTIVE_DIRECTION_ID,
            label=label, prompt=prompt, api_key=api_key, model=model,
            maximum_candidates=maximum_candidates, request_fn=request_fn,
        )
        record["search_strategy"] = "regional_recall_health_split"
        record["regional_health_version"] = REGIONAL_HEALTH_VERSION
        record["regional_target"] = region
        record["required_query"] = REGIONAL_QUERIES[region]
        attempts.append(record)
        regional_checks[region] = {
            "checked": record.get("status") in {"checked", "checked_with_gaps"},
            "query": REGIONAL_QUERIES[region],
            "candidate_count": int(record.get("candidate_count", 0) or 0),
        }

    merged, accepted, rejected = merge_candidates(
        research, collected, maximum_candidates=maximum_candidates
    )
    final = [
        item for item in merged.get("candidates") or [] if isinstance(item, dict)
    ]
    completed = legacy._base._searches_from_attempts(attempts)
    complete = len(attempts) == 4 and all(
        item.get("status") in {"checked", "checked_with_gaps"} for item in attempts
    )
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
            "completed_calls": completed,
            "remaining_calls": max(0, DEFAULT_MAXIMUM_SEARCH_CALLS - completed),
            "maximum_total_tool_calls_per_pass": legacy.HYBRID_MAX_TOOL_CALLS_PER_PASS,
            "navigation_tool_allowance_per_pass": legacy.HYBRID_NAVIGATION_TOOL_ALLOWANCE,
        },
        "primary_candidate_count": len(primary),
        "primary_cluster_counts": legacy.cluster_counts(primary),
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
        "final_cluster_counts": legacy.cluster_counts(final),
        "editorial_rerun_needed": bool(accepted),
        "merged_research_path": None,
        "diagnostic_merged_research_path": None,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    _persist_merged_if_needed(
        report=report, merged=merged, accepted=accepted,
        publication_date=publication_date, output_root=output_root,
    )
    return report


def _run_one_region(
    *, artifact_dir: Path, research: dict[str, Any], archive_path: Path,
    publication_date: str, api_key: str, model: str, maximum_candidates: int,
    region: str, request_fn: Callable[..., tuple[dict[str, Any], dict[str, Any]]],
    output_root: Path,
) -> dict[str, Any]:
    report = _run_base_with_dedupe_rule(
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
    current = research
    merged_path = report.get("merged_research_path")
    if isinstance(merged_path, str) and Path(merged_path).is_file():
        candidate = read_json(Path(merged_path))
        if isinstance(candidate, dict):
            current = candidate
    collected: list[dict[str, Any]] = []
    prompt = _regional_prompt(
        publication_date=publication_date,
        search_window=research["search_window"],
        region=region,
        existing_candidates=current.get("candidates") or [],
        archive=archive,
    )
    label = "China/Asia recall health-check" if region == "asia" else "Russia recall health-check"
    record, _ = _attempt(
        research=current, collected=collected, archive=archive,
        publication_date=publication_date,
        direction_id=legacy.ADAPTIVE_DIRECTION_ID,
        label=label, prompt=prompt, api_key=api_key, model=model,
        maximum_candidates=maximum_candidates, request_fn=request_fn,
    )
    record["search_strategy"] = "regional_recall_health"
    record["regional_health_version"] = REGIONAL_HEALTH_VERSION
    record["regional_target"] = region
    record["required_query"] = REGIONAL_QUERIES[region]
    merged, accepted, rejected = merge_candidates(
        current, collected, maximum_candidates=maximum_candidates
    )
    attempts = list(report.get("attempts") or []) + [record]
    completed = legacy._base._searches_from_attempts(attempts)
    final = [item for item in merged.get("candidates") or [] if isinstance(item, dict)]
    report.update({
        "version": HYBRID_COMPLETENESS_VERSION,
        "status": (
            "complete" if report.get("status") == "complete"
            and record.get("status") in {"checked", "checked_with_gaps"}
            else "complete_with_gaps"
        ),
        "strategy": "primary_plus_three_fixed_plus_one_regional_health",
        "attempts": attempts,
        "adaptive_needed": True,
        "regional_health": {
            "version": REGIONAL_HEALTH_VERSION,
            "gaps": [region],
            "checked": record.get("status") in {"checked", "checked_with_gaps"},
            "split_when_both": False,
            "checks": {region: {
                "checked": record.get("status") in {"checked", "checked_with_gaps"},
                "query": REGIONAL_QUERIES[region],
                "candidate_count": len(collected),
            }},
            "publication_quota": False,
            "domain_filter": False,
        },
        "additional_candidates_returned": int(report.get("additional_candidates_returned", 0) or 0) + len(collected),
        "accepted_candidates": list(report.get("accepted_candidates") or []) + accepted,
        "rejected_candidates": list(report.get("rejected_candidates") or []) + rejected,
        "final_candidate_count": len(final),
        "final_cluster_counts": legacy.cluster_counts(final),
        "editorial_rerun_needed": bool(report.get("editorial_rerun_needed") or accepted),
    })
    report["search_budget"] = {
        **dict(report.get("search_budget") or {}),
        "maximum_calls": DEFAULT_MAXIMUM_SEARCH_CALLS,
        "fixed_calls": FIXED_SEARCH_CALLS,
        "regional_calls_maximum": 1,
        "response_attempts": len(attempts),
        "completed_calls": completed,
        "remaining_calls": max(0, DEFAULT_MAXIMUM_SEARCH_CALLS - completed),
    }
    _persist_merged_if_needed(
        report=report, merged=merged, accepted=accepted,
        publication_date=publication_date, output_root=output_root,
    )
    return report


def _attach_quality_layers(
    *, report: dict[str, Any], rescue: dict[str, Any], artifact_dir: Path,
    publication_date: str, output_root: Path,
) -> dict[str, Any]:
    report = legacy._attach_rescue_to_hybrid_report(
        report=report,
        rescue=rescue,
        artifact_dir=artifact_dir,
        publication_date=publication_date,
        output_root=output_root,
    )
    pulse_path = artifact_dir / "source-pulse.json"
    if pulse_path.is_file():
        try:
            pulse = read_json(pulse_path)
            compact = dict(report.get("source_pulse_shadow") or {})
            promotion = pulse.get("promotion") if isinstance(pulse, dict) else None
            compact["supplemental_candidate_influence"] = bool(
                isinstance(pulse, dict) and pulse.get("supplemental_candidate_influence") is True
            )
            compact["supplemental_promoted_count"] = (
                int(promotion.get("promoted_count", 0) or 0)
                if isinstance(promotion, dict) else 0
            )
            report["source_pulse_shadow"] = compact
            write_json(artifact_dir / "hybrid-completeness.json", report)
            write_json(output_root / f"hybrid-completeness-{publication_date}.json", report)
        except Exception:
            pass
    return report


def run_hybrid_completeness(
    *, artifact_dir: Path, archive_path: Path, publication_date: str, api_key: str,
    model: str, maximum_search_calls: int = DEFAULT_MAXIMUM_SEARCH_CALLS,
    maximum_candidates: int = 20,
    request_fn: Callable[..., tuple[dict[str, Any], dict[str, Any]]] = legacy.run_search_request,
    output_root: Path = legacy.PRODUCTION_PREVIEW_ROOT,
) -> dict[str, Any]:
    if maximum_search_calls < FIXED_SEARCH_CALLS:
        raise ValueError(f"Hybrid completeness требует минимум {FIXED_SEARCH_CALLS} search operations")
    maximum_search_calls = min(maximum_search_calls, DEFAULT_MAXIMUM_SEARCH_CALLS)
    research = read_json(artifact_dir / "candidates.json")
    if not isinstance(research, dict) or not isinstance(research.get("candidates"), list):
        raise RuntimeError("Hybrid completeness: candidates.json имеет неожиданную структуру")

    rescue = legacy._run_pre_hybrid_agency_rescue(
        artifact_dir=artifact_dir,
        archive_path=archive_path,
        publication_date=publication_date,
        api_key=api_key,
        model=model,
        maximum_candidates=maximum_candidates,
        output_root=output_root,
    )
    rescue = legacy._pre_hybrid_source_freshness_gate(
        rescue=rescue,
        artifact_dir=artifact_dir,
        publication_date=publication_date,
        output_root=output_root,
    )
    refreshed = read_json(artifact_dir / "candidates.json")
    if isinstance(refreshed, dict):
        research = refreshed

    pulse = legacy.run_source_pulse_shadow(
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

    gaps = _regional_gaps(research)
    if not gaps or maximum_search_calls < DEFAULT_MAXIMUM_SEARCH_CALLS:
        report = _run_base_with_dedupe_rule(
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
    elif set(gaps) == {"asia", "russia"}:
        archive = read_json(archive_path)
        if not isinstance(archive, dict) or not isinstance(research.get("search_window"), dict):
            report = _run_base_with_dedupe_rule(
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
        else:
            report = _run_split_both(
                research=research,
                archive=archive,
                publication_date=publication_date,
                api_key=api_key,
                model=model,
                maximum_candidates=maximum_candidates,
                request_fn=request_fn,
                output_root=output_root,
            )
    else:
        report = _run_one_region(
            artifact_dir=artifact_dir,
            research=research,
            archive_path=archive_path,
            publication_date=publication_date,
            api_key=api_key,
            model=model,
            maximum_candidates=maximum_candidates,
            region=gaps[0],
            request_fn=request_fn,
            output_root=output_root,
        )
    return _attach_quality_layers(
        report=report,
        rescue=rescue,
        artifact_dir=artifact_dir,
        publication_date=publication_date,
        output_root=output_root,
    )


def persist_report(artifact_dir: Path, report: dict[str, Any]) -> None:
    write_json(artifact_dir / "hybrid-completeness.json", report)
    path = legacy.PRODUCTION_PREVIEW_ROOT / f"hybrid-completeness-{report.get('publication_date', 'unknown')}.json"
    write_json(path, report)
