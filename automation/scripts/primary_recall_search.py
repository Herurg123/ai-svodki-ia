#!/usr/bin/env python3
"""Deterministic recall-first primary discovery for daily AI digests.

Primary Recall v2 assigns the twelve paid search operations to fixed editorial
beats.  One *search action* is allowed per pass, while a small separate hosted-
tool allowance lets the model open/find pages from that search for verification.
A controlled 24-hour overlap before the continuity anchor heals important misses
from the preceding digest; archive-aware deduplication prevents that overlap from
becoming a licence to republish yesterday's stories.
"""
from __future__ import annotations

import copy
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from ensure_story_coverage_policy import (
    AUDIT_CANDIDATE_SCHEMA,
    AUDIT_REJECTION_SCHEMA,
    build_audit_api_metadata,
)
from story_coverage import (
    candidate_fingerprint,
    candidate_primary_url,
    compact_archive,
    merge_candidates,
    normalize_url,
    read_json,
    write_json,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = REPOSITORY_ROOT / "automation" / "prompts" / "primary_recall_pass.md"
ARCHIVE_PATH = REPOSITORY_ROOT / "automation" / "archive" / "index.json"
SITE_CONFIG_PATH = REPOSITORY_ROOT / "automation" / "config" / "site.json"
PREVIEW_ROOT = REPOSITORY_ROOT / "automation" / "preview"
PRODUCTION_PREVIEW_ROOT = PREVIEW_ROOT / "production-daily"
RUNTIME_RESEARCH_ROOT = REPOSITORY_ROOT / "automation" / "fixtures" / "research" / ".runtime"

PRIMARY_RECALL_VERSION = 2
DEFAULT_MAXIMUM_SEARCH_CALLS = 12
MAX_CANDIDATES_PER_PASS = 4
PRIMARY_NAVIGATION_TOOL_ALLOWANCE = 3
PRIMARY_MAX_TOOL_CALLS_PER_PASS = 1 + PRIMARY_NAVIGATION_TOOL_ALLOWANCE
PRIMARY_LOOKBACK_HOURS = 24
REUTERS_DOMAINS: tuple[str, ...] = ("reuters.com",)
BLOOMBERG_FT_DOMAINS: tuple[str, ...] = ("bloomberg.com", "ft.com")
AP_DOMAINS: tuple[str, ...] = ("apnews.com", "ap.org")
AGENCY_DOMAINS: tuple[str, ...] = (
    *REUTERS_DOMAINS,
    *BLOOMBERG_FT_DOMAINS,
    *AP_DOMAINS,
)

PRIMARY_DIRECTIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "global_breaking",
        "label": "Global breaking AI news",
        "guidance": (
            "Широкий мировой discovery значимых ИИ-событий: крупные лаборатории, "
            "новые модели и продукты, агенты, исследования, multimodal, robotics, "
            "инфраструктура, бизнес, regulation и security. Не концентрируйся на "
            "одной компании или одном типе событий."
        ),
    },
    {
        "id": "major_agencies",
        "label": "Major news agencies",
        "guidance": (
            "Отдельно ищи свежие ИИ-события у Reuters, Associated Press, Bloomberg "
            "и Financial Times. Нужны не только релизы моделей, но также чипы, "
            "инфраструктура, инвестиции, M&A, партнёрства, policy, legal и security."
        ),
        "allowed_domains": BLOOMBERG_FT_DOMAINS,
    },
    {
        "id": "models_products_agents",
        "label": "Models / products / agents / research",
        "guidance": (
            "OpenAI, Anthropic, Google DeepMind, Meta, xAI, Microsoft, Amazon, "
            "Mistral, Hugging Face, Cohere и другие крупные лаборатории: модели, "
            "агенты, существенные продуктовые обновления, open-weight/open-source, "
            "multimodal, robotics и важные research-результаты."
        ),
    },
    {
        "id": "infrastructure_chips_cloud",
        "label": "Infrastructure / chips / cloud / energy",
        "guidance": (
            "Nvidia, AMD, Microsoft, hyperscalers и значимые инфраструктурные "
            "игроки: AI-чипы, HBM, дата-центры, cloud, inference, networking, "
            "энергетика и крупные программы вычислительной инфраструктуры."
        ),
    },
    {
        "id": "business_investment_partnerships",
        "label": "Business / investment / M&A / partnerships",
        "guidance": (
            "Крупные инвестиции и financing, M&A, IPO, стратегические партнёрства, "
            "существенные enterprise-внедрения и бизнес-решения вокруг ИИ. "
            "Не ограничивайся стартап-раундами."
        ),
    },
    {
        "id": "china_asia_models",
        "label": "China / Asia models and releases",
        "guidance": (
            "Китай и Азия: DeepSeek, Alibaba/Qwen, Baidu/ERNIE, Tencent/Hunyuan, "
            "ByteDance/Doubao, Moonshot/Kimi, Z.ai/Zhipu/GLM, MiniMax, 01.AI, "
            "SenseTime, Huawei и другие крупные игроки. Ищи модели, релизы, "
            "агентов, coding, open-weight, multimodal, chips и cloud."
        ),
    },
    {
        "id": "china_asia_integrations",
        "label": "China / Asia integrations and partnerships",
        "guidance": (
            "Отдельно ищи продуктовые интеграции, партнёрства и реальные "
            "deployment-события в Китае и Азии. Учитывай глобальные компании, "
            "если событие относится к китайскому/азиатскому рынку, например "
            "интеграция зарубежного устройства или ОС с локальной ИИ-моделью."
        ),
    },
    {
        "id": "russia",
        "label": "Russia",
        "guidance": (
            "Яндекс, Сбер, VK, МТС AI, Т-Банк, Газпромбанк, Ростелеком, российские "
            "стартапы, вузы, исследовательские команды, госинициативы, КИИ, "
            "промышленность и regulation. Ищи модели, продукты, внедрения, "
            "инфраструктуру, сделки и security."
        ),
    },
    {
        "id": "developer_tools",
        "label": "Developer tools / coding agents",
        "guidance": (
            "IDE, coding agents, CLI-агенты, Claude Code, Cursor, GitHub Copilot, "
            "OpenCode, Cline и значимые инструменты вокруг GPT, Claude, Gemini, "
            "Qwen, DeepSeek, Kimi и GLM: генерация, review, refactoring, testing "
            "и agentic development environments."
        ),
    },
    {
        "id": "security_safety",
        "label": "Security / safety / incidents",
        "guidance": (
            "Крупные события AI security и safety: prompt injection, sandbox "
            "escapes, утечки, несанкционированные действия агентов, supply chain, "
            "компрометация моделей/API/агентов, red teaming, frontier evaluations "
            "и существенные исправления или инциденты."
        ),
    },
    {
        "id": "legal_regulation",
        "label": "Legal / regulation / copyright",
        "guidance": (
            "Крупные решения судов и регуляторов, важные этапы copyright/scraping "
            "дел, государственная политика, требования к frontier-моделям, "
            "данным, лицензированию и распространению ИИ-продуктов."
        ),
    },
    {
        "id": "independent_missing_events",
        "label": "Independent missing-events sweep",
        "guidance": (
            "Финальный независимый поиск: найди крупные ИИ-события эффективного "
            "редакционного окна, которых НЕТ среди уже найденных кандидатов. "
            "Перепроверь агентства, мировых игроков, инфраструктуру, Китай/Азию, "
            "Россию, продуктовые интеграции, security и business. Не повторяй список."
        ),
    },
)
PRIMARY_DIRECTION_IDS = tuple(str(item["id"]) for item in PRIMARY_DIRECTIONS)

PASS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {
            "type": "string",
            "enum": ["complete", "complete_with_gaps", "error"],
        },
        "error_message": {"type": ["string", "null"]},
        "direction_id": {"type": "string", "enum": list(PRIMARY_DIRECTION_IDS)},
        "candidates": {
            "type": "array",
            "minItems": 0,
            "maxItems": MAX_CANDIDATES_PER_PASS,
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


class PrimaryRecallResponseError(RuntimeError):
    def __init__(self, message: str, metadata: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.metadata = metadata or {}


def _parse_aware(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed


def _compact_candidates(candidates: list[Any], limit: int = 24) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in candidates:
        if not isinstance(raw, dict):
            continue
        source = raw.get("primary_source")
        result.append(
            {
                "title": raw.get("title"),
                "organization": raw.get("organization"),
                "published_date": raw.get("published_date"),
                "category": raw.get("category"),
                "geography": raw.get("geography"),
                "primary_url": source.get("url") if isinstance(source, dict) else None,
            }
        )
        if len(result) >= limit:
            break
    return result


def _candidate_rank(candidate: dict[str, Any]) -> tuple[Any, ...]:
    return (
        0 if candidate.get("recommendation") == "include" else 1,
        -int(candidate.get("significance_score", 0) or 0),
        str(candidate.get("organization") or "").casefold(),
        str(candidate.get("title") or "").casefold(),
    )


def _archive_source_urls(archive: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for item in archive.get("items", []):
        if not isinstance(item, dict):
            continue
        raw_urls: list[Any] = []
        if isinstance(item.get("source_urls"), list):
            raw_urls.extend(item["source_urls"])
        for story in item.get("stories", []):
            if not isinstance(story, dict):
                continue
            for source in story.get("sources", []):
                if isinstance(source, dict):
                    raw_urls.append(source.get("url"))
        for raw in raw_urls:
            if not isinstance(raw, str) or not raw.strip():
                continue
            try:
                result.add(normalize_url(raw))
            except ValueError:
                continue
    return result


def _filter_archive_exact_duplicates(
    candidates: list[Any], archive_urls: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for raw in candidates:
        if not isinstance(raw, dict):
            continue
        url = candidate_primary_url(raw)
        if url and url in archive_urls:
            rejected.append(
                {
                    "title": raw.get("title"),
                    "primary_url": url,
                    "audit_direction": raw.get("audit_direction"),
                    "errors": ["primary source URL уже опубликован в архиве"],
                }
            )
            continue
        kept.append(copy.deepcopy(raw))
    return kept, rejected


def _select_final_candidates(
    candidates: list[dict[str, Any]],
    *,
    origins: dict[Any, str],
    maximum_candidates: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if maximum_candidates < 1:
        raise RuntimeError("maximum_candidates должен быть положительным")
    ranked = sorted((dict(item) for item in candidates), key=_candidate_rank)
    buckets: dict[str, list[dict[str, Any]]] = {key: [] for key in PRIMARY_DIRECTION_IDS}
    for candidate in ranked:
        origin = origins.get(candidate_fingerprint(candidate))
        if origin in buckets:
            buckets[origin].append(candidate)
    selected: list[dict[str, Any]] = []
    seen: set[Any] = set()

    def add(candidate: dict[str, Any]) -> None:
        fingerprint = candidate_fingerprint(candidate)
        if fingerprint in seen or len(selected) >= maximum_candidates:
            return
        seen.add(fingerprint)
        selected.append(candidate)

    for direction in PRIMARY_DIRECTIONS:
        bucket = buckets.get(str(direction["id"]), [])
        if bucket:
            add(bucket[0])
        if len(selected) >= maximum_candidates:
            break
    for candidate in ranked:
        add(candidate)
        if len(selected) >= maximum_candidates:
            break
    for index, candidate in enumerate(selected, start=1):
        candidate["id"] = f"cand-{index:03d}"
    dropped = [
        {
            "title": candidate.get("title"),
            "organization": candidate.get("organization"),
            "primary_url": (
                candidate.get("primary_source", {}).get("url")
                if isinstance(candidate.get("primary_source"), dict)
                else None
            ),
            "origin_direction": origins.get(candidate_fingerprint(candidate)),
            "reason": "global maximum_candidates cap after all primary passes",
        }
        for candidate in ranked
        if candidate_fingerprint(candidate) not in seen
    ]
    return selected, dropped


def query_time_hint(search_window: dict[str, Any]) -> str:
    start = _parse_aware(str(search_window.get("start_at") or ""))
    end = _parse_aware(str(search_window.get("end_at") or ""))
    return (
        f"Точный effective window для ПОСЛЕДУЮЩЕЙ проверки кандидатов: "
        f"{start.isoformat(timespec='seconds')} → {end.isoformat(timespec='seconds')}. "
        "Сам search query должен быть date-free: не копируй в него календарные "
        "даты, годы, названия месяцев, after:/before: или иные явные временные "
        "границы. Для ranking используй естественный relative-freshness cue: "
        "latest / recent / current / breaking или эквивалент. После retrieval "
        "обязательно проверь фактическую дату/timestamp источника против полного "
        "effective window; relative wording не является freshness-фильтром."
    )


def build_prompt(
    template: str,
    *,
    publication_date: str,
    search_window: dict[str, Any],
    direction: dict[str, Any],
    existing_candidates: list[Any],
    archive: dict[str, Any],
) -> str:
    replacements = {
        "PUBLICATION_DATE": publication_date,
        "SEARCH_WINDOW_START_AT": str(search_window.get("start_at") or ""),
        "SEARCH_WINDOW_END_AT": str(search_window.get("end_at") or ""),
        "QUERY_TIME_HINT": query_time_hint(search_window),
        "DIRECTION_ID": str(direction["id"]),
        "DIRECTION_LABEL": str(direction["label"]),
        "DIRECTION_GUIDANCE": str(direction["guidance"]),
        "DIRECTION_ALLOWED_DOMAINS": (
            ", ".join(direction.get("allowed_domains", ()))
            if direction.get("allowed_domains")
            else "без API domain filter"
        ),
        "EXISTING_CANDIDATES": json.dumps(
            _compact_candidates(existing_candidates), ensure_ascii=False, indent=2
        ),
        "ARCHIVE_INDEX": json.dumps(
            compact_archive(archive, limit=14), ensure_ascii=False, indent=2
        ),
    }
    prompt = template
    for key, value in replacements.items():
        prompt = prompt.replace(f"{{{{{key}}}}}", value)
    if "{{" in prompt or "}}" in prompt:
        raise RuntimeError("В primary recall prompt остались неподставленные переменные")
    return prompt


def run_search_request(
    *,
    api_key: str,
    model: str,
    prompt: str,
    direction_id: str,
    allowed_domains: list[str] | tuple[str, ...] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=1200.0, max_retries=2)
    web_tool: dict[str, Any] = {
        "type": "web_search",
        "search_context_size": "high",
        "return_token_budget": "default",
    }
    if allowed_domains:
        web_tool["filters"] = {"allowed_domains": list(allowed_domains)}
    response = client.responses.create(
        model=model,
        input=prompt,
        tools=[web_tool],
        tool_choice="required",
        max_tool_calls=PRIMARY_MAX_TOOL_CALLS_PER_PASS,
        include=["web_search_call.action.sources"],
        reasoning={"effort": "medium"},
        max_output_tokens=3500,
        text={
            "format": {
                "type": "json_schema",
                "name": "daily_ai_primary_recall_pass",
                "strict": True,
                "schema": PASS_SCHEMA,
            }
        },
        store=False,
    )
    metadata = build_audit_api_metadata(response, maximum_web_search_calls=1)
    metadata["configured_search_operations"] = 1
    metadata["configured_total_tool_calls"] = PRIMARY_MAX_TOOL_CALLS_PER_PASS
    metadata["navigation_tool_allowance"] = PRIMARY_NAVIGATION_TOOL_ALLOWANCE
    metadata["allowed_domains"] = list(allowed_domains or ())
    completed = int(metadata.get("web_search_calls_completed", 0) or 0)
    if completed != 1:
        raise PrimaryRecallResponseError(
            f"Primary recall pass должен завершить ровно один Web Search, получено {completed}",
            metadata,
        )
    actual_queries = list(metadata.get("actual_queries") or [])
    if len(actual_queries) != 1:
        raise PrimaryRecallResponseError(
            "Primary recall pass должен выполнить один логический поисковый запрос; "
            f"получено {len(actual_queries)}",
            metadata,
        )
    if getattr(response, "status", None) != "completed":
        raise PrimaryRecallResponseError(
            f"Primary recall pass не завершён: status={getattr(response, 'status', None)!r}",
            metadata,
        )
    output_text = (getattr(response, "output_text", None) or "").strip()
    if not output_text:
        raise PrimaryRecallResponseError("Primary recall pass вернул пустой output_text", metadata)
    try:
        payload = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise PrimaryRecallResponseError(
            f"Primary recall pass вернул некорректный JSON: {exc}", metadata
        ) from exc
    if not isinstance(payload, dict):
        raise PrimaryRecallResponseError("Primary recall pass должен вернуть JSON-объект", metadata)
    if payload.get("direction_id") != direction_id:
        raise PrimaryRecallResponseError("Primary recall pass вернул чужой direction_id", metadata)
    if payload.get("status") not in {"complete", "complete_with_gaps"}:
        raise PrimaryRecallResponseError(
            f"Primary recall pass сообщил ошибку: {payload.get('error_message')}", metadata
        )
    return payload, metadata


def build_search_window(
    *,
    publication_date: str,
    archive: dict[str, Any],
    config: dict[str, Any],
    cutoff_at: datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return effective overlap window plus diagnostics for the continuity anchor."""
    import generate_digest_preview as generator

    publication_day = date.fromisoformat(publication_date)
    continuity_start, end_at = generator.expected_search_window(
        publication_day,
        archive,
        config,
        cutoff_at=cutoff_at,
    )
    latest_at = generator.latest_archive_published_at(archive, config)
    local_zone = ZoneInfo(str(config["timezone"]))
    effective_start = continuity_start - timedelta(hours=PRIMARY_LOOKBACK_HOURS)
    window = {
        "start_at": effective_start.isoformat(timespec="seconds"),
        "end_at": end_at.isoformat(timespec="seconds"),
        "latest_archive_at": (
            latest_at.isoformat(timespec="seconds") if latest_at is not None else None
        ),
        "start_date": effective_start.astimezone(local_zone).date().isoformat(),
        "end_date": end_at.astimezone(local_zone).date().isoformat(),
        "latest_archive_date": (
            latest_at.astimezone(local_zone).date().isoformat()
            if latest_at is not None
            else None
        ),
    }
    diagnostics = {
        "continuity_start_at": continuity_start.isoformat(timespec="seconds"),
        "effective_start_at": effective_start.isoformat(timespec="seconds"),
        "end_at": end_at.isoformat(timespec="seconds"),
        "lookback_hours": PRIMARY_LOOKBACK_HOURS,
        "purpose": "heal significant recall misses while archive dedupe blocks republishing",
    }
    return window, diagnostics


def build_base_research(
    *, publication_date: str, search_window: dict[str, Any]
) -> dict[str, Any]:
    return {
        "status": "ok",
        "error_message": None,
        "publication_date": publication_date,
        "search_window": dict(search_window),
        "coverage": [],
        "candidates": [],
        "rejected_as_duplicates": [],
        "research_notes": "Primary recall v2 discovery started.",
    }


SearchRunner = Callable[..., tuple[dict[str, Any], dict[str, Any]]]


def run_primary_recall_matrix(
    *,
    publication_date: str,
    search_window: dict[str, Any],
    archive: dict[str, Any],
    api_key: str,
    model: str,
    maximum_candidates: int = 20,
    template: str | None = None,
    search_runner: SearchRunner = run_search_request,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if len(PRIMARY_DIRECTIONS) != DEFAULT_MAXIMUM_SEARCH_CALLS:
        raise RuntimeError("Primary recall matrix должна содержать ровно 12 направлений")
    prompt_template = template if template is not None else PROMPT_PATH.read_text(encoding="utf-8")
    merged = build_base_research(publication_date=publication_date, search_window=search_window)
    coverage: list[dict[str, str]] = []
    direction_reports: list[dict[str, Any]] = []
    accepted_total: list[dict[str, Any]] = []
    rejected_total: list[dict[str, Any]] = []
    raw_candidate_count = 0
    origins: dict[Any, str] = {}
    archive_urls = _archive_source_urls(archive)
    discovery_capacity = max(maximum_candidates, len(PRIMARY_DIRECTIONS) * MAX_CANDIDATES_PER_PASS)

    for direction in PRIMARY_DIRECTIONS:
        prompt = build_prompt(
            prompt_template,
            publication_date=publication_date,
            search_window=search_window,
            direction=direction,
            existing_candidates=merged.get("candidates", []),
            archive=archive,
        )
        try:
            payload, metadata = search_runner(
                api_key=api_key,
                model=model,
                prompt=prompt,
                direction_id=str(direction["id"]),
                allowed_domains=direction.get("allowed_domains"),
            )
        except Exception as exc:
            metadata = getattr(exc, "metadata", {})
            report = {
                "version": PRIMARY_RECALL_VERSION,
                "status": "error",
                "publication_date": publication_date,
                "search_window": search_window,
                "search_budget": {
                    "maximum_calls": DEFAULT_MAXIMUM_SEARCH_CALLS,
                    "completed_calls": sum(
                        int(item.get("web_search_calls_completed", 0) or 0)
                        for item in direction_reports
                    ),
                },
                "failed_direction": direction["id"],
                "error": f"{type(exc).__name__}: {exc}",
                "directions": direction_reports,
                "failed_metadata": metadata,
            }
            raise PrimaryRecallResponseError(
                f"Обязательный primary direction {direction['id']} не завершён: {exc}",
                report,
            ) from exc

        raw_candidates = payload.get("candidates")
        if not isinstance(raw_candidates, list):
            raw_candidates = []
        raw_candidate_count += len(raw_candidates)
        filtered_candidates, archive_rejections = _filter_archive_exact_duplicates(
            raw_candidates, archive_urls
        )
        merged, accepted, rejected = merge_candidates(
            merged,
            filtered_candidates,
            maximum_candidates=discovery_capacity,
        )
        rejected = [*archive_rejections, *rejected]
        for candidate in accepted:
            origins.setdefault(candidate_fingerprint(candidate), str(direction["id"]))
        accepted_total.extend(accepted)
        rejected_total.extend(rejected)
        completed_calls = int(metadata.get("web_search_calls_completed", 0) or 0)
        direction_reports.append(
            {
                "direction_id": direction["id"],
                "label": direction["label"],
                "status": payload.get("status"),
                "notes": payload.get("notes"),
                "allowed_domains": list(direction.get("allowed_domains", ())),
                "raw_candidates": raw_candidates,
                "model_rejections": payload.get("rejections", []),
                "accepted_count": len(accepted),
                "validator_rejections": rejected,
                "web_search_calls_completed": completed_calls,
                "api": metadata,
            }
        )
        coverage.append(
            {
                "area": str(direction["id"]),
                "status": "covered" if accepted else "gap",
                "notes": (
                    f"Обязательный one-search pass завершён; raw={len(raw_candidates)}, "
                    f"accepted={len(accepted)}, rejected={len(rejected)}."
                ),
            }
        )

    completed_calls = sum(
        int(item.get("web_search_calls_completed", 0) or 0) for item in direction_reports
    )
    if completed_calls != DEFAULT_MAXIMUM_SEARCH_CALLS:
        raise PrimaryRecallResponseError(
            f"Primary recall должен завершить 12 Web Search operations, получено {completed_calls}",
            {"version": PRIMARY_RECALL_VERSION, "status": "error", "directions": direction_reports},
        )

    discovered_candidates = merged.get("candidates")
    if not isinstance(discovered_candidates, list):
        discovered_candidates = []
    discovered_candidates = [item for item in discovered_candidates if isinstance(item, dict)]
    final_candidates, final_cap_dropped = _select_final_candidates(
        discovered_candidates,
        origins=origins,
        maximum_candidates=maximum_candidates,
    )
    merged["candidates"] = final_candidates
    merged["coverage"] = coverage
    if final_candidates:
        merged["status"] = "ok"
        merged["error_message"] = None
    else:
        merged["status"] = "error"
        merged["error_message"] = (
            "После 12 обязательных primary recall проходов не найдено ни одного "
            "достаточно подтверждённого кандидата."
        )
    merged["research_notes"] = (
        "Primary recall v2: выполнены 12 фиксированных one-search проходов; "
        f"raw candidates={raw_candidate_count}, validated unique={len(discovered_candidates)}, "
        f"final candidates={len(final_candidates)}. Effective retrieval использует "
        f"{PRIMARY_LOOKBACK_HOURS}h overlap до continuity anchor; точные archive URL "
        "отсекаются до merge. Финальный candidate cap применяется только после "
        "завершения всех обязательных направлений."
    )
    report = {
        "version": PRIMARY_RECALL_VERSION,
        "status": "complete" if final_candidates else "complete_with_gaps",
        "publication_date": publication_date,
        "search_window": search_window,
        "search_budget": {
            "maximum_calls": DEFAULT_MAXIMUM_SEARCH_CALLS,
            "completed_calls": completed_calls,
            "search_operations_per_pass": 1,
            "maximum_total_tool_calls_per_pass": PRIMARY_MAX_TOOL_CALLS_PER_PASS,
            "navigation_tool_allowance_per_pass": PRIMARY_NAVIGATION_TOOL_ALLOWANCE,
        },
        "candidate_budget": {
            "configured_final_cap": maximum_candidates,
            "temporary_discovery_capacity": discovery_capacity,
            "cap_applied_after_all_passes": True,
        },
        "directions": direction_reports,
        "raw_candidate_count": raw_candidate_count,
        "validated_unique_candidate_count": len(discovered_candidates),
        "accepted_events": accepted_total,
        "validator_rejections": rejected_total,
        "final_cap_dropped": final_cap_dropped,
        "final_candidate_count": len(final_candidates),
        "final_candidates": _compact_candidates(final_candidates),
    }
    return merged, report


def persist_report(publication_date: str, report: dict[str, Any]) -> Path:
    PRODUCTION_PREVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    path = PRODUCTION_PREVIEW_ROOT / f"primary-recall-{publication_date}.json"
    write_json(path, report)
    return path


def _persist_research(publication_date: str, research: dict[str, Any]) -> tuple[Path, Path]:
    """Persist diagnostic preview and trusted runtime ingress for the old generator."""
    PRODUCTION_PREVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    RUNTIME_RESEARCH_ROOT.mkdir(parents=True, exist_ok=True)
    preview_path = PRODUCTION_PREVIEW_ROOT / f"primary-recall-research-{publication_date}.json"
    runtime_path = RUNTIME_RESEARCH_ROOT / f"primary-recall-research-{publication_date}.json"
    write_json(preview_path, research)
    write_json(runtime_path, research)
    return preview_path, runtime_path


def run_primary_recall_search(
    *,
    publication_date: str,
    api_key: str,
    model: str,
    maximum_candidates: int = 20,
    cutoff_at: datetime | None = None,
) -> tuple[Path, dict[str, Any]]:
    archive = read_json(ARCHIVE_PATH)
    config = read_json(SITE_CONFIG_PATH)
    if not isinstance(archive, dict) or not isinstance(archive.get("items"), list):
        raise RuntimeError("automation/archive/index.json имеет неожиданную структуру")
    if not isinstance(config, dict):
        raise RuntimeError("automation/config/site.json должен содержать объект")
    local_zone = ZoneInfo(str(config["timezone"]))
    authoritative_cutoff = cutoff_at or datetime.now(timezone.utc).astimezone(local_zone)
    search_window, overlap = build_search_window(
        publication_date=publication_date,
        archive=archive,
        config=config,
        cutoff_at=authoritative_cutoff,
    )
    try:
        research, report = run_primary_recall_matrix(
            publication_date=publication_date,
            search_window=search_window,
            archive=archive,
            api_key=api_key,
            model=model,
            maximum_candidates=maximum_candidates,
        )
    except PrimaryRecallResponseError as exc:
        diagnostic = exc.metadata if isinstance(exc.metadata, dict) else {}
        diagnostic.setdefault("version", PRIMARY_RECALL_VERSION)
        diagnostic.setdefault("status", "error")
        diagnostic.setdefault("publication_date", publication_date)
        diagnostic.setdefault("search_window", search_window)
        diagnostic["continuity_overlap"] = overlap
        persist_report(publication_date, diagnostic)
        raise
    report["continuity_overlap"] = overlap
    preview_path, runtime_path = _persist_research(publication_date, research)
    report["research_paths"] = {
        "diagnostic_preview": str(preview_path),
        "trusted_runtime_input": str(runtime_path),
    }
    persist_report(publication_date, report)
    return runtime_path, report
