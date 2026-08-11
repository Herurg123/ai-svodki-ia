#!/usr/bin/env python3
"""Deterministic recall-first primary discovery for daily AI digests.

The legacy primary prompt delegated search-budget allocation to one agentic
Responses call. Primary recall v2 instead assigns every one of the twelve Web
Search operations to a fixed editorial direction. Each direction performs
exactly one search, returns a deliberately broad set of plausible candidates,
and lets the existing story-coverage validator perform the strict qualification
and deduplication after discovery.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from ensure_story_coverage_policy import (
    AUDIT_CANDIDATE_SCHEMA,
    AUDIT_REJECTION_SCHEMA,
    build_audit_api_metadata,
)
from story_coverage import compact_archive, merge_candidates, read_json, write_json

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = REPOSITORY_ROOT / "automation" / "prompts" / "primary_recall_pass.md"
ARCHIVE_PATH = REPOSITORY_ROOT / "automation" / "archive" / "index.json"
SITE_CONFIG_PATH = REPOSITORY_ROOT / "automation" / "config" / "site.json"
PREVIEW_ROOT = REPOSITORY_ROOT / "automation" / "preview"
PRODUCTION_PREVIEW_ROOT = PREVIEW_ROOT / "production-daily"

PRIMARY_RECALL_VERSION = 2
DEFAULT_MAXIMUM_SEARCH_CALLS = 12

PRIMARY_DIRECTIONS: tuple[dict[str, str], ...] = (
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
            "Финальный независимый поиск: найди крупные ИИ-события редакционного "
            "окна, которых НЕТ среди уже найденных кандидатов. Перепроверь крупные "
            "агентства, мировых игроков, инфраструктуру, Китай/Азию, Россию, "
            "продуктовые интеграции, security и business. Не повторяй список."
        ),
    },
)
PRIMARY_DIRECTION_IDS = tuple(item["id"] for item in PRIMARY_DIRECTIONS)

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
            "maxItems": 4,
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


def build_prompt(
    template: str,
    *,
    publication_date: str,
    search_window: dict[str, Any],
    direction: dict[str, str],
    existing_candidates: list[Any],
    archive: dict[str, Any],
) -> str:
    replacements = {
        "PUBLICATION_DATE": publication_date,
        "SEARCH_WINDOW_START_AT": str(search_window.get("start_at") or ""),
        "SEARCH_WINDOW_END_AT": str(search_window.get("end_at") or ""),
        "DIRECTION_ID": direction["id"],
        "DIRECTION_LABEL": direction["label"],
        "DIRECTION_GUIDANCE": direction["guidance"],
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
) -> tuple[dict[str, Any], dict[str, Any]]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=1200.0, max_retries=2)
    response = client.responses.create(
        model=model,
        input=prompt,
        tools=[
            {
                "type": "web_search",
                "search_context_size": "high",
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
                "name": "daily_ai_primary_recall_pass",
                "strict": True,
                "schema": PASS_SCHEMA,
            }
        },
        store=False,
    )
    metadata = build_audit_api_metadata(response, maximum_web_search_calls=1)
    completed = int(metadata.get("web_search_calls_completed", 0) or 0)
    if completed != 1:
        raise PrimaryRecallResponseError(
            f"Primary recall pass должен завершить ровно один Web Search, получено {completed}",
            metadata,
        )
    if getattr(response, "status", None) != "completed":
        raise PrimaryRecallResponseError(
            f"Primary recall pass не завершён: status={getattr(response, 'status', None)!r}",
            metadata,
        )
    output_text = (getattr(response, "output_text", None) or "").strip()
    if not output_text:
        raise PrimaryRecallResponseError(
            "Primary recall pass вернул пустой output_text", metadata
        )
    try:
        payload = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise PrimaryRecallResponseError(
            f"Primary recall pass вернул некорректный JSON: {exc}", metadata
        ) from exc
    if not isinstance(payload, dict):
        raise PrimaryRecallResponseError(
            "Primary recall pass должен вернуть JSON-объект", metadata
        )
    if payload.get("direction_id") != direction_id:
        raise PrimaryRecallResponseError(
            "Primary recall pass вернул чужой direction_id", metadata
        )
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
) -> dict[str, Any]:
    # Reuse the canonical continuity functions rather than maintaining a second
    # interpretation of search_cutoff_at semantics.
    import generate_digest_preview as generator

    publication_day = date.fromisoformat(publication_date)
    start_at, end_at = generator.expected_search_window(
        publication_day,
        archive,
        config,
        cutoff_at=cutoff_at,
    )
    latest_at = generator.latest_archive_published_at(archive, config)
    local_zone = ZoneInfo(str(config["timezone"]))
    return {
        "start_at": start_at.isoformat(timespec="seconds"),
        "end_at": end_at.isoformat(timespec="seconds"),
        "latest_archive_at": (
            latest_at.isoformat(timespec="seconds") if latest_at is not None else None
        ),
        "start_date": start_at.astimezone(local_zone).date().isoformat(),
        "end_date": end_at.astimezone(local_zone).date().isoformat(),
        "latest_archive_date": (
            latest_at.astimezone(local_zone).date().isoformat()
            if latest_at is not None
            else None
        ),
    }


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
    merged = build_base_research(
        publication_date=publication_date,
        search_window=search_window,
    )
    coverage: list[dict[str, str]] = []
    direction_reports: list[dict[str, Any]] = []
    accepted_total: list[dict[str, Any]] = []
    rejected_total: list[dict[str, Any]] = []
    raw_candidate_count = 0

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
                direction_id=direction["id"],
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
        merged, accepted, rejected = merge_candidates(
            merged,
            raw_candidates,
            maximum_candidates=maximum_candidates,
        )
        accepted_total.extend(accepted)
        rejected_total.extend(rejected)
        completed_calls = int(metadata.get("web_search_calls_completed", 0) or 0)
        direction_reports.append(
            {
                "direction_id": direction["id"],
                "label": direction["label"],
                "status": payload.get("status"),
                "notes": payload.get("notes"),
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
                "area": direction["id"],
                "status": "covered" if accepted else "gap",
                "notes": (
                    f"Обязательный one-search pass завершён; raw={len(raw_candidates)}, "
                    f"accepted={len(accepted)}, rejected={len(rejected)}."
                ),
            }
        )

    completed_calls = sum(
        int(item.get("web_search_calls_completed", 0) or 0)
        for item in direction_reports
    )
    if completed_calls != DEFAULT_MAXIMUM_SEARCH_CALLS:
        raise PrimaryRecallResponseError(
            f"Primary recall должен завершить 12 Web Search operations, получено {completed_calls}",
            {
                "version": PRIMARY_RECALL_VERSION,
                "status": "error",
                "directions": direction_reports,
            },
        )

    merged["coverage"] = coverage
    final_candidates = merged.get("candidates")
    if not isinstance(final_candidates, list):
        final_candidates = []
        merged["candidates"] = final_candidates
    if final_candidates:
        merged["status"] = "ok"
        merged["error_message"] = None
    else:
        # Preserve the legacy semantic marker so run_digest_preview can normalize
        # a completed zero-pool result and continue to hybrid/fallback coverage.
        merged["status"] = "error"
        merged["error_message"] = (
            "После 12 обязательных primary recall проходов не найдено ни одного "
            "достаточно подтверждённого кандидата."
        )
    merged["research_notes"] = (
        "Primary recall v2: выполнены 12 фиксированных one-search проходов; "
        f"raw candidates={raw_candidate_count}, final candidates={len(final_candidates)}. "
        "Discovery выполнялся до строгой дедупликации/qualification; полный след "
        "сохранён в primary-recall diagnostics."
    )

    report = {
        "version": PRIMARY_RECALL_VERSION,
        "status": "complete" if final_candidates else "complete_with_gaps",
        "publication_date": publication_date,
        "search_window": search_window,
        "search_budget": {
            "maximum_calls": DEFAULT_MAXIMUM_SEARCH_CALLS,
            "completed_calls": completed_calls,
        },
        "directions": direction_reports,
        "raw_candidate_count": raw_candidate_count,
        "accepted_events": accepted_total,
        "validator_rejections": rejected_total,
        "final_candidate_count": len(final_candidates),
        "final_candidates": _compact_candidates(final_candidates),
    }
    return merged, report


def persist_report(publication_date: str, report: dict[str, Any]) -> Path:
    PRODUCTION_PREVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    path = PRODUCTION_PREVIEW_ROOT / f"primary-recall-{publication_date}.json"
    write_json(path, report)
    return path


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
    search_window = build_search_window(
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
        persist_report(publication_date, diagnostic)
        raise

    PRODUCTION_PREVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    research_path = PRODUCTION_PREVIEW_ROOT / f"primary-recall-research-{publication_date}.json"
    write_json(research_path, research)
    persist_report(publication_date, report)
    return research_path, report
