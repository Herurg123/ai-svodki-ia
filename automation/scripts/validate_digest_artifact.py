#!/usr/bin/env python3
"""Validate a generated digest artifact without calling paid APIs.

The script checks the complete artifact contract, candidate/story ordering,
service-field hygiene, normalized metadata, image prompt structure and hashes.
It performs no network requests and writes only the requested JSON report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from validate_dzen_feed import ArticleInspector, META_FOOTNOTE, normalize_space, validate_article_html

REQUIRED_JSON_FILES = (
    "run-info.json",
    "candidates.json",
    "selection.json",
    "digest.json",
    "stories.json",
    "sources.json",
    "meta.json",
    "editorial-output-raw.json",
    "metadata-normalization.json",
    "editorial-output.json",
)
REQUIRED_META_FIELDS = ("date", "slug", "title", "published_at", "author", "cover_filename")
IMAGE_PROMPT_BLOCKS = (
    "Изображение 16:9:",
    "Главные визуальные темы:",
    "Композиция:",
    "Стиль:",
)
IMAGE_PROMPT_CONSTRAINTS = (
    "без логотипов",
    "без дополнительного текста",
    "без водяных знаков",
    "без узнаваемых лиц",
)
SECRET_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9_./-])(?:sk-[A-Za-z0-9]{20,}|sk-(?:proj|svcacct)-[A-Za-z0-9_-]{20,})\b"),
    re.compile(r"(?i)(?:api[_-]?key|password|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_./+-]{16,}"),
)
URL_RE = re.compile(r"https://[^\s\"'<>]+")


def issue(report: dict[str, Any], level: str, code: str, message: str, path: str | None = None) -> None:
    payload: dict[str, str] = {"code": code, "message": message}
    if path:
        payload["path"] = path
    report[level].append(payload)


def find_files(root: Path, name: str) -> list[Path]:
    return sorted(path for path in root.rglob(name) if path.is_file())


def choose_unique_file(root: Path, name: str, report: dict[str, Any], *, required: bool = True) -> Path | None:
    matches = find_files(root, name)
    if not matches:
        if required:
            issue(report, "errors", "required_file_missing", f"В artifact отсутствует {name}.", name)
        return None
    if len(matches) > 1:
        rendered = ", ".join(str(path.relative_to(root)) for path in matches)
        issue(report, "errors", "duplicate_artifact_file", f"Найдено несколько файлов {name}: {rendered}.", name)
        return None
    return matches[0]


def load_json(path: Path, root: Path, report: dict[str, Any]) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        issue(report, "errors", "json_utf8", f"JSON должен быть UTF-8: {exc}", str(path.relative_to(root)))
    except json.JSONDecodeError as exc:
        issue(report, "errors", "json_parse", f"Некорректный JSON: {exc}", str(path.relative_to(root)))
    except OSError as exc:
        issue(report, "errors", "json_read", f"Не удалось прочитать JSON: {exc}", str(path.relative_to(root)))
    return None


def json_list(payload: Any, key: str) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get(key), list):
        return payload[key]
    return []


def first_scalar(payload: Any, keys: Iterable[str]) -> Any | None:
    wanted = set(keys)
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in wanted and not isinstance(value, (dict, list)):
                return value
        for value in payload.values():
            found = first_scalar(value, wanted)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = first_scalar(value, wanted)
            if found is not None:
                return found
    return None


def recursive_urls(payload: Any) -> set[str]:
    urls: set[str] = set()
    if isinstance(payload, str):
        for match in URL_RE.findall(payload):
            urls.add(match.rstrip(".,);]"))
    elif isinstance(payload, dict):
        for value in payload.values():
            urls.update(recursive_urls(value))
    elif isinstance(payload, list):
        for value in payload:
            urls.update(recursive_urls(value))
    return urls


def candidate_id(candidate: Any) -> str | None:
    if not isinstance(candidate, dict):
        return None
    value = candidate.get("candidate_id", candidate.get("id"))
    return str(value) if value is not None else None


def story_id(story: Any) -> str | None:
    if not isinstance(story, dict):
        return None
    value = story.get("candidate_id")
    return str(value) if value is not None else None


def sanitize_visible_fields(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {
            key: sanitize_visible_fields(value)
            for key, value in payload.items()
            if key not in {"article_html", "image_prompt", "html"}
        }
    if isinstance(payload, list):
        return [sanitize_visible_fields(value) for value in payload]
    return payload


def contains_meta_star(payload: Any) -> bool:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return "Meta*" in serialized


def get_article_html(root: Path, digest: Any, editorial_output: Any, report: dict[str, Any]) -> str:
    article_files = find_files(root, "article.html")
    if len(article_files) > 1:
        issue(report, "errors", "duplicate_artifact_file", "Найдено несколько article.html.", "article.html")
        return ""
    if article_files:
        try:
            return article_files[0].read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            issue(report, "errors", "article_read", f"Не удалось прочитать article.html: {exc}", str(article_files[0].relative_to(root)))
            return ""
    for payload in (digest, editorial_output):
        if isinstance(payload, dict) and isinstance(payload.get("article_html"), str):
            return payload["article_html"]
    issue(report, "errors", "article_missing", "Нет article.html и article_html в нормализованном JSON.")
    return ""


def get_image_prompt(root: Path, digest: Any, editorial_output: Any) -> str:
    for name in ("image-prompt.txt", "image_prompt.txt"):
        matches = find_files(root, name)
        if len(matches) == 1:
            try:
                return matches[0].read_text(encoding="utf-8").strip()
            except (OSError, UnicodeDecodeError):
                pass
    for payload in (digest, editorial_output):
        if isinstance(payload, dict) and isinstance(payload.get("image_prompt"), str):
            return payload["image_prompt"].strip()
    return ""


def metadata_view(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    result: dict[str, Any] = {}
    for field in REQUIRED_META_FIELDS + ("short_digest", "editorial_notes"):
        if field in payload:
            result[field] = payload[field]
    nested = payload.get("meta")
    if isinstance(nested, dict):
        for field in REQUIRED_META_FIELDS + ("short_digest", "editorial_notes"):
            if field in nested and field not in result:
                result[field] = nested[field]
    return result


def note_types(notes: Any) -> set[str]:
    values: set[str] = set()
    if not isinstance(notes, list):
        return values
    for note in notes:
        if isinstance(note, str):
            values.add(note)
        elif isinstance(note, dict):
            for key in ("type", "code", "name"):
                if isinstance(note.get(key), str):
                    values.add(note[key])
                    break
    return values


def validate_image_prompt(prompt: str, title: str, report: dict[str, Any]) -> None:
    if not prompt:
        issue(report, "errors", "image_prompt_missing", "В artifact отсутствует image_prompt.")
        return
    positions = [prompt.find(block) for block in IMAGE_PROMPT_BLOCKS]
    for block, position in zip(IMAGE_PROMPT_BLOCKS, positions):
        if position < 0:
            issue(report, "errors", "image_prompt_block", f"В image_prompt отсутствует блок «{block}».")
    present_positions = [position for position in positions if position >= 0]
    if len(present_positions) == len(positions) and present_positions != sorted(present_positions):
        issue(report, "errors", "image_prompt_order", "Четыре блока image_prompt расположены в неправильном порядке.")
    if not prompt.lstrip().startswith("Изображение 16:9:"):
        issue(report, "errors", "image_prompt_prefix", "image_prompt должен начинаться с «Изображение 16:9:».")
    if title and title not in prompt:
        issue(report, "errors", "image_prompt_title", f"В image_prompt отсутствует точный заголовок: {title}.")
    lower = prompt.lower()
    for constraint in IMAGE_PROMPT_CONSTRAINTS:
        if constraint not in lower:
            issue(report, "errors", "image_prompt_constraint", f"В image_prompt отсутствует ограничение «{constraint}».")


def validate_story_mapping(
    article_html: str,
    candidates_payload: Any,
    selection_payload: Any,
    stories_payload: Any,
    report: dict[str, Any],
) -> None:
    candidates = json_list(candidates_payload, "candidates")
    stories = json_list(stories_payload, "stories")
    selected_raw = selection_payload.get("selected_candidate_ids") if isinstance(selection_payload, dict) else None
    if not isinstance(selected_raw, list):
        issue(report, "errors", "selected_ids_missing", "selection.json не содержит selected_candidate_ids[].")
        return
    selected_ids = [str(value) for value in selected_raw]
    story_ids = [value for value in (story_id(story) for story in stories) if value is not None]

    if len(story_ids) != len(stories):
        issue(report, "errors", "story_candidate_id", "Каждая запись stories.json должна содержать candidate_id.")
    if story_ids != selected_ids:
        issue(
            report,
            "errors",
            "story_order",
            f"Порядок candidate_id в stories.json не совпадает с selected_candidate_ids: {story_ids} != {selected_ids}.",
        )

    candidate_map: dict[str, set[str]] = {}
    for candidate in candidates:
        cid = candidate_id(candidate)
        if cid is None:
            issue(report, "errors", "candidate_id", "У кандидата отсутствует candidate_id/id.")
            continue
        if cid in candidate_map:
            issue(report, "errors", "duplicate_candidate_id", f"Повторяющийся candidate_id: {cid}.")
        candidate_map[cid] = recursive_urls(candidate)

    missing = [cid for cid in selected_ids if cid not in candidate_map]
    if missing:
        issue(report, "errors", "selected_candidate_missing", f"Выбранные кандидаты отсутствуют в candidates.json: {missing}.")

    inspector = ArticleInspector()
    inspector.feed(article_html)
    inspector.close()
    if len(inspector.stories) != len(selected_ids):
        issue(
            report,
            "errors",
            "html_story_count",
            f"Число сюжетов <h3> ({len(inspector.stories)}) не совпадает с selected_candidate_ids ({len(selected_ids)}).",
        )
        return

    resolved_ids: list[str] = []
    for block in inspector.stories:
        block_urls = set(block.links)
        if not block_urls:
            issue(report, "errors", "story_source_links", f"У сюжета «{block.headline}» нет цитируемых ссылок для сопоставления.")
            continue
        matches = [cid for cid in selected_ids if block_urls.intersection(candidate_map.get(cid, set()))]
        if len(matches) != 1:
            issue(
                report,
                "errors",
                "ambiguous_story_mapping",
                f"Сюжет «{block.headline}» должен однозначно сопоставляться по ссылкам с одним кандидатом; найдено: {matches}.",
            )
            continue
        resolved_ids.append(matches[0])

    if len(resolved_ids) == len(selected_ids) and resolved_ids != selected_ids:
        issue(
            report,
            "errors",
            "resolved_story_order",
            f"Порядок сюжетов по фактически процитированным ссылкам не совпадает с selection: {resolved_ids} != {selected_ids}.",
        )


def scan_secrets(root: Path, report: dict[str, Any], report_path: Path) -> None:
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.resolve() == report_path.resolve():
            continue
        try:
            if path.stat().st_size > 5_000_000:
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                issue(report, "errors", "secret_detected", "В artifact обнаружено значение, похожее на secret/API key.", str(path.relative_to(root)))
                break


def sha256_manifest(root: Path, report_path: Path) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.resolve() == report_path.resolve():
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        manifest.append(
            {
                "path": str(path.relative_to(root)),
                "size_bytes": path.stat().st_size,
                "sha256": digest.hexdigest(),
            }
        )
    return manifest


def validate_artifact(root: Path, report_path: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "validator": "digest-artifact-contract",
        "artifact_dir": str(root),
        "status": "error",
        "errors": [],
        "warnings": [],
        "manifest": [],
    }
    if not root.is_dir():
        issue(report, "errors", "artifact_missing", f"Каталог artifact не найден: {root}")
        return report

    paths: dict[str, Path] = {}
    payloads: dict[str, Any] = {}
    for name in REQUIRED_JSON_FILES:
        path = choose_unique_file(root, name, report)
        if path is not None:
            paths[name] = path
            payloads[name] = load_json(path, root, report)

    digest = payloads.get("digest.json")
    editorial_output = payloads.get("editorial-output.json")
    meta_payload = payloads.get("meta.json")
    article_html = get_article_html(root, digest, editorial_output, report)

    if article_html:
        html_report: dict[str, Any] = {"errors": [], "warnings": []}
        validate_article_html(
            article_html,
            report=html_report,
            item_label="artifact/article",
            strict_editorial=True,
        )
        report["errors"].extend(html_report["errors"])
        report["warnings"].extend(html_report["warnings"])

    run_info = payloads.get("run-info.json")
    mode = first_scalar(run_info, ("mode", "pipeline"))
    web_search_calls = first_scalar(run_info, ("web_search_calls", "web_search_call_count"))
    if mode in {"editorial_only", "editorial_from_saved_research"}:
        if web_search_calls is None:
            issue(report, "errors", "web_search_calls_missing", "Для editorial_only в run-info.json нужен web_search_calls.")
        else:
            try:
                calls = int(web_search_calls)
            except (TypeError, ValueError):
                issue(report, "errors", "web_search_calls_type", "web_search_calls должен быть целым числом.")
            else:
                if calls != 0:
                    issue(report, "errors", "web_search_calls_nonzero", f"В editorial_only web_search_calls должен быть 0, получено: {calls}.")

    if isinstance(run_info, dict):
        run_status = first_scalar(run_info, ("status",))
        if run_status not in {None, "ok", "success"}:
            issue(report, "errors", "run_status", f"run-info сообщает неуспешный статус: {run_status}.")

    if article_html and all(payloads.get(name) is not None for name in ("candidates.json", "selection.json", "stories.json")):
        validate_story_mapping(
            article_html,
            payloads["candidates.json"],
            payloads["selection.json"],
            payloads["stories.json"],
            report,
        )

    service_payload_names = (
        "stories.json",
        "sources.json",
        "meta.json",
        "candidates.json",
        "selection.json",
        "metadata-normalization.json",
    )
    for name in service_payload_names:
        payload = payloads.get(name)
        if payload is not None and contains_meta_star(payload):
            issue(report, "errors", "meta_star_service_field", f"Meta* запрещено в служебном файле {name}.", name)
    for name in ("digest.json", "editorial-output-raw.json", "editorial-output.json"):
        payload = payloads.get(name)
        if payload is not None and contains_meta_star(sanitize_visible_fields(payload)):
            issue(report, "errors", "meta_star_service_field", f"Meta* найдено вне article_html в {name}.", name)

    meta = metadata_view(meta_payload)
    if not meta:
        issue(report, "errors", "meta_shape", "meta.json должен быть объектом с техническими метаданными.")
    for field in REQUIRED_META_FIELDS:
        value = meta.get(field)
        if not isinstance(value, str) or not value.strip():
            issue(report, "errors", "meta_required_field", f"В meta.json отсутствует непустое поле {field}.", "meta.json")

    for source_name in ("digest.json", "editorial-output.json"):
        source_meta = metadata_view(payloads.get(source_name))
        for field in REQUIRED_META_FIELDS:
            if field in source_meta and field in meta and source_meta[field] != meta[field]:
                issue(
                    report,
                    "errors",
                    "metadata_mismatch",
                    f"Поле {field} в {source_name} не совпадает с meta.json: {source_meta[field]!r} != {meta[field]!r}.",
                    source_name,
                )

    stories = json_list(payloads.get("stories.json"), "stories")
    story_count = len(stories)
    short_digest = meta.get("short_digest")
    if short_digest is None:
        short_digest = first_scalar(digest, ("short_digest",))
    if not isinstance(short_digest, bool):
        issue(report, "errors", "short_digest_type", "short_digest должен быть явным boolean.")
    if story_count == 0:
        issue(report, "errors", "zero_stories", "Artifact со status=ok не может содержать 0 сюжетов.")
    elif 1 <= story_count <= 5:
        if short_digest is not True:
            issue(report, "errors", "short_digest_flag", "Для 1–5 сюжетов short_digest должен быть true.")
        notice = "<p>День на новости выдался слабым - поэтому коротко</p>"
        if article_html and not article_html.lstrip().startswith(notice):
            issue(report, "errors", "short_digest_notice", "Короткий выпуск должен начинаться с точного уведомления о слабом новостном дне.")
        if "low_news_volume" not in note_types(meta.get("editorial_notes")):
            issue(report, "errors", "low_news_volume_note", "Для короткого выпуска editorial_notes должен содержать low_news_volume.")
    elif story_count >= 6 and short_digest is True:
        issue(report, "errors", "short_digest_false", "Для 6 и более сюжетов short_digest не должен быть true.")

    cover_filename = str(meta.get("cover_filename", ""))
    if cover_filename and not cover_filename.lower().endswith(".png"):
        issue(report, "errors", "cover_extension", "cover_filename должен иметь расширение .png.")

    title = str(meta.get("title", ""))
    prompt = get_image_prompt(root, digest, editorial_output)
    validate_image_prompt(prompt, title, report)

    if article_html:
        visible = ArticleInspector()
        visible.feed(article_html)
        visible.close()
        if META_FOOTNOTE in visible.visible_text and "Meta*" not in visible.visible_text.replace(META_FOOTNOTE, ""):
            issue(report, "errors", "meta_footnote_orphan", "Сноска Meta не связана с корректным первым упоминанием Meta*.")

    scan_secrets(root, report, report_path)
    report["manifest"] = sha256_manifest(root, report_path)
    report["status"] = "ok" if not report["errors"] else "error"
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.artifact_dir.resolve()
    report_path = (args.report or (root / "artifact-validation.json")).resolve()
    report = validate_artifact(root, report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Digest artifact validation: {report['status']}")
    print(f"Errors: {len(report['errors'])}; warnings: {len(report['warnings'])}")
    for row in report["errors"]:
        suffix = f" [{row['path']}]" if "path" in row else ""
        print(f"ERROR {row['code']}{suffix}: {row['message']}")
    for row in report["warnings"]:
        suffix = f" [{row['path']}]" if "path" in row else ""
        print(f"WARN {row['code']}{suffix}: {row['message']}")
    print(f"Report: {report_path}")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
