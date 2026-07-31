from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
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
                    "area": {"type": "string", "enum": ["world", "russia", "cross"]},
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
    missing_world: int,
    missing_russia: int,
    maximum_web_search_calls: int,
    existing_candidates: list[Any],
    archive: dict[str, Any],
) -> str:
    replacements = {
        "PUBLICATION_DATE": publication_date,
        "SEARCH_WINDOW_START_AT": str(search_window.get("start_at", "")),
        "SEARCH_WINDOW_END_AT": str(search_window.get("end_at", "")),
        "MISSING_WORLD": str(missing_world),
        "MISSING_RUSSIA": str(missing_russia),
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


def count_web_search_calls(response: Any) -> int:
    return sum(
        1
        for item in getattr(response, "output", []) or []
        if getattr(item, "type", None) == "web_search_call"
    )


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


@dataclass
class AuditRequestResult:
    payload: dict[str, Any] | None
    metadata: dict[str, Any]
    output_text: str
    raw_response: Any
    validation_error: str | None

    def __iter__(self):
        # Keep tuple unpacking compatible for older callers and regression tests.
        yield self.payload
        yield self.metadata


def run_audit_request(
    *,
    api_key: str,
    model: str,
    prompt: str,
    maximum_web_search_calls: int,
) -> AuditRequestResult:
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
    web_search_calls = count_web_search_calls(response)
    metadata = {
        "response_id": getattr(response, "id", None),
        "status": getattr(response, "status", None),
        "model": getattr(response, "model", None),
        "web_search_calls": web_search_calls,
        "configured_web_search_limit": maximum_web_search_calls,
        "observed_web_search_calls": web_search_calls,
        "budget_overrun": web_search_calls > maximum_web_search_calls,
        "usage": response_to_plain(getattr(response, "usage", None)),
    }
    output_text = (getattr(response, "output_text", None) or "").strip()
    payload: Any = None
    validation_error: str | None = None

    if web_search_calls < 1:
        validation_error = "Coverage audit не выполнил ни одного web_search_call"
    elif getattr(response, "status", None) != "completed":
        validation_error = (
            "Coverage audit не завершён: "
            f"status={getattr(response, 'status', None)!r}"
        )
    elif not output_text:
        validation_error = "Coverage audit вернул пустой output_text"
    else:
        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError as exc:
            validation_error = f"Coverage audit вернул некорректный JSON: {exc}"
        if validation_error is None and not isinstance(payload, dict):
            validation_error = "Coverage audit должен вернуть JSON-объект"
        if validation_error is None:
            queries = payload.get("queries_used")
            if not isinstance(queries, list) or not queries:
                validation_error = "Coverage audit не заполнил queries_used"
            elif len(queries) > maximum_web_search_calls:
                validation_error = "queries_used превышает установленный лимит"

    result = AuditRequestResult(
        payload=payload if isinstance(payload, dict) else None,
        metadata=metadata,
        output_text=output_text,
        raw_response=response_to_plain(response),
        validation_error=validation_error,
    )
    if validation_error is None and metadata["budget_overrun"]:
        print(
            "::warning title=Coverage audit web-search budget::"
            "Responses API вернул больше web_search_call, чем настроено: "
            f"{web_search_calls}>{maximum_web_search_calls}. "
            "Ответ завершён и пригоден, поэтому публикация продолжается.",
            file=sys.stderr,
        )
    return result


def coerce_audit_result(value: Any) -> AuditRequestResult:
    if isinstance(value, AuditRequestResult):
        return value
    if isinstance(value, tuple) and len(value) == 2:
        payload, metadata = value
        if isinstance(payload, dict) and isinstance(metadata, dict):
            return AuditRequestResult(
                payload=payload,
                metadata=metadata,
                output_text=json.dumps(payload, ensure_ascii=False),
                raw_response=None,
                validation_error=None,
            )
    raise RuntimeError("Coverage audit вернул результат неожиданного типа")


def persist_audit_diagnostics(
    result: AuditRequestResult,
    output_dir: Path,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "coverage-audit-output.txt"
    response_path = output_dir / "coverage-audit-response.json"
    output_text = result.output_text
    output_path.write_text(
        output_text + ("\n" if output_text else ""),
        encoding="utf-8",
    )
    response_path.write_text(
        json.dumps(
            result.raw_response,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "api_output_path": str(output_path),
        "api_response_path": str(response_path),
    }


def rerun_editorial(
    *,
    publication_date: str,
    merged_research_path: Path,
    minimum_total: int,
    minimum_russia: int,
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
        "--minimum-russian-candidates",
        str(minimum_russia),
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


def completed_prior_audit(payload: Any) -> bool:
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        return False
    audit_state = payload.get("audit_state")
    if audit_state is not None and audit_state != "completed_usable":
        return False
    api = payload.get("api") or {}
    return (
        payload.get("web_search_performed") is True
        and isinstance(api, dict)
        and api.get("status") == "completed"
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
        if not (isinstance(item, dict) and item.get("type") == "low_news_volume")
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Довести итоговый выпуск до обязательного покрытия 5+2."
    )
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--publication-date", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--minimum-total", type=int, default=7)
    parser.add_argument("--minimum-world", type=int, default=5)
    parser.add_argument("--minimum-russia", type=int, default=2)
    parser.add_argument("--maximum-audit-web-search-calls", type=int, default=5)
    parser.add_argument("--maximum-candidates", type=int, default=20)
    parser.add_argument("--maximum-selected-stories", type=int, default=12)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

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
        "requirements": {
            "total": args.minimum_total,
            "world": args.minimum_world,
            "russia": args.minimum_russia,
        },
        "maximum_audit_web_search_calls": args.maximum_audit_web_search_calls,
        "audit_needed": False,
        "audit_state": "not_started",
        "validation_error": None,
        "web_search_performed": False,
        "prior_audit_reused": False,
        "publication_mode": None,
        "before": None,
        "after": None,
        "candidate_pool_before": None,
        "candidate_pool_after": None,
        "accepted_candidates": [],
        "rejected_candidates": [],
        "warnings": [],
        "api": None,
        "api_output_path": None,
        "api_response_path": None,
        "error_stage": None,
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

        args.report.parent.mkdir(parents=True, exist_ok=True)
        for source_name, target_name in (
            ("run-info.json", "coverage-audit-initial-run-info.json"),
            ("candidates.json", "coverage-audit-initial-candidates.json"),
            ("stories.json", "coverage-audit-initial-stories.json"),
            ("editorial-output.json", "coverage-audit-initial-editorial.json"),
            ("editorial-output-raw.json", "coverage-audit-initial-editorial-raw.json"),
        ):
            source_path = args.artifact_dir / source_name
            if source_path.is_file():
                (args.report.parent / target_name).write_bytes(source_path.read_bytes())

        before = coverage_summary(
            stories,
            minimum_total=args.minimum_total,
            minimum_world=args.minimum_world,
            minimum_russia=args.minimum_russia,
        )
        report["before"] = before
        report["candidate_pool_before"] = eligible_candidate_summary(
            research["candidates"]
        )
        if before["valid"] and artifact_mode == "complete":
            report["status"] = "ok"
            report["mode"] = "no_op"
            report["after"] = before
            report["candidate_pool_after"] = report["candidate_pool_before"]
            write_json(args.report, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        report["audit_needed"] = True
        candidate_pool = report["candidate_pool_before"]
        pool_has_required_geography = (
            candidate_pool["total"] >= args.minimum_total
            and candidate_pool["world"] >= args.minimum_world
            and candidate_pool["russia"] >= args.minimum_russia
        )
        additional_candidates: list[Any] = []
        prior_audit_complete = completed_prior_audit(prior_report)
        if not pool_has_required_geography and not prior_audit_complete:
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY не задан для coverage audit")
            template = PROMPT_PATH.read_text(encoding="utf-8")
            search_window = research.get("search_window")
            if not isinstance(search_window, dict):
                raise RuntimeError("candidates.json не содержит search_window")
            prompt = build_prompt(
                template,
                publication_date=args.publication_date,
                search_window=search_window,
                missing_world=max(0, args.minimum_world - candidate_pool["world"]),
                missing_russia=max(0, args.minimum_russia - candidate_pool["russia"]),
                maximum_web_search_calls=args.maximum_audit_web_search_calls,
                existing_candidates=research["candidates"],
                archive=archive,
            )
            prompt_path = args.report.parent / "coverage-audit-prompt.txt"
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(prompt.rstrip() + "\n", encoding="utf-8")
            audit_result = coerce_audit_result(
                run_audit_request(
                    api_key=api_key,
                    model=args.model,
                    prompt=prompt,
                    maximum_web_search_calls=args.maximum_audit_web_search_calls,
                )
            )
            api_metadata = audit_result.metadata
            report["web_search_performed"] = api_metadata.get("web_search_calls", 0) > 0
            report["api"] = api_metadata
            report.update(persist_audit_diagnostics(audit_result, args.report.parent))
            report["audit_state"] = "completed_unusable"

            validation_error = audit_result.validation_error
            if validation_error:
                report["validation_error"] = validation_error
                report["error_stage"] = "response_validation"
                raise RuntimeError(validation_error)

            audit_payload = audit_result.payload
            if not isinstance(audit_payload, dict):
                report["validation_error"] = (
                    "Coverage audit не вернул пригодный JSON-объект"
                )
                report["error_stage"] = "response_validation"
                raise RuntimeError(report["validation_error"])
            if api_metadata.get("budget_overrun"):
                report["warnings"].append(
                    "Responses API превысил настроенный счётчик web_search_call, "
                    "но завершённый валидный audit был сохранён и использован."
                )
            report["queries_used"] = audit_payload.get("queries_used", [])
            report["audit_notes"] = audit_payload.get("notes")
            if audit_payload.get("status") != "ok":
                report["validation_error"] = (
                    "Coverage audit вернул status=error: "
                    + str(audit_payload.get("error_message") or "причина не указана")
                )
                report["error_stage"] = "response_validation"
                raise RuntimeError(report["validation_error"])
            additional_candidates = audit_payload.get("candidates", [])
            if not isinstance(additional_candidates, list):
                report["validation_error"] = (
                    "Coverage audit candidates должен быть массивом"
                )
                report["error_stage"] = "response_validation"
                raise RuntimeError(report["validation_error"])
            report["audit_state"] = "completed_usable"
        elif not pool_has_required_geography and prior_audit_complete:
            report["audit_needed"] = True
            report["audit_state"] = "completed_usable"
            report["web_search_performed"] = True
            report["prior_audit_reused"] = True
            report["api"] = prior_report.get("api") if prior_report else None
            report["queries_used"] = (prior_report or {}).get("queries_used", [])
            report["audit_notes"] = (
                "Использован уже завершённый targeted audit из recovery artifact; "
                "повторный web search не выполнялся."
            )

        merged, accepted, rejected = merge_candidates(
            research,
            additional_candidates,
            maximum_candidates=args.maximum_candidates,
        )
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
        if pool_after["total"] < 1:
            raise RuntimeError(
                "После основного и targeted поиска не осталось ни одного достойного сюжета"
            )
        full_pool_available = (
            pool_after["total"] >= args.minimum_total
            and pool_after["world"] >= args.minimum_world
            and pool_after["russia"] >= args.minimum_russia
        )
        report["short_edition_candidate"] = not full_pool_available

        RUNTIME_RESEARCH_ROOT.mkdir(parents=True, exist_ok=True)
        PERSISTED_RESEARCH_ROOT.mkdir(parents=True, exist_ok=True)
        write_json(runtime_research_path, merged)
        write_json(persisted_research_path, merged)
        report["runtime_research_path"] = str(runtime_research_path)
        report["persisted_research_path"] = str(persisted_research_path)
        # Backward-compatible report key now points to the durable artifact copy.
        report["merged_research_path"] = str(persisted_research_path)
        rerun_editorial(
            publication_date=args.publication_date,
            merged_research_path=runtime_research_path,
            minimum_total=args.minimum_total,
            minimum_russia=args.minimum_russia,
            maximum_candidates=args.maximum_candidates,
            maximum_selected_stories=args.maximum_selected_stories,
        )
        rerun_stories = read_json(args.artifact_dir / "stories.json")
        if not isinstance(rerun_stories, list):
            raise RuntimeError("После editorial rerun stories.json должен быть массивом")
        after = coverage_summary(
            rerun_stories,
            minimum_total=args.minimum_total,
            minimum_world=args.minimum_world,
            minimum_russia=args.minimum_russia,
        )
        report["after"] = after
        if after["counts"]["total"] < 1:
            raise RuntimeError("Редакторский повтор не выбрал ни одного достойного сюжета")
        short_edition = not after["valid"]
        apply_short_edition_marker(args.artifact_dir, short_edition=short_edition)
        report["publication_mode"] = "short" if short_edition else "full"
        report["status"] = "ok"
        if report["prior_audit_reused"]:
            report["mode"] = "reused_completed_audit_and_editorial_rerun"
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
