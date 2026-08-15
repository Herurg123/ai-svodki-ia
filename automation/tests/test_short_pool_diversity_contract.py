from __future__ import annotations

import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from editorial_policy import validate_diversity_overrides  # noqa: E402

POLICY_PATH = ROOT / "automation" / "config" / "editorial.json"
PROMPT_PATH = ROOT / "automation" / "prompts" / "daily_digest.md"
SPEC_PATH = ROOT / "automation" / "specs" / "editorial-policy.md"
AUG15_CANDIDATES_PATH = ROOT / "automation" / "content" / "2026-08-15" / "candidates.json"


def _baseline_eligible(candidate: dict, policy: dict) -> bool:
    if candidate.get("recommendation") == "exclude":
        return False
    if candidate.get("verification_status") != policy["candidate_selection"][
        "verification_required_for_selection"
    ]:
        return False
    if candidate.get("freshness_status") not in policy["candidate_selection"][
        "allowed_freshness_for_selection"
    ]:
        return False

    if candidate.get("category") == policy["candidate_selection"]["legal_category"]:
        if candidate.get("legal_scale") != policy["candidate_selection"][
            "legal_scale_required_for_selection"
        ]:
            return False
        if int(candidate.get("significance_score", 0)) < int(
            policy["candidate_selection"]["legal_minimum_significance_score"]
        ):
            return False

    if candidate.get("category") == policy["candidate_selection"]["curiosity_category"]:
        if policy["candidate_selection"]["curiosity_requires_explicit_verification"]:
            if not candidate.get("curiosity_eligible"):
                return False

    return True


class ShortPoolDiversityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.prompt = PROMPT_PATH.read_text(encoding="utf-8")
        cls.spec = SPEC_PATH.read_text(encoding="utf-8")
        cls.aug15 = json.loads(AUG15_CANDIDATES_PATH.read_text(encoding="utf-8"))

    def test_machine_readable_policy_makes_soft_limits_advisory_for_short_pool(self) -> None:
        diversity = self.policy["diversity"]
        self.assertFalse(diversity["short_pool_soft_limits_may_reduce_selection"])
        self.assertEqual(diversity["max_selected_per_publisher_soft"], 2)
        self.assertTrue(diversity["override_requires_reason"])

        self.assertIn(
            "мягкие лимиты разнообразия издателей и организаций\nне могут сами по себе уменьшать число выбранных сюжетов",
            self.prompt,
        )
        self.assertIn(
            "soft publisher/organization limit не может сам по себе уменьшать selection",
            self.spec,
        )

    def test_real_aug15_pool_hits_short_pool_publisher_pressure_case(self) -> None:
        candidates = [
            item for item in self.aug15["candidates"] if _baseline_eligible(item, self.policy)
        ]
        target = int(self.policy["story_counts"]["total_target_minimum"])
        publisher_counts = Counter(
            str(item["primary_source"]["publisher"]).casefold() for item in candidates
        )

        self.assertEqual(len(candidates), 5)
        self.assertLess(len(candidates), target)
        self.assertEqual(publisher_counts["techcrunch"], 4)
        self.assertGreater(
            publisher_counts["techcrunch"],
            int(self.policy["diversity"]["max_selected_per_publisher_soft"]),
        )

        google = next(item for item in candidates if item["id"] == "cand-004")
        self.assertEqual(google["organization"], "Google; Gemini; Flow")
        self.assertEqual(google["recommendation"], "consider")
        self.assertEqual(google["verification_status"], "verified")
        self.assertEqual(google["freshness_status"], "new_event")
        self.assertEqual(google["significance_score"], 2)

    def test_diversity_override_is_still_required_when_soft_cap_is_exceeded(self) -> None:
        selected = [
            item
            for item in self.aug15["candidates"]
            if item["id"] in {"cand-001", "cand-002", "cand-003", "cand-004"}
        ]

        errors_without_override = validate_diversity_overrides(
            selected,
            [],
            self.policy,
        )
        self.assertTrue(
            any("techcrunch" in error.casefold() for error in errors_without_override)
        )

        errors_with_override = validate_diversity_overrides(
            selected,
            [
                {
                    "type": "publisher",
                    "value": "TechCrunch",
                    "reason": (
                        "Короткий достойный пул: четыре независимых подтверждённых "
                        "события одного издателя сохраняются без искусственного отсева."
                    ),
                }
            ],
            self.policy,
        )
        self.assertEqual(errors_with_override, [])

    def test_normal_size_pool_keeps_existing_diversity_balancing_role(self) -> None:
        self.assertIn(
            "Для пула,\nкоторый позволяет выбрать обычные 7–12 сюжетов, применяй мягкие цели как обычно",
            self.prompt,
        )
        self.assertIn(
            "Для пула, который позволяет выбрать обычные 7–12 сюжетов, мягкие лимиты\nприменяются как балансирующий фактор",
            self.spec,
        )


if __name__ == "__main__":
    unittest.main()
