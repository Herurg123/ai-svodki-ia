#!/usr/bin/env python3
"""Shared strict-schema and prompt contract for event-origin freshness evidence."""
from __future__ import annotations

import copy
from typing import Any

EVENT_TIME_CONTRACT_VERSION = 1
EVENT_EVIDENCE_KINDS = (
    "official_announcement",
    "official_release",
    "official_research",
    "filing",
    "court_docket",
    "release_note",
    "changelog",
    "first_party_timestamp",
    "authoritative_secondary",
    "unknown",
)

EVENT_FRESHNESS_PROMPT_RULE = """
Event-origin freshness contract v1:
- `published_date`, `published_at`, `time_precision` continue to describe the
  cited source/article publication timestamp used by Source Freshness Proof.
- `event_date`, `event_at`, `event_time_precision` describe the event itself: its
  occurrence or first material public announcement/release.
- A fresh secondary article never makes an older event fresh.
- Prefer event-origin evidence in this order: official announcement/release/
  research; filing/court docket/release note/changelog; unambiguous first-party
  timestamp; authoritative secondary source only when a primary origin is not
  available.
- Put the evidence URL in `event_origin_url`, classify it in
  `event_evidence_kind`, and briefly quote/paraphrase the date evidence in
  `event_date_evidence`.
- If event origin is unknown or ambiguous, use event_date=null, event_at=null,
  event_time_precision=unknown, event_origin_url=null, event_evidence_kind=unknown,
  and an empty event_date_evidence. Do not substitute the article publication
  date and do not reject merely to manufacture certainty. The deterministic gate
  preserves recall for unknown event origin while Source Freshness remains
  fail-closed for the cited page itself.
""".strip()


def _event_properties() -> dict[str, dict[str, Any]]:
    return {
        "event_date": {
            "type": ["string", "null"],
            "pattern": r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
            "description": (
                "Calendar date of the event occurrence or first material public "
                "announcement/release. Never use a later article publication date."
            ),
        },
        "event_at": {
            "type": ["string", "null"],
            "description": (
                "Verified timezone-aware exact event-origin timestamp when available; "
                "otherwise null. Never invent a time."
            ),
        },
        "event_time_precision": {
            "type": "string",
            "enum": ["datetime", "date", "unknown"],
            "description": "Precision of event_date/event_at, separate from source time.",
        },
        "event_origin_url": {
            "type": ["string", "null"],
            "description": "URL that proves the event-origin date/timestamp, or null if unknown.",
        },
        "event_evidence_kind": {
            "type": "string",
            "enum": list(EVENT_EVIDENCE_KINDS),
            "description": "Reliability class of event-origin date evidence.",
        },
        "event_date_evidence": {
            "type": "string",
            "description": "Concise evidence explaining where the event date came from; empty if unknown.",
        },
    }


def apply_candidate_schema_contract(schema: dict[str, Any]) -> dict[str, Any]:
    """Idempotently extend a strict candidate schema with nullable event evidence."""
    properties = schema.get("properties")
    required = schema.get("required")
    if not isinstance(properties, dict) or not isinstance(required, list):
        raise ValueError("candidate schema must contain properties and required")
    for field, definition in _event_properties().items():
        properties[field] = copy.deepcopy(definition)
        if field not in required:
            required.append(field)
    return schema


def append_event_freshness_prompt(prompt: str) -> str:
    if EVENT_FRESHNESS_PROMPT_RULE in prompt:
        return prompt
    return prompt.rstrip() + "\n\n" + EVENT_FRESHNESS_PROMPT_RULE + "\n"
