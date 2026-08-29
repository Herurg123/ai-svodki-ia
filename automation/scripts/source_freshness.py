#!/usr/bin/env python3
"""Stable Source Freshness v2 with independent event-age proof.

The preserved v1 module owns page parsing, safe HTTPS fetching and publication
metadata extraction. v2 keeps those mechanics byte-for-byte compatible while
separating candidate event time from source-page publication time. Candidate
``published_*`` fields are event occurrence / first material announcement time
and are never overwritten by source metadata.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

_V1_PATH = Path(__file__).with_name("source_freshness_v1.py")
_V1_SPEC = importlib.util.spec_from_file_location("source_freshness_v1", _V1_PATH)
assert _V1_SPEC and _V1_SPEC.loader
_v1 = importlib.util.module_from_spec(_V1_SPEC)
sys.modules[_V1_SPEC.name] = _v1
_V1_SPEC.loader.exec_module(_v1)

for _name in dir(_v1):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_v1, _name)

# Existing tests and compatibility callers use these private helpers directly.
_parse_aware = _v1._parse_aware
_source_rows = _v1._source_rows
_promote_source = _v1._promote_source
_safe_public_url = _v1._safe_public_url
_parse_publication_value = _v1._parse_publication_value
_collect_jsonld_dates = _v1._collect_jsonld_dates
_jsonld_types = _v1._jsonld_types
_stage_name = _v1._stage_name

SOURCE_FRESHNESS_VERSION = 2
EVENT_FRESHNESS_VERSION = 1
USER_AGENT = "ai-svodki-source-freshness/2.0 (+https://rybalka.one/posts/)"


@dataclass(frozen=True)
class EventFreshnessEvidence:
    raw: str
    event_date: date
    event_at: datetime | None
    time_precision: str


def evidence_in_window(
    evidence: PublicationEvidence, *, start_at: datetime, end_at: datetime
) -> bool:
    """Source-page proof with fail-closed exact boundary-day semantics."""
    if evidence.published_at is not None:
        return start_at <= evidence.published_at <= end_at
    published = evidence.published_date
    if not (start_at.date() <= published <= end_at.date()):
        return False
    if published == start_at.date() and start_at.time() != datetime.min.time():
        return False
    if published == end_at.date() and end_at.time() != datetime.max.time():
        return False
    return True


def extract_event_freshness_evidence(
    candidate: dict[str, Any],
) -> EventFreshnessEvidence | None:
    """Read the event timestamp from candidate metadata without guessing."""
    raw_date = candidate.get("published_date")
    precision = candidate.get("time_precision")
    raw_at = candidate.get("published_at")
    if not isinstance(raw_date, str) or not _v1._DATE_ONLY_RE.fullmatch(raw_date):
        return None
    try:
        event_date = date.fromisoformat(raw_date)
    except ValueError:
        return None
    if precision == "date":
        if raw_at is not None:
            return None
        return EventFreshnessEvidence(raw_date, event_date, None, "date")
    if precision != "datetime" or not isinstance(raw_at, str) or not raw_at.strip():
        return None
    try:
        event_at = datetime.fromisoformat(raw_at.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if event_at.tzinfo is None or event_at.date() != event_date:
        return None
    return EventFreshnessEvidence(raw_at, event_date, event_at, "datetime")


def event_evidence_status(
    evidence: EventFreshnessEvidence, *, start_at: datetime, end_at: datetime
) -> str:
    """Return fresh/stale/unknown for an event against the exact saved window."""
    if evidence.event_at is not None:
        return "fresh" if start_at <= evidence.event_at <= end_at else "stale"
    day = evidence.event_date
    if day < start_at.date() or day > end_at.date():
        return "stale"
    if day == start_at.date() and start_at.time() != datetime.min.time():
        return "unknown"
    if day == end_at.date() and end_at.time() != datetime.max.time():
        return "unknown"
    return "fresh"


def _event_gate(
    candidate: dict[str, Any], *, start_at: datetime, end_at: datetime,
    record: dict[str, Any],
) -> bool:
    evidence = extract_event_freshness_evidence(candidate)
    if evidence is None:
        candidate["recommendation"] = "exclude"
        candidate["verification_status"] = "unconfirmed"
        candidate["freshness_reason"] = (
            f"Event Freshness Proof v{EVENT_FRESHNESS_VERSION}: event timestamp "
            "отсутствует или внутренне противоречив; публикация fail-closed."
        )
        record["status"] = "excluded_unverified_event_freshness"
        record["event_freshness_status"] = "unknown"
        return False

    status = event_evidence_status(evidence, start_at=start_at, end_at=end_at)
    record.update(
        {
            "event_freshness_status": status,
            "event_date": evidence.event_date.isoformat(),
            "event_at": (
                evidence.event_at.isoformat()
                if evidence.event_at is not None
                else None
            ),
            "event_time_precision": evidence.time_precision,
        }
    )
    if status == "fresh":
        return True

    candidate["recommendation"] = "exclude"
    if status == "stale":
        candidate["freshness_status"] = "old_reprint"
        candidate["freshness_reason"] = (
            f"Event Freshness Proof v{EVENT_FRESHNESS_VERSION}: candidate event "
            f"timestamp {evidence.raw} находится вне effective window."
        )
        record["status"] = "excluded_event_outside_window"
    else:
        candidate["verification_status"] = "unconfirmed"
        candidate["freshness_reason"] = (
            f"Event Freshness Proof v{EVENT_FRESHNESS_VERSION}: date-only event "
            f"{evidence.raw} лежит на частичном boundary day exact window; "
            "точное попадание не доказано, публикация fail-closed."
        )
        record["status"] = "excluded_unverified_event_freshness"
    return False


def verify_candidate(
    candidate: dict[str, Any], *, start_at: datetime, end_at: datetime,
    fetcher: Fetcher,
) -> dict[str, Any]:
    """Require event-age proof first, then preserved v1 source-page proof."""
    title = str(candidate.get("title") or "Кандидат без заголовка")
    original_recommendation = str(candidate.get("recommendation") or "")
    record: dict[str, Any] = {
        "title": title,
        "candidate_id": candidate.get("id", candidate.get("candidate_id")),
        "original_recommendation": original_recommendation,
        "status": "skipped",
        "sources": [],
    }
    if original_recommendation not in {"include", "consider"}:
        record["reason"] = "candidate_not_eligible_before_freshness_gate"
        return record
    if not _event_gate(candidate, start_at=start_at, end_at=end_at, record=record):
        return record

    fresh_matches: list[tuple[dict[str, Any], PublicationEvidence, str]] = []
    dated_matches: list[tuple[dict[str, Any], PublicationEvidence, str]] = []
    for source in _source_rows(candidate):
        source_url = str(source.get("url") or "")
        source_record: dict[str, Any] = {
            "publisher": source.get("publisher"),
            "url": source_url,
            "status": "error",
        }
        try:
            html, final_url, http_status = fetcher(source_url)
            evidence = extract_publication_evidence(html)
        except Exception as exc:
            source_record["error"] = f"{type(exc).__name__}: {exc}"
        else:
            source_record["final_url"] = final_url
            source_record["http_status"] = http_status
            if evidence is None:
                source_record["status"] = "no_publication_date"
            else:
                in_window = evidence_in_window(
                    evidence, start_at=start_at, end_at=end_at
                )
                source_record.update(
                    {
                        "status": "fresh" if in_window else "outside_window",
                        "published_date": evidence.published_date.isoformat(),
                        "published_at": (
                            evidence.published_at.isoformat()
                            if evidence.published_at is not None
                            else None
                        ),
                        "time_precision": evidence.time_precision,
                        "locator": evidence.locator,
                        "raw_date": evidence.raw,
                    }
                )
                dated_matches.append((source, evidence, final_url))
                if in_window:
                    fresh_matches.append((source, evidence, final_url))
        record["sources"].append(source_record)

    if fresh_matches:
        source, evidence, _final_url = fresh_matches[0]
        _promote_source(candidate, source)
        event_value = candidate.get("published_at") or candidate.get("published_date")
        event_proof = (
            f"Event Freshness Proof v{EVENT_FRESHNESS_VERSION}: candidate event "
            f"timestamp {event_value} проверен отдельно и не был заменён "
            "source-page timestamp."
        )
        source_proof = (
            f"Source Freshness Proof v{SOURCE_FRESHNESS_VERSION}: "
            f"{evidence.locator}={evidence.raw}; source timestamp проверен Python "
            "против effective window."
        )
        previous = str(candidate.get("freshness_reason") or "").strip()
        candidate["freshness_reason"] = (
            f"{event_proof} {source_proof} {previous}".strip()
        )
        record.update(
            {
                "status": "verified_fresh",
                "selected_source_url": str(source.get("url") or ""),
                "source_published_date": evidence.published_date.isoformat(),
                "source_published_at": (
                    evidence.published_at.isoformat()
                    if evidence.published_at is not None
                    else None
                ),
            }
        )
        return record

    candidate["recommendation"] = "exclude"
    if dated_matches:
        source, evidence, _final_url = dated_matches[0]
        candidate["freshness_status"] = "old_reprint"
        candidate["freshness_reason"] = (
            f"Source Freshness Proof v{SOURCE_FRESHNESS_VERSION}: подтверждённая "
            f"дата основного/цитируемого источника {evidence.raw} находится вне "
            "effective window. Event timestamp сохранён и не перезаписан."
        )
        record.update(
            {
                "status": "excluded_outside_window",
                "selected_source_url": str(source.get("url") or ""),
                "source_published_date": evidence.published_date.isoformat(),
                "source_published_at": (
                    evidence.published_at.isoformat()
                    if evidence.published_at is not None
                    else None
                ),
            }
        )
        return record

    candidate["verification_status"] = "unconfirmed"
    candidate["freshness_reason"] = (
        f"Source Freshness Proof v{SOURCE_FRESHNESS_VERSION}: ни один уже "
        "цитируемый source URL не отдал независимо проверяемую дату публикации; "
        "публикация fail-closed."
    )
    record["status"] = "excluded_unverified_freshness"
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
        "verified_fresh": sum(
            item.get("status") == "verified_fresh" for item in records
        ),
        "excluded_event_outside_window": sum(
            item.get("status") == "excluded_event_outside_window"
            for item in records
        ),
        "excluded_unverified_event_freshness": sum(
            item.get("status") == "excluded_unverified_event_freshness"
            for item in records
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
    research_path: Path, *, publication_date: str, report_path: Path,
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
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return run


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify event and source publication freshness without paid APIs"
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
        print(
            f"Source freshness verification failed: {type(exc).__name__}: {exc}"
        )
        return 1
    print(json.dumps(run, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
