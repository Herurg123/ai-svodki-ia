#!/usr/bin/env python3
"""Budget-capped independent completeness search layered over primary research.

The primary research result remains canonical input. This module performs three
one-search high-signal passes and, only when the combined pool still has an
obvious thematic hole, one adaptive gap pass. New candidates are merged through
the existing story-coverage validator and can be fed back into editorial without
re-running paid primary research.
"""
from __future__ import annotations

import copy
import json
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

HYBRID_COMPLETENESS_VERSION = 1
DEFAULT_MAXIMUM_SEARCH_CALLS = 4
FIXED_SEARCH_CALLS = 3

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
DIRECTION_IDS = tuple(item["id"] for item in COMPLETENESS_DIRECTIONS) + (
    ADAPTIVE_DIRECTION_ID,
)

CLUSTER_CATEGORIES: dict[str, frozenset[str]] = {
    "models_products_research": frozenset(
        {
            "models",
            "agents",
            "coding",
            "research",
            "multimodal",
            "robotics",
            "open_source",
        }
    ),
    "infrastructure_business": frozenset(
        {"infrastructure", "chips", "enterprise", "investment"}
    ),
    "safety_policy_regions": frozenset(
        {"security", "regulation", "legal", "russia"}
    ),
}

COMPLETENESS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {
            "type": "string",
            "enum": ["complete", "complete_with_gaps", "error"],
        },
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
    "required": [
        "status",
        "error_message",
        "direction_id",
        "candidates",
        "rejections",
        "notes",
    ],
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
            {
                "date": raw.get("date"),
                "stories": raw.get("stories", []),
                "source_urls": raw.get("source_urls", []),
            }
        )
    return result


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
            + ". Сконцентрируй единственный поиск на этих пробелах, не повторяя "
            "уже найденные сюжеты.\n"
        )
    return f"""Ты — независимый completeness-проход редакции «ИИ-Сводки».

Дата выпуска: {publication_date}
Строгое редакционное окно: {start_at} → {end_at}
Авторитетное текущее время задачи: {end_at}
Идентификатор прохода: {direction_id}
Роль прохода: {direction_label}

Основной research уже завершён и НЕ должен заменяться. Твоя задача — дать ему
независимый второй шанс заметить крупное событие, которое могло выпасть из
первичного discovery. Выполни РОВНО ОДИН Web Search. Не делай несколько
независимых search operations внутри этого прохода. После выдачи можешь открыть
релевантные страницы для проверки, но дополнительные поисковые операции не нужны.
API domain filter отсутствует намеренно: discovery должен быть широким, а
качество источника проверяется после получения результатов.

Тематическая задача:
{direction_guidance}
{adaptive_note}
Ищи только самостоятельные события высокой новостной ценности. Предпочитай
официальный первоисточник, Reuters/AP/Bloomberg/FT или авторитетное деловое,
технологическое и отраслевое СМИ. Не считай SEO-пересказ, слух, старую статью или
малозначительный комментарий полноценной новостью. Для спорного утверждения
нужна достаточная проверяемость.

Событие и основной источник обязаны попадать в редакционное окно. Всё, что не
позже {end_at}, не является будущим независимо от системной даты модели или UTC
среды исполнения. Старую перепечатку без нового развития отклоняй. Для
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
    *,
    api_key: str,
    model: str,
    prompt: str,
    direction_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=1200.0, max_retries=2)
    response = client.responses.create(
        model=model,
        input=prompt,
        tools=[
            {
                "type": "web_search",
                "search_context_size": "medium",
                "return_token_budget": "default",
            }
        ],
        tool_choice="required",
        max_tool_calls=1,
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
    completed = int(metadata.get("web_search_calls_completed", 0) or 0)
    if completed != 1:
        raise CompletenessResponseError(
            f"Completeness pass должен завершить ровно один Web Search, получено {completed}",
            metadata,
        )
    if getattr(response, "status", None) != "completed":
        raise CompletenessResponseError(
            f"Completeness pass не завершён: status={getattr(response, 'status', None)!r}",
            metadata,
        )
    output_text = (getattr(response, "output_text", None) or "").strip()
    if not output_text:
        raise CompletenessResponseError("Completeness pass вернул пустой output_text", metadata)
    try:
        payload = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise CompletenessResponseError(
            f"Completeness pass вернул некорректный JSON: {exc}", metadata
        ) from exc
    if not isinstance(payload, dict):
        raise CompletenessResponseError("Completeness pass должен вернуть JSON-объект", metadata)
    if payload.get("direction_id") != direction_id:
        raise CompletenessResponseError("Completeness pass вернул чужой direction_id", metadata)
    if payload.get("status") not in {"complete", "complete_with_gaps"}:
        raise CompletenessResponseError(
            f"Completeness pass вернул непригодный status={payload.get('status')!r}", metadata
        )
    if not metadata.get("actual_queries"):
        raise CompletenessResponseError(
            "Completeness pass не сохранил фактический поисковый запрос", metadata
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
    *,
    direction_id: str,
    label: str,
    prompt: str,
    payload: dict[str, Any] | None,
    metadata: dict[str, Any],
    error: str | None,
) -> dict[str, Any]:
    raw_candidates = payload.get("candidates") if isinstance(payload, dict) else []
    candidates = [
        _normalize_candidate(item, direction_id)
        for item in raw_candidates
        if isinstance(item, dict)
    ] if isinstance(raw_candidates, list) else []
    return {
        "direction_id": direction_id,
        "label": label,
        "prompt": prompt,
        "status": (
            "checked"
            if isinstance(payload, dict) and payload.get("status") == "complete"
            else (
                "checked_with_gaps"
                if isinstance(payload, dict)
                and payload.get("status") == "complete_with_gaps"
                else "error"
            )
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
        for item in attempts
        if isinstance(item, dict)
    )


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
        raise ValueError(
            f"Hybrid completeness требует минимум {FIXED_SEARCH_CALLS} search operations"
        )
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
    primary_candidates = [
        copy.deepcopy(item)
        for item in research.get("candidates", [])
        if isinstance(item, dict)
    ]
    attempts: list[dict[str, Any]] = []
    collected: list[dict[str, Any]] = []
    working_candidates = copy.deepcopy(primary_candidates)

    for direction in COMPLETENESS_DIRECTIONS:
        prompt = build_prompt(
            publication_date=publication_date,
            search_window=search_window,
            direction_id=direction["id"],
            direction_label=direction["label"],
            direction_guidance=direction["guidance"],
            existing_candidates=working_candidates,
            archive=archive,
        )
        payload: dict[str, Any] | None = None
        metadata: dict[str, Any] = {}
        error: str | None = None
        try:
            payload, metadata = request_fn(
                api_key=api_key,
                model=model,
                prompt=prompt,
                direction_id=direction["id"],
            )
        except CompletenessResponseError as exc:
            metadata = exc.metadata
            error = f"{type(exc).__name__}: {exc}"
        except Exception as exc:  # transport must not destroy the baseline primary result
            error = f"{type(exc).__name__}: {exc}"
        record = _attempt_record(
            direction_id=direction["id"],
            label=direction["label"],
            prompt=prompt,
            payload=payload,
            metadata=metadata,
            error=error,
        )
        attempts.append(record)
        collected.extend(copy.deepcopy(record["candidates"]))
        provisional, _, _ = merge_candidates(
            research,
            collected,
            maximum_candidates=maximum_candidates,
        )
        working_candidates = [
            copy.deepcopy(item)
            for item in provisional.get("candidates", [])
            if isinstance(item, dict)
        ]

    provisional, _, _ = merge_candidates(
        research,
        collected,
        maximum_candidates=maximum_candidates,
    )
    counts_after_fixed = cluster_counts(
        [item for item in provisional.get("candidates", []) if isinstance(item, dict)]
    )
    missing_clusters = tuple(
        item["id"]
        for item in COMPLETENESS_DIRECTIONS
        if counts_after_fixed.get(item["id"], 0) == 0
    )

    adaptive_needed = bool(missing_clusters) and len(attempts) < maximum_search_calls
    if adaptive_needed:
        guidance = (
            "Один адаптивный last-mile проход по очевидным пустым кластерам: "
            + ", ".join(missing_clusters)
            + ". Проверь прежде всего крупные события, которые могли не попасть "
            "ни в primary, ни в три фиксированных completeness-прохода."
        )
        prompt = build_prompt(
            publication_date=publication_date,
            search_window=search_window,
            direction_id=ADAPTIVE_DIRECTION_ID,
            direction_label="Adaptive gap query",
            direction_guidance=guidance,
            existing_candidates=[
                item for item in provisional.get("candidates", []) if isinstance(item, dict)
            ],
            archive=archive,
            missing_clusters=missing_clusters,
        )
        payload = None
        metadata = {}
        error = None
        try:
            payload, metadata = request_fn(
                api_key=api_key,
                model=model,
                prompt=prompt,
                direction_id=ADAPTIVE_DIRECTION_ID,
            )
        except CompletenessResponseError as exc:
            metadata = exc.metadata
            error = f"{type(exc).__name__}: {exc}"
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        record = _attempt_record(
            direction_id=ADAPTIVE_DIRECTION_ID,
            label="Adaptive gap query",
            prompt=prompt,
            payload=payload,
            metadata=metadata,
            error=error,
        )
        attempts.append(record)
        collected.extend(copy.deepcopy(record["candidates"]))

    merged, accepted, rejected = merge_candidates(
        research,
        collected,
        maximum_candidates=maximum_candidates,
    )
    final_candidates = [
        item for item in merged.get("candidates", []) if isinstance(item, dict)
    ]
    fixed_completed = sum(
        1
        for item in attempts[:FIXED_SEARCH_CALLS]
        if item.get("status") in {"checked", "checked_with_gaps"}
    )
    adaptive_record = next(
        (item for item in attempts if item.get("direction_id") == ADAPTIVE_DIRECTION_ID),
        None,
    )
    complete = fixed_completed == FIXED_SEARCH_CALLS and (
        not adaptive_needed
        or (
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
            "remaining_calls": max(
                0, maximum_search_calls - _searches_from_attempts(attempts)
            ),
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
    }

    output_root.mkdir(parents=True, exist_ok=True)
    merged_path = output_root / f"hybrid-completeness-merged-{publication_date}.json"
    report_path = output_root / f"hybrid-completeness-{publication_date}.json"
    if accepted:
        write_json(merged_path, merged)
        report["merged_research_path"] = str(merged_path)
    write_json(report_path, report)
    write_json(artifact_dir / "hybrid-completeness.json", report)
    return report


def persist_report(artifact_dir: Path, report: dict[str, Any]) -> None:
    write_json(artifact_dir / "hybrid-completeness.json", report)
    production_path = PRODUCTION_PREVIEW_ROOT / (
        f"hybrid-completeness-{report.get('publication_date', 'unknown')}.json"
    )
    write_json(production_path, report)
