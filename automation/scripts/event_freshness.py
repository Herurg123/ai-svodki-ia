#!/usr/bin/env python3
"""Deterministic event-age freshness gate.

This module does not fetch pages or call any model/search API. It only evaluates
structured event-origin evidence already present on a candidate. Reliable stale
evidence rejects; missing/ambiguous evidence stays unknown to preserve recall.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time
from typing import Any
from urllib.parse import urlsplit

EVENT_FRESHNESS_VERSION = 1
EVENT_FRESHNESS_STALE_CODE = "event_freshness_stale"
RELIABLE_EVIDENCE_KINDS = frozenset({
    "official_announcement",
    "official_release",
    "official_research",
    "filing",
    "court_docket",
    "release_note",
    "changelog",
    "first_party_timestamp",
    "authoritative_secondary",
})


@dataclass(frozen=True)
class EventFreshnessResult:
    status: str
    reason: str
    reliable: bool
    event_date: str | None = None
    event_at: str | None = None
    time_precision: str = "unknown"
    origin_url: str | None = None
    evidence_kind: str = "unknown"
    evidence: str = ""
    rejection_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_aware(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _valid_origin_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    parsed = urlsplit(raw)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        return None
    return raw


def evaluate_candidate(
    candidate: dict[str, Any], *, start_at: datetime, end_at: datetime
) -> EventFreshnessResult:
    if start_at.tzinfo is None or end_at.tzinfo is None or end_at < start_at:
        raise ValueError("event freshness requires a valid timezone-aware window")

    raw_date = candidate.get("event_date")
    raw_at = candidate.get("event_at")
    precision = str(candidate.get("event_time_precision") or "unknown")
    origin_url = _valid_origin_url(candidate.get("event_origin_url"))
    evidence_kind = str(candidate.get("event_evidence_kind") or "unknown")
    evidence_text = " ".join(str(candidate.get("event_date_evidence") or "").split())

    reliable = bool(
        origin_url
        and evidence_kind in RELIABLE_EVIDENCE_KINDS
        and evidence_text
    )
    if not reliable:
        return EventFreshnessResult(
            status="unknown",
            reason=(
                "event origin is missing, ambiguous, or lacks reliable evidence; "
                "recall is preserved and source freshness remains authoritative"
            ),
            reliable=False,
            origin_url=origin_url,
            evidence_kind=evidence_kind,
            evidence=evidence_text,
        )

    if not isinstance(raw_date, str):
        return EventFreshnessResult(
            status="unknown",
            reason="reliable origin exists but event_date is missing or invalid",
            reliable=True,
            origin_url=origin_url,
            evidence_kind=evidence_kind,
            evidence=evidence_text,
        )
    try:
        event_date = date.fromisoformat(raw_date)
    except ValueError:
        return EventFreshnessResult(
            status="unknown",
            reason="reliable origin exists but event_date is invalid",
            reliable=True,
            origin_url=origin_url,
            evidence_kind=evidence_kind,
            evidence=evidence_text,
        )

    common = {
        "reliable": True,
        "event_date": event_date.isoformat(),
        "origin_url": origin_url,
        "evidence_kind": evidence_kind,
        "evidence": evidence_text,
    }

    if precision == "datetime":
        event_at = _parse_aware(raw_at)
        if event_at is None or event_at.date() != event_date:
            return EventFreshnessResult(
                status="unknown",
                reason="event_at is missing, naive, invalid, or disagrees with event_date",
                event_at=None,
                time_precision="datetime",
                **common,
            )
        if start_at <= event_at <= end_at:
            return EventFreshnessResult(
                status="fresh",
                reason="reliable exact event timestamp is inside the effective window",
                event_at=event_at.isoformat(),
                time_precision="datetime",
                **common,
            )
        return EventFreshnessResult(
            status="stale",
            reason="reliable exact event timestamp is outside the effective window",
            event_at=event_at.isoformat(),
            time_precision="datetime",
            rejection_code=EVENT_FRESHNESS_STALE_CODE,
            **common,
        )

    if precision != "date" or raw_at is not None:
        return EventFreshnessResult(
            status="unknown",
            reason="event time precision is unknown or internally inconsistent",
            time_precision=precision if precision in {"date", "datetime"} else "unknown",
            **common,
        )

    if event_date < start_at.date() or event_date > end_at.date():
        return EventFreshnessResult(
            status="stale",
            reason="reliable event date is outside the effective window",
            time_precision="date",
            rejection_code=EVENT_FRESHNESS_STALE_CODE,
            **common,
        )

    start_partial = start_at.time() != time.min
    end_partial = end_at.time() != time.max
    if (event_date == start_at.date() and start_partial) or (
        event_date == end_at.date() and end_partial
    ):
        return EventFreshnessResult(
            status="unknown",
            reason=(
                "reliable date-only event evidence falls on a partial boundary day; "
                "exact inclusion cannot be proved, so recall is preserved"
            ),
            time_precision="date",
            **common,
        )

    return EventFreshnessResult(
        status="fresh",
        reason="reliable event date is unambiguously inside the effective window",
        time_precision="date",
        **common,
    )


def apply_event_freshness(
    candidate: dict[str, Any], *, start_at: datetime, end_at: datetime
) -> EventFreshnessResult:
    result = evaluate_candidate(candidate, start_at=start_at, end_at=end_at)
    candidate["event_freshness_status"] = result.status
    candidate["event_freshness_reason"] = result.reason
    candidate["event_freshness_rejection_code"] = result.rejection_code
    if result.status == "stale":
        candidate["recommendation"] = "exclude"
        candidate["freshness_status"] = "old_reprint"
        candidate["freshness_reason"] = (
            f"Event Freshness Proof v{EVENT_FRESHNESS_VERSION}: {result.reason}; "
            f"origin={result.origin_url}; event={result.event_at or result.event_date}."
        )
    return result
