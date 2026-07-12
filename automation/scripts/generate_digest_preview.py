from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime, time, timezone
from html.parser import HTMLParser
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from openai import OpenAI


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPOSITORY_ROOT / "automation/config/site.json"
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
            "required": ["start_date", "end_date", "latest_archive_date"],
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
        "digest": DIGEST_SCHEMA,
    },
    "required": [
        "status",
        "error_message",
        "selected_candidate_ids",
        "excluded_candidate_ids",
        "selection_summary",
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


def expected_published_at(
    publication_date: date,
    config: dict[str, Any],
) -> str:
    timezone_name = str(config["timezone"])
    publication_hour = int(config["publication_hour"])

    if not 0 <= publication_hour <= 23:
        raise RuntimeError("publication_hour должен быть в диапазоне 0..23.")

    local_datetime = datetime.combine(
        publication_date,
        time(hour=publication_hour),
        tzinfo=ZoneInfo(timezone_name),
    )

    return local_datetime.isoformat(timespec="seconds")


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


def validate_research(
    research: dict[str, Any],
    publication_date: date,
    archive: dict[str, Any],
    minimum_candidates: int,
    minimum_russian_candidates: int,
    maximum_candidates: int,
) -> list[str]:
    errors: list[str] = []
    publication_date_text = publication_date.isoformat()

    if research.get("status") != "ok":
        error_message = str(research.get("error_message") or "").strip()
        errors.append(
            "Исследовательский этап вернул status=error: "
            + (error_message or "причина не указана")
        )
        return errors

    if research.get("error_message") is not None:
        errors.append("При research status=ok поле error_message должно быть null.")

    if research.get("publication_date") != publication_date_text:
        errors.append("Research publication_date не совпадает с датой запуска.")

    search_window = research.get("search_window")
    if not isinstance(search_window, dict):
        errors.append("search_window должен быть объектом.")
    else:
        if search_window.get("end_date") != publication_date_text:
            errors.append("search_window.end_date не совпадает с датой выпуска.")

        expected_latest = latest_archive_date(archive)
        if search_window.get("latest_archive_date") != expected_latest:
            errors.append(
                "search_window.latest_archive_date не совпадает с архивом: "
                f"ожидалось {expected_latest!r}."
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
        return errors

    if not minimum_candidates <= len(candidates) <= maximum_candidates:
        errors.append(
            f"Найдено {len(candidates)} кандидатов; требуется от "
            f"{minimum_candidates} до {maximum_candidates}."
        )

    candidate_ids: list[str] = []
    normalized_urls: set[str] = set()
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
        if isinstance(primary, dict):
            publisher = str(primary.get("publisher", "")).strip().casefold()
            if publisher:
                publisher_counter[publisher] += 1

        try:
            candidate_date = date.fromisoformat(str(candidate.get("published_date")))
            if candidate_date > publication_date:
                errors.append(
                    f"{candidate_id}: published_date находится после даты выпуска."
                )
        except ValueError:
            errors.append(f"{candidate_id}: некорректный published_date.")

        for source in candidate_sources(candidate):
            source_url = str(source.get("url", "")).strip()
            try:
                normalized = normalize_url(source_url)
            except RuntimeError as exc:
                errors.append(f"{candidate_id}: {exc}")
                continue

            if normalized in normalized_urls:
                errors.append(
                    f"URL повторяется между кандидатами или источниками: {source_url}"
                )
            normalized_urls.add(normalized)

            if normalized in archive_urls:
                errors.append(
                    f"{candidate_id}: URL уже присутствует в архиве: {source_url}"
                )

    if len(set(candidate_ids)) != len(candidate_ids):
        errors.append("Кандидаты содержат повторяющиеся id.")

    if russian_count < minimum_russian_candidates:
        errors.append(
            f"Найдено {russian_count} российских кандидатов; "
            f"для этого теста требуется минимум {minimum_russian_candidates}."
        )

    overloaded_publishers = [
        name for name, count in publisher_counter.items() if count > 3
    ]
    if overloaded_publishers:
        errors.append(
            "Более трёх кандидатов от одного издателя: "
            + ", ".join(sorted(overloaded_publishers))
        )

    overloaded_organizations = [
        name for name, count in organization_counter.items() if count > 2
    ]
    if overloaded_organizations:
        errors.append(
            "Более двух кандидатов от одной организации: "
            + ", ".join(sorted(overloaded_organizations))
        )

    return errors


def validate_digest(
    digest: dict[str, Any],
    publication_date: date,
    config: dict[str, Any],
    archive: dict[str, Any],
    allowed_sources: dict[str, dict[str, Any]],
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
    for href in html_validator.hrefs:
        try:
            normalized_article_links.add(normalize_url(href))
        except RuntimeError as exc:
            errors.append(f"Некорректная ссылка в article_html: {exc}")

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

    duplicates_from_archive = normalized_sources & archive_source_urls(archive)
    if duplicates_from_archive:
        errors.append(
            "Обнаружены URL, уже присутствующие в архиве: "
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


def validate_editorial(
    editorial: dict[str, Any],
    research: dict[str, Any],
    publication_date: date,
    config: dict[str, Any],
    archive: dict[str, Any],
    minimum_selected_stories: int,
    maximum_selected_stories: int,
) -> list[str]:
    errors: list[str] = []

    if editorial.get("status") != "ok":
        errors.append(
            "Редакторский этап вернул status=error: "
            + str(editorial.get("error_message") or "причина не указана")
        )
        return errors

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

    if not isinstance(selected, list):
        errors.append("selected_candidate_ids должен быть массивом.")
        return errors

    if not isinstance(excluded, list):
        errors.append("excluded_candidate_ids должен быть массивом.")
        excluded = []

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

    if not minimum_selected_stories <= len(selected) <= maximum_selected_stories:
        errors.append(
            f"Выбрано {len(selected)} сюжетов; требуется от "
            f"{minimum_selected_stories} до {maximum_selected_stories}."
        )

    selected_candidates = [candidate_map[item] for item in selected if item in candidate_map]

    for candidate in selected_candidates:
        if candidate.get("recommendation") == "exclude":
            errors.append(
                f"Выбран кандидат {candidate.get('id')} с recommendation exclude."
            )

    publisher_counter: Counter[str] = Counter()
    organization_counter: Counter[str] = Counter()
    selected_russian = 0

    for candidate in selected_candidates:
        primary = candidate.get("primary_source")
        if isinstance(primary, dict):
            publisher = str(primary.get("publisher", "")).strip().casefold()
            if publisher:
                publisher_counter[publisher] += 1

        organization = str(candidate.get("organization", "")).strip().casefold()
        if organization:
            organization_counter[organization] += 1

        if candidate.get("geography") == "russia":
            selected_russian += 1

    overloaded_publishers = [
        name for name, count in publisher_counter.items() if count > 2
    ]
    if overloaded_publishers:
        errors.append(
            "В выпуск выбрано более двух сюжетов одного издателя: "
            + ", ".join(sorted(overloaded_publishers))
        )

    overloaded_organizations = [
        name for name, count in organization_counter.items() if count > 2
    ]
    if overloaded_organizations:
        errors.append(
            "В выпуск выбрано более двух сюжетов одной организации: "
            + ", ".join(sorted(overloaded_organizations))
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
    for candidate in selected_candidates:
        for source in candidate_sources(candidate):
            try:
                normalized = normalize_url(str(source.get("url", "")))
            except RuntimeError:
                continue
            allowed_sources[normalized] = source

    digest = editorial.get("digest")
    if not isinstance(digest, dict):
        errors.append("editorial.digest должен быть объектом.")
        return errors

    digest_errors, html_validator = validate_digest(
        digest,
        publication_date,
        config,
        archive,
        allowed_sources,
    )
    errors.extend(digest_errors)

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

    return errors


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
        )
    }

    selection = {
        "status": editorial["status"],
        "error_message": editorial["error_message"],
        "selected_candidate_ids": editorial["selected_candidate_ids"],
        "excluded_candidate_ids": editorial["excluded_candidate_ids"],
        "selection_summary": editorial["selection_summary"],
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
        "pipeline": "research_then_editorial",
        "request_id": request_id,
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
        archive = read_json(ARCHIVE_PATH)
        research_template = read_text(RESEARCH_PROMPT_PATH)
        editorial_template = read_text(EDITORIAL_PROMPT_PATH)

        if not isinstance(config, dict):
            raise RuntimeError("automation/config/site.json должен содержать объект.")
        if not isinstance(archive, dict) or not isinstance(archive.get("items"), list):
            raise RuntimeError("automation/archive/index.json имеет неожиданную структуру.")

        run_info["archive_items"] = len(archive["items"])
        archive_context = pretty_json(archive).strip()

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

        research = parse_json_response(research_response, "research")
        atomic_write(output_dir / "candidates.json", pretty_json(research))

        research_errors = validate_research(
            research,
            publication_date,
            archive,
            args.minimum_candidates,
            args.minimum_russian_candidates,
            args.maximum_candidates,
        )
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
            output_dir / "editorial-output.json",
            pretty_json(editorial),
        )

        editorial_errors = validate_editorial(
            editorial,
            research,
            publication_date,
            config,
            archive,
            args.minimum_selected_stories,
            args.maximum_selected_stories,
        )
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

        research_usage = run_info["research"]["response"].get("usage") or {}
        editorial_usage = run_info["editorial"]["response"].get("usage") or {}

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

        write_digest_files(output_dir, editorial, run_info)

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
