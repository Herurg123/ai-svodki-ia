#!/usr/bin/env python3
"""Source Freshness v2 with an independent event-age gate.

The preserved v1 module remains the authority for safe source fetching,
publication-metadata parsing and fail-closed source-page freshness. v2 adds a
separate zero-paid deterministic event-origin check before that source proof.
Reliable stale event evidence rejects immediately; unknown event origin preserves
recall and still has to pass the unchanged source-page proof.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

_EVENT_PATH = Path(__file__).with_name("event_freshness.py")
_EVENT_SPEC = importlib.util.spec_from_file_location("event_freshness", _EVENT_PATH)
assert _EVENT_SPEC and _EVENT_SPEC.loader
_event = importlib.util.module_from_spec(_EVENT_SPEC)
sys.modules[_EVENT_SPEC.name] = _event
_EVENT_SPEC.loader.exec_module(_event)
EVENT_FRESHNESS_VERSION = _event.EVENT_FRESHNESS_VERSION
EventFreshnessResult = _event.EventFreshnessResult
apply_event_freshness = _event.apply_event_freshness

_V1_PATH = Path(__file__).with_name("source_freshness_v1.py")
_V1_SPEC = importlib.util.spec_from_file_location("source_freshness_v1", _V1_PATH)
assert _V1_SPEC and _V1_SPEC.loader
_v1 = importlib.util.module_from_spec(_V1_SPEC)
sys.modules[_V1_SPEC.name] = _v1
_V1_SPEC.loader.exec_module(_v1)

for _name in dir(_v1):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_v1, _name)

_parse_aware = _v1._parse_aware
_stage_name = _v1._stage_name
SOURCE_FRESHNESS_VERSION = 2
USER_AGENT = "ai-svodki-source-freshness/2.0 (+https://rybalka.one/posts/)"


def _event_record_fields(result: EventFreshnessResult) -> dict[str, Any]:
    return {
        "event_freshness_status": result.status,
        "event_freshness_reason": result.reason,
        "event_date": result.event_date,
        "event_at": result.event_at,
        "event_time_precision": result.time_precision,
        "event_origin_url": result.origin_url,
        "event_evidence_kind": result.evidence_kind,
        "event_date_evidence": result.evidence,
        "event_freshness_rejection_code": result.rejection_code,
    }


def _selected_source_record(record: dict[str, Any]) -> dict[str, Any] | None:
    selected = str(record.get("selected_source_url") or "")
    if not selected:
        return None
    for raw in record.get("sources") or []:
        if isinstance(raw, dict) and str(raw.get("url") or "") == selected:
            return raw
    return None


def _annotate_source_diagnostics(
    candidate: dict[str, Any], record: dict[str, Any]
) -> None:
    status = str(record.get("status") or "")
    source_status = {
        "verified_fresh": "fresh",
        "excluded_outside_window": "stale",
        "excluded_unverified_freshness": "unknown",
    }.get(status, "unknown")
    candidate["source_freshness_status"] = source_status
    candidate["source_publication_url"] = record.get("selected_source_url")
    selected = _selected_source_record(record)
    if selected is None:
        candidate["source_published_date"] = None
        candidate["source_published_at"] = None
        candidate["source_time_precision"] = "unknown"
        candidate["source_publication_evidence"] = ""
        return
    candidate["source_published_date"] = selected.get("published_date")
    candidate["source_published_at"] = selected.get("published_at")
    candidate["source_time_precision"] = selected.get("time_precision") or "unknown"
    locator = str(selected.get("locator") or "").strip()
    raw_date = str(selected.get("raw_date") or "").strip()
    candidate["source_publication_evidence"] = (
        f"{locator}={raw_date}" if locator and raw_date else raw_date or locator
    )


def verify_candidate(
    candidate: dict[str, Any], *, start_at, end_at, fetcher: Fetcher
) -> dict[str, Any]:
    original_recommendation = str(candidate.get("recommendation") or "")
    if original_recommendation not in {"include", "consider"}:
        return _v1.verify_candidate(
            candidate, start_at=start_at, end_at=end_at, fetcher=fetcher
        )

    event_result = apply_event_freshness(
        candidate, start_at=start_at, end_at=end_at
    )
    if event_result.status == "stale":
        return {
            "title": str(candidate.get("title") or "Кандидат без заголовка"),
            "candidate_id": candidate.get("id", candidate.get("candidate_id")),
            "original_recommendation": original_recommendation,
            "status": "excluded_event_freshness_stale",
            "reason": event_result.reason,
            "sources": [],
            **_event_record_fields(event_result),
        }

    record = _v1.verify_candidate(
        candidate, start_at=start_at, end_at=end_at, fetcher=fetcher
    )
    _annotate_source_diagnostics(candidate, record)
    record.update(_event_record_fields(event_result))
    return record


def verify_research_payload(
    research: dict[str, Any], *, fetcher: Fetcher = fetch_source_html
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(research, dict) or not isinstance(research.get("candidates"), list):
        raise SourceFreshnessError("research artifact должен содержать candidates[]")
    window = research.get("search_window")
    if not isinstance(window, dict):
        raise SourceFreshnessError("research artifact не содержит search_window")
    start_at = _parse_aware(window.get("start_at"), "search_window.start_at")
    end_at = _parse_aware(window.get("end_at"), "search_window.end_at")
    if end_at < start_at:
        raise SourceFreshnessError("search_window.end_at раньше start_at")

    result = copy.deepcopy(research)
    records: list[dict[str, Any]] = []
    eligible_before = 0
    for candidate in result["candidates"]:
        if not isinstance(candidate, dict):
            continue
        if candidate.get("recommendation") in {"include", "consider"}:
            eligible_before += 1
        records.append(
            verify_candidate(
                candidate, start_at=start_at, end_at=end_at, fetcher=fetcher
            )
        )

    eligible_after = sum(
        1
        for candidate in result["candidates"]
        if isinstance(candidate, dict)
        and candidate.get("recommendation") in {"include", "consider"}
    )
    summary = {
        "version": SOURCE_FRESHNESS_VERSION,
        "event_freshness_version": EVENT_FRESHNESS_VERSION,
        "status": "complete",
        "search_window": copy.deepcopy(window),
        "candidate_count": len(
            [item for item in result["candidates"] if isinstance(item, dict)]
        ),
        "eligible_before": eligible_before,
        "eligible_after": eligible_after,
        "event_fresh": sum(
            item.get("event_freshness_status") == "fresh" for item in records
        ),
        "event_unknown": sum(
            item.get("event_freshness_status") == "unknown" for item in records
        ),
        "excluded_event_freshness_stale": sum(
            item.get("status") == "excluded_event_freshness_stale"
            for item in records
        ),
        "verified_fresh": sum(
            item.get("status") == "verified_fresh" for item in records
        ),
        "excluded_outside_window": sum(
            item.get("status") == "excluded_outside_window" for item in records
        ),
        "excluded_unverified_freshness": sum(
            item.get("status") == "excluded_unverified_freshness"
            for item in records
        ),
        "paid_api_calls": 0,
        "candidates": records,
    }
    return result, summary


def verify_research_file(
    research_path: Path,
    *,
    publication_date: str,
    report_path: Path,
    fetcher: Fetcher = fetch_source_html,
) -> dict[str, Any]:
    try:
        research = json.loads(research_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceFreshnessError(
            f"не удалось прочитать research artifact: {exc}"
        ) from exc
    verified, run = verify_research_payload(research, fetcher=fetcher)
    research_path.write_text(
        json.dumps(verified, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report: dict[str, Any] = {
        "version": SOURCE_FRESHNESS_VERSION,
        "event_freshness_version": EVENT_FRESHNESS_VERSION,
        "publication_date": publication_date,
        "status": "complete",
        "runs": [],
        "paid_api_calls": 0,
    }
    if report_path.is_file():
        try:
            prior = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            prior = None
        if (
            isinstance(prior, dict)
            and prior.get("version") == SOURCE_FRESHNESS_VERSION
            and prior.get("publication_date") == publication_date
            and isinstance(prior.get("runs"), list)
        ):
            report = prior
    run["stage"] = _stage_name(research_path)
    run["research_path"] = str(research_path)
    report["runs"].append(run)
    report["paid_api_calls"] = 0
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return run


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify event age and source publication freshness without paid APIs"
    )
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--publication-date", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        run = verify_research_file(
            args.research,
            publication_date=args.publication_date,
            report_path=args.report,
        )
    except Exception as exc:
        print(f"Freshness verification failed: {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(run, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
