from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

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
    ],
}
AUDIT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {"type": "string", "enum": ["ok", "error"]},
        "error_message": {"type": ["string", "null"]},
        "queries_used": {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "area": {
                        "type": "string",
                        "enum": ["world", "china", "russia", "cross"],
                    },
                    "query": {"type": "string", "minLength": 1},
                    "purpose": {"type": "string", "minLength": 1},
                },
                "required": ["area", "query", "purpose"],
            },
        },
        "candidates": {
            "type": "array",
            "minItems": 0,
            "maxItems": 10,
            "items": AUDIT_CANDIDATE_SCHEMA,
        },
        "notes": {"type": "string", "minLength": 1},
    },
    "required": ["status", "error_message", "queries_used", "candidates", "notes"],
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
) -> str:
    replacements = {
        "PUBLICATION_DATE": publication_date,
        "SEARCH_WINDOW_START_AT": str(search_window.get("start_at", "")),
        "SEARCH_WINDOW_END_AT": str(search_window.get("end_at", "")),
        "MISSING_TOTAL": str(missing_total),
        "MAX_WEB_SEARCH_CALLS": str(maximum_web_search_calls),
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


def response_to_plain(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, (dict, list, str, int, float, bool)):
        return value
    return str(value)


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
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) != "web_search_call":
            continue
        status = str(getattr(item, "status", None) or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        call_items.append(
            {
                "id": getattr(item, "id", None),
                "status": status,
            }
        )

    completed_calls = status_counts.get("completed", 0)
    total_items = len(call_items)
    output_item_limit_exceeded = total_items > maximum_web_search_calls
    return {
        "response_id": getattr(response, "id", None),
        "status": getattr(response, "status", None),
        "model": getattr(response, "model", None),
        "configured_max_tool_calls": maximum_web_search_calls,
        # Compatibility with the first production hotfix for run 30602601828.
        "configured_web_search_limit": maximum_web_search_calls,
        "observed_web_search_calls": total_items,
        "budget_overrun": output_item_limit_exceeded,
        # Backward-compatible key: only completed searches count as performed.
        "web_search_calls": completed_calls,
        "web_search_calls_completed": completed_calls,
        "web_search_call_items_total": total_items,
        "web_search_call_statuses": status_counts,
        "web_search_call_items": call_items,
        "completed_call_limit_exceeded": (
            completed_calls > maximum_web_search_calls
        ),
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
        max_tool_calls=maximum_web_search_calls,
        include=["web_search_call.action.sources"],
        reasoning={"effort": "medium"},
        max_output_tokens=10000,
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
            "::warning title=Coverage audit web-search budget::"
            "Responses API вернул больше web_search_call, чем настроено: "
            f"{metadata['web_search_call_items_total']}>"
            f"{maximum_web_search_calls}. Ответ сохранён для диагностики; "
            "пригодный короткий выпуск не блокируется.",
            file=sys.stderr,
        )
    if metadata["web_search_call_items_total"] < 1:
        raise CoverageAuditResponseError(
            "Coverage audit не вернул ни одного web_search_call",
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
    queries = payload.get("queries_used")
    if not isinstance(queries, list) or not queries:
        raise CoverageAuditResponseError(
            "Coverage audit не заполнил queries_used",
            metadata,
        )
    if len(queries) > maximum_web_search_calls:
        raise CoverageAuditResponseError(
            "queries_used превышает установленный лимит",
            metadata,
        )
    return payload, metadata


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
    parser.add_argument("--maximum-audit-web-search-calls", type=int, default=5)
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
        "audit_failure_blocks_publication": False,
        "maximum_audit_web_search_calls": args.maximum_audit_web_search_calls,
        "audit_needed": False,
        "web_search_requested": False,
        "web_search_performed": False,
        "prior_audit_reused": False,
        "audit_error": None,
        "publication_mode": None,
        "before": None,
        "after": None,
        "candidate_pool_before": None,
        "candidate_pool_after": None,
        "accepted_candidates": [],
        "rejected_candidates": [],
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

        if (
            artifact_mode == "complete"
            and before["publication_allowed"]
            and before["usual_target_met"]
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

        report["audit_needed"] = candidate_pool["total"] < args.usual_total
        additional_candidates: list[Any] = []
        prior_attempted = prior_audit_attempted(prior_report)
        if report["audit_needed"] and not prior_attempted:
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
            if not api_key:
                report["audit_error"] = (
                    "OPENAI_API_KEY не задан для необязательного coverage audit"
                )
            else:
                template = PROMPT_PATH.read_text(encoding="utf-8")
                search_window = research.get("search_window")
                if not isinstance(search_window, dict):
                    raise RuntimeError("candidates.json не содержит search_window")
                prompt = build_prompt(
                    template,
                    publication_date=args.publication_date,
                    search_window=search_window,
                    missing_total=max(0, args.usual_total - candidate_pool["total"]),
                    maximum_web_search_calls=args.maximum_audit_web_search_calls,
                    existing_candidates=research["candidates"],
                    archive=archive,
                )
                prompt_path = args.report.parent / "coverage-audit-prompt.txt"
                prompt_path.parent.mkdir(parents=True, exist_ok=True)
                prompt_path.write_text(prompt.rstrip() + "\n", encoding="utf-8")
                report["web_search_requested"] = True
                try:
                    audit_payload, api_metadata = run_audit_request(
                        api_key=api_key,
                        model=args.model,
                        prompt=prompt,
                        maximum_web_search_calls=(
                            args.maximum_audit_web_search_calls
                        ),
                    )
                except CoverageAuditResponseError as exc:
                    report["api"] = exc.metadata
                    report["web_search_performed"] = (
                        exc.metadata.get("web_search_call_items_total", 0) > 0
                    )
                    report["audit_error"] = (
                        f"{type(exc).__name__}: {exc}"
                    )
                except Exception as exc:
                    report["audit_error"] = (
                        f"{type(exc).__name__}: {exc}"
                    )
                else:
                    report["api"] = api_metadata
                    report["web_search_performed"] = (
                        api_metadata.get("web_search_call_items_total", 0) > 0
                    )
                    report["queries_used"] = audit_payload.get("queries_used", [])
                    report["audit_notes"] = audit_payload.get("notes")
                    if (
                        api_metadata.get("completed_call_limit_exceeded")
                        or api_metadata.get("output_item_limit_exceeded")
                    ):
                        audit_warning = (
                            "Ответ API содержит больше web_search_call items, "
                            "чем настроенный max_tool_calls; результат сохранён "
                            "для диагностики и не блокирует короткий выпуск."
                        )
                        report["audit_warning"] = audit_warning
                        report["warnings"].append(audit_warning)
                    if audit_payload.get("status") != "ok":
                        report["audit_error"] = (
                            "Coverage audit вернул status=error: "
                            + str(
                                audit_payload.get("error_message")
                                or "причина не указана"
                            )
                        )
                    else:
                        raw_candidates = audit_payload.get("candidates", [])
                        if isinstance(raw_candidates, list):
                            additional_candidates = raw_candidates
                        else:
                            report["audit_error"] = (
                                "Coverage audit candidates должен быть массивом"
                            )
        elif report["audit_needed"] and prior_attempted:
            report["prior_audit_reused"] = True
            report["web_search_requested"] = True
            report["web_search_performed"] = bool(
                (prior_report or {}).get("web_search_performed")
                or (prior_report or {}).get("api")
                or "Coverage audit превысил лимит web search"
                in str((prior_report or {}).get("error") or "")
            )
            report["api"] = prior_report.get("api") if prior_report else None
            report["queries_used"] = (prior_report or {}).get("queries_used", [])
            report["audit_notes"] = (
                "Использован отчёт уже выполненной попытки coverage audit из "
                "recovery artifact; повторный web search не выполнялся."
            )
            report["prior_audit_error"] = (prior_report or {}).get("error")

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
                "primary_source": item.get("primary_source"),
            }
            for item in accepted
        ]
        report["rejected_candidates"] = rejected
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
