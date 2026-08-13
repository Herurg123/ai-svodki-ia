#!/usr/bin/env python3
"""Budget-capped independent completeness search layered over primary research.

Hybrid remains an independent safety net after Primary Recall v2.  Each pass is
limited to one actual search operation, but may spend a small separate hosted-
tool allowance opening/finding pages from that search.  Accepted merged research
is staged under the generator's trusted runtime-research root while diagnostics
remain in automation/preview.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ensure_story_coverage_policy import (
    AUDIT_CANDIDATE_SCHEMA,
    AUDIT_REJECTION_SCHEMA,
    build_audit_api_metadata,
)
from story_coverage import compact_archive, merge_candidates, read_json, write_json

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_PREVIEW_ROOT = REPOSITORY_ROOT / "automation" / "preview" / "production-daily"
RUNTIME_RESEARCH_ROOT = REPOSITORY_ROOT / "automation" / "fixtures" / "research" / ".runtime"

HYBRID_COMPLETENESS_VERSION = 1
DEFAULT_MAXIMUM_SEARCH_CALLS = 4
FIXED_SEARCH_CALLS = 3
HYBRID_NAVIGATION_TOOL_ALLOWANCE = 3
HYBRID_MAX_TOOL_CALLS_PER_PASS = 1 + HYBRID_NAVIGATION_TOOL_ALLOWANCE

COMPLETENESS_DIRECTIONS: tuple[dict[str, str], ...] = (
    {
        "id": "models_products_research",
        "label": "Models / products / agents / research",
        "guidance": (
            "Ищи крупные новые модели и существенные обновления, AI-продукты, "
            "агентов и coding tools, важные research-результаты, multimodal, "
            "robotics и заметные open-weight/open-source релизы."
        ),
    },
    {
        "id": "infrastructure_business",
        "label": "Infrastructure / chips / business",
        "guidance": (
            "Ищи крупные AI-чипы, HBM, дата-центры, облака и инфраструктуру, "
            "сделки и M&A, инвестиции, существенные earnings/enterprise-события "
            "и стратегические корпоративные решения вокруг ИИ."
        ),
    },
    {
        "id": "safety_policy_regions",
        "label": "Safety / security / policy / regions",
        "guidance": (
            "Ищи крупные события AI safety и cybersecurity, тестирование и "
            "инциденты frontier-моделей, регулирование и значимые legal-события, "
            "а также важные сюжеты Китая/Азии и России, которые могли выпасть из "
            "основного мирового discovery."
        ),
    },
)
ADAPTIVE_DIRECTION_ID = "adaptive_gap"
DIRECTION_IDS = tuple(item["id"] for item in COMPLETENESS_DIRECTIONS) + (ADAPTIVE_DIRECTION_ID,)

CLUSTER_CATEGORIES: dict[str, frozenset[str]] = {
    "models_products_research": frozenset(
        {"models", "agents", "coding", "research", "multimodal", "robotics", "open_source"}
    ),
    "infrastructure_business": frozenset({"infrastructure", "chips", "enterprise", "investment"}),
    "safety_policy_regions": frozenset({"security", "regulation", "legal", "russia"}),
}

COMPLETENESS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {"type": "string", "enum": ["complete", "complete_with_gaps", "error"]},
        "error_message": {"type": ["string", "null"]},
        "direction_id": {"type": "string", "enum": list(DIRECTION_IDS)},
        "candidates": {
            "type": "array",
            "minItems": 0,
            "maxItems": 6,
            "items": AUDIT_CANDIDATE_SCHEMA,
        },
        "rejections": {
            "type": "array",
            "minItems": 0,
            "maxItems": 10,
            "items": AUDIT_REJECTION_SCHEMA,
        },
        "notes": {"type": "string", "minLength": 1},
    },
    "required": ["status", "error_message", "direction_id", "candidates", "rejections", "notes"],
}


class CompletenessResponseError(RuntimeError):
    def __init__(self, message: str, metadata: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.metadata = metadata or {}


def _eligible(candidate: Any) -> bool:
    return bool(
        isinstance(candidate, dict)
        and candidate.get("recommendation") in {"include", "consider"}
        and candidate.get("verification_status") == "verified"
        and candidate.get("freshness_status") in {"new_event", "material_update"}
    )


def candidate_clusters(candidate: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    category = str(candidate.get("category") or "")
    for cluster, categories in CLUSTER_CATEGORIES.items():
        if category in categories:
            result.add(cluster)
    if candidate.get("geography") == "russia":
        result.add("safety_policy_regions")
    return result


def cluster_counts(candidates: list[Any]) -> dict[str, int]:
    counts = {item["id"]: 0 for item in COMPLETENESS_DIRECTIONS}
    for raw in candidates:
        if not _eligible(raw):
            continue
        assert isinstance(raw, dict)
        for cluster in candidate_clusters(raw):
            counts[cluster] += 1
    return counts


def _compact_candidates(candidates: list[Any], limit: int = 20) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in candidates:
        if not isinstance(raw, dict):
            continue
        primary = raw.get("primary_source")
        result.append(
            {
                "title": raw.get("title"),
                "organization": raw.get("organization"),
                "published_date": raw.get("published_date"),
                "category": raw.get("category"),
                "geography": raw.get("geography"),
                "recommendation": raw.get("recommendation"),
                "primary_url": primary.get("url") if isinstance(primary, dict) else None,
            }
        )
        if len(result) >= limit:
            break
    return result


def _compact_archive(archive: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in compact_archive(archive, limit=14):
        if not isinstance(raw, dict):
            continue
        result.append(
            {"date": raw.get("date"), "stories": raw.get("stories", []), "source_urls": raw.get("source_urls", [])}
        )
    return result


def _time_hint(search_window: dict[str, Any]) -> str:
    try:
        start = datetime.fromisoformat(str(search_window.get("start_at") or "").replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(search_window.get("end_at") or "").replace("Z", "+00:00"))
        return (
            "Для единственного search query используй короткую natural-language фразу "
            f"примерно на 6–18 значимых слов и обычные календарные даты {start.date()} "
            f"и {end.date()}. Не используй after:, before:, site:, скобки или длинные "
            "OR-цепочки. После выдачи проверь фактический timestamp против точных "
            "границ effective window."
        )
    except ValueError:
        return (
            "В поисковом запросе явно укажи календарные даты effective window обычным "
            "текстом; не используй after:, before:, site: или длинные OR-цепочки и "
            "проверь timestamp источника."
        )


def build_prompt(
    *,
    publication_date: str,
    search_window: dict[str, Any],
    direction_id: str,
    direction_label: str,
    direction_guidance: str,
    existing_candidates: list[Any],
    archive: dict[str, Any],
    missing_clusters: tuple[str, ...] = (),
) -> str:
    start_at = str(search_window.get("start_at") or "")
    end_at = str(search_window.get("end_at") or "")
    adaptive_note = ""
    if missing_clusters:
        adaptive_note = (
            "\nАдаптивный приоритет: после трёх независимых проходов в объединённом "
            "пуле остаются пустыми кластеры: "
            + ", ".join(missing_clusters)
            + ". Сконцентрируй единственный поиск на этих пробелах, не повторяя уже найденные сюжеты.\n"
        )
    return f"""Ты — независимый completeness-проход редакции «ИИ-Сводки».

Дата выпуска: {publication_date}
Эффективное редакционное окно: {start_at} → {end_at}
Авторитетное текущее время задачи: {end_at}
Идентификатор прохода: {direction_id}
Роль прохода: {direction_label}

Основной research уже завершён и НЕ должен заменяться. Твоя задача — дать ему
независимый второй шанс заметить крупное событие, которое могло выпасть из
первичного discovery. Выполни РОВНО ОДНУ поисковую операцию Web Search и один
логический query. Второй search запрещён. После выдачи можно и нужно использовать
open_page/find_in_page для проверки релевантных страниц; эти навигационные tool
calls не расходуют search-operation budget. API domain filter отсутствует
намеренно: discovery должен быть широким, а качество источника проверяется после
получения результатов.

{_time_hint(search_window)}

Тематическая задача:
{direction_guidance}
{adaptive_note}
Ищи только самостоятельные события высокой новостной ценности. Предпочитай
официальный первоисточник, Reuters/AP/Bloomberg/FT или авторитетное деловое,
технологическое и отраслевое СМИ. Не считай SEO-пересказ, слух, старую статью или
малозначительный комментарий полноценной новостью. Для спорного утверждения
нужна достаточная проверяемость.

Событие и основной источник обязаны попадать в effective window. Контролируемый
overlap до предыдущего continuity cutoff существует для восстановления крупных
пропусков, но уже опубликованные архивные события нельзя повторять. Для
include/consider обязательны verification_status=verified и freshness_status
new_event/material_update. Точное время не выдумывай: если его нет, используй
published_at=null и time_precision=date. Не добивай количество слабым материалом.

Уже найденные кандидаты, которые нельзя дублировать:
{json.dumps(_compact_candidates(existing_candidates), ensure_ascii=False, indent=2)}

Недавний архив для дедупликации:
{json.dumps(_compact_archive(archive), ensure_ascii=False, indent=2)}

Верни до 4 действительно достойных NEW-only кандидатов по JSON-схеме. Если
ничего достойного не найдено, верни пустой candidates и status=complete_with_gaps.
direction_id должен быть строго {direction_id}. Верни только JSON по схеме."""


def run_search_request(
    *, api_key: str, model: str, prompt: str, direction_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=1200.0, max_retries=2)
    response = client.responses.create(
        model=model,
        input=prompt,
        tools=[{"type": "web_search", "search_context_size": "medium", "return_token_budget": "default"}],
        tool_choice="required",
        max_tool_calls=HYBRID_MAX_TOOL_CALLS_PER_PASS,
        include=["web_search_call.action.sources"],
        reasoning={"effort": "medium"},
        max_output_tokens=3500,
        text={
            "format": {
                "type": "json_schema",
                "name": "daily_ai_hybrid_completeness",
                "strict": True,
                "schema": COMPLETENESS_SCHEMA,
            }
        },
        store=False,
    )
    metadata = build_audit_api_metadata(response, maximum_web_search_calls=1)
    metadata["configured_search_operations"] = 1
    metadata["configured_total_tool_calls"] = HYBRID_MAX_TOOL_CALLS_PER_PASS
    metadata["navigation_tool_allowance"] = HYBRID_NAVIGATION_TOOL_ALLOWANCE
    completed = int(metadata.get("web_search_calls_completed", 0) or 0)
    if completed != 1:
        raise CompletenessResponseError(
            f"Completeness pass должен завершить ровно один Web Search, получено {completed}", metadata
        )
    actual_queries = list(metadata.get("actual_queries") or [])
    if len(actual_queries) != 1:
        raise CompletenessResponseError(
            f"Completeness pass должен выполнить один логический query, получено {len(actual_queries)}", metadata
        )
    if getattr(response, "status", None) != "completed":
        raise CompletenessResponseError(
            f"Completeness pass не завершён: status={getattr(response, 'status', None)!r}", metadata
        )
    output_text = (getattr(response, "output_text", None) or "").strip()
    if not output_text:
        raise CompletenessResponseError("Completeness pass вернул пустой output_text", metadata)
    try:
        payload = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise CompletenessResponseError(f"Completeness pass вернул некорректный JSON: {exc}", metadata) from exc
    if not isinstance(payload, dict):
        raise CompletenessResponseError("Completeness pass должен вернуть JSON-объект", metadata)
    if payload.get("direction_id") != direction_id:
        raise CompletenessResponseError("Completeness pass вернул чужой direction_id", metadata)
    if payload.get("status") not in {"complete", "complete_with_gaps"}:
        raise CompletenessResponseError(
            f"Completeness pass вернул непригодный status={payload.get('status')!r}", metadata
        )
    return payload, metadata


def _normalize_candidate(candidate: dict[str, Any], direction_id: str) -> dict[str, Any]:
    value = copy.deepcopy(candidate)
    value["audit_direction"] = f"hybrid_{direction_id}"
    if value.get("category") != "legal":
        value["legal_scale"] = "not_applicable"
        value["legal_scale_reason"] = ""
    return value


def _attempt_record(
    *, direction_id: str, label: str, prompt: str, payload: dict[str, Any] | None,
    metadata: dict[str, Any], error: str | None
) -> dict[str, Any]:
    raw_candidates = payload.get("candidates") if isinstance(payload, dict) else []
    candidates = (
        [_normalize_candidate(item, direction_id) for item in raw_candidates if isinstance(item, dict)]
        if isinstance(raw_candidates, list) else []
    )
    return {
        "direction_id": direction_id,
        "label": label,
        "prompt": prompt,
        "status": (
            "checked" if isinstance(payload, dict) and payload.get("status") == "complete"
            else "checked_with_gaps" if isinstance(payload, dict) and payload.get("status") == "complete_with_gaps"
            else "error"
        ),
        "actual_queries": list(metadata.get("actual_queries") or []),
        "sources": list(metadata.get("consulted_sources") or []),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "rejections": list(payload.get("rejections") or []) if isinstance(payload, dict) else [],
        "notes": payload.get("notes") if isinstance(payload, dict) else None,
        "api": metadata or None,
        "error": error,
    }


def _searches_from_attempts(attempts: list[dict[str, Any]]) -> int:
    return sum(
        int((item.get("api") or {}).get("web_search_calls_completed", 0) or 0)
        for item in attempts if isinstance(item, dict)
    )


def _runtime_root_for(output_root: Path) -> Path:
    try:
        if output_root.resolve() == PRODUCTION_PREVIEW_ROOT.resolve():
            return RUNTIME_RESEARCH_ROOT
    except OSError:
        pass
    return output_root / ".runtime"


def run_hybrid_completeness(
    *,
    artifact_dir: Path,
    archive_path: Path,
    publication_date: str,
    api_key: str,
    model: str,
    maximum_search_calls: int = DEFAULT_MAXIMUM_SEARCH_CALLS,
    maximum_candidates: int = 20,
    request_fn: Callable[..., tuple[dict[str, Any], dict[str, Any]]] = run_search_request,
    output_root: Path = PRODUCTION_PREVIEW_ROOT,
) -> dict[str, Any]:
    if maximum_search_calls < FIXED_SEARCH_CALLS:
        raise ValueError(f"Hybrid completeness требует минимум {FIXED_SEARCH_CALLS} search operations")
    maximum_search_calls = min(maximum_search_calls, DEFAULT_MAXIMUM_SEARCH_CALLS)
    research = read_json(artifact_dir / "candidates.json")
    archive = read_json(archive_path)
    if not isinstance(research, dict) or not isinstance(research.get("candidates"), list):
        raise RuntimeError("Hybrid completeness: candidates.json имеет неожиданную структуру")
    if not isinstance(research.get("search_window"), dict):
        raise RuntimeError("Hybrid completeness: отсутствует search_window")
    if not isinstance(archive, dict):
        raise RuntimeError("Hybrid completeness: archive index должен быть объектом")

    search_window = research["search_window"]
    primary_candidates = [copy.deepcopy(item) for item in research.get("candidates", []) if isinstance(item, dict)]
    attempts: list[dict[str, Any]] = []
    collected: list[dict[str, Any]] = []
    working_candidates = copy.deepcopy(primary_candidates)

    def execute(direction_id: str, label: str, guidance: str, missing: tuple[str, ...] = ()) -> None:
        nonlocal working_candidates
        prompt = build_prompt(
            publication_date=publication_date,
            search_window=search_window,
            direction_id=direction_id,
            direction_label=label,
            direction_guidance=guidance,
            existing_candidates=working_candidates,
            archive=archive,
            missing_clusters=missing,
        )
        payload: dict[str, Any] | None = None
        metadata: dict[str, Any] = {}
        error: str | None = None
        try:
            payload, metadata = request_fn(api_key=api_key, model=model, prompt=prompt, direction_id=direction_id)
        except CompletenessResponseError as exc:
            metadata = exc.metadata
            error = f"{type(exc).__name__}: {exc}"
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        record = _attempt_record(
            direction_id=direction_id, label=label, prompt=prompt, payload=payload, metadata=metadata, error=error
        )
        attempts.append(record)
        collected.extend(copy.deepcopy(record["candidates"]))
        provisional, _, _ = merge_candidates(research, collected, maximum_candidates=maximum_candidates)
        working_candidates = [copy.deepcopy(item) for item in provisional.get("candidates", []) if isinstance(item, dict)]

    for direction in COMPLETENESS_DIRECTIONS:
        execute(direction["id"], direction["label"], direction["guidance"])

    provisional, _, _ = merge_candidates(research, collected, maximum_candidates=maximum_candidates)
    counts_after_fixed = cluster_counts([item for item in provisional.get("candidates", []) if isinstance(item, dict)])
    missing_clusters = tuple(
        item["id"] for item in COMPLETENESS_DIRECTIONS if counts_after_fixed.get(item["id"], 0) == 0
    )
    adaptive_needed = bool(missing_clusters) and len(attempts) < maximum_search_calls
    if adaptive_needed:
        execute(
            ADAPTIVE_DIRECTION_ID,
            "Adaptive gap query",
            "Один адаптивный last-mile проход по очевидным пустым кластерам: "
            + ", ".join(missing_clusters)
            + ". Проверь прежде всего крупные события, которые могли не попасть ни в primary, ни в три фиксированных completeness-прохода.",
            missing_clusters,
        )

    merged, accepted, rejected = merge_candidates(research, collected, maximum_candidates=maximum_candidates)
    final_candidates = [item for item in merged.get("candidates", []) if isinstance(item, dict)]
    fixed_completed = sum(
        1 for item in attempts[:FIXED_SEARCH_CALLS] if item.get("status") in {"checked", "checked_with_gaps"}
    )
    adaptive_record = next(
        (item for item in attempts if item.get("direction_id") == ADAPTIVE_DIRECTION_ID), None
    )
    complete = fixed_completed == FIXED_SEARCH_CALLS and (
        not adaptive_needed or (
            isinstance(adaptive_record, dict)
            and adaptive_record.get("status") in {"checked", "checked_with_gaps"}
        )
    )
    report: dict[str, Any] = {
        "version": HYBRID_COMPLETENESS_VERSION,
        "status": "complete" if complete else "complete_with_gaps",
        "publication_date": publication_date,
        "search_window": copy.deepcopy(search_window),
        "strategy": "primary_plus_three_fixed_plus_optional_adaptive_gap",
        "search_budget": {
            "maximum_calls": maximum_search_calls,
            "fixed_calls": FIXED_SEARCH_CALLS,
            "adaptive_calls_maximum": 1,
            "response_attempts": len(attempts),
            "completed_calls": _searches_from_attempts(attempts),
            "remaining_calls": max(0, maximum_search_calls - _searches_from_attempts(attempts)),
            "maximum_total_tool_calls_per_pass": HYBRID_MAX_TOOL_CALLS_PER_PASS,
            "navigation_tool_allowance_per_pass": HYBRID_NAVIGATION_TOOL_ALLOWANCE,
        },
        "primary_candidate_count": len(primary_candidates),
        "primary_cluster_counts": cluster_counts(primary_candidates),
        "cluster_counts_after_fixed": counts_after_fixed,
        "missing_clusters_after_fixed": list(missing_clusters),
        "adaptive_needed": adaptive_needed,
        "attempts": attempts,
        "additional_candidates_returned": len(collected),
        "accepted_candidates": accepted,
        "rejected_candidates": rejected,
        "final_candidate_count": len(final_candidates),
        "final_cluster_counts": cluster_counts(final_candidates),
        "editorial_rerun_needed": bool(accepted),
        "merged_research_path": None,
        "diagnostic_merged_research_path": None,
    }

    output_root.mkdir(parents=True, exist_ok=True)
    report_path = output_root / f"hybrid-completeness-{publication_date}.json"
    if accepted:
        diagnostic_merged = output_root / f"hybrid-completeness-merged-{publication_date}.json"
        runtime_root = _runtime_root_for(output_root)
        runtime_root.mkdir(parents=True, exist_ok=True)
        runtime_merged = runtime_root / f"hybrid-completeness-merged-{publication_date}.json"
        write_json(diagnostic_merged, merged)
        write_json(runtime_merged, merged)
        report["diagnostic_merged_research_path"] = str(diagnostic_merged)
        report["merged_research_path"] = str(runtime_merged)
    write_json(report_path, report)
    write_json(artifact_dir / "hybrid-completeness.json", report)
    return report


def persist_report(artifact_dir: Path, report: dict[str, Any]) -> None:
    write_json(artifact_dir / "hybrid-completeness.json", report)
    production_path = PRODUCTION_PREVIEW_ROOT / f"hybrid-completeness-{report.get('publication_date', 'unknown')}.json"
    write_json(production_path, report)
