from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
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
PROMPT_PATH = REPOSITORY_ROOT / "automation/prompts/daily_digest.md"
ARCHIVE_PATH = REPOSITORY_ROOT / "automation/archive/index.json"
PREVIEW_ROOT = REPOSITORY_ROOT / "automation/preview"

DEFAULT_MODEL = "gpt-5.6-terra"
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

DIGEST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {"type": "string", "enum": ["ok", "error"]},
        "error_message": {"type": ["string", "null"]},
        "date": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        "slug": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
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
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string", "minLength": 1},
                    "publisher": {"type": "string", "minLength": 1},
                    "url": {"type": "string", "minLength": 1},
                },
                "required": ["title", "publisher", "url"],
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
    ],
}


class ArticleHTMLValidator(HTMLParser):
    """Validate the deliberately small HTML subset accepted by the site builder."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.hrefs: list[str] = []
        self.errors: list[str] = []

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
                self.errors.append("Тег <a> должен содержать только непустой атрибут href.")
            else:
                self.hrefs.append(attrs[0][1].strip())
        elif attrs:
            self.errors.append(f"У тега <{tag}> не должно быть атрибутов.")

        self.stack.append(tag)

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
                f"Нарушена вложенность HTML: ожидался </{expected}>, получен </{tag}>."
            )

    def finish(self) -> None:
        if self.stack:
            self.errors.append(
                "Не закрыты HTML-теги: " + ", ".join(f"<{tag}>" for tag in self.stack)
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Создать безопасный preview выпуска ИИ-сводки через OpenAI Responses API."
    )
    parser.add_argument(
        "--publication-date",
        required=True,
        help="Дата выпуска в формате YYYY-MM-DD.",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Не найден обязательный файл: {path.relative_to(REPOSITORY_ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Некорректный JSON в {path.relative_to(REPOSITORY_ROOT)}: {exc}"
        ) from exc


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError(f"Не найден обязательный файл: {path.relative_to(REPOSITORY_ROOT)}") from exc


def parse_publication_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise RuntimeError("publication_date должна иметь формат YYYY-MM-DD.") from exc
    if parsed.isoformat() != value:
        raise RuntimeError("publication_date должна иметь строгий формат YYYY-MM-DD.")
    return parsed


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_url(value: str) -> str:
    value = value.strip()
    parts = urlsplit(value)
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        raise RuntimeError(f"Некорректный URL источника: {value}")

    host = parts.hostname.lower() if parts.hostname else ""
    try:
        port = parts.port
    except ValueError as exc:
        raise RuntimeError(f"Некорректный URL источника: {value}") from exc
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
                # Старый архив не должен ломать тест из-за одного исторического URL.
                continue
    return normalized


def build_prompt(template: str, publication_date: str, archive: dict[str, Any]) -> str:
    archive_context = pretty_json(archive).strip()
    prompt = template.replace("{{CURRENT_DATE}}", publication_date)
    prompt = prompt.replace("{{ARCHIVE_CONTEXT}}", archive_context)

    unresolved = sorted(set(re.findall(r"\{\{[A-Z0-9_]+\}\}", prompt)))
    if unresolved:
        raise RuntimeError(
            "В промпте остались неподставленные переменные: " + ", ".join(unresolved)
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


def validate_digest(
    digest: dict[str, Any],
    publication_date: date,
    config: dict[str, Any],
    archive: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    publication_date_text = publication_date.isoformat()

    status = digest.get("status")
    if status not in {"ok", "error"}:
        errors.append("Поле status должно быть равно ok или error.")
    if digest.get("date") != publication_date_text:
        errors.append("Поле date не совпадает с publication_date.")
    if digest.get("slug") != publication_date_text:
        errors.append("Поле slug не совпадает с publication_date.")

    expected_author = str(config["author"])
    if digest.get("author") != expected_author:
        errors.append(f"Поле author должно быть равно {expected_author!r}.")

    expected_timestamp = expected_published_at(publication_date, config)
    if digest.get("published_at") != expected_timestamp:
        errors.append(f"Поле published_at должно быть равно {expected_timestamp!r}.")

    if status == "error":
        error_message = str(digest.get("error_message") or "").strip()
        if not error_message:
            errors.append("При status=error поле error_message должно быть непустым.")
        else:
            errors.append(f"Модель не смогла подготовить выпуск: {error_message}")
        return errors

    if digest.get("error_message") is not None:
        errors.append("При status=ok поле error_message должно быть null.")

    expected_cover = str(config["image_filename_template"]).format(
        date=publication_date_text
    )
    if digest.get("cover_filename") != expected_cover:
        errors.append(f"Поле cover_filename должно быть равно {expected_cover!r}.")

    description = str(digest.get("description", "")).strip()
    if not 150 <= len(description) <= 300:
        errors.append("description должна содержать от 150 до 300 символов.")

    title = str(digest.get("title", "")).strip()
    expected_title = (
        f"ИИ-Сводка на {publication_date.day} "
        f"{RUSSIAN_MONTHS[publication_date.month]} {publication_date.year}"
    )
    if title != expected_title:
        errors.append(f"Поле title должно быть равно {expected_title!r}.")

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
    except Exception as exc:  # HTMLParser редко падает, но диагностика полезнее трассировки.
        html_validator.errors.append(f"Ошибка разбора article_html: {exc}")
    errors.extend(html_validator.errors)

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
                    errors.append(f"sources[{index}].{key} должен быть непустой строкой.")
            if not isinstance(source.get("url"), str) or not source["url"].strip():
                continue
            source_url = source["url"].strip()
            try:
                normalized = normalize_url(source_url)
            except RuntimeError as exc:
                errors.append(str(exc))
                continue
            if normalized in normalized_sources:
                errors.append(f"В sources повторяется URL: {source_url}")
            normalized_sources.add(normalized)

    normalized_article_links: set[str] = set()
    for href in html_validator.hrefs:
        try:
            normalized_article_links.add(normalize_url(href))
        except RuntimeError as exc:
            errors.append(f"Некорректная ссылка в article_html: {exc}")

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

    return errors


def count_web_search_calls(response: Any) -> int:
    return sum(
        1
        for item in getattr(response, "output", []) or []
        if getattr(item, "type", None) == "web_search_call"
    )


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


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def write_preview_files(
    output_dir: Path,
    digest: dict[str, Any],
    run_info: dict[str, Any],
) -> None:
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

    atomic_write(output_dir / "digest.json", pretty_json(digest))
    atomic_write(output_dir / "meta.json", pretty_json(meta))
    atomic_write(output_dir / "article.html", digest["article_html"].strip() + "\n")
    atomic_write(output_dir / "image-prompt.txt", digest["image_prompt"].strip() + "\n")
    atomic_write(output_dir / "sources.json", pretty_json(digest["sources"]))
    atomic_write(output_dir / "run-info.json", pretty_json(run_info))


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
    return message[:4000]


def main() -> int:
    args = parse_args()
    publication_date = parse_publication_date(args.publication_date)
    publication_date_text = publication_date.isoformat()
    output_dir = PREVIEW_ROOT / publication_date_text

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    api_key = os.getenv("OPENAI_API_KEY")
    model = (os.getenv("OPENAI_TEXT_MODEL") or DEFAULT_MODEL).strip()
    started_at = datetime.now(timezone.utc)

    run_info: dict[str, Any] = {
        "status": "running",
        "publication_date": publication_date_text,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": None,
        "model_requested": model,
        "model_returned": None,
        "openai_response_id": None,
        "openai_response_status": None,
        "openai_sdk_version": sdk_version(),
        "web_search_calls": 0,
        "archive_items": 0,
        "prompt_sha256": None,
        "digest_sha256": None,
        "usage": None,
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
        prompt_template = read_text(PROMPT_PATH)

        if not isinstance(config, dict):
            raise RuntimeError("automation/config/site.json должен содержать JSON-объект.")
        if not isinstance(archive, dict) or not isinstance(archive.get("items"), list):
            raise RuntimeError("automation/archive/index.json имеет неожиданную структуру.")

        prompt = build_prompt(prompt_template, publication_date_text, archive)
        run_info["archive_items"] = len(archive["items"])
        run_info["prompt_sha256"] = sha256_text(prompt)

        client = OpenAI(api_key=api_key, timeout=900.0, max_retries=2)
        response = client.responses.create(
            model=model,
            input=prompt,
            tools=[
                {
                    "type": "web_search",
                    "search_context_size": "high",
                }
            ],
            tool_choice="required",
            reasoning={"effort": "medium"},
            max_output_tokens=20000,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "daily_ai_digest",
                    "strict": True,
                    "schema": DIGEST_SCHEMA,
                }
            },
            store=False,
        )

        run_info["model_returned"] = getattr(response, "model", None)
        run_info["openai_response_id"] = getattr(response, "id", None)
        run_info["openai_response_status"] = getattr(response, "status", None)
        run_info["usage"] = to_plain_dict(getattr(response, "usage", None))
        run_info["web_search_calls"] = count_web_search_calls(response)

        if getattr(response, "status", None) != "completed":
            error_value = to_plain_dict(getattr(response, "error", None))
            raise RuntimeError(
                "OpenAI Responses API не завершил ответ: "
                f"status={getattr(response, 'status', None)!r}, error={error_value!r}"
            )
        if run_info["web_search_calls"] < 1:
            raise RuntimeError("Ответ не содержит web_search_call, хотя поиск был обязательным.")

        output_text = (getattr(response, "output_text", None) or "").strip()
        if not output_text:
            raise RuntimeError("OpenAI Responses API вернул пустой output_text.")

        try:
            digest = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Ответ модели не является корректным JSON: {exc}") from exc
        if not isinstance(digest, dict):
            raise RuntimeError("Корневое значение digest должно быть JSON-объектом.")

        validation_errors = validate_digest(digest, publication_date, config, archive)
        if validation_errors:
            raise RuntimeError(
                "Проверка digest завершилась ошибками:\n- " + "\n- ".join(validation_errors)
            )

        digest_serialized = pretty_json(digest)
        run_info["status"] = "ok"
        run_info["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        run_info["digest_sha256"] = sha256_text(digest_serialized)
        write_preview_files(output_dir, digest, run_info)

        print(f"Preview создан: {output_dir.relative_to(REPOSITORY_ROOT)}")
        print(f"Модель: {run_info['model_returned'] or model}")
        print(f"Вызовов web_search: {run_info['web_search_calls']}")
        return 0

    except Exception as exc:
        run_info["status"] = "error"
        run_info["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        run_info["error"] = sanitized_error(exc, api_key)
        atomic_write(output_dir / "run-info.json", pretty_json(run_info))
        print(run_info["error"], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
