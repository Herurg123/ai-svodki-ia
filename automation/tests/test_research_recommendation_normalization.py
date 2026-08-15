from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from editorial_policy_runtime import (  # noqa: E402
    normalize_research_recommendations,
    wrap_research_sanitizer,
)


class ResearchRecommendationNormalizationTests(unittest.TestCase):
    def test_today_low_score_includes_are_downgraded_without_changing_scores(self) -> None:
        research = {
            "candidates": [
                {
                    "id": "cand-001",
                    "title": "Anthropic multi-agent safety research",
                    "significance_score": 1,
                    "recommendation": "include",
                },
                {
                    "id": "cand-004",
                    "title": "OpenAI Ultrafast preview",
                    "significance_score": 1,
                    "recommendation": "include",
                },
            ]
        }
        facts_before = [copy.deepcopy(item) for item in research["candidates"]]

        changes = normalize_research_recommendations(research)

        self.assertEqual(
            [item["recommendation"] for item in research["candidates"]],
            ["consider", "consider"],
        )
        self.assertEqual(
            [item["significance_score"] for item in research["candidates"]],
            [1, 1],
        )
        self.assertEqual(
            [item["candidate_id"] for item in changes],
            ["cand-001", "cand-004"],
        )
        for before, after in zip(facts_before, research["candidates"], strict=True):
            before.pop("recommendation")
            after_without_recommendation = copy.deepcopy(after)
            after_without_recommendation.pop("recommendation")
            self.assertEqual(after_without_recommendation, before)

    def test_valid_recommendations_are_untouched(self) -> None:
        research = {
            "candidates": [
                {"id": "cand-001", "significance_score": 3, "recommendation": "include"},
                {"id": "cand-002", "significance_score": 1, "recommendation": "consider"},
                {"id": "cand-003", "significance_score": 1, "recommendation": "exclude"},
            ]
        }
        before = copy.deepcopy(research)

        self.assertEqual(normalize_research_recommendations(research), [])
        self.assertEqual(research, before)

    def test_wrapper_repairs_production_shaped_result_before_legacy_validation(self) -> None:
        original_input = {
            "candidates": [
                {"id": "cand-001", "significance_score": 1, "recommendation": "include"},
                {"id": "cand-002", "significance_score": 3, "recommendation": "consider"},
                {"id": "cand-004", "significance_score": 1, "recommendation": "include"},
            ]
        }

        def original(research: dict, *args, **kwargs):
            del args, kwargs
            return copy.deepcopy(research), [], ["existing warning"]

        wrapped = wrap_research_sanitizer(original)
        sanitized, filtered, warnings = wrapped(original_input)

        self.assertEqual(filtered, [])
        self.assertEqual(original_input["candidates"][0]["recommendation"], "include")
        self.assertEqual(sanitized["candidates"][0]["recommendation"], "consider")
        self.assertEqual(sanitized["candidates"][1]["recommendation"], "consider")
        self.assertEqual(sanitized["candidates"][2]["recommendation"], "consider")
        self.assertTrue(any("include→consider" in warning for warning in warnings))
        violations = [
            item
            for item in sanitized["candidates"]
            if item.get("recommendation") == "include"
            and isinstance(item.get("significance_score"), int)
            and item["significance_score"] < 3
        ]
        self.assertEqual(violations, [])

    def test_wrapper_preserves_unrelated_validator_failures(self) -> None:
        research = {
            "candidates": [
                {
                    "id": "cand-001",
                    "significance_score": 1,
                    "recommendation": "include",
                    "verification_status": "unconfirmed",
                }
            ]
        }

        def original(payload: dict, *args, **kwargs):
            del args, kwargs
            return copy.deepcopy(payload), [], []

        sanitized, _filtered, _warnings = wrap_research_sanitizer(original)(research)
        self.assertEqual(sanitized["candidates"][0]["recommendation"], "consider")
        self.assertEqual(sanitized["candidates"][0]["verification_status"], "unconfirmed")

    def test_primary_prompt_declares_hard_cross_field_contract(self) -> None:
        prompt = (ROOT / "automation" / "prompts" / "primary_recall_pass.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("`recommendation=include` разрешён только при", prompt)
        self.assertIn("`significance_score >= 3`", prompt)
        self.assertIn("комбинация `include` + score 1–2 запрещена", prompt)


if __name__ == "__main__":
    unittest.main()
