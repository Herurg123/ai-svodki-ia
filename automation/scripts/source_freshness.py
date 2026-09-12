#!/usr/bin/env python3
"""Source Freshness v3 with event-age and trusted first-party feed proof.

The complete v2 implementation is preserved in ``source_freshness_v2.py``. v3
keeps its event-age gate, direct-page authority and first-party page adapters,
then adds one candidate-local fallback for durable trusted-feed evidence created
by Source Pulse. The fallback never fetches or repolls the feed.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

import source_freshness_v2 as _v2
from trusted_feed_source_freshness import verify_candidate_with_trusted_feed

for _name in dir(_v2):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_v2, _name)


def __getattr__(name: str) -> Any:
    return getattr(_v2, name)


SOURCE_FRESHNESS_VERSION = 3
EVENT_FRESHNESS_VERSION = _v2.EVENT_FRESHNESS_VERSION
USER_AGENT = "ai-svodki-source-freshness/3.0 (+https://rybalka.one/posts/)"
_parse_aware = _v2._parse_aware
_stage_name = _v2._stage_name


def verify_candidate(
    candidate: dict[str, Any], *, start_at, end_at, fetcher: Fetcher
) -> dict[str, Any]:
    original_recommendation = str(candidate.get("recommendation") or "")
    if original_recommendation not in {"include", "consider"}:
        return _v2.verify_candidate(
            candidate, start_at=start_at, end_at=end_at, fetcher=fetcher
        )

    event_result = _v2.apply_event_freshness(
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
            **_v2._event_record_fields(event_result),
        }

    record = verify_candidate_with_trusted_feed(
        candidate,
        start_at=start_at,
        end_at=end_at,
        fetcher=fetcher,
        base_module=_v2._v1,
        first_party_evidence=_v2._first_party_evidence,
    )
    _v2._annotate_source_diagnostics(candidate, record)
    record.update(_v2._event_record_fields(event_result))
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
        "trusted_feed_publication_evidence_version": 1,
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
        "trusted_feed_evidence_used": sum(
            item.get("trusted_feed_publication_evidence_used") is True
            for item in records
        ),
        "trusted_feed_conflicts": sum(
            isinstance(item.get("trusted_feed_publication_conflict"), dict)
            for item in records
        ),
        "paid_api_calls": 0,
        "web_search_operations": 0,
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
        "trusted_feed_publication_evidence_version": 1,
        "publication_date": publication_date,
        "status": "complete",
        "runs": [],
        "paid_api_calls": 0,
        "web_search_operations": 0,
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
    report["web_search_operations"] = 0
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return run


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify event age and source publication freshness, including strict "
            "saved first-party feed evidence, without paid APIs"
        )
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
