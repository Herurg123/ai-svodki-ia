from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from story_coverage import (
    compact_archive,
    coverage_summary,
    eligible_candidate_summary,
    merge_candidates,
    read_json,
    write_json,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = REPOSITORY_ROOT / "automation/prompts/coverage_audit.md"
GENERATOR_PATH = REPOSITORY_ROOT / "automation/scripts/run_digest_preview.py"
RUNTIME_RESEARCH_ROOT = REPOSITORY_ROOT / "automation/fixtures/research"
PERSISTED_RESEARCH_ROOT = REPOSITORY_ROOT / "automation/preview/production-daily"

ALLOWED_CATEGORIES = [
    "models",
    "agents",
    "coding",
    "security",
    "research",
    "multimodal",
    "robotics",
    "infrastructure",
    "chips",
    "regulation",
    "enterprise",
    "open_source",
    "investment",
    "legal",
    "curiosity",
    "russia",
    "other",
]
SOURCE_TYPES = [
    "official",
    "documentation",
    "research",
    "government",
    "regulator",
    "court",
    "news_agency",
    "technology_media",
    "business_media",
    "industry_media",
]
SOURCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string", "minLength": 1},
        "publisher": {"type": "string", "minLength": 1},
        "url": {"type": "string", "minLength": 1},
    },
    "required": ["title", "publisher", "url"],
}
AUDIT_CANDIDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string", "minLength": 1},
        "organization": {"type": "string", "minLength": 1},
        "published_date": {
            "type": "string",
            "pattern": r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
        },
        "published_at": {"type": ["string", "null"]},
        "time_precision": {"type": "string", "enum": ["datetime", "date"]},
        "topic": {"type": "string", "minLength": 1},
        "event_type": {"type": "string", "minLength": 1},
        "keywords": {
            "type": "array",
            "minItems": 1,
            "maxItems": 12,
            "items": {"type": "string", "minLength": 1},
        },
        "geography": {"type": "string", "enum": ["world", "russia"]},
        "category": {"type": "string", "enum": ALLOWED_CATEGORIES},
        "source_type": {"type": "string", "enum": SOURCE_TYPES},
        "primary_source": SOURCE_SCHEMA,
        "supporting_sources": {
            "type": "array",
            "minItems": 0,
            "maxItems": 2,
            "items": SOURCE_SCHEMA,
        },
        "event_summary": {"type": "string", "minLength": 1},
        "verified_facts": {
            "type": "array",
            "minItems": 2,
            "maxItems": 6,
            "items": {"type": "string", "minLength": 1},
        },
        "significance": {"type": "string", "minLength": 1},
        "significance_score": {
            "type": "integer",
            "minimum": 1,
            "maximum": 5,
        },
        "limitations": {"type": "string"},
        "archive_status": {"type": "string", "enum": ["none", "update"]},
        "archive_reason": {"type": "string"},
        "recommendation": {
            "type": "string",
            "enum": ["include", "consider", "exclude"],
        },
        "verification_status": {
            "type": "string",
            "enum": ["verified", "unconfirmed", "contradicted"],
        },
        "verification_notes": {"type": "string"},
        "freshness_status": {
            "type": "string",
            "enum": ["new_event", "material_update", "old_reprint"],
        },
        "freshness_reason": {"type": "string"},
        "legal_scale": {
            "type": "string",
            "enum": ["not_applicable", "major", "minor"],
        },
        "legal_scale_reason": {"type": "string"},
        "curiosity_eligible": {"type": "boolean"},
        "curiosity_verification": {"type": "string"},
    },
    "required": [
        "title",
        "organization",
        "published_date",
        "published_at",
        "time_precision",
        "topic",
        "event_type",
        "keywords",
        "geography",
        "category",
        "source_type",
        "primary_source",
        "supporting_sources",
        "event_summary",
        "verified_facts",
        "significance",
        "significance_score",
        "limitations",
        "archive_status",
        "archive_reason",
        "recommendation",
        "verification_status",
        "verification_notes",
        "freshness_status",
        "freshness_reason",
        "legal_scale",
        "legal_scale_reason",
        "curiosity_eligible",
        "curiosity_verification",
    ],
}

AUTHORITATIVE_LAST_MILE_DOMAINS: tuple[str, ...] = (
    "reuters.com",
    "apnews.com",
    "bloomberg.com",
    "ft.com",
    "openai.com",
    "anthropic.com",
    "deepmind.google",
    "blog.google",
    "microsoft.com",
    "aws.amazon.com",
    "aboutamazon.com",
    "about.fb.com",
    "ai.meta.com",
    "nvidia.com",
    "amd.com",
    "news.samsung.com",
    "news.skhynix.com",
    "pr.tsmc.com",
    "alibabacloud.com",
    "tencent.com",
    "huawei.com",
    "baidu.com",
    "bytedance.com",
    "deepseek.com",
    "yandex.ru",
    "sber.ru",
    "tass.com",
    "interfax.ru",
    "whitehouse.gov",
    "congress.gov",
    "justice.gov",
    "ftc.gov",
    "ec.europa.eu",
    "gov.uk",
    "aisi.gov.uk",
    "theregister.com",
    "bleepingcomputer.com",
    "securityweek.com",
    "techcrunch.com",
    "arstechnica.com",
)


AUDIT_DIRECTIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "security_world",
        "label": "Security — мировой сегмент",
        "guidance": (
            "Уязвимости ИИ-продуктов и моделей, prompt injection, утечки "
            "данных, sandbox escapes, несанкционированные действия агентов, "
            "атаки через документы, изображения, сайты, плагины и инструменты, "
            "supply chain, red teaming и крупные инциденты вне России и Азии."
        ),
    },
    {
        "id": "security_russia",
        "label": "Security — Россия",
        "guidance": (
            "Те же классы рисков для российских ИИ-продуктов, КИИ, банков, "
            "телекома, промышленности, исследовательских команд и регуляторов."
        ),
    },
    {
        "id": "security_asia",
        "label": "Security — Китай и Азия",
        "guidance": (
            "Те же классы рисков для DeepSeek, Qwen, Baidu, Tencent, "
            "ByteDance, Kimi, GLM, MiniMax, Huawei и других азиатских игроков."
        ),
    },
    {
        "id": "legal_copyright_scraping",
        "label": "Legal / copyright / scraping",
        "guidance": (
            "Только крупные судебные решения и значимые этапы процессов об "
            "авторском праве, обучении моделей, лицензировании данных, scraping "
            "и доступе к платформенным данным. Мелкие бытовые и локальные иски "
            "отклоняй с legal_scale=minor."
        ),
    },
    {
        "id": "curiosity",
        "label": "Проверяемый курьёз или необычный факт",
        "guidance": (
            "Ищи один самый необычный, парадоксальный или забавный реальный "
            "ИИ-сюжет. Сатира, слухи, вымысел и обычная продуктовая новость с "
            "забавным заголовком не подходят. Отсутствие кандидата нормально."
        ),
    },
    {
        "id": "general_coverage_gaps",
        "label": "Авторитетный last-mile sweep оставшихся пробелов",
        "guidance": (
            "Последним проходом перепроверь первоисточники, агентства, суды и "
            "регуляторов на предмет незакрытых значимых событий мировых "
            "компаний, Китая и Азии, России, coding tools, исследований, "
            "мультимодальности, робототехники, инфраструктуры, чипов, облаков, "
            "регулирования, бизнеса, внедрений и инвестиций. Не повторяй уже "
            "найденное и не считай отсутствие Reuters-документа отсутствием "
            "события: подтверждай доступным авторитетным первоисточником."
        ),
        "search_strategy": "authoritative_last_mile",
        "allowed_domains": AUTHORITATIVE_LAST_MILE_DOMAINS,
    },
)
AUDIT_DIRECTION_IDS = tuple(item["id"] for item in AUDIT_DIRECTIONS)
MINIMUM_REQUIRED_AUDIT_CALLS = len(AUDIT_DIRECTIONS)
DEFAULT_MAXIMUM_AUDIT_CALLS = 7

AGENCY_SOURCE_HEALTH_DOMAINS: tuple[str, ...] = (
    "reuters.com",
    "apnews.com",
    "bloomberg.com",
    "ft.com",
)
SOURCE_HEALTH_CONTRACT_VERSION = 3


def _host_matches_domain(url: str, domains: tuple[str, ...]) -> bool:
    try:
        host = (urlsplit(url).hostname or "").casefold().strip(".")
    except ValueError:
        return False
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def _search_window_days(search_window: dict[str, Any]) -> tuple[date, date] | None:
    try:
        start = datetime.fromisoformat(
            str(search_window.get("start_at") or "").replace("Z", "+00:00")
        )
        end = datetime.fromisoformat(
            str(search_window.get("end_at") or "").replace("Z", "+00:00")
        )
    except ValueError:
        return None
    if start.tzinfo is None or end.tzinfo is None or end < start:
        return None
    return start.date(), end.date()


def _candidate_has_fresh_agency_source(
    candidate: Any, search_window: dict[str, Any]
) -> bool:
    if not isinstance(candidate, dict):
        return False
    if candidate.get("recommendation") == "exclude":
        return False
    window = _search_window_days(search_window)
    if window is None:
        return False
    try:
        published = date.fromisoformat(str(candidate.get("published_date") or ""))
    except ValueError:
        return False
    if not (window[0] <= published <= window[1]):
        return False
    source = candidate.get("primary_source")
    return bool(
        isinstance(source, dict)
        and isinstance(source.get("url"), str)
        and _host_matches_domain(source["url"], AGENCY_SOURCE_HEALTH_DOMAINS)
    )


def _candidates_have_fresh_agency_source(
    candidates: Any, search_window: dict[str, Any]
) -> bool:
    return bool(
        isinstance(candidates, list)
        and any(
            _candidate_has_fresh_agency_source(item, search_window)
            for item in candidates
        )
    )


AUDIT_REJECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string", "minLength": 1},
        "url": {"type": ["string", "null"]},
        "reason_code": {
            "type": "string",
            "enum": [
                "duplicate",
                "outside_window",
                "old_reprint",
                "insufficient_significance",
                "minor_legal_event",
                "unverified",
                "satire_or_fiction",
                "weak_source",
                "not_ai_news",
                "other",
            ],
        },
        "reason": {"type": "string", "minLength": 1},
    },
    "required": ["title", "url", "reason_code", "reason"],
}

AUDIT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {
            "type": "string",
            "enum": ["complete", "complete_with_gaps", "error"],
        },
        "error_message": {"type": ["string", "null"]},
        "direction_id": {
            "type": "string",
            "enum": list(AUDIT_DIRECTION_IDS),
        },
        "candidates": {
            "type": "array",
            "minItems": 0,
            "maxItems": 10,
            "items": AUDIT_CANDIDATE_SCHEMA,
        },
        "rejections": {
            "type": "array",
            "minItems": 0,
            "maxItems": 12,
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


def build_prompt(
    template: str,
    *,
    publication_date: str,
    search_window: dict[str, Any],
    missing_total: int,
    maximum_web_search_calls: int,
    existing_candidates: list[Any],
    archive: dict[str, Any],
    direction: dict[str, Any] | None = None,
    attempt: int = 1,
) -> str:
    selected_direction = direction or AUDIT_DIRECTIONS[-1]
    replacements = {
        "PUBLICATION_DATE": publication_date,
        "SEARCH_WINDOW_START_AT": str(search_window.get("start_at", "")),
        "SEARCH_WINDOW_END_AT": str(search_window.get("end_at", "")),
        "MISSING_TOTAL": str(missing_total),
        "MAX_WEB_SEARCH_CALLS": str(maximum_web_search_calls),
        "DIRECTION_ID": selected_direction["id"],
        "DIRECTION_LABEL": selected_direction["label"],
        "DIRECTION_GUIDANCE": selected_direction["guidance"],
        "DIRECTION_SEARCH_STRATEGY": str(
            selected_direction.get("search_strategy", "targeted_topic_search")
        ),
        "DIRECTION_ALLOWED_DOMAINS": ", ".join(
            selected_direction.get("allowed_domains", ())
        )
        or "без доменного фильтра",
        "DIRECTION_ATTEMPT": str(attempt),
        "EXISTING_CANDIDATES": json.dumps(
            existing_candidates, ensure_ascii=False, indent=2
        ),
        "ARCHIVE_INDEX": json.dumps(
            compact_archive(archive), ensure_ascii=False, indent=2
        ),
    }
    prompt = template
    for key, value in replacements.items():
        prompt = prompt.replace(f"{{{{{key}}}}}", value)
    if "{{" in prompt or "}}" in prompt:
        raise RuntimeError("В coverage audit prompt остались неподставленные переменные")
    return prompt


SENSITIVE_URL_QUERY_KEYS = frozenset({"access_token", "api_key", "apikey", "key", "password", "secret", "sig", "signature", "token", "x-amz-credential", "x-amz-security-token", "x-amz-signature"})

def sanitize_diagnostic_url(value: str) -> str:
    """Remove credentials from provider-returned URLs before persisting diagnostics."""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    if parsed.scheme not in {"http", "https"} or not parsed.query:
        return value
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    safe_pairs = [(key, item) for key, item in pairs if key.casefold() not in SENSITIVE_URL_QUERY_KEYS]
    if len(safe_pairs) == len(pairs):
        return value
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(safe_pairs, doseq=True), parsed.fragment))

def sanitize_diagnostic_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: sanitize_diagnostic_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_diagnostic_value(item) for item in value]
    if isinstance(value, str):
        return sanitize_diagnostic_url(value)
    return value

def response_to_plain(value: Any) -> Any:
    if value is None:
        plain: Any = None
    elif hasattr(value, "model_dump"):
        plain = value.model_dump()
    elif hasattr(value, "to_dict"):
        plain = value.to_dict()
    elif isinstance(value, (dict, list, str, int, float, bool)):
        plain = value
    else:
        plain = str(value)
    return sanitize_diagnostic_value(plain)

class CoverageAuditResponseError(RuntimeError):
    def __init__(self, message: str, metadata: dict[str, Any]) -> None:
        super().__init__(message)
        self.metadata = metadata


def build_audit_api_metadata(
    response: Any,
    *,
    maximum_web_search_calls: int,
) -> dict[str, Any]:
    call_items: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    action_type_counts: dict[str, int] = {}
    search_status_counts: dict[str, int] = {}
    actual_queries: list[str] = []
    consulted_sources: list[dict[str, Any]] = []
    seen_queries: set[str] = set()
    seen_sources: set[str] = set()
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) != "web_search_call":
            continue
        status = str(getattr(item, "status", None) or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        plain_item = response_to_plain(item)
        action = getattr(item, "action", None)
        plain_action = response_to_plain(action)
        if not isinstance(plain_action, dict) and isinstance(plain_item, dict):
            plain_action = plain_item.get("action")
        if not isinstance(plain_action, dict):
            plain_action = {}
        action_type = str(plain_action.get("type") or "unknown")
        action_type_counts[action_type] = action_type_counts.get(action_type, 0) + 1
        if action_type == "search":
            search_status_counts[status] = search_status_counts.get(status, 0) + 1

        raw_queries: list[Any] = []
        if plain_action.get("query") is not None:
            raw_queries.append(plain_action.get("query"))
        if isinstance(plain_action.get("queries"), list):
            raw_queries.extend(plain_action["queries"])
        for raw_query in raw_queries:
            query = str(raw_query).strip()
            if query and query not in seen_queries:
                seen_queries.add(query)
                actual_queries.append(query)

        raw_sources = plain_action.get("sources")
        if isinstance(raw_sources, list):
            for source in raw_sources:
                plain_source = response_to_plain(source)
                if not isinstance(plain_source, dict):
                    continue
                key = str(plain_source.get("url") or plain_source)
                if key in seen_sources:
                    continue
                seen_sources.add(key)
                consulted_sources.append(plain_source)
        call_items.append(
            {
                "id": getattr(item, "id", None),
                "status": status,
                "action_type": action_type,
                "action": plain_action,
            }
        )

    completed_searches = search_status_counts.get("completed", 0)
    performed_searches = completed_searches + search_status_counts.get("unknown", 0)
    incomplete_searches = sum(
        count
        for status, count in search_status_counts.items()
        if status not in {"completed", "unknown"}
    )
    total_items = len(call_items)
    output_item_limit_exceeded = total_items > maximum_web_search_calls
    completed_call_limit_exceeded = completed_searches > maximum_web_search_calls
    return {
        "response_id": getattr(response, "id", None),
        "status": getattr(response, "status", None),
        "model": getattr(response, "model", None),
        "configured_max_tool_calls": maximum_web_search_calls,
        # Compatibility with the first production hotfix for run 30602601828.
        "configured_web_search_limit": maximum_web_search_calls,
        "observed_web_search_calls": total_items,
        # Only completed action.type=search operations spend the audit budget.
        # open_page/find_in_page remain visible diagnostics but are not searches.
        "budget_overrun": completed_call_limit_exceeded,
        "web_search_calls": completed_searches,
        "web_search_calls_completed": completed_searches,
        "web_search_search_operations_total": sum(search_status_counts.values()),
        "web_search_search_operations_performed": performed_searches,
        "web_search_search_operations_incomplete": incomplete_searches,
        "web_search_navigation_items_total": sum(
            count
            for action_type, count in action_type_counts.items()
            if action_type in {"open_page", "find_in_page"}
        ),
        "web_search_call_items_total": total_items,
        "web_search_call_statuses": status_counts,
        "web_search_search_statuses": search_status_counts,
        "web_search_action_type_counts": action_type_counts,
        "web_search_call_items": call_items,
        "actual_queries": actual_queries,
        "consulted_sources": consulted_sources,
        "completed_call_limit_exceeded": completed_call_limit_exceeded,
        "output_item_limit_exceeded": output_item_limit_exceeded,
        "usage": response_to_plain(getattr(response, "usage", None)),
        "error": response_to_plain(getattr(response, "error", None)),
        "incomplete_details": response_to_plain(
            getattr(response, "incomplete_details", None)
        ),
    }


def run_audit_request(
    *,
    api_key: str,
    model: str,
    prompt: str,
    maximum_web_search_calls: int,
    allowed_domains: list[str] | tuple[str, ...] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=1200.0, max_retries=2)
    web_search_tool: dict[str, Any] = {
        "type": "web_search",
        "search_context_size": "medium",
        "return_token_budget": "default",
    }
    if allowed_domains:
        web_search_tool["filters"] = {
            "allowed_domains": list(allowed_domains),
        }
    response = client.responses.create(
        model=model,
        input=prompt,
        tools=[web_search_tool],
        tool_choice="required",
        max_tool_calls=maximum_web_search_calls,
        include=["web_search_call.action.sources"],
        reasoning={"effort": "medium"},
        max_output_tokens=3500,
        text={
            "format": {
                "type": "json_schema",
                "name": "daily_ai_targeted_coverage_audit",
                "strict": True,
                "schema": AUDIT_SCHEMA,
            }
        },
        store=False,
    )
    metadata = build_audit_api_metadata(
        response,
        maximum_web_search_calls=maximum_web_search_calls,
    )
    if metadata["output_item_limit_exceeded"]:
        print(
            "::notice title=Coverage audit tool trajectory::"
            "Responses API вернул больше служебных web_search_call items, чем "
            "поисковых операций разрешено: "
            f"{metadata['web_search_call_items_total']}>"
            f"{maximum_web_search_calls}. Навигационные open_page/find_in_page "
            "не расходуют поисковый бюджет.",
            file=sys.stderr,
        )
    if metadata["web_search_calls_completed"] < 1:
        raise CoverageAuditResponseError(
            "Coverage audit не завершил ни одной поисковой операции "
            "web_search action.type=search",
            metadata,
        )
    if getattr(response, "status", None) != "completed":
        raise CoverageAuditResponseError(
            f"Coverage audit не завершён: status={getattr(response, 'status', None)!r}",
            metadata,
        )
    output_text = (getattr(response, "output_text", None) or "").strip()
    if not output_text:
        raise CoverageAuditResponseError(
            "Coverage audit вернул пустой output_text",
            metadata,
        )
    try:
        payload = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise CoverageAuditResponseError(
            f"Coverage audit вернул некорректный JSON: {exc}",
            metadata,
        ) from exc
    if not isinstance(payload, dict):
        raise CoverageAuditResponseError(
            "Coverage audit должен вернуть JSON-объект",
            metadata,
        )
    direction_id = payload.get("direction_id")
    if direction_id not in AUDIT_DIRECTION_IDS:
        raise CoverageAuditResponseError(
            "Coverage audit вернул неизвестный direction_id",
            metadata,
        )
    if not metadata.get("actual_queries"):
        raise CoverageAuditResponseError(
            "Coverage audit не сохранил фактический поисковый запрос",
            metadata,
        )
    return payload, metadata


def _aggregate_api_metadata(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    responses = [
        item.get("api")
        for item in attempts
        if isinstance(item.get("api"), dict)
    ]
    status_counts: dict[str, int] = {}
    action_type_counts: dict[str, int] = {}
    search_status_counts: dict[str, int] = {}
    usage: dict[str, int] = {}
    for response in responses:
        for status, count in (response.get("web_search_call_statuses") or {}).items():
            status_counts[str(status)] = status_counts.get(str(status), 0) + int(
                count or 0
            )
        for action_type, count in (
            response.get("web_search_action_type_counts") or {}
        ).items():
            action_type_counts[str(action_type)] = action_type_counts.get(
                str(action_type), 0
            ) + int(count or 0)
        for status, count in (
            response.get("web_search_search_statuses") or {}
        ).items():
            search_status_counts[str(status)] = search_status_counts.get(
                str(status), 0
            ) + int(count or 0)
        response_usage = response.get("usage")
        if isinstance(response_usage, dict):
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                value = response_usage.get(key)
                if isinstance(value, (int, float)):
                    usage[key] = usage.get(key, 0) + int(value)
    response_statuses = [str(item.get("status") or "unknown") for item in responses]
    return {
        "status": (
            "completed"
            if responses and all(status == "completed" for status in response_statuses)
            else ("partial" if responses else "not_started")
        ),
        "responses_attempted": len(attempts),
        "responses": responses,
        "response_statuses": response_statuses,
        "web_search_calls": sum(
            int(item.get("web_search_calls", 0) or 0) for item in responses
        ),
        "web_search_calls_completed": sum(
            int(item.get("web_search_calls_completed", 0) or 0)
            for item in responses
        ),
        "web_search_call_items_total": sum(
            int(item.get("web_search_call_items_total", 0) or 0)
            for item in responses
        ),
        "web_search_call_statuses": status_counts,
        "web_search_action_type_counts": action_type_counts,
        "web_search_search_statuses": search_status_counts,
        "web_search_navigation_items_total": sum(
            int(item.get("web_search_navigation_items_total", 0) or 0)
            for item in responses
        ),
        "usage": usage or None,
    }


def execute_audit_plan(
    *,
    api_key: str,
    model: str,
    template: str,
    publication_date: str,
    search_window: dict[str, Any],
    missing_total: int,
    maximum_web_search_calls: int,
    existing_candidates: list[Any],
    archive: dict[str, Any],
    prior_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run six explicit one-search passes plus at most one retry.

    A separate Responses request per direction prevents a broad model answer
    from claiming that one generic query covered every required beat. The
    configured tool cap is one for every request; the global budget counts
    only completed action.type=search operations. Navigation items such as
    open_page/find_in_page remain diagnostics and never stop later directions.
    A recovered partial plan resumes only directions that were not completed.
    """

    if maximum_web_search_calls < MINIMUM_REQUIRED_AUDIT_CALLS:
        raise RuntimeError(
            "Coverage audit требует минимум "
            f"{MINIMUM_REQUIRED_AUDIT_CALLS} web-search calls"
        )

    prior_plan = prior_plan if isinstance(prior_plan, dict) else {}
    prior_attempts = prior_plan.get("attempts")
    attempts: list[dict[str, Any]] = copy.deepcopy(
        prior_attempts if isinstance(prior_attempts, list) else []
    )
    latest_by_direction: dict[str, dict[str, Any]] = {}
    prior_directions = prior_plan.get("directions")
    if isinstance(prior_directions, list):
        for record in prior_directions:
            if (
                isinstance(record, dict)
                and record.get("direction_id") in AUDIT_DIRECTION_IDS
                and int(record.get("attempt", 0) or 0) > 0
            ):
                latest_by_direction[str(record["direction_id"])] = copy.deepcopy(
                    record
                )
    for record in attempts:
        if (
            isinstance(record, dict)
            and record.get("direction_id") in AUDIT_DIRECTION_IDS
        ):
            direction_id = str(record["direction_id"])
            if int(record.get("attempt", 0) or 0) >= int(
                latest_by_direction.get(direction_id, {}).get("attempt", 0) or 0
            ):
                latest_by_direction[direction_id] = copy.deepcopy(record)

    candidates: list[Any] = []
    for record in latest_by_direction.values():
        if record.get("status") not in {"checked", "checked_with_gaps"}:
            continue
        raw_candidates = record.get("candidates")
        if isinstance(raw_candidates, list):
            candidates.extend(copy.deepcopy(raw_candidates))

    prior_budget = prior_plan.get("search_budget")
    prior_budget = prior_budget if isinstance(prior_budget, dict) else {}
    response_attempts = int(
        prior_budget.get("response_attempts", len(attempts)) or 0
    )
    observed_call_items = int(prior_budget.get("observed_call_items", 0) or 0)
    completed_searches = int(prior_budget.get("completed_calls", 0) or 0)
    provider_search_overrun = bool(prior_budget.get("provider_overrun"))

    def run_direction(direction: dict[str, Any], attempt_number: int) -> None:
        nonlocal response_attempts, observed_call_items
        nonlocal completed_searches, provider_search_overrun
        prompt = build_prompt(
            template,
            publication_date=publication_date,
            search_window=search_window,
            missing_total=missing_total,
            maximum_web_search_calls=maximum_web_search_calls,
            existing_candidates=existing_candidates,
            archive=archive,
            direction=direction,
            attempt=attempt_number,
        )
        record: dict[str, Any] = {
            "direction_id": direction["id"],
            "label": direction["label"],
            "required": True,
            "attempt": attempt_number,
            "search_strategy": direction.get(
                "search_strategy", "targeted_topic_search"
            ),
            "allowed_domains": list(direction.get("allowed_domains", ())),
            "prompt": prompt,
            "status": "error",
            "outcome": "search_not_completed",
            "actual_queries": [],
            "sources": [],
            "candidate_count": 0,
            "candidates": [],
            "rejections": [],
            "notes": None,
            "api": None,
            "error": None,
        }
        response_attempts += 1
        try:
            payload, metadata = run_audit_request(
                api_key=api_key,
                model=model,
                prompt=prompt,
                # Every thematic pass gets exactly one search opportunity.
                maximum_web_search_calls=1,
                allowed_domains=direction.get("allowed_domains"),
            )
        except CoverageAuditResponseError as exc:
            metadata = exc.metadata
            record["api"] = metadata
            record["error"] = f"{type(exc).__name__}: {exc}"
            record["outcome"] = (
                "incomplete_response"
                if int(metadata.get("web_search_calls_completed", 0) or 0) > 0
                else "search_not_completed"
            )
        except Exception as exc:
            metadata = {}
            record["error"] = f"{type(exc).__name__}: {exc}"
            record["outcome"] = "transport_error"
        else:
            record["api"] = metadata
            actual_queries = metadata.get("actual_queries")
            sources = metadata.get("consulted_sources")
            record["actual_queries"] = (
                actual_queries if isinstance(actual_queries, list) else []
            )
            record["sources"] = sources if isinstance(sources, list) else []
            direction_matches = payload.get("direction_id") == direction["id"]
            completed_search = int(
                metadata.get("web_search_calls_completed", 0) or 0
            ) >= 1
            has_actual_query = bool(record["actual_queries"])
            payload_status = payload.get("status")
            usable_payload = (
                direction_matches
                and payload_status in {"complete", "complete_with_gaps"}
                and completed_search
                and has_actual_query
            )
            if usable_payload:
                record["status"] = (
                    "checked"
                    if payload_status == "complete"
                    else "checked_with_gaps"
                )
                record["outcome"] = (
                    "candidates_found"
                    if isinstance(payload.get("candidates"), list)
                    and bool(payload.get("candidates"))
                    else "no_news_found"
                )
                raw_rejections = payload.get("rejections")
                if isinstance(raw_rejections, list):
                    record["rejections"] = raw_rejections
                raw_candidates = payload.get("candidates")
                if isinstance(raw_candidates, list):
                    expected_category = {
                        "security_world": "security",
                        "security_russia": "security",
                        "security_asia": "security",
                        "legal_copyright_scraping": "legal",
                        "curiosity": "curiosity",
                    }.get(direction["id"])
                    expected_geography = (
                        "russia"
                        if direction["id"] == "security_russia"
                        else (
                            "world"
                            if direction["id"]
                            in {"security_world", "security_asia"}
                            else None
                        )
                    )
                    accepted_for_direction: list[dict[str, Any]] = []
                    for raw_candidate in raw_candidates:
                        if not isinstance(raw_candidate, dict):
                            continue
                        mismatch: list[str] = []
                        if (
                            expected_category is not None
                            and raw_candidate.get("category") != expected_category
                        ):
                            mismatch.append(
                                f"ожидалась category={expected_category}"
                            )
                        if (
                            expected_geography is not None
                            and raw_candidate.get("geography")
                            != expected_geography
                        ):
                            mismatch.append(
                                f"ожидалась geography={expected_geography}"
                            )
                        if mismatch:
                            primary = raw_candidate.get("primary_source")
                            record["rejections"].append(
                                {
                                    "title": raw_candidate.get("title")
                                    or "Кандидат без заголовка",
                                    "url": (
                                        primary.get("url")
                                        if isinstance(primary, dict)
                                        else None
                                    ),
                                    "reason_code": "other",
                                    "reason": (
                                        "Кандидат не соответствует тематическому "
                                        "проходу: " + ", ".join(mismatch)
                                    ),
                                }
                            )
                            continue
                        candidate_with_direction = copy.deepcopy(raw_candidate)
                        candidate_with_direction["audit_direction"] = direction["id"]
                        accepted_for_direction.append(candidate_with_direction)
                    record["candidates"] = accepted_for_direction
                    record["candidate_count"] = len(accepted_for_direction)
                    candidates.extend(accepted_for_direction)
                record["notes"] = payload.get("notes")
            else:
                # A response about another beat is not partial evidence for the
                # requested beat. Keep it explicitly unchecked so diagnostics
                # cannot accidentally claim that the direction was covered.
                record["status"] = (
                    "partial" if direction_matches else "unchecked"
                )
                record["outcome"] = "response_validation_failed"
                problems: list[str] = []
                if not direction_matches:
                    problems.append("response direction_id does not match request")
                if not completed_search:
                    problems.append("no completed web_search_call")
                if not has_actual_query:
                    problems.append("actual search query is missing")
                if payload_status not in {"complete", "complete_with_gaps"}:
                    problems.append(f"payload status={payload_status!r}")
                record["error"] = "; ".join(problems)

        metadata = record.get("api")
        if isinstance(metadata, dict):
            pass_call_items = int(
                metadata.get("web_search_call_items_total", 0) or 0
            )
            pass_completed_searches = int(
                metadata.get("web_search_calls_completed", 0) or 0
            )
            observed_call_items += pass_call_items
            completed_searches += pass_completed_searches
            if pass_completed_searches > 1:
                provider_search_overrun = True
            if not record["actual_queries"]:
                queries = metadata.get("actual_queries")
                if isinstance(queries, list):
                    record["actual_queries"] = queries
            if not record["sources"]:
                sources = metadata.get("consulted_sources")
                if isinstance(sources, list):
                    record["sources"] = sources
        attempts.append(record)
        latest_by_direction[direction["id"]] = record

    # First finish every never-attempted mandatory direction. A failed prior
    # direction is retried only after the other mandatory beats received their
    # first chance, preserving the six-direction contract under a seven-call cap.
    for direction in AUDIT_DIRECTIONS:
        if direction["id"] in latest_by_direction:
            continue
        if response_attempts >= maximum_web_search_calls:
            break
        if completed_searches >= maximum_web_search_calls:
            break
        run_direction(direction, 1)

    incomplete = [
        direction
        for direction in AUDIT_DIRECTIONS
        if latest_by_direction.get(direction["id"], {}).get("status")
        not in {"checked", "checked_with_gaps"}
    ]
    if (
        incomplete
        and response_attempts < maximum_web_search_calls
        and completed_searches < maximum_web_search_calls
    ):
        retry_direction = next(
            (
                direction
                for direction in incomplete
                if int(
                    latest_by_direction.get(direction["id"], {}).get(
                        "attempt", 0
                    )
                    or 0
                )
                < 2
            ),
            None,
        )
        if retry_direction is not None:
            retry_number = int(
                latest_by_direction.get(retry_direction["id"], {}).get(
                    "attempt", 0
                )
                or 0
            ) + 1
            run_direction(retry_direction, retry_number)

    checked = [
        direction_id
        for direction_id in AUDIT_DIRECTION_IDS
        if latest_by_direction.get(direction_id, {}).get("status")
        in {"checked", "checked_with_gaps"}
    ]
    partial = [
        direction_id
        for direction_id in AUDIT_DIRECTION_IDS
        if latest_by_direction.get(direction_id, {}).get("status")
        in {"partial", "error"}
    ]
    unchecked = [
        direction_id
        for direction_id in AUDIT_DIRECTION_IDS
        if latest_by_direction.get(direction_id, {}).get("status")
        in {None, "unchecked"}
    ]
    budget_exhausted = bool(partial or unchecked) and (
        completed_searches >= maximum_web_search_calls
    )
    attempt_limit_exhausted = bool(partial or unchecked) and (
        response_attempts >= maximum_web_search_calls
    )
    if len(checked) == len(AUDIT_DIRECTION_IDS):
        audit_status = (
            "complete_with_gaps"
            if any(
                latest_by_direction[item]["status"] == "checked_with_gaps"
                for item in checked
            )
            else "complete"
        )
    elif not checked:
        audit_status = "error"
    elif budget_exhausted or attempt_limit_exhausted:
        audit_status = "budget_exhausted"
    elif checked:
        audit_status = "partial"

    api = _aggregate_api_metadata(attempts)
    return {
        "audit_status": audit_status,
        "required_directions": list(AUDIT_DIRECTION_IDS),
        "checked_directions": checked,
        "partial_directions": partial,
        "unchecked_directions": unchecked,
        "directions": [
            latest_by_direction.get(
                direction["id"],
                {
                    "direction_id": direction["id"],
                    "label": direction["label"],
                    "required": True,
                    "attempt": 0,
                    "status": "unchecked",
                    "outcome": (
                        "budget_exhausted"
                        if budget_exhausted or attempt_limit_exhausted
                        else "not_attempted"
                    ),
                    "actual_queries": [],
                    "sources": [],
                    "candidate_count": 0,
                    "candidates": [],
                    "rejections": [],
                    "notes": None,
                    "api": None,
                    "error": (
                        "search budget ended before this direction"
                        if budget_exhausted or attempt_limit_exhausted
                        else "direction was not completed"
                    ),
                },
            )
            for direction in AUDIT_DIRECTIONS
        ],
        "attempts": attempts,
        "search_budget": {
            "maximum_calls": maximum_web_search_calls,
            "minimum_required_calls": MINIMUM_REQUIRED_AUDIT_CALLS,
            "response_attempts": response_attempts,
            "observed_call_items": observed_call_items,
            "completed_calls": completed_searches,
            "remaining_calls": max(
                0, maximum_web_search_calls - completed_searches
            ),
            "exhausted": budget_exhausted or attempt_limit_exhausted,
            "search_budget_exhausted": budget_exhausted,
            "response_attempt_limit_exhausted": attempt_limit_exhausted,
            "provider_overrun": provider_search_overrun,
            "stop_reason": (
                "all_required_directions_checked"
                if len(checked) == len(AUDIT_DIRECTION_IDS)
                else (
                    "completed_search_budget_exhausted"
                    if budget_exhausted
                    else (
                        "response_attempt_limit_exhausted"
                        if attempt_limit_exhausted
                        else "mandatory_direction_incomplete"
                    )
                )
            ),
        },
        "api": api,
        "candidates": candidates,
        "time_precision_warnings": [
            {
                "title": item.get("title"),
                "published_date": item.get("published_date"),
                "warning": "time_precision=date: источник не указал точное время",
            }
            for item in candidates
            if isinstance(item, dict) and item.get("time_precision") == "date"
        ],
    }


def rerun_editorial(
    *,
    publication_date: str,
    merged_research_path: Path,
    minimum_total: int,
    maximum_candidates: int,
    maximum_selected_stories: int,
) -> None:
    command = [
        sys.executable,
        str(GENERATOR_PATH),
        "--publication-date",
        publication_date,
        "--minimum-candidates",
        str(minimum_total),
        "--maximum-candidates",
        str(maximum_candidates),
        "--minimum-selected-stories",
        str(minimum_total),
        "--maximum-selected-stories",
        str(maximum_selected_stories),
        "--research-input",
        str(merged_research_path.relative_to(REPOSITORY_ROOT)),
    ]
    subprocess.run(command, cwd=REPOSITORY_ROOT, env=os.environ.copy(), check=True)



def load_initial_stories(
    artifact_dir: Path,
    research: dict[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    """Load final stories or derive provisional geography from editorial output.

    A failed initial editorial validation can leave a perfectly reusable paid
    research result and parsed editorial JSON but no stories.json. Coverage must
    still be able to decide whether a targeted search is needed.
    """

    stories_path = artifact_dir / "stories.json"
    if stories_path.is_file():
        stories = read_json(stories_path)
        if not isinstance(stories, list):
            raise RuntimeError("stories.json должен содержать массив")
        return [item for item in stories if isinstance(item, dict)], "complete"

    candidate_map = {
        str(item.get("id")): item
        for item in research.get("candidates", [])
        if isinstance(item, dict) and item.get("id") is not None
    }
    for name in ("editorial-output.json", "editorial-output-raw.json"):
        path = artifact_dir / name
        if not path.is_file():
            continue
        payload = read_json(path)
        if not isinstance(payload, dict):
            continue
        selected = payload.get("selected_candidate_ids")
        if not isinstance(selected, list):
            continue
        provisional: list[dict[str, Any]] = []
        for raw_id in selected:
            candidate_id = str(raw_id)
            candidate = candidate_map.get(candidate_id)
            if not isinstance(candidate, dict):
                continue
            provisional.append(
                {
                    "candidate_id": candidate_id,
                    "geography": candidate.get("geography"),
                    "section": candidate.get("geography"),
                }
            )
        return provisional, "partial_editorial"

    return [], "research_only"


SHORT_NOTICE = "Новостей сегодня меньше, чем обычно"
SHORT_NOTICE_HTML = f"<p><em>{SHORT_NOTICE}</em></p>"
LEGACY_SHORT_NOTICE = "День на новости выдался слабым - поэтому коротко"


def prior_audit_attempted(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    api = payload.get("api") or {}
    error = str(payload.get("error") or "")
    return bool(
        payload.get("web_search_requested") is True
        or payload.get("web_search_performed") is True
        or isinstance(api, dict)
        and bool(api)
        or "Coverage audit превысил лимит web search" in error
    )


def completed_prior_audit(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("audit_state") not in {None, "completed_usable"}:
        return False
    api = payload.get("api") or {}
    return bool(
        payload.get("web_search_performed") is True
        and payload.get("audit_status") in {"complete", "complete_with_gaps"}
        and set(payload.get("checked_directions") or ())
        == set(AUDIT_DIRECTION_IDS)
        and isinstance(api, dict)
        and api.get("status") == "completed"
    )


def completed_prior_audit_for_source_health(
    payload: Any, *, source_health_rescue_needed: bool
) -> bool:
    """Reuse legacy audits normally; version them only for modern source-health rescue."""
    if not completed_prior_audit(payload):
        return False
    if not source_health_rescue_needed:
        return True
    return bool(
        isinstance(payload, dict)
        and payload.get("source_health_contract_version")
        == SOURCE_HEALTH_CONTRACT_VERSION
    )


def _remove_short_notices(article_html: str) -> str:
    value = article_html
    for notice in (SHORT_NOTICE, LEGACY_SHORT_NOTICE):
        value = re.sub(
            r"^\s*<p>\s*(?:<em>\s*)?" + re.escape(notice) + r"(?:\s*</em>)?\s*</p>\s*",
            "",
            value,
            flags=re.IGNORECASE,
        )
    return value.strip()


def apply_short_edition_marker(artifact_dir: Path, *, short_edition: bool) -> None:
    digest_path = artifact_dir / "digest.json"
    if not digest_path.is_file():
        return
    meta_path = artifact_dir / "meta.json"
    editorial_path = artifact_dir / "editorial-output.json"
    article_path = artifact_dir / "article.html"
    digest = read_json(digest_path)
    if not isinstance(digest, dict):
        raise RuntimeError("digest.json должен содержать объект")
    article_html = _remove_short_notices(str(digest.get("article_html", "")))
    notes = digest.get("editorial_notes")
    if not isinstance(notes, list):
        notes = []
    notes = [
        item
        for item in notes
        if not (
            isinstance(item, dict)
            and item.get("type") in {"low_news_volume", "regional_gap"}
        )
    ]
    if short_edition:
        article_html = SHORT_NOTICE_HTML + "\n" + article_html
        notes.insert(
            0,
            {
                "type": "low_news_volume",
                "area": "total",
                "message": "После основного и дополнительного поиска опубликован сокращённый выпуск.",
            },
        )
    digest["short_digest"] = short_edition
    digest["article_html"] = article_html
    digest["editorial_notes"] = notes
    write_json(digest_path, digest)
    article_path.write_text(article_html.rstrip() + "\n", encoding="utf-8")

    if meta_path.is_file():
        meta = read_json(meta_path)
        if isinstance(meta, dict):
            meta["short_digest"] = short_edition
            meta["editorial_notes"] = notes
            write_json(meta_path, meta)

    if editorial_path.is_file():
        editorial = read_json(editorial_path)
        if isinstance(editorial, dict) and isinstance(editorial.get("digest"), dict):
            editorial["digest"] = digest
            write_json(editorial_path, editorial)


def snapshot_artifact(artifact_dir: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(artifact_dir): path.read_bytes()
        for path in artifact_dir.rglob("*")
        if path.is_file()
    }


def restore_artifact(artifact_dir: Path, snapshot: dict[Path, bytes]) -> None:
    if artifact_dir.exists():
        shutil.rmtree(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    for relative_path, content in snapshot.items():
        target = artifact_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Попытаться дополнить короткий выпуск без региональных квот и "
            "сохранить публикацию, если найден хотя бы один достойный сюжет."
        )
    )
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--publication-date", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--usual-total", type=int, default=7)
    parser.add_argument("--minimum-publishable", type=int, default=1)
    parser.add_argument(
        "--maximum-audit-web-search-calls",
        type=int,
        default=DEFAULT_MAXIMUM_AUDIT_CALLS,
    )
    parser.add_argument("--maximum-candidates", type=int, default=20)
    parser.add_argument("--maximum-selected-stories", type=int, default=12)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if not (
        1
        <= args.minimum_publishable
        <= args.usual_total
        <= args.maximum_selected_stories
    ):
        parser.error(
            "Требуется 1 <= minimum-publishable <= usual-total "
            "<= maximum-selected-stories."
        )
    if not (
        MINIMUM_REQUIRED_AUDIT_CALLS
        <= args.maximum_audit_web_search_calls
        <= DEFAULT_MAXIMUM_AUDIT_CALLS
    ):
        parser.error(
            "maximum-audit-web-search-calls должен быть 6 или 7; "
            "увеличение выше 7 требует отдельного решения."
        )

    prior_report: dict[str, Any] | None = None
    if args.report.is_file():
        try:
            loaded_prior = read_json(args.report)
            if isinstance(loaded_prior, dict):
                prior_report = loaded_prior
        except Exception:
            prior_report = None

    report: dict[str, Any] = {
        "status": "running",
        "publication_date": args.publication_date,
        "targets": {
            "usual_total": args.usual_total,
            "minimum_publishable": args.minimum_publishable,
        },
        "regional_story_quotas_enabled": False,
        "audit_failure_blocks_publication": True,
        "maximum_audit_web_search_calls": args.maximum_audit_web_search_calls,
        "minimum_required_audit_web_search_calls": (
            MINIMUM_REQUIRED_AUDIT_CALLS
        ),
        "audit_needed": False,
        "audit_status": "not_needed",
        "required_directions": list(AUDIT_DIRECTION_IDS),
        "checked_directions": [],
        "partial_directions": [],
        "unchecked_directions": list(AUDIT_DIRECTION_IDS),
        "directions": [],
        "search_budget": {
            "maximum_calls": args.maximum_audit_web_search_calls,
            "minimum_required_calls": MINIMUM_REQUIRED_AUDIT_CALLS,
            "response_attempts": 0,
            "observed_call_items": 0,
            "completed_calls": 0,
            "remaining_calls": args.maximum_audit_web_search_calls,
            "exhausted": False,
            "provider_overrun": False,
        },
        "web_search_requested": False,
        "web_search_performed": False,
        "prior_audit_reused": False,
        "prior_audit_resumed": False,
        "audit_error": None,
        "publication_mode": None,
        "before": None,
        "after": None,
        "candidate_pool_before": None,
        "candidate_pool_after": None,
        "accepted_candidates": [],
        "rejected_candidates": [],
        "audit_added_candidates": 0,
        "editorial_rerun_required": False,
        "editorial_rerun_performed": False,
        "editorial_completion_required": False,
        "editorial_completion_performed": False,
        "warnings": [],
        "api": None,
        "error": None,
    }

    runtime_research_path = (
        RUNTIME_RESEARCH_ROOT / f".coverage-audit-{args.publication_date}.json"
    )
    persisted_research_path = (
        PERSISTED_RESEARCH_ROOT
        / f"coverage-audit-merged-candidates-{args.publication_date}.json"
    )
    try:
        research = read_json(args.artifact_dir / "candidates.json")
        archive = read_json(args.archive)
        if not isinstance(research, dict) or not isinstance(research.get("candidates"), list):
            raise RuntimeError("candidates.json имеет неожиданную структуру")
        if not isinstance(archive, dict):
            raise RuntimeError("archive index должен содержать объект")
        stories, artifact_mode = load_initial_stories(args.artifact_dir, research)
        report["initial_artifact_mode"] = artifact_mode
        initial_snapshot = (
            snapshot_artifact(args.artifact_dir)
            if artifact_mode == "complete"
            else {}
        )

        args.report.parent.mkdir(parents=True, exist_ok=True)
        for source_name, target_name in (
            ("run-info.json", "coverage-audit-initial-run-info.json"),
            ("candidates.json", "coverage-audit-initial-candidates.json"),
            ("stories.json", "coverage-audit-initial-stories.json"),
            ("digest.json", "coverage-audit-initial-digest.json"),
            ("meta.json", "coverage-audit-initial-meta.json"),
            ("article.html", "coverage-audit-initial-article.html"),
            ("editorial-output.json", "coverage-audit-initial-editorial.json"),
            ("editorial-output-raw.json", "coverage-audit-initial-editorial-raw.json"),
        ):
            source_path = args.artifact_dir / source_name
            if source_path.is_file():
                (args.report.parent / target_name).write_bytes(source_path.read_bytes())

        before = coverage_summary(
            stories,
            usual_total=args.usual_total,
            minimum_publishable=args.minimum_publishable,
        )
        report["before"] = before
        report["candidate_pool_before"] = eligible_candidate_summary(
            research["candidates"]
        )
        candidate_pool = report["candidate_pool_before"]

        search_window = research.get("search_window")
        if not isinstance(search_window, dict):
            raise RuntimeError("candidates.json не содержит search_window")
        modern_primary_artifact = (args.artifact_dir / "primary-recall.json").is_file()
        source_health_rescue_needed = bool(
            modern_primary_artifact
            and candidate_pool["total"] > 0
            and not _candidates_have_fresh_agency_source(
                research["candidates"], search_window
            )
        )
        report["source_health_contract_required"] = modern_primary_artifact
        report["source_health_rescue_needed"] = source_health_rescue_needed

        if (
            artifact_mode == "complete"
            and before["publication_allowed"]
            and before["usual_target_met"]
            and not source_health_rescue_needed
        ):
            apply_short_edition_marker(args.artifact_dir, short_edition=False)
            report["status"] = "ok"
            report["mode"] = "existing_full_digest"
            report["publication_mode"] = "full"
            report["after"] = before
            report["candidate_pool_after"] = candidate_pool
            write_json(args.report, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        report["audit_needed"] = (
            not before["usual_target_met"]
            or candidate_pool["total"] < args.usual_total
            or source_health_rescue_needed
        )
        additional_candidates: list[Any] = []
        prior_attempted = prior_audit_attempted(prior_report)
        prior_complete = completed_prior_audit_for_source_health(
            prior_report, source_health_rescue_needed=source_health_rescue_needed
        )
        if report["audit_needed"] and not prior_complete:
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
            if not api_key:
                report["audit_error"] = (
                    "OPENAI_API_KEY не задан для обязательного coverage audit"
                )
                report["audit_status"] = "error"
            else:
                template = PROMPT_PATH.read_text(encoding="utf-8")
                search_window = research.get("search_window")
                if not isinstance(search_window, dict):
                    raise RuntimeError("candidates.json не содержит search_window")
                report["web_search_requested"] = True
                report["prior_audit_resumed"] = prior_attempted
                try:
                    audit_plan = execute_audit_plan(
                        api_key=api_key,
                        model=args.model,
                        template=template,
                        publication_date=args.publication_date,
                        search_window=search_window,
                        missing_total=max(
                            0, args.usual_total - candidate_pool["total"]
                        ),
                        maximum_web_search_calls=args.maximum_audit_web_search_calls,
                        existing_candidates=research["candidates"],
                        archive=archive,
                        prior_plan=prior_report if prior_attempted else None,
                    )
                except Exception as exc:
                    report["audit_error"] = (
                        f"{type(exc).__name__}: {exc}"
                    )
                    report["audit_status"] = "error"
                else:
                    prompt_dir = args.report.parent / "coverage-audit-prompts"
                    prompt_dir.mkdir(parents=True, exist_ok=True)
                    for index, attempt in enumerate(
                        audit_plan.get("attempts", []), start=1
                    ):
                        if not isinstance(attempt, dict):
                            continue
                        if "prompt" not in attempt:
                            # Recovered attempts already point to their original
                            # diagnostics and must not be replaced by blank files.
                            continue
                        prompt = str(attempt.pop("prompt", ""))
                        direction_id = str(
                            attempt.get("direction_id") or "unknown"
                        )
                        prompt_path = (
                            prompt_dir
                            / f"{index:02d}-{direction_id}-attempt-"
                            f"{attempt.get('attempt', 1)}.txt"
                        )
                        prompt_path.write_text(
                            prompt.rstrip() + "\n", encoding="utf-8"
                        )
                        attempt["prompt_path"] = str(prompt_path)
                    for key in (
                        "audit_status",
                        "required_directions",
                        "checked_directions",
                        "partial_directions",
                        "unchecked_directions",
                        "directions",
                        "attempts",
                        "search_budget",
                        "time_precision_warnings",
                        "api",
                        "temporal_anchor_version",
                    ):
                        report[key] = audit_plan.get(key)
                    report["web_search_performed"] = (
                        int(
                            (audit_plan.get("search_budget") or {}).get(
                                "completed_calls", 0
                            )
                            or 0
                        )
                        > 0
                    )
                    report["queries_used"] = [
                        {
                            "area": item.get("direction_id"),
                            "query": query,
                            "purpose": item.get("label"),
                        }
                        for item in report.get("attempts", [])
                        if isinstance(item, dict)
                        for query in item.get("actual_queries", [])
                    ]
                    report["audit_notes"] = (
                        "Шесть обязательных тематических проходов; седьмой "
                        "вызов используется только для повтора незавершённого "
                        "направления."
                    )
                    budget = audit_plan.get("search_budget") or {}
                    if budget.get("provider_overrun"):
                        audit_warning = (
                            "Responses API завершил больше одной поисковой "
                            "операции внутри отдельного прохода; расход учтён "
                            "по фактическим search actions."
                        )
                        report["audit_warning"] = audit_warning
                        report["warnings"].append(audit_warning)
                    if audit_plan.get("audit_status") in {
                        "partial",
                        "budget_exhausted",
                        "error",
                    }:
                        report["warnings"].append(
                            "Coverage audit завершён не полностью; publication, "
                            "image generation и deploy будут заблокированы."
                        )
                    raw_candidates = audit_plan.get("candidates", [])
                    if isinstance(raw_candidates, list):
                        additional_candidates = raw_candidates
        elif report["audit_needed"] and prior_complete:
            report["prior_audit_reused"] = True
            report["temporal_anchor_version"] = (prior_report or {}).get(
                "temporal_anchor_version"
            )
            report["web_search_requested"] = True
            report["web_search_performed"] = bool(
                (prior_report or {}).get("web_search_performed")
                or (prior_report or {}).get("api")
                or "Coverage audit превысил лимит web search"
                in str((prior_report or {}).get("error") or "")
            )
            report["api"] = prior_report.get("api") if prior_report else None
            report["queries_used"] = (prior_report or {}).get("queries_used", [])
            for key in (
                "audit_status",
                "required_directions",
                "checked_directions",
                "partial_directions",
                "unchecked_directions",
                "directions",
                "attempts",
                "search_budget",
                "time_precision_warnings",
            ):
                if (prior_report or {}).get(key) is not None:
                    report[key] = (prior_report or {}).get(key)
            if not (prior_report or {}).get("audit_status"):
                report["audit_status"] = "partial"
                report["warnings"].append(
                    "Legacy recovery artifact не содержит понаправленной "
                    "диагностики; полнота прежнего audit неизвестна."
                )
            report["audit_notes"] = (
                "Использован полный отчёт coverage audit из recovery artifact; "
                "повторный web search не выполнялся."
            )
            report["prior_audit_error"] = (prior_report or {}).get("error")
            for direction_record in (prior_report or {}).get("directions", []):
                if not isinstance(direction_record, dict):
                    continue
                raw_candidates = direction_record.get("candidates")
                if isinstance(raw_candidates, list):
                    additional_candidates.extend(copy.deepcopy(raw_candidates))

        if report["audit_needed"] and report.get("audit_status") not in {
            "complete",
            "complete_with_gaps",
        }:
            unchecked = ", ".join(
                map(str, report.get("unchecked_directions") or [])
            ) or "нет данных"
            partial = ", ".join(
                map(str, report.get("partial_directions") or [])
            ) or "нет данных"
            stop_reason = str(
                (report.get("search_budget") or {}).get("stop_reason")
                or report.get("audit_error")
                or "mandatory_direction_incomplete"
            )
            report["audit_error"] = (
                "Обязательный coverage audit не завершён: "
                f"status={report.get('audit_status')}; "
                f"partial={partial}; unchecked={unchecked}; "
                f"stop_reason={stop_reason}."
            )
            raise RuntimeError(
                report["audit_error"]
                + " Публикация, генерация изображения и deploy заблокированы."
            )

        if additional_candidates:
            merged, accepted, rejected = merge_candidates(
                research,
                additional_candidates,
                maximum_candidates=args.maximum_candidates,
            )
        else:
            merged = copy.deepcopy(research)
            accepted = []
            rejected = []
        report["accepted_candidates"] = [
            {
                "title": item.get("title"),
                "geography": item.get("geography"),
                "category": item.get("category"),
                "audit_direction": item.get("audit_direction"),
                "published_date": item.get("published_date"),
                "time_precision": item.get("time_precision"),
                "primary_source": item.get("primary_source"),
            }
            for item in accepted
        ]
        report["rejected_candidates"] = rejected
        report["audit_added_candidates"] = len(accepted)
        report["editorial_rerun_required"] = bool(accepted)
        report["editorial_completion_required"] = artifact_mode != "complete"
        report["candidate_pool_after"] = eligible_candidate_summary(merged["candidates"])
        pool_after = report["candidate_pool_after"]
        if pool_after["total"] < args.minimum_publishable:
            raise RuntimeError(
                "После основного и дополнительного поиска не осталось ни одного "
                "достойного сюжета"
            )
        report["short_edition_candidate"] = (
            pool_after["total"] < args.usual_total
        )

        if (
            artifact_mode == "complete"
            and before["publication_allowed"]
            and not accepted
        ):
            short_edition = bool(before["short_digest"])
            apply_short_edition_marker(
                args.artifact_dir,
                short_edition=short_edition,
            )
            report["after"] = before
            report["publication_mode"] = (
                "short" if short_edition else "full"
            )
            report["status"] = "ok"
            if report["prior_audit_reused"]:
                report["mode"] = "existing_short_digest_after_reused_audit"
            elif report["audit_needed"]:
                report["mode"] = (
                    "existing_short_digest_after_best_effort_audit"
                )
            else:
                report["mode"] = "existing_short_digest"
            write_json(args.report, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        RUNTIME_RESEARCH_ROOT.mkdir(parents=True, exist_ok=True)
        PERSISTED_RESEARCH_ROOT.mkdir(parents=True, exist_ok=True)
        write_json(runtime_research_path, merged)
        write_json(persisted_research_path, merged)
        report["runtime_research_path"] = str(runtime_research_path)
        report["persisted_research_path"] = str(persisted_research_path)
        # Backward-compatible report key now points to the durable artifact copy.
        report["merged_research_path"] = str(persisted_research_path)
        try:
            rerun_editorial(
                publication_date=args.publication_date,
                merged_research_path=runtime_research_path,
                minimum_total=args.usual_total,
                maximum_candidates=args.maximum_candidates,
                maximum_selected_stories=args.maximum_selected_stories,
            )
        except Exception as exc:
            if initial_snapshot and before["publication_allowed"]:
                restore_artifact(args.artifact_dir, initial_snapshot)
                short_edition = bool(before["short_digest"])
                apply_short_edition_marker(
                    args.artifact_dir,
                    short_edition=short_edition,
                )
                report["editorial_repair_error"] = (
                    f"{type(exc).__name__}: {exc}"
                )
                report["after"] = before
                report["publication_mode"] = (
                    "short" if short_edition else "full"
                )
                report["status"] = "ok"
                report["mode"] = (
                    "existing_digest_after_editorial_repair_error"
                )
                write_json(args.report, report)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 0
            raise
        report["editorial_rerun_performed"] = bool(accepted)
        report["editorial_completion_performed"] = artifact_mode != "complete"
        rerun_stories = read_json(args.artifact_dir / "stories.json")
        if not isinstance(rerun_stories, list):
            raise RuntimeError("После editorial rerun stories.json должен быть массивом")
        after = coverage_summary(
            rerun_stories,
            usual_total=args.usual_total,
            minimum_publishable=args.minimum_publishable,
        )
        report["after"] = after
        if not after["publication_allowed"]:
            if initial_snapshot and before["publication_allowed"]:
                restore_artifact(args.artifact_dir, initial_snapshot)
                apply_short_edition_marker(
                    args.artifact_dir,
                    short_edition=bool(before["short_digest"]),
                )
                report["after"] = before
                report["publication_mode"] = (
                    "short" if before["short_digest"] else "full"
                )
                report["status"] = "ok"
                report["mode"] = "existing_digest_after_empty_editorial_rerun"
                write_json(args.report, report)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 0
            raise RuntimeError("Редакторский повтор не выбрал ни одного достойного сюжета")
        short_edition = bool(after["short_digest"])
        apply_short_edition_marker(args.artifact_dir, short_edition=short_edition)
        report["publication_mode"] = "short" if short_edition else "full"
        report["status"] = "ok"
        if report["prior_audit_reused"]:
            report["mode"] = "reused_prior_audit_and_editorial_rerun"
        elif report["web_search_performed"]:
            report["mode"] = "targeted_web_search_and_editorial_rerun"
        else:
            report["mode"] = "editorial_rerun_only"
        write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        report["status"] = "error"
        report["error"] = f"{type(exc).__name__}: {exc}"
        write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    finally:
        # The generator intentionally accepts saved research only from the
        # fixture root. Remove that transient execution copy, while retaining
        # the persisted copy under automation/preview/production-daily for
        # artifact recovery after any later failure.
        if runtime_research_path.exists():
            runtime_research_path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
