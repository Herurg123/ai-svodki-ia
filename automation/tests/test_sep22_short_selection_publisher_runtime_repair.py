from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from editorial_policy import validate_diversity_overrides  # noqa: E402
from editorial_policy_runtime import (  # noqa: E402
    normalize_short_selection_publisher_overrides,
    wrap_editorial_validator,
)

POLICY = json.loads(
    (ROOT / "automation" / "config" / "editorial.json").read_text(encoding="utf-8")
)
FIXTURE = (
    ROOT
    / "automation"
    / "fixtures"
    / "editorial"
    / "short-selection-publisher-2026-09-22.json"
)


def selected(research: dict, editorial: dict) -> list[dict]:
    candidate_map = {
        str(item.get("id")): item
        for item in research["candidates"]
        if isinstance(item, dict)
    }
    return [candidate_map[item] for item in editorial["selected_candidate_ids"]]


def validate_stub(editorial: dict, research: dict, *args, **kwargs):
    del args, kwargs
    errors = validate_diversity_overrides(
        selected(research, editorial),
        editorial["diversity_overrides"],
        POLICY,
    )
    return errors, [], []


def run_wrapped(editorial: dict, research: dict):
    wrapped = wrap_editorial_validator(validate_stub, lambda value: value)
    return wrapped(editorial, research, None, None, None, POLICY, 7, 12)


class Sep22ShortSelectionPublisherRuntimeRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def case(self) -> tuple[dict, dict]:
        return (
            copy.deepcopy(self.fixture["research"]),
            copy.deepcopy(self.fixture["editorial"]),
        )

    def test_exact_sep22_replay_repairs_override_without_changing_selection(self) -> None:
        self.assertEqual(self.fixture["source_run_id"], 35676364066)
        self.assertEqual(
            self.fixture["source_head_sha"],
            "fefb11c504a93b9ca1c964db9d46c5c293613fd6",
        )
        self.assertEqual(self.fixture["openai_calls_for_replay"], 0)
        self.assertEqual(self.fixture["web_search_operations_for_replay"], 0)

        research, editorial = self.case()
        original_selected = list(editorial["selected_candidate_ids"])
        original_excluded = list(editorial["excluded_candidate_ids"])

        self.assertEqual(
            validate_diversity_overrides(selected(research, editorial), [], POLICY),
            [
                "Издатель 'techcrunch' представлен 3 сюжетами без diversity override с причиной."
            ],
        )

        errors, warnings, _stories = run_wrapped(editorial, research)

        self.assertEqual(errors, [])
        self.assertEqual(editorial["selected_candidate_ids"], original_selected)
        self.assertEqual(editorial["excluded_candidate_ids"], original_excluded)
        self.assertEqual(len(editorial["diversity_overrides"]), 1)
        override = editorial["diversity_overrides"][0]
        self.assertEqual(override["type"], "publisher")
        self.assertEqual(override["value"], "TechCrunch")
        self.assertIn("все baseline-eligible include-кандидаты сохранены", override["reason"])
        self.assertEqual(
            editorial["digest"]["editorial_notes"][-1]["type"],
            "diversity_override",
        )
        self.assertTrue(
            any("short-selection publisher diversity override" in item for item in warnings)
        )

    def test_unselected_include_candidate_keeps_fail_closed(self) -> None:
        research, editorial = self.case()
        research["candidates"][3]["recommendation"] = "include"

        changes = normalize_short_selection_publisher_overrides(
            editorial, research, POLICY
        )

        self.assertEqual(changes, [])
        self.assertEqual(editorial["diversity_overrides"], [])

    def test_missing_low_news_volume_marker_keeps_fail_closed(self) -> None:
        research, editorial = self.case()
        editorial["digest"]["editorial_notes"] = [
            item
            for item in editorial["digest"]["editorial_notes"]
            if item.get("type") != "low_news_volume"
        ]

        self.assertEqual(
            normalize_short_selection_publisher_overrides(editorial, research, POLICY),
            [],
        )

    def test_incomplete_partition_keeps_fail_closed(self) -> None:
        research, editorial = self.case()
        editorial["excluded_candidate_ids"].pop()

        self.assertEqual(
            normalize_short_selection_publisher_overrides(editorial, research, POLICY),
            [],
        )

    def test_repeated_primary_subject_keeps_fail_closed(self) -> None:
        research, editorial = self.case()
        research["candidates"][2]["organization"] = "Google; duplicate"

        self.assertEqual(
            normalize_short_selection_publisher_overrides(editorial, research, POLICY),
            [],
        )

    def test_true_short_eligible_pool_remains_owned_by_preserved_base(self) -> None:
        research, editorial = self.case()
        keep = set(editorial["selected_candidate_ids"])
        research["candidates"] = [
            item for item in research["candidates"] if item["id"] in keep
        ]
        editorial["excluded_candidate_ids"] = []

        self.assertEqual(
            normalize_short_selection_publisher_overrides(editorial, research, POLICY),
            [],
        )
        errors, _warnings, _stories = run_wrapped(editorial, research)
        self.assertEqual(errors, [])
        self.assertEqual(editorial["diversity_overrides"][0]["value"], "TechCrunch")

    def test_normal_seven_story_selection_does_not_use_short_selection_repair(self) -> None:
        research, editorial = self.case()
        for candidate_id in ("cand-004", "cand-005"):
            editorial["selected_candidate_ids"].append(candidate_id)
            editorial["excluded_candidate_ids"].remove(candidate_id)

        self.assertEqual(len(editorial["selected_candidate_ids"]), 7)
        self.assertEqual(
            normalize_short_selection_publisher_overrides(editorial, research, POLICY),
            [],
        )


if __name__ == "__main__":
    unittest.main()
