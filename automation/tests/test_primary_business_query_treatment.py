#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import primary_recall_search as primary


def _direction(direction_id: str) -> dict[str, object]:
    return next(
        item
        for item in primary.PRIMARY_DIRECTIONS
        if item.get("id") == direction_id
    )


def _prompt(direction_id: str) -> str:
    return primary.build_prompt(
        "base prompt",
        publication_date="2026-09-03",
        search_window={
            "start_at": "2026-09-01T04:01:28+03:00",
            "end_at": "2026-09-03T04:07:02+03:00",
        },
        direction=_direction(direction_id),
        existing_candidates=[],
        archive={"items": []},
    )


def test_business_treatment_is_narrow_and_date_free() -> None:
    query = primary.BUSINESS_QUERY_TREATMENT
    words = query.split()

    assert 6 <= len(words) <= 18
    assert query.startswith("latest ")
    for token in ("2026", "september", "after:", "before:", "site:", " OR "):
        assert token.casefold() not in query.casefold()

    for required in (
        "investment",
        "financing",
        "acquisitions",
        "partnerships",
        "enterprise",
        "deals",
        "revenue",
        "monetization",
        "ads",
        "earnings",
    ):
        assert required in query


def test_business_prompt_requires_exact_treatment_query() -> None:
    prompt = _prompt(primary.BUSINESS_QUERY_DIRECTION_ID)

    assert primary.BUSINESS_QUERY_TREATMENT in prompt
    assert "фактический query должен быть РОВНО" in prompt
    assert "Search-operation budget" in prompt
    assert "ровно один Web Search" in prompt


def test_treatment_does_not_leak_into_other_primary_lanes() -> None:
    prompt = _prompt("models_products_agents")

    assert primary.BUSINESS_QUERY_TREATMENT not in prompt
    assert "Business recall treatment" not in prompt


def test_treatment_keeps_primary_search_budget_unchanged() -> None:
    assert primary.DEFAULT_MAXIMUM_SEARCH_CALLS == 12
    assert len(primary.PRIMARY_DIRECTIONS) == 12

    research, report = primary._annotate(
        {"candidates": []},
        {"directions": []},
    )
    for payload in (research, report):
        treatment = payload["business_query_treatment"]
        assert treatment["query"] == primary.BUSINESS_QUERY_TREATMENT
        assert treatment["additional_search_operations"] == 0
