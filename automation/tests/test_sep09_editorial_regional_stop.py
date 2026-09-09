from __future__ import annotations

import copy
import json
import sys
import types
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation/scripts"))
if "openai" not in sys.modules:
    stub = types.ModuleType("openai")
    stub.OpenAI = object
    sys.modules["openai"] = stub

import generate_digest_preview as generator  # noqa: E402
from editorial_policy_runtime import (  # noqa: E402
    patch_editorial_policy,
    patch_editorial_source_validation,
)


class Sep09EditorialRegionalStopTests(unittest.TestCase):
    def setUp(self) -> None:
        fixture = ROOT / "automation/fixtures/recall/2026-09-09-editorial-regional-stop.json"
        self.saved = json.loads(fixture.read_text(encoding="utf-8"))
        self.research = self.saved["research"]
        self.editorial = self.saved["editorial"]
        self.policy = json.loads((ROOT / "automation/config/editorial.json").read_text())
        patch_editorial_policy(generator)
        patch_editorial_source_validation(generator)

    def validate(self):
        return generator.validate_editorial(
            self.editorial, self.research, date(2026, 9, 9),
            self.saved["site_config"], self.saved["archive"], self.policy, 7, 12,
        )

    def test_saved_seven_story_editorial_passes_without_inserting_weak_lead(self):
        before = copy.deepcopy((self.research, self.editorial))
        errors, warnings, stories = self.validate()
        self.assertEqual(errors, [])
        self.assertEqual(len(stories), 7)
        self.assertEqual((self.research, self.editorial), before)
        self.assertTrue(any("cand-008" in warning for warning in warnings))
        self.assertNotIn("Российские лидеры ИИ", self.editorial["digest"]["article_html"])

    def test_preliminary_include_or_consider_does_not_create_regional_quota(self):
        for recommendation in ("include", "consider"):
            for score in (3, 4, 5):
                with self.subTest(recommendation=recommendation, score=score):
                    self.research["candidates"][-1].update(
                        recommendation=recommendation, significance_score=score,
                    )
                    self.assertEqual(self.validate()[0], [])

    def test_weak_or_excluded_lead_does_not_trigger_regional_warning(self):
        for recommendation, score in (("exclude", 3), ("consider", 2)):
            with self.subTest(recommendation=recommendation, score=score):
                self.research["candidates"][-1].update(
                    recommendation=recommendation, significance_score=score,
                )
                errors, warnings, _ = self.validate()
                self.assertEqual(errors, [])
                self.assertFalse(any("региональная квота" in warning for warning in warnings))

    def test_selected_russian_story_still_requires_its_section(self):
        self.research["candidates"][0]["geography"] = "russia"
        errors, _, _ = self.validate()
        self.assertTrue(any("российские сюжеты" in error for error in errors), errors)

    def test_selected_excluded_candidate_still_fails(self):
        self.research["candidates"][0]["recommendation"] = "exclude"
        self.assertTrue(any("recommendation exclude" in error for error in self.validate()[0]))

    def test_unassigned_candidate_still_fails(self):
        self.editorial["excluded_candidate_ids"] = []
        self.assertTrue(any("Не все кандидаты" in error for error in self.validate()[0]))

    def test_unknown_candidate_still_fails(self):
        self.editorial["selected_candidate_ids"].append("unknown")
        self.assertTrue(any("неизвестные candidate ID" in error for error in self.validate()[0]))

    def test_no_selected_story_still_fails(self):
        self.editorial["selected_candidate_ids"] = []
        self.editorial["excluded_candidate_ids"] = [c["id"] for c in self.research["candidates"]]
        self.assertTrue(any("ни одного достойного" in error for error in self.validate()[0]))

    def test_missing_diversity_override_still_fails(self):
        self.editorial["diversity_overrides"] = []
        self.assertTrue(any("diversity override" in error for error in self.validate()[0]))

    def test_unknown_article_source_still_fails(self):
        self.editorial["digest"]["article_html"] = self.editorial["digest"]["article_html"].replace(
            "https://cognition.com/blog/series-e", "https://unrelated.example/not-a-source",
        )
        self.assertTrue(self.validate()[0])


if __name__ == "__main__":
    unittest.main()
