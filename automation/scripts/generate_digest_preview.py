from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import sys
from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta, timezone
from html.parser import HTMLParser
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from openai import OpenAI

from editorial_policy import (
    build_editorial_notes,
    build_stories,
    normalize_article_html,
    normalize_candidate_ids,
    order_candidates_by_article_links,
    read_policy,
    validate_article_policy,
    validate_diversity_overrides,
    validate_stories,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPOSITORY_ROOT / "automation/config/site.json"
EDITORIAL_CONFIG_PATH = REPOSITORY_ROOT / "automation/config/editorial.json"
RESEARCH_PROMPT_PATH = REPOSITORY_ROOT / "automation/prompts/research_candidates.md"
EDITORIAL_PROMPT_PATH = REPOSITORY_ROOT / "automation/prompts/daily_digest.md"
ARCHIVE_PATH = REPOSITORY_ROOT / "automation/archive/index.json"
PREVIEW_ROOT = REPOSITORY_ROOT / "automation/preview"

DEFAULT_MODEL = "gpt-5.6-terra"
DEFAULT_MINIMUM_CANDIDATES = 12
DEFAULT_MINIMUM_RUSSIAN_CANDIDATES = 2
DEFAULT_MAXIMUM_CANDIDATES = 20
DEFAULT_MINIMUM_SELECTED_STORIES = 6
DEFAULT_MAXIMUM_SELECTED_STORIES = 12

ALLOWED_HTML_TAGS = {
    "p",
    "h2",
    "h3",
    "ul",
    "ol",
    "li",
    "strong",
    "em",
    "a",
    "blockquote",
}

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
    "russia",
    "other",
]

TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "yclid",
    "mc_cid",
    "mc_eid",
}

RUSSIAN_MONTHS = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}

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

CANDIDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "id": {
            "type": "string",
            "pattern": r"^cand-[0-9]{3}$",
        },
        "title": {"type": "string", "minLength": 1},
        "organization": {"type": "string", "minLength": 1},
        "published_date": {
            "type": "string",
            "pattern": r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
        },
        "published_at": {"type": ["string", "null"]},
        "time_precision": {
            "type": "string",
            "enum": ["datetime", "date"],
        },
        "topic": {"type": "string", "minLength": 1},
        "event_type": {"type": "string", "minLength": 1},
        "keywords": {
            "type": "array",
            "minItems": 1,
            "maxItems": 12,
            "items": {"type": "string", "minLength": 1},
        },
        "geography": {
            "type": "string",
            "enum": ["world", "russia"],
        },
        "category": {
            "type": "string",
            "enum": ALLOWED_CATEGORIES,
        },
        "source_type": {
            "type": "string",
            "enum": [
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
            ],
        },
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
        "archive_status": {
            "type": "string",
            "enum": ["none", "update"],
        },
        "archive_reason": {"type": "string"},
        "recommendation": {
            "type": "string",
            "enum": ["include", "consider", "exclude"],
        },
    },
    "required": [
        "id",
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
    ],
}

RESEARCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {"type": "string", "enum": ["ok", "error"]},
        "error_message": {"type": ["string", "null"]},
        "publication_date": {
            "type": "string",
            "pattern": r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
        },
        "search_window": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "start_at": {"type": "string", "minLength": 1},
                "end_at": {"type": "string", "minLength": 1},
                "latest_archive_at": {"type": ["string", "null"]},
                "start_date": {
                    "type": "string",
                    "pattern": r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
                },
                "end_date": {
                    "type": "string",
                    "pattern": r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
                },
                "latest_archive_date": {
                    "type": ["string", "null"],
                    "pattern": r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
                },
            },
            "required": [
                "start_at",
                "end_at",
                "latest_archive_at",
                "start_date",
                "end_date",
                "latest_archive_date",
            ],
        },
        "coverage": {
            "type": "array",
            "minItems": 9,
            "maxItems": 12,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "area": {"type": "string", "minLength": 1},
                    "status": {
                        "type": "string",
                        "enum": ["covered", "gap"],
                    },
                    "notes": {"type": "string", "minLength": 1},
                },
                "required": ["area", "status", "notes"],
            },
        },
        "candidates": {
            "type": "array",
            "minItems": 0,
            "maxItems": 24,
            "items": CANDIDATE_SCHEMA,
        },
        "rejected_as_duplicates": {
            "type": "array",
            "minItems": 0,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string", "minLength": 1},
                    "url": {"type": "string", "minLength": 1},
                    "archive_item_date": {
                        "type": ["string", "null"],
                    },
                    "matched_topic_or_url": {"type": "string", "minLength": 1},
                    "reason": {"type": "string", "minLength": 1},
                },
                "required": [
                    "title",
                    "url",
                    "archive_item_date",
                    "matched_topic_or_url",
                    "reason",
                ],
            },
        },
        "research_notes": {"type": "string", "minLength": 1},
    },
    "required": [
        "status",
        "error_message",
        "publication_date",
        "search_window",
        "coverage",
        "candidates",
        "rejected_as_duplicates",
        "research_notes",
    ],
}

DIGEST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {"type": "string", "enum": ["ok", "error"]},
        "error_message": {"type": ["string", "null"]},
        "date": {
            "type": "string",
            "pattern": r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
        },
        "slug": {
            "type": "string",
            "pattern": r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
        },
        "title": {"type": "string"},
        "description": {"type": "string"},
        "published_at": {"type": "string", "minLength": 1},
        "author": {"type": "string", "minLength": 1},
        "cover_filename": {"type": "string"},
        "article_html": {"type": "string"},
        "image_prompt": {"type": "string"},
        "topics": {
            "type": "array",
            "minItems": 0,
            "items": {"type": "string", "minLength": 1},
        },
        "sources": {
            "type": "array",
            "minItems": 0,
            "items": SOURCE_SCHEMA,
        },
        "short_digest": {"type": "boolean"},
        "editorial_notes": {
            "type": "array",
            "minItems": 0,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {"type": "string", "minLength": 1},
                    "area": {"type": "string", "minLength": 1},
                    "message": {"type": "string", "minLength": 1},
                },
                "required": ["type", "area", "message"],
            },
        },
    },
    "required": [
        "status",
        "error_message",
        "date",
        "slug",
        "title",
        "description",
        "published_at",
        "author",
        "cover_filename",
        "article_html",
        "image_prompt",
        "topics",
        "sources",
        "short_digest",
        "editorial_notes",
    ],
}

EDITORIAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {"type": "string", "enum": ["ok", "error"]},
        "error_message": {"type": ["string", "null"]},
        "selected_candidate_ids": {
            "type": "array",
            "minItems": 0,
            "items": {
                "type": "string",
                "pattern": r"^cand-[0-9]{3}$",
            },
        },
        "excluded_candidate_ids": {
            "type": "array",
            "minItems": 0,
            "items": {
                "type": "string",
                "pattern": r"^cand-[0-9]{3}$",
            },
        },
        "selection_summary": {"type": "string", "minLength": 1},
        "diversity_overrides": {
            "type": "array",
            "minItems": 0,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["publisher", "organization"],
                    },
                    "value": {"type": "string", "minLength": 1},
                    "reason": {"type": "string", "minLength": 1},
                },
                "required": ["type", "value", "reason"],
            },
        },
        "digest": DIGEST_SCHEMA,
    },
    "required": [
        "status",
        "error_message",
        "selected_candidate_ids",
        "excluded_candidate_ids",
        "selection_summary",
        "diversity_overrides",
        "digest",
    ],
}


class ArticleHTMLValidator(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.hrefs: list[str] = []
        self.h2_texts: list[str] = []
        self.h3_texts: list[str] = []
        self.errors: list[str] = []
        self._capture_tag: str | None = None
        self._capture_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag = tag.lower()

        if tag not in ALLOWED_HTML_TAGS:
            self.errors.append(f"Недопустимый HTML-тег: <{tag}>")
            return

        if tag == "a":
            if len(attrs) != 1 or attrs[0][0].lower() != "href" or not attrs[0][1]:
                self.errors.append(
                    "Тег <a> должен содержать только непустой атрибут href."
                )
            else:
                self.hrefs.append(attrs[0][1].strip())
        elif attrs:
            self.errors.append(f"У тега <{tag}> не должно быть атрибутов.")

        self.stack.append(tag)

        if tag in {"h2", "h3"}:
            self._capture_tag = tag
            self._capture_parts = []

    def handle_data(self, data: str) -> None:
        if self._capture_tag:
            self._capture_parts.append(data)

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        self.errors.append(f"Самозакрывающийся тег <{tag}/> не разрешён.")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if tag not in ALLOWED_HTML_TAGS:
            self.errors.append(f"Недопустимый закрывающий HTML-тег: </{tag}>")
            return

        if not self.stack:
            self.errors.append(f"Лишний закрывающий тег: </{tag}>")
            return

        expected = self.stack.pop()
        if expected != tag:
            self.errors.append(
                f"Нарушена вложенность HTML: ожидался </{expected}>, "
                f"получен </{tag}>."
            )

        if self._capture_tag == tag:
            text = " ".join("".join(self._capture_parts).split())
            if tag == "h2":
                self.h2_texts.append(text)
            else:
                self.h3_texts.append(text)
            self._capture_tag = None
            self._capture_parts = []

    def finish(self) -> None:
        if self.stack:
            self.errors.append(
                "Не закрыты HTML-теги: "
                + ", ".join(f"<{tag}>" for tag in self.stack)
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Создать двухэтапный preview ИИ-сводки: "
            "research candidates, затем editorial digest."
        )
    )
    parser.add_argument(
        "--publication-date",
        required=True,
        help="Дата выпуска в формате YYYY-MM-DD.",
    )
    parser.add_argument(
        "--minimum-candidates",
        type=int,
        default=DEFAULT_MINIMUM_CANDIDATES,
    )
    parser.add_argument(
        "--minimum-russian-candidates",
        type=int,
        default=DEFAULT_MINIMUM_RUSSIAN_CANDIDATES,
    )
    parser.add_argument(
        "--maximum-candidates",
        type=int,
        default=DEFAULT_MAXIMUM_CANDIDATES,
    )
    parser.add_argument(
        "--minimum-selected-stories",
        type=int,
        default=DEFAULT_MINIMUM_SELECTED_STORIES,
    )
    parser.add_argument(
        "--maximum-selected-stories",
        type=int,
        default=DEFAULT_MAXIMUM_SELECTED_STORIES,
    )
    parser.add_argument(
        "--research-input",
        default=None,
        help=(
            "Необязательный путь к сохранённому candidates.json. "
            "Если задан, web search пропускается и выполняется только "
            "редакторский этап."
        ),
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Не найден обязательный файл: {path.relative_to(REPOSITORY_ROOT)}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Некорректный JSON в {path.relative_to(REPOSITORY_ROOT)}: {exc}"
        ) from exc


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Не найден обязательный файл: {path.relative_to(REPOSITORY_ROOT)}"
        ) from exc


def parse_publication_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise RuntimeError(
            "publication_date должна иметь формат YYYY-MM-DD."
        ) from exc

    if parsed.isoformat() != value:
        raise RuntimeError(
            "publication_date должна иметь строгий формат YYYY-MM-DD."
        )

    return parsed


def validate_limits(args: argparse.Namespace) -> None:
    if not 1 <= args.minimum_candidates <= args.maximum_candidates <= 24:
        raise RuntimeError(
            "Требуется 1 <= minimum_candidates <= maximum_candidates <= 24."
        )

    if not 0 <= args.minimum_russian_candidates <= args.maximum_candidates:
        raise RuntimeError(
            "minimum_russian_candidates имеет недопустимое значение."
        )

    if not 1 <= args.minimum_selected_stories <= args.maximum_selected_stories <= 15:
        raise RuntimeError(
            "Требуется 1 <= minimum_selected_stories "
            "<= maximum_selected_stories <= 15."
        )


def pretty_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=False,
    ) + "\n"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def normalize_url(value: str) -> str:
    value = value.strip()
    parts = urlsplit(value)

    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        raise RuntimeError(f"Некорректный URL: {value}")

    host = parts.hostname.lower() if parts.hostname else ""

    try:
        port = parts.port
    except ValueError as exc:
        raise RuntimeError(f"Некорректный URL: {value}") from exc

    if port and not (
        (parts.scheme.lower() == "http" and port == 80)
        or (parts.scheme.lower() == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    else:
        netloc = host

    clean_query: list[tuple[str, str]] = []
    for key, query_value in parse_qsl(parts.query, keep_blank_values=True):
        key_lower = key.lower()
        if key_lower.startswith("utm_") or key_lower in TRACKING_QUERY_KEYS:
            continue
        clean_query.append((key, query_value))

    clean_query.sort()
    path = parts.path.rstrip("/") or "/"

    return urlunsplit(
        (
            parts.scheme.lower(),
            netloc,
            path,
            urlencode(clean_query, doseq=True),
            "",
        )
    )


def archive_source_urls(archive: dict[str, Any]) -> set[str]:
    normalized: set[str] = set()

    for item in archive.get("items", []):
        if not isinstance(item, dict):
            continue

        for source_url in item.get("source_urls", []):
            if not isinstance(source_url, str) or not source_url.strip():
                continue
            try:
                normalized.add(normalize_url(source_url))
            except RuntimeError:
                continue

    return normalized


def latest_archive_date(archive: dict[str, Any]) -> str | None:
    values: list[str] = []

    for item in archive.get("items", []):
        value = item.get("date") if isinstance(item, dict) else None
        if not isinstance(value, str):
            continue
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            continue
        values.append(parsed.isoformat())

    return max(values) if values else None


def build_prompt(template: str, replacements: dict[str, str]) -> str:
    prompt = template

    for key, value in replacements.items():
        prompt = prompt.replace(f"{{{{{key}}}}}", value)

    unresolved = sorted(set(re.findall(r"\{\{[A-Z0-9_]+\}\}", prompt)))
    if unresolved:
        raise RuntimeError(
            "В промпте остались неподставленные переменные: "
            + ", ".join(unresolved)
        )

    return prompt


def planned_published_datetime(
    publication_date: date,
    config: dict[str, Any],
) -> datetime:
    timezone_name = str(config["timezone"])
    publication_hour = int(config["publication_hour"])

    if not 0 <= publication_hour <= 23:
        raise RuntimeError("publication_hour должен быть в диапазоне 0..23.")

    return datetime.combine(
        publication_date,
        time(hour=publication_hour),
        tzinfo=ZoneInfo(timezone_name),
    )


def expected_published_at(
    publication_date: date,
    config: dict[str, Any],
) -> str:
    return planned_published_datetime(publication_date, config).isoformat(
        timespec="seconds"
    )


def parse_aware_datetime(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError(f"{label} имеет некорректный ISO timestamp: {value!r}.") from exc
    if parsed.tzinfo is None:
        raise RuntimeError(f"{label} должен содержать часовой пояс.")
    return parsed


def latest_archive_published_at(
    archive: dict[str, Any],
    config: dict[str, Any],
) -> datetime | None:
    values: list[datetime] = []
    for item in archive.get("items", []):
        if not isinstance(item, dict):
            continue
        published_at = item.get("published_at")
        if isinstance(published_at, str) and published_at.strip():
            try:
                values.append(parse_aware_datetime(published_at, "archive.published_at"))
                continue
            except RuntimeError:
                pass
        raw_date = item.get("date")
        if isinstance(raw_date, str):
            try:
                values.append(
                    planned_published_datetime(date.fromisoformat(raw_date), config)
                )
            except ValueError:
                continue
    return max(values) if values else None


def sdk_version() -> str:
    try:
        return package_version("openai")
    except PackageNotFoundError:
        return "unknown"


def github_context() -> dict[str, str | None]:
    return {
        "repository": os.getenv("GITHUB_REPOSITORY"),
        "ref": os.getenv("GITHUB_REF"),
        "sha": os.getenv("GITHUB_SHA"),
        "run_id": os.getenv("GITHUB_RUN_ID"),
        "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
        "actor": os.getenv("GITHUB_ACTOR"),
    }


def sanitized_error(exc: Exception, api_key: str | None) -> str:
    message = f"{type(exc).__name__}: {exc}"
    if api_key:
        message = message.replace(api_key, "***")
    return message[:8000]


def to_plain_dict(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, (dict, list, str, int, float, bool)):
        return value
    return str(value)


def response_output_text(response: Any) -> str:
    return (getattr(response, "output_text", None) or "").strip()


def count_web_search_calls(response: Any) -> int:
    return sum(
        1
        for item in getattr(response, "output", []) or []
        if getattr(item, "type", None) == "web_search_call"
    )


def extract_consulted_sources(response: Any) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) != "web_search_call":
            continue

        action = getattr(item, "action", None)
        sources = getattr(action, "sources", None) if action is not None else None

        if sources is None:
            plain_item = to_plain_dict(item)
            if isinstance(plain_item, dict):
                plain_action = plain_item.get("action")
                if isinstance(plain_action, dict):
                    sources = plain_action.get("sources")

        if not isinstance(sources, Iterable) or isinstance(sources, (str, bytes, dict)):
            continue

        for source in sources:
            plain_source = to_plain_dict(source)
            if not isinstance(plain_source, dict):
                continue
            url = plain_source.get("url")
            key = str(url or plain_source)
            if key in seen:
                continue
            seen.add(key)
            collected.append(plain_source)

    return collected


def parse_json_response(response: Any, stage_name: str) -> dict[str, Any]:
    if getattr(response, "status", None) != "completed":
        raise RuntimeError(
            f"{stage_name}: Responses API не завершил ответ: "
            f"status={getattr(response, 'status', None)!r}, "
            f"error={to_plain_dict(getattr(response, 'error', None))!r}"
        )

    output_text = response_output_text(response)
    if not output_text:
        raise RuntimeError(f"{stage_name}: получен пустой output_text.")

    try:
        value = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{stage_name}: ответ не является корректным JSON: {exc}"
        ) from exc

    if not isinstance(value, dict):
        raise RuntimeError(f"{stage_name}: корневое значение должно быть объектом.")

    return value


def candidate_sources(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    primary = candidate.get("primary_source")
    if isinstance(primary, dict):
        result.append(primary)

    supporting = candidate.get("supporting_sources")
    if isinstance(supporting, list):
        result.extend(item for item in supporting if isinstance(item, dict))

    return result


def normalize_candidate_sources(candidates: list[Any]) -> dict[str, Any]:
    """Normalize repeated source URLs without discarding valid candidates.

    The research model can cite one article for several related candidates, or
    repeat a primary source in ``supporting_sources``. Reusing one URL across
    candidates is not itself a research error. This function removes only
    duplicates inside a single candidate and makes metadata for the same
    normalized URL deterministic across the complete pool.
    """
    canonical_by_url: dict[str, dict[str, Any]] = {}
    removed_supporting: list[dict[str, str]] = []
    canonicalized: list[dict[str, str]] = []
    owners_by_url: dict[str, list[str]] = {}

    # Prefer metadata from a primary source when the same URL also appears as
    # a supporting source elsewhere. The first primary occurrence wins.
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        primary = candidate.get("primary_source")
        if not isinstance(primary, dict):
            continue
        try:
            normalized = normalize_url(str(primary.get("url", "")))
        except RuntimeError:
            continue
        canonical_by_url.setdefault(normalized, copy.deepcopy(primary))

    for position, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, dict):
            continue

        candidate_id = str(candidate.get("id", "")) or f"candidate-{position}"
        local_urls: set[str] = set()

        primary = candidate.get("primary_source")
        if isinstance(primary, dict):
            try:
                normalized = normalize_url(str(primary.get("url", "")))
            except RuntimeError:
                normalized = None
            if normalized is not None:
                canonical = canonical_by_url.setdefault(
                    normalized, copy.deepcopy(primary)
                )
                if primary != canonical:
                    candidate["primary_source"] = copy.deepcopy(canonical)
                    canonicalized.append(
                        {
                            "candidate_id": candidate_id,
                            "role": "primary",
                            "url": normalized,
                        }
                    )
                local_urls.add(normalized)

        supporting = candidate.get("supporting_sources")
        if not isinstance(supporting, list):
            continue

        clean_supporting: list[Any] = []
        for source in supporting:
            if not isinstance(source, dict):
                clean_supporting.append(source)
                continue

            try:
                normalized = normalize_url(str(source.get("url", "")))
            except RuntimeError:
                clean_supporting.append(source)
                continue

            if normalized in local_urls:
                removed_supporting.append(
                    {
                        "candidate_id": candidate_id,
                        "url": normalized,
                    }
                )
                continue

            local_urls.add(normalized)
            canonical = canonical_by_url.setdefault(
                normalized, copy.deepcopy(source)
            )
            if source != canonical:
                canonicalized.append(
                    {
                        "candidate_id": candidate_id,
                        "role": "supporting",
                        "url": normalized,
                    }
                )
            clean_supporting.append(copy.deepcopy(canonical))

        candidate["supporting_sources"] = clean_supporting

    for position, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, dict):
            continue
        candidate_id = str(candidate.get("id", "")) or f"candidate-{position}"
        seen_for_candidate: set[str] = set()
        for source in candidate_sources(candidate):
            try:
                normalized = normalize_url(str(source.get("url", "")))
            except RuntimeError:
                continue
            if normalized in seen_for_candidate:
                continue
            seen_for_candidate.add(normalized)
            owners_by_url.setdefault(normalized, []).append(candidate_id)

    reused_urls = [
        {"url": url, "candidate_ids": list(dict.fromkeys(candidate_ids))}
        for url, candidate_ids in sorted(owners_by_url.items())
        if len(set(candidate_ids)) > 1
    ]

    return {
        "removed_supporting_duplicates": removed_supporting,
        "canonicalized_sources": canonicalized,
        "reused_urls": reused_urls,
    }


def expected_search_window(
    publication_date: date,
    archive: dict[str, Any],
    config: dict[str, Any],
) -> tuple[datetime, datetime]:
    end_at = planned_published_datetime(publication_date, config)
    latest_at = latest_archive_published_at(archive, config)
    if latest_at is None:
        return end_at - timedelta(days=1), end_at
    return min(latest_at, end_at), end_at

def resolve_research_input(value: str | None) -> Path | None:
    if value is None or not value.strip():
        return None

    candidate = (REPOSITORY_ROOT / value).resolve()
    allowed_root = (REPOSITORY_ROOT / "automation/fixtures/research").resolve()

    try:
        candidate.relative_to(allowed_root)
    except ValueError as exc:
        raise RuntimeError(
            "research_input должен находиться внутри automation/fixtures/research/."
        ) from exc

    if not candidate.is_file():
        raise RuntimeError(
            f"Не найден research_input: {candidate.relative_to(REPOSITORY_ROOT)}"
        )

    return candidate


def russian_gap_documented(research: dict[str, Any]) -> bool:
    coverage = research.get("coverage")
    if not isinstance(coverage, list):
        return False

    for item in coverage:
        if not isinstance(item, dict):
            continue
        area = str(item.get("area", "")).casefold()
        status = str(item.get("status", "")).casefold()
        notes = str(item.get("notes", "")).strip()
        if "россий" in area and status == "gap" and notes:
            return True

    return False


def sanitize_research_candidates(
    research: dict[str, Any],
    publication_date: date,
    archive: dict[str, Any],
    config: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    sanitized = copy.deepcopy(research)
    candidates = sanitized.get("candidates")

    if not isinstance(candidates, list):
        return sanitized, [], []

    start_at, end_at = expected_search_window(publication_date, archive, config)
    local_zone = ZoneInfo(str(config["timezone"]))
    start_date = start_at.astimezone(local_zone).date()
    end_date = end_at.astimezone(local_zone).date()
    kept: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    warnings: list[str] = []

    for raw_candidate in candidates:
        if not isinstance(raw_candidate, dict):
            kept.append(raw_candidate)
            continue

        candidate = copy.deepcopy(raw_candidate)
        candidate_id = str(candidate.get("id", "unknown"))
        raw_date = str(candidate.get("published_date", ""))

        candidate.setdefault("published_at", None)
        candidate.setdefault("time_precision", "date")
        candidate.setdefault(
            "topic", str(candidate.get("category") or "other")
        )
        candidate.setdefault(
            "event_type", str(candidate.get("category") or "other")
        )
        candidate.setdefault(
            "keywords",
            [
                value
                for value in (
                    str(candidate.get("organization", "")).strip(),
                    str(candidate.get("category", "")).strip(),
                )
                if value
            ]
            or ["ИИ"],
        )

        try:
            candidate_date = date.fromisoformat(raw_date)
        except ValueError:
            kept.append(candidate)
            continue

        is_in_window = False
        if (
            candidate.get("time_precision") == "datetime"
            and isinstance(candidate.get("published_at"), str)
            and str(candidate["published_at"]).strip()
        ):
            try:
                candidate_at = parse_aware_datetime(
                    str(candidate["published_at"]),
                    f"{candidate_id}.published_at",
                )
                is_in_window = start_at <= candidate_at <= end_at
                candidate["published_at"] = candidate_at.isoformat(
                    timespec="seconds"
                )
            except RuntimeError:
                is_in_window = False
        else:
            candidate["published_at"] = None
            candidate["time_precision"] = "date"
            is_in_window = start_date <= candidate_date <= end_date
            warnings.append(
                f"{candidate_id}: источник показывает дату без точного времени."
            )

        if not is_in_window:
            filtered.append(
                {
                    "id": candidate_id,
                    "title": candidate.get("title"),
                    "published_date": raw_date,
                    "published_at": candidate.get("published_at"),
                    "reason": (
                        "Публикация вне редакционного окна "
                        f"{start_at.isoformat()}..{end_at.isoformat()}."
                    ),
                }
            )
            continue

        kept.append(candidate)

    id_changes = normalize_candidate_ids(kept)
    source_changes = normalize_candidate_sources(kept)
    sanitized["candidates"] = kept

    if id_changes:
        warnings.append(
            "Нормализованы внутренние id кандидатов: "
            + ", ".join(
                f"{item['old_id'] or '<empty>'}->{item['new_id']}"
                for item in id_changes
            )
            + "."
        )

    removed_source_duplicates = source_changes[
        "removed_supporting_duplicates"
    ]
    canonicalized_sources = source_changes["canonicalized_sources"]
    reused_urls = source_changes["reused_urls"]

    if removed_source_duplicates:
        warnings.append(
            "Удалены повторные supporting_sources внутри кандидатов: "
            f"{len(removed_source_duplicates)}."
        )
    if canonicalized_sources:
        warnings.append(
            "Унифицированы метаданные одинаковых URL источников: "
            f"{len(canonicalized_sources)}."
        )
    if reused_urls:
        warnings.append(
            "Одинаковые источники используются несколькими кандидатами: "
            f"{len(reused_urls)}; это допустимо и будет проверено "
            "на редакторском этапе."
        )

    if filtered:
        warnings.append(
            f"Отфильтровано кандидатов вне временного окна: {len(filtered)}."
        )

    latest_at = latest_archive_published_at(archive, config)
    sanitized["search_window"] = {
        "start_at": start_at.isoformat(timespec="seconds"),
        "end_at": end_at.isoformat(timespec="seconds"),
        "latest_archive_at": (
            latest_at.isoformat(timespec="seconds") if latest_at else None
        ),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "latest_archive_date": latest_archive_date(archive),
    }

    return sanitized, filtered, warnings

def validate_research(
    research: dict[str, Any],
    publication_date: date,
    archive: dict[str, Any],
    config: dict[str, Any],
    target_candidates: int,
    target_russian_candidates: int,
    maximum_candidates: int,
    target_selected_stories: int,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    publication_date_text = publication_date.isoformat()

    if research.get("status") != "ok":
        error_message = str(research.get("error_message") or "").strip()
        errors.append(
            "Исследовательский этап вернул status=error: "
            + (error_message or "причина не указана")
        )
        return errors, warnings

    if research.get("error_message") is not None:
        errors.append("При research status=ok поле error_message должно быть null.")

    if research.get("publication_date") != publication_date_text:
        errors.append("Research publication_date не совпадает с датой запуска.")

    expected_start, expected_end = expected_search_window(
        publication_date,
        archive,
        config,
    )
    local_zone = ZoneInfo(str(config["timezone"]))
    expected_start_date = expected_start.astimezone(local_zone).date().isoformat()
    expected_end_date = expected_end.astimezone(local_zone).date().isoformat()
    expected_latest_at = latest_archive_published_at(archive, config)
    search_window = research.get("search_window")

    if not isinstance(search_window, dict):
        errors.append("search_window должен быть объектом.")
    else:
        expected_values = {
            "start_at": expected_start.isoformat(timespec="seconds"),
            "end_at": expected_end.isoformat(timespec="seconds"),
            "latest_archive_at": (
                expected_latest_at.isoformat(timespec="seconds")
                if expected_latest_at
                else None
            ),
            "start_date": expected_start_date,
            "end_date": expected_end_date,
            "latest_archive_date": latest_archive_date(archive),
        }
        for key, expected_value in expected_values.items():
            if search_window.get(key) != expected_value:
                errors.append(
                    f"search_window.{key} не совпадает: ожидалось "
                    f"{expected_value!r}."
                )

    coverage = research.get("coverage")
    if not isinstance(coverage, list) or len(coverage) < 9:
        errors.append("coverage должен содержать не менее девяти направлений.")
    else:
        areas = [str(item.get("area", "")).strip().casefold() for item in coverage]
        if any(not area for area in areas):
            errors.append("coverage содержит пустое название направления.")
        if len(set(areas)) != len(areas):
            errors.append("coverage содержит повторяющиеся направления.")

    candidates = research.get("candidates")
    if not isinstance(candidates, list):
        errors.append("candidates должен быть массивом.")
        return errors, warnings

    if len(candidates) > maximum_candidates:
        errors.append(
            f"Найдено {len(candidates)} кандидатов; максимум {maximum_candidates}."
        )

    if len(candidates) == 0:
        errors.append("После проверки свежести не осталось ни одного достойного кандидата.")
    elif len(candidates) < target_candidates:
        warnings.append(
            f"Целевой пул — {target_candidates} кандидатов, "
            f"но после проверки свежести осталось {len(candidates)}."
        )
    if 0 < len(candidates) < target_selected_stories:
        warnings.append(
            f"Кандидатов меньше обычной цели выпуска ({target_selected_stories}); "
            "разрешён короткий выпуск."
        )

    candidate_ids: list[str] = []
    source_owners: dict[str, list[str]] = {}
    publisher_counter: Counter[str] = Counter()
    organization_counter: Counter[str] = Counter()
    russian_count = 0
    archive_urls = archive_source_urls(archive)

    for index, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, dict):
            errors.append(f"candidates[{index}] должен быть объектом.")
            continue

        candidate_id = str(candidate.get("id", ""))
        candidate_ids.append(candidate_id)

        if candidate.get("geography") == "russia":
            russian_count += 1

        recommendation = candidate.get("recommendation")
        score = candidate.get("significance_score")
        if recommendation == "include" and isinstance(score, int) and score < 3:
            errors.append(
                f"{candidate_id}: recommendation include несовместим "
                f"с significance_score={score}."
            )

        if candidate.get("archive_status") == "update" and not str(
            candidate.get("archive_reason", "")
        ).strip():
            errors.append(f"{candidate_id}: update требует archive_reason.")

        organization = str(candidate.get("organization", "")).strip().casefold()
        if organization:
            organization_counter[organization] += 1

        primary = candidate.get("primary_source")
        primary_normalized: str | None = None
        if isinstance(primary, dict):
            publisher = str(primary.get("publisher", "")).strip().casefold()
            if publisher:
                publisher_counter[publisher] += 1
            try:
                primary_normalized = normalize_url(str(primary.get("url", "")))
            except RuntimeError as exc:
                errors.append(f"{candidate_id}: {exc}")

        try:
            candidate_date = date.fromisoformat(str(candidate.get("published_date")))
        except ValueError:
            errors.append(f"{candidate_id}: некорректный published_date.")
            candidate_date = None

        time_precision = candidate.get("time_precision")
        published_at = candidate.get("published_at")
        if time_precision == "datetime":
            if not isinstance(published_at, str) or not published_at.strip():
                errors.append(
                    f"{candidate_id}: time_precision=datetime требует published_at."
                )
            else:
                try:
                    candidate_at = parse_aware_datetime(
                        published_at,
                        f"{candidate_id}.published_at",
                    )
                    if not expected_start <= candidate_at <= expected_end:
                        errors.append(
                            f"{candidate_id}: published_at вне окна "
                            f"{expected_start.isoformat()}..{expected_end.isoformat()}."
                        )
                except RuntimeError as exc:
                    errors.append(str(exc))
        elif time_precision == "date":
            if published_at is not None:
                errors.append(
                    f"{candidate_id}: при time_precision=date published_at должен быть null."
                )
            if candidate_date is not None and not (
                date.fromisoformat(expected_start_date)
                <= candidate_date
                <= date.fromisoformat(expected_end_date)
            ):
                errors.append(f"{candidate_id}: published_date вне календарного окна.")
        else:
            errors.append(f"{candidate_id}: некорректный time_precision.")

        for field in ("topic", "event_type"):
            if not isinstance(candidate.get(field), str) or not candidate[field].strip():
                errors.append(f"{candidate_id}: поле {field} должно быть непустым.")
        keywords = candidate.get("keywords")
        if not isinstance(keywords, list) or not keywords:
            errors.append(f"{candidate_id}: keywords должен быть непустым массивом.")

        for source in candidate_sources(candidate):
            source_url = str(source.get("url", "")).strip()
            try:
                normalized = normalize_url(source_url)
            except RuntimeError as exc:
                errors.append(f"{candidate_id}: {exc}")
                continue

            owners = source_owners.setdefault(normalized, [])
            if candidate_id not in owners:
                owners.append(candidate_id)

        if (
            primary_normalized is not None
            and primary_normalized in archive_urls
            and candidate.get("archive_status") != "update"
        ):
            errors.append(
                f"{candidate_id}: основной URL уже присутствует в архиве, "
                "но кандидат не помечен как update."
            )

    reused_source_urls = [
        (url, owners)
        for url, owners in sorted(source_owners.items())
        if len(owners) > 1
    ]
    if reused_source_urls:
        preview = "; ".join(
            f"{url} ({', '.join(owners)})"
            for url, owners in reused_source_urls[:5]
        )
        suffix = "" if len(reused_source_urls) <= 5 else "; …"
        warnings.append(
            "URL используется в нескольких кандидатах: "
            + preview
            + suffix
        )

    if len(set(candidate_ids)) != len(candidate_ids):
        errors.append("Кандидаты содержат повторяющиеся id.")

    if russian_count < target_russian_candidates:
        if russian_gap_documented(research):
            warnings.append(
                f"Цель — {target_russian_candidates} российских кандидатов, "
                f"найдено {russian_count}; пробел явно зафиксирован в coverage."
            )
        else:
            errors.append(
                f"Найдено {russian_count} российских кандидатов при цели "
                f"{target_russian_candidates}, но российский пробел не "
                "зафиксирован в coverage."
            )

    overloaded_publishers = [
        f"{name} ({count})"
        for name, count in publisher_counter.items()
        if count > 3
    ]
    if overloaded_publishers:
        warnings.append(
            "Исследовательский пул перегружен одним издателем: "
            + ", ".join(sorted(overloaded_publishers))
        )

    overloaded_organizations = [
        f"{name} ({count})"
        for name, count in organization_counter.items()
        if count > 2
    ]
    if overloaded_organizations:
        warnings.append(
            "Исследовательский пул перегружен одной организацией: "
            + ", ".join(sorted(overloaded_organizations))
        )

    return errors, warnings

def validate_digest(
    digest: dict[str, Any],
    publication_date: date,
    config: dict[str, Any],
    archive: dict[str, Any],
    policy: dict[str, Any],
    allowed_sources: dict[str, dict[str, Any]],
    allowed_archive_reuse: set[str],
) -> tuple[list[str], ArticleHTMLValidator]:
    errors: list[str] = []
    publication_date_text = publication_date.isoformat()

    if digest.get("status") != "ok":
        errors.append(
            "Digest вернул status=error: "
            + str(digest.get("error_message") or "причина не указана")
        )
        return errors, ArticleHTMLValidator()

    if digest.get("error_message") is not None:
        errors.append("При digest status=ok поле error_message должно быть null.")

    if digest.get("date") != publication_date_text:
        errors.append("Поле date не совпадает с publication_date.")

    if digest.get("slug") != publication_date_text:
        errors.append("Поле slug не совпадает с publication_date.")

    expected_author = str(config["author"])
    if digest.get("author") != expected_author:
        errors.append(f"Поле author должно быть равно {expected_author!r}.")

    expected_timestamp = expected_published_at(publication_date, config)
    if digest.get("published_at") != expected_timestamp:
        errors.append(
            f"Поле published_at должно быть равно {expected_timestamp!r}."
        )

    expected_cover = str(config["image_filename_template"]).format(
        date=publication_date_text
    )
    if digest.get("cover_filename") != expected_cover:
        errors.append(
            f"Поле cover_filename должно быть равно {expected_cover!r}."
        )

    expected_title = (
        f"ИИ-Сводка на {publication_date.day} "
        f"{RUSSIAN_MONTHS[publication_date.month]} {publication_date.year}"
    )
    title = str(digest.get("title", "")).strip()
    if title != expected_title:
        errors.append(f"Поле title должно быть равно {expected_title!r}.")

    description = str(digest.get("description", "")).strip()
    if not 150 <= len(description) <= 300:
        errors.append("description должна содержать от 150 до 300 символов.")
    if "<" in description or ">" in description or re.search(r"https?://", description):
        errors.append("description не должна содержать HTML или ссылки.")

    topics = digest.get("topics")
    if not isinstance(topics, list):
        errors.append("topics должен быть массивом.")
    else:
        clean_topics = [str(topic).strip() for topic in topics]
        if not 5 <= len(clean_topics) <= 20:
            errors.append("topics должен содержать от 5 до 20 элементов.")
        if any(not topic for topic in clean_topics):
            errors.append("topics не должен содержать пустые элементы.")
        if len({topic.casefold() for topic in clean_topics}) != len(clean_topics):
            errors.append("topics не должен содержать дубли.")

    article_html = str(digest.get("article_html", "")).strip()
    if not article_html:
        errors.append("article_html не должен быть пустым.")
    if "```" in article_html or re.search(r"(?m)^\s{0,3}#{1,6}\s+", article_html):
        errors.append("article_html содержит Markdown.")

    html_validator = ArticleHTMLValidator()
    try:
        html_validator.feed(article_html)
        html_validator.close()
        html_validator.finish()
    except Exception as exc:
        html_validator.errors.append(f"Ошибка разбора article_html: {exc}")
    errors.extend(html_validator.errors)

    required_h2 = {"Мировые лидеры ИИ", "Что это значит"}
    missing_h2 = required_h2 - set(html_validator.h2_texts)
    if missing_h2:
        errors.append(
            "В article_html отсутствуют обязательные разделы: "
            + ", ".join(sorted(missing_h2))
        )

    normalized_article_links: set[str] = set()
    try:
        dzen_url = normalize_url(str(policy["dzen"]["url"]))
    except RuntimeError as exc:
        errors.append(f"Некорректный URL Дзена в editorial.json: {exc}")
        dzen_url = ""

    for href in html_validator.hrefs:
        try:
            normalized = normalize_url(href)
        except RuntimeError as exc:
            errors.append(f"Некорректная ссылка в article_html: {exc}")
            continue
        if normalized == dzen_url:
            continue
        normalized_article_links.add(normalized)

    sources = digest.get("sources")
    normalized_sources: set[str] = set()

    if not isinstance(sources, list) or not sources:
        errors.append("sources должен быть непустым массивом.")
    else:
        for index, source in enumerate(sources, start=1):
            if not isinstance(source, dict):
                errors.append(f"sources[{index}] должен быть объектом.")
                continue

            for key in ("title", "publisher", "url"):
                if not isinstance(source.get(key), str) or not source[key].strip():
                    errors.append(
                        f"sources[{index}].{key} должен быть непустой строкой."
                    )

            source_url = str(source.get("url", "")).strip()
            try:
                normalized = normalize_url(source_url)
            except RuntimeError as exc:
                errors.append(str(exc))
                continue

            if normalized in normalized_sources:
                errors.append(f"В sources повторяется URL: {source_url}")
            normalized_sources.add(normalized)

            allowed = allowed_sources.get(normalized)
            if allowed is None:
                errors.append(
                    f"Источник отсутствует в исследовательском пуле: {source_url}"
                )
            else:
                for key in ("title", "publisher", "url"):
                    if source.get(key) != allowed.get(key):
                        errors.append(
                            f"Источник {source_url}: поле {key} отличается "
                            "от исследовательского пула."
                        )

    missing_in_article = normalized_sources - normalized_article_links
    if missing_in_article:
        errors.append(
            "В article_html отсутствуют ссылки из sources: "
            + ", ".join(sorted(missing_in_article))
        )

    unlisted_article_links = normalized_article_links - normalized_sources
    if unlisted_article_links:
        errors.append(
            "В article_html есть ссылки, которых нет в sources: "
            + ", ".join(sorted(unlisted_article_links))
        )

    duplicates_from_archive = (
        normalized_sources & archive_source_urls(archive)
    ) - allowed_archive_reuse
    if duplicates_from_archive:
        errors.append(
            "Обнаружены URL, уже присутствующие в архиве без статуса update: "
            + ", ".join(sorted(duplicates_from_archive))
        )

    image_prompt = str(digest.get("image_prompt", "")).strip()
    if not image_prompt:
        errors.append("image_prompt не должен быть пустым.")
    if expected_title not in image_prompt:
        errors.append("image_prompt не содержит точный заголовок выпуска.")
    if expected_cover.casefold() in image_prompt.casefold():
        errors.append("image_prompt не должен содержать техническое имя файла.")

    required_image_sections = [
        "Изображение 16:9:",
        "Главные визуальные темы:",
        "Композиция:",
        "Стиль:",
    ]
    positions = [image_prompt.find(marker) for marker in required_image_sections]
    if any(position < 0 for position in positions):
        errors.append(
            "image_prompt должен содержать разделы: "
            + ", ".join(required_image_sections)
        )
    elif positions != sorted(positions):
        errors.append("Разделы image_prompt расположены в неправильном порядке.")

    return errors, html_validator



def normalize_digest_metadata(
    editorial: dict[str, Any],
    publication_date: date,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Replace deterministic publication metadata with values from site.json.

    The model is responsible for editorial content. It is not allowed to decide
    the canonical author, timestamp, slug, title, or output filename.
    """
    digest = editorial.get("digest")
    if not isinstance(digest, dict):
        return []

    publication_date_text = publication_date.isoformat()
    expected_title = (
        f"ИИ-Сводка на {publication_date.day} "
        f"{RUSSIAN_MONTHS[publication_date.month]} {publication_date.year}"
    )

    expected_values: dict[str, Any] = {
        "date": publication_date_text,
        "slug": publication_date_text,
        "title": expected_title,
        "published_at": expected_published_at(publication_date, config),
        "author": str(config["author"]),
        "cover_filename": str(config["image_filename_template"]).format(
            date=publication_date_text
        ),
    }

    changes: list[dict[str, Any]] = []

    for field, expected_value in expected_values.items():
        previous_value = digest.get(field)

        if previous_value != expected_value:
            changes.append(
                {
                    "field": field,
                    "model_value": previous_value,
                    "normalized_value": expected_value,
                }
            )

        digest[field] = expected_value

    return changes

def validate_editorial(
    editorial: dict[str, Any],
    research: dict[str, Any],
    publication_date: date,
    config: dict[str, Any],
    archive: dict[str, Any],
    policy: dict[str, Any],
    target_selected_stories: int,
    maximum_selected_stories: int,
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    warnings: list[str] = []

    if editorial.get("status") != "ok":
        errors.append(
            "Редакторский этап вернул status=error: "
            + str(editorial.get("error_message") or "причина не указана")
        )
        return errors, warnings, []

    if editorial.get("error_message") is not None:
        errors.append("При editorial status=ok error_message должен быть null.")

    candidates = research.get("candidates", [])
    candidate_map = {
        str(candidate.get("id")): candidate
        for candidate in candidates
        if isinstance(candidate, dict)
    }

    selected = editorial.get("selected_candidate_ids")
    excluded = editorial.get("excluded_candidate_ids")
    overrides = editorial.get("diversity_overrides")

    if not isinstance(selected, list):
        errors.append("selected_candidate_ids должен быть массивом.")
        return errors, warnings, []

    if not isinstance(excluded, list):
        errors.append("excluded_candidate_ids должен быть массивом.")
        excluded = []

    if not isinstance(overrides, list):
        errors.append("diversity_overrides должен быть массивом.")
        overrides = []

    if len(set(selected)) != len(selected):
        errors.append("selected_candidate_ids содержит дубли.")

    if len(set(excluded)) != len(excluded):
        errors.append("excluded_candidate_ids содержит дубли.")

    if set(selected) & set(excluded):
        errors.append("Один кандидат одновременно выбран и исключён.")

    unknown_selected = sorted(set(selected) - set(candidate_map))
    if unknown_selected:
        errors.append(
            "Выбраны неизвестные candidate ID: " + ", ".join(unknown_selected)
        )

    unknown_excluded = sorted(set(excluded) - set(candidate_map))
    if unknown_excluded:
        errors.append(
            "Исключены неизвестные candidate ID: " + ", ".join(unknown_excluded)
        )

    if set(selected) | set(excluded) != set(candidate_map):
        missing = sorted(set(candidate_map) - set(selected) - set(excluded))
        errors.append(
            "Не все кандидаты распределены между selected и excluded: "
            + ", ".join(missing)
        )

    if len(selected) == 0:
        errors.append("Редактор не выбрал ни одного достойного сюжета.")
    elif len(selected) > maximum_selected_stories:
        errors.append(
            f"Выбрано {len(selected)} сюжетов; максимум {maximum_selected_stories}."
        )
    elif len(selected) < target_selected_stories:
        warnings.append(
            f"Выбрано {len(selected)} сюжетов при обычной цели "
            f"{target_selected_stories}; формируется короткий выпуск."
        )

    selected_candidates = [
        candidate_map[item] for item in selected if item in candidate_map
    ]

    digest_for_order = editorial.get("digest")
    article_for_order = (
        str(digest_for_order.get("article_html", ""))
        if isinstance(digest_for_order, dict)
        else ""
    )
    ordered_candidates, order_errors = order_candidates_by_article_links(
        article_for_order,
        selected_candidates,
    )
    errors.extend(order_errors)
    if not order_errors:
        ordered_ids = [str(item.get("id", "")) for item in ordered_candidates]
        if ordered_ids != [str(item) for item in selected]:
            errors.append(
                "Порядок selected_candidate_ids не совпадает с порядком сюжетов "
                "в article_html."
            )

    for candidate in selected_candidates:
        if candidate.get("recommendation") == "exclude":
            errors.append(
                f"Выбран кандидат {candidate.get('id')} с recommendation exclude."
            )

    errors.extend(
        validate_diversity_overrides(selected_candidates, overrides, policy)
    )

    selected_world = sum(
        1 for item in selected_candidates if item.get("geography") == "world"
    )
    selected_russian = sum(
        1 for item in selected_candidates if item.get("geography") == "russia"
    )
    counts = policy["story_counts"]
    if selected_world < int(counts["world_target_minimum"]):
        warnings.append(
            f"Мировых сюжетов {selected_world}, редакционная цель — "
            f"{counts['world_target_minimum']}–{counts['world_target_maximum']}."
        )
    if selected_russian < int(counts["russian_target_minimum"]):
        warnings.append(
            f"Российских сюжетов {selected_russian}, редакционная цель — "
            f"{counts['russian_target_minimum']}–{counts['russian_target_maximum']}."
        )

    worthy_russian = [
        candidate
        for candidate in candidates
        if isinstance(candidate, dict)
        and candidate.get("geography") == "russia"
        and isinstance(candidate.get("significance_score"), int)
        and candidate["significance_score"] >= 3
        and candidate.get("recommendation") in {"include", "consider"}
    ]
    if worthy_russian and selected_russian == 0:
        errors.append(
            "В пуле есть достойные российские кандидаты, но ни один не выбран."
        )

    allowed_sources: dict[str, dict[str, Any]] = {}
    allowed_archive_reuse: set[str] = set()
    for candidate in selected_candidates:
        for source in candidate_sources(candidate):
            try:
                normalized = normalize_url(str(source.get("url", "")))
            except RuntimeError:
                continue
            allowed_sources[normalized] = source
            if candidate.get("archive_status") == "update":
                allowed_archive_reuse.add(normalized)

    digest = editorial.get("digest")
    if not isinstance(digest, dict):
        errors.append("editorial.digest должен быть объектом.")
        return errors, warnings, []

    digest_errors, html_validator = validate_digest(
        digest,
        publication_date,
        config,
        archive,
        policy,
        allowed_sources,
        allowed_archive_reuse,
    )
    errors.extend(digest_errors)

    policy_errors, policy_warnings, _analysis = validate_article_policy(
        str(digest.get("article_html", "")),
        selected_candidates,
        bool(digest.get("short_digest")),
        policy,
    )
    errors.extend(policy_errors)
    warnings.extend(policy_warnings)

    if len(html_validator.h3_texts) != len(selected):
        errors.append(
            f"Число сюжетных <h3> ({len(html_validator.h3_texts)}) "
            f"не равно числу selected_candidate_ids ({len(selected)})."
        )

    if selected_russian > 0 and "Российские лидеры ИИ" not in html_validator.h2_texts:
        errors.append(
            "Выбраны российские сюжеты, но отсутствует раздел "
            "«Российские лидеры ИИ»."
        )

    stories = build_stories(
        selected_candidates,
        str(digest.get("article_html", "")),
    )
    errors.extend(validate_stories(stories, selected_candidates))
    return errors, warnings, stories

def build_candidate_source_map(research: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    for candidate in research.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        for source in candidate_sources(candidate):
            try:
                normalized = normalize_url(str(source.get("url", "")))
            except RuntimeError:
                continue
            result[normalized] = source

    return result


def write_digest_files(
    output_dir: Path,
    editorial: dict[str, Any],
    stories: list[dict[str, Any]],
    run_info: dict[str, Any],
) -> None:
    digest = editorial["digest"]

    meta = {
        key: digest[key]
        for key in (
            "status",
            "error_message",
            "date",
            "slug",
            "title",
            "description",
            "published_at",
            "author",
            "cover_filename",
            "topics",
            "short_digest",
            "editorial_notes",
        )
    }

    selection = {
        "status": editorial["status"],
        "error_message": editorial["error_message"],
        "selected_candidate_ids": editorial["selected_candidate_ids"],
        "excluded_candidate_ids": editorial["excluded_candidate_ids"],
        "selection_summary": editorial["selection_summary"],
        "diversity_overrides": editorial["diversity_overrides"],
    }

    atomic_write(output_dir / "digest.json", pretty_json(digest))
    atomic_write(output_dir / "selection.json", pretty_json(selection))
    atomic_write(output_dir / "meta.json", pretty_json(meta))
    atomic_write(output_dir / "article.html", digest["article_html"].strip() + "\n")
    atomic_write(
        output_dir / "image-prompt.txt",
        digest["image_prompt"].strip() + "\n",
    )
    atomic_write(output_dir / "sources.json", pretty_json(digest["sources"]))
    atomic_write(output_dir / "stories.json", pretty_json(stories))
    atomic_write(output_dir / "run-info.json", pretty_json(run_info))


def stage_info(response: Any, web_search_calls: int = 0) -> dict[str, Any]:
    return {
        "response_id": getattr(response, "id", None),
        "response_status": getattr(response, "status", None),
        "model_returned": getattr(response, "model", None),
        "web_search_calls": web_search_calls,
        "usage": to_plain_dict(getattr(response, "usage", None)),
    }


def main() -> int:
    args = parse_args()
    validate_limits(args)

    publication_date = parse_publication_date(args.publication_date)
    publication_date_text = publication_date.isoformat()
    output_dir = PREVIEW_ROOT / publication_date_text

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    api_key = os.getenv("OPENAI_API_KEY")
    model = (os.getenv("OPENAI_TEXT_MODEL") or DEFAULT_MODEL).strip()
    request_id = os.getenv("DIGEST_REQUEST_ID")
    started_at = datetime.now(timezone.utc)

    run_info: dict[str, Any] = {
        "status": "running",
        "pipeline": (
            "editorial_from_saved_research"
            if args.research_input
            else "research_then_editorial"
        ),
        "request_id": request_id,
        "research_input": args.research_input,
        "warnings": [],
        "publication_date": publication_date_text,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": None,
        "model_requested": model,
        "openai_sdk_version": sdk_version(),
        "archive_items": 0,
        "limits": {
            "minimum_candidates": args.minimum_candidates,
            "minimum_russian_candidates": args.minimum_russian_candidates,
            "maximum_candidates": args.maximum_candidates,
            "minimum_selected_stories": args.minimum_selected_stories,
            "maximum_selected_stories": args.maximum_selected_stories,
        },
        "research": {
            "status": "pending",
            "prompt_sha256": None,
            "candidates_sha256": None,
            "settings": {
                "source": (
                    "saved_fixture"
                    if args.research_input
                    else "responses_api_web_search"
                ),
                "max_retries": 0,
                "reasoning_effort": "medium",
                "search_context_size": "high",
                "return_token_budget": "default",
                "max_output_tokens": 16000,
                "store": False,
            },
            "response": None,
            "error": None,
        },
        "editorial": {
            "status": "pending",
            "prompt_sha256": None,
            "editorial_sha256": None,
            "digest_sha256": None,
            "metadata_normalization": None,
            "policy_normalization": None,
            "settings": {
                "max_retries": 0,
                "reasoning_effort": "medium",
                "web_search": False,
                "max_output_tokens": 18000,
                "store": False,
            },
            "response": None,
            "error": None,
        },
        "total_usage": None,
        "github": github_context(),
        "error": None,
    }

    try:
        if not api_key:
            raise RuntimeError("Переменная окружения OPENAI_API_KEY не задана.")
        if not model:
            raise RuntimeError("OPENAI_TEXT_MODEL не должен быть пустым.")

        config = read_json(CONFIG_PATH)
        policy = read_policy(EDITORIAL_CONFIG_PATH)
        archive = read_json(ARCHIVE_PATH)
        research_template = read_text(RESEARCH_PROMPT_PATH)
        editorial_template = read_text(EDITORIAL_PROMPT_PATH)

        if not isinstance(config, dict):
            raise RuntimeError("automation/config/site.json должен содержать объект.")
        if not isinstance(archive, dict) or not isinstance(archive.get("items"), list):
            raise RuntimeError("automation/archive/index.json имеет неожиданную структуру.")

        run_info["archive_items"] = len(archive["items"])
        archive_context = pretty_json(archive).strip()
        policy_context = pretty_json(policy).strip()
        search_start_at, search_end_at = expected_search_window(
            publication_date, archive, config
        )

        research_prompt = build_prompt(
            research_template,
            {
                "CURRENT_DATE": publication_date_text,
                "ARCHIVE_CONTEXT": archive_context,
                "MINIMUM_CANDIDATES": str(args.minimum_candidates),
                "MINIMUM_RUSSIAN_CANDIDATES": str(
                    args.minimum_russian_candidates
                ),
                "MAXIMUM_CANDIDATES": str(args.maximum_candidates),
                "MINIMUM_SELECTED_STORIES": str(
                    args.minimum_selected_stories
                ),
                "SEARCH_WINDOW_START_AT": search_start_at.isoformat(
                    timespec="seconds"
                ),
                "SEARCH_WINDOW_END_AT": search_end_at.isoformat(
                    timespec="seconds"
                ),
                "EDITORIAL_POLICY_CONTEXT": policy_context,
            },
        )

        run_info["research"]["prompt_sha256"] = sha256_text(research_prompt)
        atomic_write(
            output_dir / "research-prompt-input.txt",
            research_prompt.rstrip() + "\n",
        )

        client = OpenAI(
            api_key=api_key,
            timeout=1200.0,
            max_retries=0,
        )

        research_input_path = resolve_research_input(args.research_input)
        research_calls = 0

        if research_input_path is None:
            research_response = client.responses.create(
                model=model,
                input=research_prompt,
                tools=[
                    {
                        "type": "web_search",
                        "search_context_size": "high",
                        "return_token_budget": "default",
                    }
                ],
                tool_choice="required",
                include=["web_search_call.action.sources"],
                reasoning={"effort": "medium"},
                max_output_tokens=16000,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "daily_ai_research_candidates",
                        "strict": True,
                        "schema": RESEARCH_SCHEMA,
                    }
                },
                store=False,
            )

            research_calls = count_web_search_calls(research_response)
            run_info["research"]["response"] = stage_info(
                research_response,
                web_search_calls=research_calls,
            )

            if research_calls < 1:
                raise RuntimeError(
                    "Исследовательский ответ не содержит web_search_call."
                )

            consulted_sources = extract_consulted_sources(research_response)
            atomic_write(
                output_dir / "research-consulted-sources.json",
                pretty_json(consulted_sources),
            )

            research_raw = parse_json_response(research_response, "research")
        else:
            research_raw = read_json(research_input_path)
            if not isinstance(research_raw, dict):
                raise RuntimeError("research_input должен содержать JSON-объект.")

            run_info["research"]["response"] = {
                "response_id": None,
                "response_status": "reused",
                "model_returned": None,
                "web_search_calls": 0,
                "usage": None,
            }

            atomic_write(
                output_dir / "research-input-info.json",
                pretty_json(
                    {
                        "mode": "editorial_only",
                        "source_file": str(
                            research_input_path.relative_to(REPOSITORY_ROOT)
                        ),
                        "source_sha256": sha256_text(
                            pretty_json(research_raw)
                        ),
                    }
                ),
            )

        atomic_write(
            output_dir / "research-output-raw.json",
            pretty_json(research_raw),
        )

        research, filtered_candidates, sanitation_warnings = (
            sanitize_research_candidates(
                research_raw,
                publication_date,
                archive,
                config,
            )
        )

        atomic_write(output_dir / "candidates.json", pretty_json(research))
        atomic_write(
            output_dir / "research-filtered-out.json",
            pretty_json(filtered_candidates),
        )

        research_errors, research_warnings = validate_research(
            research,
            publication_date,
            archive,
            config,
            args.minimum_candidates,
            args.minimum_russian_candidates,
            args.maximum_candidates,
            args.minimum_selected_stories,
        )
        run_info["warnings"].extend(sanitation_warnings)
        run_info["warnings"].extend(research_warnings)

        if research_errors:
            raise RuntimeError(
                "Проверка research завершилась ошибками:\n- "
                + "\n- ".join(research_errors)
            )

        candidates_serialized = pretty_json(research)
        run_info["research"]["status"] = "ok"
        run_info["research"]["candidates_sha256"] = sha256_text(
            candidates_serialized
        )
        atomic_write(
            output_dir / "run-info.json",
            pretty_json(run_info),
        )

        editorial_prompt = build_prompt(
            editorial_template,
            {
                "CURRENT_DATE": publication_date_text,
                "ARCHIVE_CONTEXT": archive_context,
                "CANDIDATES_CONTEXT": candidates_serialized.strip(),
                "MINIMUM_SELECTED_STORIES": str(args.minimum_selected_stories),
                "MAXIMUM_SELECTED_STORIES": str(args.maximum_selected_stories),
                "EDITORIAL_POLICY_CONTEXT": policy_context,
            },
        )

        run_info["editorial"]["prompt_sha256"] = sha256_text(editorial_prompt)
        atomic_write(
            output_dir / "editorial-prompt-input.txt",
            editorial_prompt.rstrip() + "\n",
        )

        editorial_response = client.responses.create(
            model=model,
            input=editorial_prompt,
            reasoning={"effort": "medium"},
            max_output_tokens=18000,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "daily_ai_editorial_digest",
                    "strict": True,
                    "schema": EDITORIAL_SCHEMA,
                }
            },
            store=False,
        )

        run_info["editorial"]["response"] = stage_info(editorial_response)
        editorial = parse_json_response(editorial_response, "editorial")

        atomic_write(
            output_dir / "editorial-output-raw.json",
            pretty_json(editorial),
        )

        metadata_changes = normalize_digest_metadata(
            editorial,
            publication_date,
            config,
        )

        editorial.setdefault("diversity_overrides", [])
        digest = editorial.get("digest")
        if not isinstance(digest, dict):
            raise RuntimeError("editorial.digest должен быть объектом.")

        candidate_map = {
            str(candidate.get("id")): candidate
            for candidate in research.get("candidates", [])
            if isinstance(candidate, dict)
        }
        selected_candidates = [
            candidate_map[candidate_id]
            for candidate_id in editorial.get("selected_candidate_ids", [])
            if candidate_id in candidate_map
        ]

        ordered_candidates, order_errors = order_candidates_by_article_links(
            str(digest.get("article_html", "")),
            selected_candidates,
        )
        if order_errors:
            raise RuntimeError(
                "Не удалось сопоставить сюжеты статьи с кандидатами:\n- "
                + "\n- ".join(order_errors)
            )

        original_selected_ids = [
            str(item) for item in editorial.get("selected_candidate_ids", [])
        ]
        ordered_selected_ids = [
            str(item.get("id", "")) for item in ordered_candidates
        ]
        selected_candidates = ordered_candidates
        editorial["selected_candidate_ids"] = ordered_selected_ids

        normalized_html, short_digest, policy_changes = normalize_article_html(
            str(digest.get("article_html", "")),
            selected_candidates,
            policy,
        )
        if original_selected_ids != ordered_selected_ids:
            policy_changes.insert(
                0,
                {
                    "field": "selected_candidate_ids",
                    "model_value": original_selected_ids,
                    "normalized_value": ordered_selected_ids,
                },
            )
        digest["article_html"] = normalized_html
        digest["short_digest"] = short_digest
        digest["editorial_notes"] = build_editorial_notes(
            research,
            selected_candidates,
            policy,
        )

        for override in editorial.get("diversity_overrides", []):
            if not isinstance(override, dict):
                continue
            digest["editorial_notes"].append(
                {
                    "type": "diversity_override",
                    "area": str(override.get("type", "diversity")),
                    "message": (
                        f"{override.get('value')}: {override.get('reason')}"
                    ),
                }
            )

        run_info["editorial"]["metadata_normalization"] = {
            "status": "applied",
            "changed_fields": metadata_changes,
            "changed_count": len(metadata_changes),
        }
        run_info["editorial"]["policy_normalization"] = {
            "status": "applied",
            "changed_fields": policy_changes,
            "changed_count": len(policy_changes),
            "short_digest": short_digest,
            "editorial_notes": digest["editorial_notes"],
        }

        atomic_write(
            output_dir / "metadata-normalization.json",
            pretty_json(run_info["editorial"]["metadata_normalization"]),
        )
        atomic_write(
            output_dir / "policy-normalization.json",
            pretty_json(run_info["editorial"]["policy_normalization"]),
        )
        atomic_write(
            output_dir / "editorial-output.json",
            pretty_json(editorial),
        )

        editorial_errors, editorial_warnings, stories = validate_editorial(
            editorial,
            research,
            publication_date,
            config,
            archive,
            policy,
            args.minimum_selected_stories,
            args.maximum_selected_stories,
        )
        run_info["warnings"].extend(editorial_warnings)
        if editorial_errors:
            raise RuntimeError(
                "Проверка editorial завершилась ошибками:\n- "
                + "\n- ".join(editorial_errors)
            )

        editorial_serialized = pretty_json(editorial)
        digest_serialized = pretty_json(editorial["digest"])
        run_info["editorial"]["status"] = "ok"
        run_info["editorial"]["editorial_sha256"] = sha256_text(
            editorial_serialized
        )
        run_info["editorial"]["digest_sha256"] = sha256_text(digest_serialized)

        research_response_info = run_info["research"]["response"] or {}
        editorial_response_info = run_info["editorial"]["response"] or {}
        research_usage = research_response_info.get("usage") or {}
        editorial_usage = editorial_response_info.get("usage") or {}

        def token_value(usage: dict[str, Any], key: str) -> int:
            value = usage.get(key, 0)
            return int(value) if isinstance(value, (int, float)) else 0

        run_info["total_usage"] = {
            "input_tokens": token_value(research_usage, "input_tokens")
            + token_value(editorial_usage, "input_tokens"),
            "output_tokens": token_value(research_usage, "output_tokens")
            + token_value(editorial_usage, "output_tokens"),
            "total_tokens": token_value(research_usage, "total_tokens")
            + token_value(editorial_usage, "total_tokens"),
            "web_search_calls": research_calls,
        }

        run_info["status"] = "ok"
        run_info["finished_at"] = datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )

        write_digest_files(output_dir, editorial, stories, run_info)

        print(f"Preview создан: {output_dir.relative_to(REPOSITORY_ROOT)}")
        print(f"Кандидатов: {len(research['candidates'])}")
        print(
            "Российских кандидатов: "
            + str(
                sum(
                    1
                    for item in research["candidates"]
                    if item.get("geography") == "russia"
                )
            )
        )
        print(
            "Выбрано сюжетов: "
            + str(len(editorial["selected_candidate_ids"]))
        )
        print(f"Вызовов web_search: {research_calls}")
        if run_info["warnings"]:
            print("Предупреждения:")
            for warning in run_info["warnings"]:
                print(f"- {warning}")

        return 0

    except Exception as exc:
        error_message = sanitized_error(exc, api_key)
        run_info["status"] = "error"
        run_info["finished_at"] = datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )
        run_info["error"] = error_message

        if run_info["research"]["status"] != "ok":
            run_info["research"]["status"] = "error"
            run_info["research"]["error"] = error_message
        elif run_info["editorial"]["status"] != "ok":
            run_info["editorial"]["status"] = "error"
            run_info["editorial"]["error"] = error_message

        atomic_write(output_dir / "run-info.json", pretty_json(run_info))
        print(error_message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
