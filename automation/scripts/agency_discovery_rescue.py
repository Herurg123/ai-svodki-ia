#!/usr/bin/env python3
"""One bounded missing-event agency discovery rescue after Primary Recall.

This is deliberately distinct from Coverage's ``fresh_agency_rescue``.  The
Coverage mechanism corroborates an event that is already present in the pool.
This module is allowed to discover a missing Reuters event only when the
mandatory ``major_agencies`` Primary direction completed but produced a proven
quality gap (raw=0 or accepted=0).

The stage reserves at most one Web Search operation.  Its state is persisted
before the call so recovery never spends a second discovery operation when the
outcome of the first call is uncertain.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from ensure_story_coverage_policy import (
    AUDIT_CANDIDATE_SCHEMA,
    AUDIT_REJECTION_SCHEMA,
    build_audit_api_metadata,
)
from story_coverage import (
    candidate_primary_url,
    merge_candidates,
    normalize_url,
    read_json,
    write_json,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_PREVIEW_ROOT = REPOSITORY_ROOT / "automation" / "preview" / "production-daily"
RUNTIME_RESEARCH_ROOT = (
    REPOSITORY_ROOT / "automation" / "fixtures" / "research" / ".runtime"
)

AGENCY_DISCOVERY_RESCUE_VERSION = 3
AGENCY_DISCOVERY_RESCUE_STRATEGY = "agency_discovery_rescue"
AGENCY_DISCOVERY_RESCUE_DIRECTION = "agency_discovery_rescue"
AGENCY_DISCOVERY_RESCUE_QUERY = (
    "latest AI chips infrastructure financing earnings business deals policy security"
)
AGENCY_DISCOVERY_ALLOWED_DOMAINS: tuple[str, ...] = ("reuters.com",)
AGENCY_DISCOVERY_SEARCH_CONTEXT_SIZE = "high"
MAXIMUM_SEARCH_OPERATIONS = 1
NAVIGATION_TOOL_ALLOWANCE = 3
MAXIMUM_TOOL_CALLS = MAXIMUM_SEARCH_OPERATIONS + NAVIGATION_TOOL_ALLOWANCE
MAXIMUM_RETURNED_CANDIDATES = 3
PRIMARY_SEARCH_OPERATIONS = 12
HYBRID_MAXIMUM_SEARCH_OPERATIONS = 4
COVERAGE_MAXIMUM_SEARCH_OPERATIONS = 7
PIPELINE_MAXIMUM_SEARCH_OPERATIONS = (
    PRIMARY_SEARCH_OPERATIONS
    + MAXIMUM_SEARCH_OPERATIONS
    + HYBRID_MAXIMUM_SEARCH_OPERATIONS
    + COVERAGE_MAXIMUM_SEARCH_OPERATIONS
)

_DIRECT_AGENCY_HOSTS = AGENCY_DISCOVERY_ALLOWED_DOMAINS

RESCUE_SCHEMA: dict[str, Any] = {
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
            "enum": [AGENCY_DISCOVERY_RESCUE_DIRECTION],
        },
        "candidates": {
            "type": "array",
            "minItems": 0,
            "maxItems": MAXIMUM_RETURNED_CANDIDATES,
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


class AgencyDiscoveryResponseError(RuntimeError):
    def __init__(self, message: str, metadata: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.metadata = metadata or {}


SearchRunner = Callable[..., tuple[dict[str, Any], dict[str, Any]]]


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _primary_report_path(
    artifact_dir: Path, output_root: Path, publication_date: str
) -> Path | None:
    local = artifact_dir / "primary-recall.json"
    if local.is_file():
        return local
    diagnostic = output_root / f"primary-recall-{publication_date}.json"
    return diagnostic if diagnostic.is_file() else None


def _major_agencies_row(primary_report: dict[str, Any]) -> dict[str, Any] | None:
    rows = primary_report.get("directions")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, dict) and row.get("direction_id") == "major_agencies":
            return row
    return None


def trigger_from_primary(
    primary_report: dict[str, Any],
) -> tuple[bool, str | None, dict[str, int | str | None]]:
    """Return a deterministic quality-gap trigger, independent of pool size."""
    row = _major_agencies_row(primary_report)
    if not isinstance(row, dict):
        return False, None, {
            "major_agencies_status": None,
            "major_agencies_raw_count": 0,
            "major_agencies_accepted_count": 0,
        }
    status = _clean(row.get("status"))
    raw = row.get("raw_candidates")
    raw_count = len(raw) if isinstance(raw, list) else 0
    accepted_count = int(row.get("accepted_count", 0) or 0)
    facts: dict[str, int | str | None] = {
        "major_agencies_status": status or None,
        "major_agencies_raw_count": raw_count,
        "major_agencies_accepted_count": accepted_count,
    }
    if status not in {"complete", "complete_with_gaps"}:
        return False, None, facts
    if raw_count == 0:
        return True, "major_agencies_raw_zero", facts
    if accepted_count == 0:
        return True, "major_agencies_accepted_zero", facts
    return False, None, facts


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
                "event_type": raw.get("event_type"),
                "recommendation": raw.get("recommendation"),
                "primary_url": primary.get("url") if isinstance(primary, dict) else None,
            }
        )
        if len(result) >= limit:
            break
    return result


def _compact_archive(archive: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    items = archive.get("items")
    if not isinstance(items, list):
        return []
    result: list[dict[str, Any]] = []
    for raw in items[:limit]:
        if not isinstance(raw, dict):
            continue
        stories = raw.get("stories")
        result.append(
            {
                "date": raw.get("date"),
                "source_urls": raw.get("source_urls", []),
                "stories": [
                    {
                        "headline": story.get("headline") or story.get("title"),
                        "organization": story.get("organization"),
                        "topic": story.get("topic"),
                        "source_urls": story.get("source_urls", []),
                    }
                    for story in (stories if isinstance(stories, list) else [])
                    if isinstance(story, dict)
                ],
            }
        )
    return result


def build_prompt(
    *,
    publication_date: str,
    search_window: dict[str, Any],
    existing_candidates: list[Any],
    archive: dict[str, Any],
) -> str:
    return f"""Ты — bounded agency DISCOVERY rescue редакции «ИИ-Сводки».

Дата выпуска: {publication_date}
Effective window: {search_window.get('start_at')} → {search_window.get('end_at')}
Strategy: {AGENCY_DISCOVERY_RESCUE_STRATEGY}

Mandatory Primary direction `major_agencies` технически завершён, но не дал
пригодного agency candidate. Это missing-event discovery, НЕ corroboration уже
известного события и НЕ квота Reuters.

Выполни РОВНО ОДНУ поисковую операцию Web Search. Второй search запрещён.
API domain filter задаёт отдельный Reuters-only provider route, чтобы rescue не
получал загрязнённый source-open ranked pool. Publisher в query не дублируется:
фактический query должен быть ТОЧНО:
`{AGENCY_DISCOVERY_RESCUE_QUERY}`

Query date-free. Не добавляй календарные даты, after:, before:, site:, OR-цепочки
или второй publisher sweep. Reuters routing здесь только шанс обнаружить
отсутствующее high-signal событие, а не причина автоматически публиковать его.

Возвращай только самостоятельные свежие AI events высокой новостной ценности,
для которых primary_source является ПРЯМЫМ Reuters (`reuters.com`) URL.
Syndication/агрегатор не считается прямым agency source. Событие и фактический
source timestamp обязаны попадать в effective window. Все обычные
verification/freshness/significance/archive правила сохраняются. Не дублируй уже
найденное событие под другим URL.

Уже найденные candidates:
{json.dumps(_compact_candidates(existing_candidates), ensure_ascii=False, indent=2)}

Недавний archive:
{json.dumps(_compact_archive(archive), ensure_ascii=False, indent=2)}

Верни до {MAXIMUM_RETURNED_CANDIDATES} candidates по штатной audit schema.
Для include/consider обязательны verification_status=verified и
freshness_status=new_event/material_update. Если достойного нового события нет,
верни пустой candidates и status=complete_with_gaps.
direction_id должен быть `{AGENCY_DISCOVERY_RESCUE_DIRECTION}`.
Верни только JSON."""


def _web_search_tool() -> dict[str, Any]:
    return {
        "type": "web_search",
        "search_context_size": AGENCY_DISCOVERY_SEARCH_CONTEXT_SIZE,
        "return_token_budget": "default",
        "filters": {"allowed_domains": list(AGENCY_DISCOVERY_ALLOWED_DOMAINS)},
    }


def run_search_request(
    *, api_key: str, model: str, prompt: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=1200.0, max_retries=2)
    response = client.responses.create(
        model=model,
        input=prompt,
        tools=[_web_search_tool()],
        tool_choice="required",
        max_tool_calls=MAXIMUM_TOOL_CALLS,
        include=["web_search_call.action.sources"],
        reasoning={"effort": "medium"},
        max_output_tokens=5000,
        text={
            "format": {
                "type": "json_schema",
                "name": "daily_ai_agency_discovery_rescue",
                "strict": True,
                "schema": RESCUE_SCHEMA,
            }
        },
        store=False,
    )
    metadata = build_audit_api_metadata(
        response, maximum_web_search_calls=MAXIMUM_SEARCH_OPERATIONS
    )
    metadata["configured_search_operations"] = MAXIMUM_SEARCH_OPERATIONS
    metadata["configured_total_tool_calls"] = MAXIMUM_TOOL_CALLS
    metadata["navigation_tool_allowance"] = NAVIGATION_TOOL_ALLOWANCE
    metadata["allowed_domains"] = list(AGENCY_DISCOVERY_ALLOWED_DOMAINS)
    metadata["search_context_size"] = AGENCY_DISCOVERY_SEARCH_CONTEXT_SIZE
    completed = int(metadata.get("web_search_calls_completed", 0) or 0)
    if completed != MAXIMUM_SEARCH_OPERATIONS:
        raise AgencyDiscoveryResponseError(
            "Agency discovery rescue должен завершить ровно один Web Search, "
            f"получено {completed}",
            metadata,
        )
    actual_queries = list(metadata.get("actual_queries") or [])
    if len(actual_queries) != 1:
        raise AgencyDiscoveryResponseError(
            "Agency discovery rescue должен выполнить один logical query, "
            f"получено {len(actual_queries)}",
            metadata,
        )
    if _clean(actual_queries[0]) != AGENCY_DISCOVERY_RESCUE_QUERY:
        raise AgencyDiscoveryResponseError(
            "Agency discovery rescue выполнил неожиданный query: "
            f"{actual_queries[0]!r}",
            metadata,
        )
    if getattr(response, "status", None) != "completed":
        raise AgencyDiscoveryResponseError(
            "Agency discovery rescue не завершён: "
            f"status={getattr(response, 'status', None)!r}",
            metadata,
        )
    output_text = (getattr(response, "output_text", None) or "").strip()
    if not output_text:
        raise AgencyDiscoveryResponseError(
            "Agency discovery rescue вернул пустой output_text", metadata
        )
    try:
        payload = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise AgencyDiscoveryResponseError(
            f"Agency discovery rescue вернул некорректный JSON: {exc}", metadata
        ) from exc
    if not isinstance(payload, dict):
        raise AgencyDiscoveryResponseError(
            "Agency discovery rescue должен вернуть JSON-объект", metadata
        )
    if payload.get("direction_id") != AGENCY_DISCOVERY_RESCUE_DIRECTION:
        raise AgencyDiscoveryResponseError(
            "Agency discovery rescue вернул чужой direction_id", metadata
        )
    if payload.get("status") not in {"complete", "complete_with_gaps"}:
        raise AgencyDiscoveryResponseError(
            "Agency discovery rescue вернул непригодный status="
            f"{payload.get('status')!r}",
            metadata,
        )
    return payload, metadata


def _report_paths(
    artifact_dir: Path, output_root: Path, publication_date: str
) -> tuple[Path, Path]:
    return (
        artifact_dir / "agency-discovery-rescue.json",
        output_root / f"agency-discovery-rescue-{publication_date}.json",
    )


def _persist_report(
    report: dict[str, Any],
    *,
    artifact_dir: Path,
    output_root: Path,
    publication_date: str,
) -> None:
    artifact_path, diagnostic_path = _report_paths(
        artifact_dir, output_root, publication_date
    )
    write_json(artifact_path, report)
    write_json(diagnostic_path, report)


def _load_prior_report(
    artifact_dir: Path, output_root: Path, publication_date: str
) -> dict[str, Any] | None:
    for path in _report_paths(artifact_dir, output_root, publication_date):
        if not path.is_file():
            continue
        try:
            value = read_json(path)
        except Exception:
            continue
        if (
            isinstance(value, dict)
            and value.get("publication_date") == publication_date
            and value.get("search_strategy") == AGENCY_DISCOVERY_RESCUE_STRATEGY
        ):
            return value
    return None


def _direct_agency_source(candidate: dict[str, Any]) -> bool:
    url = candidate_primary_url(candidate)
    if not url:
        return False
    host = (urlsplit(url).hostname or "").casefold().strip(".")
    return any(host == allowed or host.endswith("." + allowed) for allowed in _DIRECT_AGENCY_HOSTS)


def _event_identity(candidate: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _clean(candidate.get("organization")).casefold(),
        _clean(candidate.get("event_type")).casefold(),
        _clean(candidate.get("published_date")),
    )


def _same_existing_event(
    candidate: dict[str, Any], existing_candidates: list[Any]
) -> bool:
    identity = _event_identity(candidate)
    if not all(identity):
        return False
    return any(
        isinstance(raw, dict) and _event_identity(raw) == identity
        for raw in existing_candidates
    )


def _archive_urls(archive: dict[str, Any]) -> set[str]:
    result: set[str] = set()

    def add(raw: Any) -> None:
        if not isinstance(raw, str) or not raw.strip():
            return
        try:
            result.add(normalize_url(raw))
        except ValueError:
            return

    items = archive.get("items")
    if not isinstance(items, list):
        return result
    for item in items:
        if not isinstance(item, dict):
            continue
        for raw in item.get("source_urls") or []:
            add(raw)
        for story in item.get("stories") or []:
            if not isinstance(story, dict):
                continue
            for raw in story.get("source_urls") or []:
                add(raw)
            for source in story.get("sources") or []:
                if isinstance(source, dict):
                    add(source.get("url"))
    return result


def _base_report(
    *,
    publication_date: str,
    trigger_reason: str | None,
    trigger_facts: dict[str, int | str | None],
    candidate_pool_count: int,
) -> dict[str, Any]:
    return {
        "version": AGENCY_DISCOVERY_RESCUE_VERSION,
        "search_strategy": AGENCY_DISCOVERY_RESCUE_STRATEGY,
        "publication_date": publication_date,
        "triggered": trigger_reason is not None,
        "trigger_reason": trigger_reason,
        **trigger_facts,
        "candidate_pool_count_at_trigger": candidate_pool_count,
        "candidate_count_independent_trigger": True,
        "executed": False,
        "state": "not_triggered",
        "status": "complete",
        "query": AGENCY_DISCOVERY_RESCUE_QUERY,
        "allowed_domains": list(AGENCY_DISCOVERY_ALLOWED_DOMAINS),
        "required_direct_source_hosts": list(_DIRECT_AGENCY_HOSTS),
        "search_context_size": AGENCY_DISCOVERY_SEARCH_CONTEXT_SIZE,
        "search_operation_limit": MAXIMUM_SEARCH_OPERATIONS,
        "search_operation_reserved": 0,
        "search_operation_count_contribution": 0,
        "search_retry_allowed": False,
        "raw_count": 0,
        "validated_count": 0,
        "accepted_count": 0,
        "added_count": 0,
        "duplicate_count": 0,
        "archive_duplicate_count": 0,
        "rejections": [],
        "model_rejections": [],
        "api": {},
        "resumed": False,
        "recovered_from_artifact": False,
        "pipeline_search_budget": {
            "primary_maximum": PRIMARY_SEARCH_OPERATIONS,
            "agency_discovery_rescue_maximum": MAXIMUM_SEARCH_OPERATIONS,
            "hybrid_maximum": HYBRID_MAXIMUM_SEARCH_OPERATIONS,
            "coverage_maximum": COVERAGE_MAXIMUM_SEARCH_OPERATIONS,
            "maximum_total": PIPELINE_MAXIMUM_SEARCH_OPERATIONS,
        },
    }


def _metadata_completed_calls(metadata: dict[str, Any]) -> int:
    return int(metadata.get("web_search_calls_completed", 0) or 0)


def run_agency_discovery_rescue(
    *,
    artifact_dir: Path,
    archive_path: Path,
    publication_date: str,
    api_key: str,
    model: str,
    maximum_candidates: int = 20,
    search_runner: SearchRunner = run_search_request,
    output_root: Path = PRODUCTION_PREVIEW_ROOT,
) -> dict[str, Any]:
    """Run or resume the bounded discovery rescue without ever searching twice."""
    research = read_json(artifact_dir / "candidates.json")
    archive = read_json(archive_path)
    if not isinstance(research, dict) or not isinstance(research.get("candidates"), list):
        raise RuntimeError("Agency discovery rescue: candidates.json непригоден")
    if not isinstance(archive, dict):
        raise RuntimeError("Agency discovery rescue: archive должен быть объектом")

    primary_path = _primary_report_path(artifact_dir, output_root, publication_date)
    if primary_path is None:
        report = _base_report(
            publication_date=publication_date,
            trigger_reason=None,
            trigger_facts={
                "major_agencies_status": None,
                "major_agencies_raw_count": 0,
                "major_agencies_accepted_count": 0,
            },
            candidate_pool_count=len(research["candidates"]),
        )
        report["state"] = "diagnostics_missing"
        report["status"] = "complete_with_gaps"
        report["rejections"] = [
            {"reason_code": "primary_diagnostics_missing", "detail": "primary-recall.json отсутствует"}
        ]
        _persist_report(
            report,
            artifact_dir=artifact_dir,
            output_root=output_root,
            publication_date=publication_date,
        )
        return report

    primary_report = read_json(primary_path)
    if not isinstance(primary_report, dict):
        raise RuntimeError("Agency discovery rescue: primary report должен быть объектом")
    triggered, trigger_reason, trigger_facts = trigger_from_primary(primary_report)
    existing_candidates = [
        copy.deepcopy(item)
        for item in research.get("candidates", [])
        if isinstance(item, dict)
    ]
    prior = _load_prior_report(artifact_dir, output_root, publication_date)

    if isinstance(prior, dict):
        report = copy.deepcopy(prior)
        report["resumed"] = True
        report["recovered_from_artifact"] = True
        state = str(report.get("state") or "")
        if state in {
            "not_triggered",
            "completed",
            "completed_no_addition",
            "search_failed",
            "indeterminate_after_interruption",
            "diagnostics_missing",
        }:
            _persist_report(
                report,
                artifact_dir=artifact_dir,
                output_root=output_root,
                publication_date=publication_date,
            )
            return report
        if state == "search_started":
            report["state"] = "indeterminate_after_interruption"
            report["status"] = "complete_with_gaps"
            report["executed"] = True
            report["search_operation_reserved"] = 1
            report["search_operation_count_contribution"] = max(
                1, int(report.get("search_operation_count_contribution", 0) or 0)
            )
            report["rejections"] = list(report.get("rejections") or []) + [
                {
                    "reason_code": "search_outcome_indeterminate",
                    "detail": "search_started persisted without a saved response; automatic retry forbidden",
                }
            ]
            _persist_report(
                report,
                artifact_dir=artifact_dir,
                output_root=output_root,
                publication_date=publication_date,
            )
            return report
        if state not in {"search_completed", "merge_failed"}:
            report["state"] = "indeterminate_after_interruption"
            report["status"] = "complete_with_gaps"
            _persist_report(
                report,
                artifact_dir=artifact_dir,
                output_root=output_root,
                publication_date=publication_date,
            )
            return report
    else:
        report = _base_report(
            publication_date=publication_date,
            trigger_reason=trigger_reason,
            trigger_facts=trigger_facts,
            candidate_pool_count=len(existing_candidates),
        )
        if not triggered:
            _persist_report(
                report,
                artifact_dir=artifact_dir,
                output_root=output_root,
                publication_date=publication_date,
            )
            return report

        report.update(
            {
                "executed": True,
                "state": "search_started",
                "status": "complete_with_gaps",
                "search_operation_reserved": 1,
            }
        )
        _persist_report(
            report,
            artifact_dir=artifact_dir,
            output_root=output_root,
            publication_date=publication_date,
        )
        search_window = research.get("search_window")
        if not isinstance(search_window, dict):
            report["state"] = "search_failed"
            report["rejections"] = [
                {
                    "reason_code": "search_window_missing",
                    "detail": "candidates.json не содержит search_window",
                }
            ]
            _persist_report(
                report,
                artifact_dir=artifact_dir,
                output_root=output_root,
                publication_date=publication_date,
            )
            return report
        prompt = build_prompt(
            publication_date=publication_date,
            search_window=search_window,
            existing_candidates=existing_candidates,
            archive=archive,
        )
        try:
            payload, metadata = search_runner(
                api_key=api_key, model=model, prompt=prompt
            )
        except AgencyDiscoveryResponseError as exc:
            metadata = copy.deepcopy(exc.metadata)
            report["api"] = metadata
            report["search_operation_count_contribution"] = _metadata_completed_calls(metadata)
            report["state"] = "search_failed"
            report["status"] = "complete_with_gaps"
            report["rejections"] = [
                {"reason_code": "search_response_error", "detail": f"{type(exc).__name__}: {exc}"}
            ]
            _persist_report(
                report,
                artifact_dir=artifact_dir,
                output_root=output_root,
                publication_date=publication_date,
            )
            return report
        except Exception as exc:
            report["state"] = "search_failed"
            report["status"] = "complete_with_gaps"
            report["rejections"] = [
                {"reason_code": "search_transport_error", "detail": f"{type(exc).__name__}: {exc}"}
            ]
            _persist_report(
                report,
                artifact_dir=artifact_dir,
                output_root=output_root,
                publication_date=publication_date,
            )
            return report

        raw_candidates = payload.get("candidates")
        if not isinstance(raw_candidates, list):
            raw_candidates = []
        report.update(
            {
                "state": "search_completed",
                "status": (
                    "complete"
                    if payload.get("status") == "complete"
                    else "complete_with_gaps"
                ),
                "api": copy.deepcopy(metadata),
                "search_operation_count_contribution": _metadata_completed_calls(metadata),
                "raw_count": len(raw_candidates),
                "raw_candidates": copy.deepcopy(raw_candidates),
                "model_rejections": copy.deepcopy(payload.get("rejections") or []),
                "notes": payload.get("notes"),
            }
        )
        _persist_report(
            report,
            artifact_dir=artifact_dir,
            output_root=output_root,
            publication_date=publication_date,
        )

    raw_candidates = [
        copy.deepcopy(item)
        for item in report.get("raw_candidates", [])
        if isinstance(item, dict)
    ]
    current_research = read_json(artifact_dir / "candidates.json")
    if not isinstance(current_research, dict) or not isinstance(
        current_research.get("candidates"), list
    ):
        report["state"] = "merge_failed"
        report["status"] = "complete_with_gaps"
        report["rejections"] = list(report.get("rejections") or []) + [
            {"reason_code": "merge_input_invalid", "detail": "candidates.json непригоден для merge"}
        ]
        _persist_report(
            report,
            artifact_dir=artifact_dir,
            output_root=output_root,
            publication_date=publication_date,
        )
        return report

    existing_candidates = [
        copy.deepcopy(item)
        for item in current_research.get("candidates", [])
        if isinstance(item, dict)
    ]
    archive_urls = _archive_urls(archive)
    eligible: list[dict[str, Any]] = []
    rescue_rejections: list[dict[str, Any]] = []
    duplicate_count = 0
    archive_duplicate_count = 0
    for raw in raw_candidates:
        candidate = copy.deepcopy(raw)
        candidate["audit_direction"] = AGENCY_DISCOVERY_RESCUE_DIRECTION
        if not _direct_agency_source(candidate):
            rescue_rejections.append(
                {
                    "title": candidate.get("title"),
                    # Keep the historical reason code stable for old diagnostics consumers.
                    "reason_code": "non_direct_reuters_ap_source",
                    "primary_url": candidate_primary_url(candidate),
                }
            )
            continue
        if _same_existing_event(candidate, existing_candidates):
            duplicate_count += 1
            rescue_rejections.append(
                {
                    "title": candidate.get("title"),
                    "reason_code": "duplicate_existing_event",
                    "primary_url": candidate_primary_url(candidate),
                }
            )
            continue
        primary_url = candidate_primary_url(candidate)
        if primary_url and primary_url in archive_urls:
            archive_duplicate_count += 1
            rescue_rejections.append(
                {
                    "title": candidate.get("title"),
                    "reason_code": "archive_exact_url_duplicate",
                    "primary_url": primary_url,
                }
            )
            continue
        eligible.append(candidate)

    try:
        merged, accepted, merge_rejections = merge_candidates(
            current_research,
            eligible,
            maximum_candidates=maximum_candidates,
        )
    except Exception as exc:
        report["state"] = "merge_failed"
        report["status"] = "complete_with_gaps"
        report["duplicate_count"] = duplicate_count
        report["archive_duplicate_count"] = archive_duplicate_count
        report["rejections"] = rescue_rejections + [
            {"reason_code": "merge_exception", "detail": f"{type(exc).__name__}: {exc}"}
        ]
        _persist_report(
            report,
            artifact_dir=artifact_dir,
            output_root=output_root,
            publication_date=publication_date,
        )
        return report

    duplicate_count += sum(
        1
        for item in merge_rejections
        if "дубликат существующего кандидата" in " ".join(item.get("errors") or [])
    )
    report.update(
        {
            "validated_count": len(eligible),
            "accepted_count": len(accepted),
            "added_count": len(accepted),
            "duplicate_count": duplicate_count,
            "archive_duplicate_count": archive_duplicate_count,
            "rejections": rescue_rejections + copy.deepcopy(merge_rejections),
            "accepted_candidates": copy.deepcopy(accepted),
            "state": "completed" if accepted else "completed_no_addition",
            "status": "complete",
        }
    )
    if accepted:
        write_json(artifact_dir / "candidates.json", merged)
        diagnostic = output_root / f"agency-discovery-rescue-merged-{publication_date}.json"
        runtime = RUNTIME_RESEARCH_ROOT / f"agency-discovery-rescue-merged-{publication_date}.json"
        write_json(diagnostic, merged)
        write_json(runtime, merged)
        report["diagnostic_merged_research_path"] = str(diagnostic)
        report["merged_research_path"] = str(runtime)

    _persist_report(
        report,
        artifact_dir=artifact_dir,
        output_root=output_root,
        publication_date=publication_date,
    )
    return report
