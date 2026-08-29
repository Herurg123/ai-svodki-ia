#!/usr/bin/env python3
"""Shared retrieval contract for candidate event-time semantics.

This module changes no search query, routing or budget. Stable retrieval
entrypoints apply it to the strict candidate schema before an API request so
``published_*`` consistently describes the event itself rather than a fresh
secondary page that happens to mention an older event.
"""
from __future__ import annotations

from typing import Any

EVENT_TIME_CONTRACT_VERSION = 1

EVENT_DATE_DESCRIPTION = (
    "Calendar date of the event occurrence or first material public announcement. "
    "This is event time, not the publication date of a later article, reprint, "
    "recap, or corroborating page. Never substitute a secondary page date when "
    "the event origin date is older or cannot be established."
)
EVENT_AT_DESCRIPTION = (
    "Exact timezone-aware timestamp of the event occurrence or first material "
    "public announcement when verified. This is event time, not source-page "
    "publication time. Use null rather than inventing a timestamp."
)
TIME_PRECISION_DESCRIPTION = (
    "Precision of the event timestamp in published_date/published_at. Use datetime "
    "only for a verified timezone-aware event timestamp; otherwise use date."
)

EVENT_FRESHNESS_PROMPT_RULE = """
Event-time contract v1:
`published_date`, `published_at` and `time_precision` describe the EVENT itself:
its occurrence or first material public announcement. They do NOT describe a
later article, reprint, recap or corroborating page. A fresh secondary page
cannot make an older event fresh. If event origin time is not established, do
not copy the page publication date into these fields and do not invent a time.
The deterministic Event Freshness Proof and Source Freshness Proof validate event
age and source-page age separately against the exact saved window.
""".strip()


def apply_candidate_schema_contract(schema: dict[str, Any]) -> dict[str, Any]:
    """Attach event-time semantics to an existing strict candidate schema."""
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        raise ValueError("candidate schema is missing properties")
    descriptions = {
        "published_date": EVENT_DATE_DESCRIPTION,
        "published_at": EVENT_AT_DESCRIPTION,
        "time_precision": TIME_PRECISION_DESCRIPTION,
    }
    for field, description in descriptions.items():
        definition = properties.get(field)
        if not isinstance(definition, dict):
            raise ValueError(f"candidate schema is missing {field}")
        definition["description"] = description
    return schema


def append_event_freshness_prompt(prompt: str) -> str:
    """Append the same rule once when a stable wrapper owns prompt composition."""
    if EVENT_FRESHNESS_PROMPT_RULE in prompt:
        return prompt
    return prompt.rstrip() + "\n\n" + EVENT_FRESHNESS_PROMPT_RULE + "\n"
