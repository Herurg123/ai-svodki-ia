from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from editorial_policy import validate_diversity_overrides
from editorial_policy_runtime import normalize_full_pool_publisher_overrides

FIXTURE = (
    ROOT
    / "automation"
    / "fixtures"
    / "recall"
    / "editorial-full-pool-publisher-2026-09-03.json"
)
POLICY = ROOT / "automation" / "config" / "editorial.json"


def _policy() -> dict:
    return json.loads(POLICY.read_text(encoding="utf-8"))


def _selected(research: dict, editorial: dict) -> list[dict]:
    candidate_map = {
        str(item.get("id")): item
        for item in research["candidates"]
        if isinstance(item, dict)
    }
    return [candidate_map[item] for item in editorial["selected_candidate_ids"]]


def _candidate(
    candidate_id: str,
    publisher: str,
    score: int,
    *,
    organization: str | None = None,
    recommendation: str = "include",
) -> dict:
    return {
        "id": candidate_id,
        "organization": organization or f"Org {candidate_id}",
        "category": "models",
        "recommendation": recommendation,
        "verification_status": "verified",
        "freshness_status": "new_event",
        "significance_score": score,
        "legal_scale": "not_applicable",
        "curiosity_eligible": False,
        "primary_source": {
            "title": f"Story {candidate_id}",
            "publisher": publisher,
            "url": f"https://{publisher.casefold()}.example/{candidate_id}",
        },
    }


def _synthetic_case(*, alternative_score: int = 2) -> tuple[dict, dict]:
    candidates = [
        _candidate("a", "HuggingNews", 4, organization="Meta"),
        _candidate("b", "HuggingNews", 4, organization="Tencent"),
        _candidate("c", "HuggingNews", 3, organization="Perplexity"),
        _candidate("d", "Publisher D", 5),
        _candidate("e", "Publisher E", 4),
        _candidate("f", "Publisher F", 3),
        _candidate("g", "Publisher G", 3),
        _candidate("h", "Publisher H", alternative_score, recommendation="consider"),
    ]
    research = {"candidates": candidates}
    editorial = {
        "selected_candidate_ids": ["a", "b", "c", "d", "e", "f", "g"],
        "diversity_overrides": [],
        "digest": {"editorial_notes": []},
    }
    return research, editorial


def test_exact_sep3_replay_is_repaired_without_api_or_search() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fixture["source_run_id"] == 33716335547
    assert fixture["openai_calls_for_replay"] == 0
    assert fixture["web_search_operations_for_replay"] == 0

    research = {"candidates": copy.deepcopy(fixture["candidates"])}
    editorial = {
        "selected_candidate_ids": list(fixture["selected_candidate_ids"]),
        "diversity_overrides": list(fixture["diversity_overrides"]),
        "digest": {"editorial_notes": []},
    }
    policy = _policy()

    before = validate_diversity_overrides(_selected(research, editorial), [], policy)
    assert before == [
        "Издатель 'huggingnews' представлен 3 сюжетами без diversity override с причиной."
    ]

    changes = normalize_full_pool_publisher_overrides(editorial, research, policy)

    assert len(changes) == 1
    assert changes[0]["type"] == "publisher"
    assert changes[0]["value"] == "HuggingNews"
    assert "score 2" in changes[0]["reason"]
    assert "significance_score" in changes[0]["reason"]
    assert validate_diversity_overrides(
        _selected(research, editorial),
        editorial["diversity_overrides"],
        policy,
    ) == []


def test_equal_strength_different_publisher_alternative_keeps_fail_closed() -> None:
    research, editorial = _synthetic_case(alternative_score=3)
    policy = _policy()

    assert normalize_full_pool_publisher_overrides(editorial, research, policy) == []
    assert validate_diversity_overrides(
        _selected(research, editorial), editorial["diversity_overrides"], policy
    ) == [
        "Издатель 'huggingnews' представлен 3 сюжетами без diversity override с причиной."
    ]


def test_repeated_primary_subject_keeps_fail_closed() -> None:
    research, editorial = _synthetic_case()
    research["candidates"][2]["organization"] = "Meta; Another Product"
    policy = _policy()

    assert normalize_full_pool_publisher_overrides(editorial, research, policy) == []


def test_over_cap_by_more_than_one_keeps_fail_closed() -> None:
    research, editorial = _synthetic_case()
    research["candidates"][3]["primary_source"]["publisher"] = "HuggingNews"
    research["candidates"][3]["primary_source"]["url"] = "https://huggingnews.example/d"
    research["candidates"][3]["organization"] = "World Labs"
    policy = _policy()

    assert normalize_full_pool_publisher_overrides(editorial, research, policy) == []


def test_non_include_over_cap_story_keeps_fail_closed() -> None:
    research, editorial = _synthetic_case()
    research["candidates"][2]["recommendation"] = "consider"
    policy = _policy()

    assert normalize_full_pool_publisher_overrides(editorial, research, policy) == []


def test_existing_reasoned_override_is_not_duplicated() -> None:
    research, editorial = _synthetic_case()
    editorial["diversity_overrides"] = [
        {
            "type": "publisher",
            "value": "HuggingNews",
            "reason": "Existing editorial reason.",
        }
    ]
    policy = _policy()

    assert normalize_full_pool_publisher_overrides(editorial, research, policy) == []
    assert len(editorial["diversity_overrides"]) == 1


def test_organization_diversity_error_is_not_hidden_by_publisher_repair() -> None:
    research, editorial = _synthetic_case()
    policy = _policy()
    # Keep the three HuggingNews primary subjects distinct so publisher repair is
    # allowed, but make three other selected stories share an organization. The
    # canonical organization guard must still reject that separate violation.
    research["candidates"][3]["organization"] = "Shared Org"
    research["candidates"][4]["organization"] = "Shared Org"
    research["candidates"][5]["organization"] = "Shared Org"

    changes = normalize_full_pool_publisher_overrides(editorial, research, policy)
    assert len(changes) == 1

    errors = validate_diversity_overrides(
        _selected(research, editorial), editorial["diversity_overrides"], policy
    )
    assert errors == [
        "Организация 'shared org' представлена 3 сюжетами без diversity override с причиной."
    ]
