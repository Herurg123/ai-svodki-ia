from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from editorial_policy import validate_diversity_overrides


def _candidate(candidate_id: str, publisher: str, *, supporting: str | None = None) -> dict:
    candidate = {
        "id": candidate_id,
        "organization": f"Org {candidate_id}",
        "primary_source": {
            "title": f"Primary {candidate_id}",
            "publisher": publisher,
            "url": f"https://example.com/{candidate_id}",
        },
        "supporting_sources": [],
    }
    if supporting:
        candidate["supporting_sources"].append(
            {
                "title": f"Supporting {candidate_id}",
                "publisher": supporting,
                "url": f"https://support.example.com/{candidate_id}",
            }
        )
    return candidate


def _policy() -> dict:
    return json.loads(
        (ROOT / "automation" / "config" / "editorial.json").read_text(encoding="utf-8")
    )


def test_policy_tells_editorial_to_count_primary_publisher() -> None:
    policy = _policy()
    diversity = policy["diversity"]

    assert diversity["publisher_identity_field"] == "primary_source.publisher"
    assert "supporting_sources" in diversity["publisher_identity_rule"]
    assert "article_html" in diversity["publisher_identity_rule"]
    assert "selected_candidate_ids" in diversity["pre_response_publisher_check"]
    assert "primary_source.publisher" in diversity["pre_response_publisher_check"]

    prompt = (ROOT / "automation" / "prompts" / "daily_digest.md").read_text(
        encoding="utf-8"
    )
    assert "{{EDITORIAL_POLICY_CONTEXT}}" in prompt


def test_supporting_axios_does_not_hide_three_huggingnews_primaries() -> None:
    policy = _policy()
    selected = [
        _candidate("cand-002", "HuggingNews"),
        _candidate("cand-006", "HuggingNews", supporting="Axios"),
        _candidate("cand-010", "HuggingNews"),
    ]

    errors = validate_diversity_overrides(selected, [], policy)

    assert errors == [
        "Издатель 'huggingnews' представлен 3 сюжетами без diversity override с причиной."
    ]


def test_explicit_reasoned_override_remains_the_only_full_pool_exception() -> None:
    policy = _policy()
    selected = [
        _candidate("cand-002", "HuggingNews"),
        _candidate("cand-006", "HuggingNews", supporting="Axios"),
        _candidate("cand-010", "HuggingNews"),
    ]
    overrides = [
        {
            "type": "publisher",
            "value": "HuggingNews",
            "reason": "Three independently significant events require the documented exception.",
        }
    ]

    assert validate_diversity_overrides(selected, overrides, policy) == []
