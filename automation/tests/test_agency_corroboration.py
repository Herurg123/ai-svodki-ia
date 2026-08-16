from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runtime = load_module("agency_corroboration_runtime", SCRIPTS / "ensure_story_coverage.py")
policy = runtime._policy


def candidate(
    cid: str,
    organization: str,
    event_type: str,
    score: int,
    *,
    category: str = "investment",
    primary_url: str = "https://techcrunch.com/2026/08/13/example/",
    keywords: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": cid,
        "title": f"{organization} event",
        "organization": organization,
        "published_date": "2026-08-13",
        "published_at": "2026-08-13T12:00:00+00:00",
        "time_precision": "datetime",
        "topic": "AI",
        "event_type": event_type,
        "keywords": keywords or [organization, event_type, "valuation"],
        "geography": "world",
        "category": category,
        "source_type": "technology_media",
        "primary_source": {"title": "Original", "publisher": "TechCrunch", "url": primary_url},
        "supporting_sources": [],
        "event_summary": "Fresh event.",
        "verified_facts": ["Fact one.", "Fact two."],
        "significance": "Major event.",
        "significance_score": score,
        "limitations": "",
        "archive_status": "none",
        "archive_reason": "Not in archive.",
        "recommendation": "include",
        "verification_status": "verified",
        "verification_notes": "Initial verification.",
        "freshness_status": "new_event",
        "freshness_reason": "Inside window.",
        "legal_scale": "not_applicable",
        "legal_scale_reason": "",
        "curiosity_eligible": False,
        "curiosity_verification": "",
    }


class AgencyCorroborationTests(unittest.TestCase):
    def test_target_selection_prefers_high_score_funding_over_partnership(self):
        pool = [
            candidate("cand-001", "Anthropic", "research publication", 5, category="security"),
            candidate("cand-003", "Databricks", "funding", 5),
            candidate("cand-004", "IBM; OpenAI", "partnership", 5, category="enterprise"),
            candidate("cand-005", "Thrive Holdings", "funding", 4),
        ]
        target = runtime._select_agency_corroboration_target(pool)
        self.assertIsNotNone(target)
        self.assertEqual(target["id"], "cand-003")

    def test_target_selection_treats_acquisition_closed_as_acquisition_family(self):
        pool = [
            candidate(
                "cand-001",
                "SpaceX; Cursor",
                "acquisition_closed",
                4,
                category="investment",
            ),
            candidate(
                "cand-002",
                "Kog",
                "model_release",
                2,
                category="infrastructure",
            ),
        ]
        target = runtime._select_agency_corroboration_target(pool)
        self.assertIsNotNone(target)
        self.assertEqual(target["id"], "cand-001")

    def test_rerun_editorial_preserves_child_output_on_failure(self):
        import contextlib
        import io
        import subprocess
        from types import SimpleNamespace
        from unittest import mock

        fake = SimpleNamespace(returncode=7, stdout="exact editorial failure\n")
        research_path = policy.REPOSITORY_ROOT / "automation/fixtures/research/.coverage-audit-test.json"
        stream = io.StringIO()
        with mock.patch.object(policy.subprocess, "run", return_value=fake):
            with contextlib.redirect_stdout(stream):
                with self.assertRaises(subprocess.CalledProcessError) as raised:
                    policy.rerun_editorial(
                        publication_date="2026-08-16",
                        merged_research_path=research_path,
                        minimum_total=7,
                        maximum_candidates=20,
                        maximum_selected_stories=12,
                    )
        self.assertEqual(raised.exception.output, "exact editorial failure\n")
        self.assertIn("exact editorial failure", stream.getvalue())

    def test_databricks_query_is_short_date_free_and_adaptive(self):
        target = candidate(
            "cand-003",
            "Databricks",
            "funding",
            5,
            keywords=["Databricks", "funding", "valuation", "enterprise AI"],
        )
        target["title"] = "Databricks раскрыла раунд на $5 млрд при оценке $190 млрд"
        self.assertEqual(runtime._money_anchors(target), ["$5 billion", "$190 billion"])
        self.assertEqual(
            runtime._agency_corroboration_query(target),
            "Databricks $5 billion $190 billion",
        )
        self.assertNotIn("2026", runtime._agency_corroboration_query(target))

    def test_same_event_guard_requires_org_event_and_date(self):
        target = candidate("cand-003", "Databricks", "funding", 5)
        confirmed = copy.deepcopy(target)
        confirmed["primary_source"] = {
            "title": "Reuters confirmation",
            "publisher": "Reuters",
            "url": "https://www.reuters.com/business/databricks-funding-2026-08-13/",
        }
        self.assertTrue(runtime._same_event_for_corroboration(target, confirmed))
        wrong = copy.deepcopy(confirmed)
        wrong["organization"] = "Another Company"
        self.assertFalse(runtime._same_event_for_corroboration(target, wrong))
        wrong = copy.deepcopy(confirmed)
        wrong["published_date"] = "2026-08-12"
        self.assertFalse(runtime._same_event_for_corroboration(target, wrong))

    def test_source_promotion_replaces_primary_without_duplicating_event(self):
        target = candidate("cand-003", "Databricks", "funding", 5)
        research = {"search_window": {}, "candidates": [target]}
        corroboration = copy.deepcopy(target)
        corroboration["corroboration_target_id"] = "cand-003"
        corroboration["audit_direction"] = "agency_rescue"
        corroboration["source_type"] = "news_agency"
        corroboration["primary_source"] = {
            "title": "Databricks raises $5 billion",
            "publisher": "Reuters",
            "url": "https://www.reuters.com/technology/databricks-raises-5-billion-2026-08-13/",
        }
        merged, details, remaining = policy.apply_agency_corroborations(
            research, [corroboration]
        )
        self.assertEqual(len(merged["candidates"]), 1)
        promoted = merged["candidates"][0]
        self.assertEqual(promoted["id"], "cand-003")
        self.assertEqual(promoted["primary_source"]["publisher"], "Reuters")
        self.assertEqual(promoted["supporting_sources"][0]["publisher"], "TechCrunch")
        self.assertEqual(promoted["source_type"], "news_agency")
        self.assertEqual(len(details), 1)
        self.assertEqual(remaining, [])

    def test_non_corroboration_candidate_is_left_for_normal_merge(self):
        research = {"candidates": [candidate("cand-003", "Databricks", "funding", 5)]}
        ordinary = candidate("", "Other", "funding", 4)
        ordinary.pop("id")
        merged, details, remaining = policy.apply_agency_corroborations(research, [ordinary])
        self.assertEqual(len(merged["candidates"]), 1)
        self.assertEqual(details, [])
        self.assertEqual(remaining, [ordinary])


    def test_post_cutoff_same_day_agency_candidate_fails_closed(self):
        item = candidate("cand-003", "Databricks", "funding", 5)
        item["published_date"] = "2026-08-14"
        item["published_at"] = "2026-08-14T12:00:00+03:00"
        item["time_precision"] = "datetime"
        item["primary_source"] = {
            "title": "Reuters confirmation",
            "publisher": "Reuters",
            "url": "https://www.reuters.com/technology/databricks-2026-08-14/",
        }
        window = {
            "start_at": "2026-08-12T02:58:08+03:00",
            "end_at": "2026-08-14T07:36:56+03:00",
        }
        self.assertFalse(policy._candidate_has_fresh_agency_source(item, window))
        item["published_at"] = "2026-08-14T06:00:00+03:00"
        self.assertTrue(policy._candidate_has_fresh_agency_source(item, window))

    def test_cutoff_day_date_only_agency_candidate_fails_closed(self):
        item = candidate("cand-003", "Databricks", "funding", 5)
        item["primary_source"] = {
            "title": "Reuters confirmation",
            "publisher": "Reuters",
            "url": "https://www.reuters.com/technology/databricks-2026-08-14/",
        }
        item["time_precision"] = "date"
        item["published_at"] = None
        window = {
            "start_at": "2026-08-12T02:58:08+03:00",
            "end_at": "2026-08-14T07:36:56+03:00",
        }
        item["published_date"] = "2026-08-14"
        self.assertFalse(policy._candidate_has_fresh_agency_source(item, window))
        item["published_date"] = "2026-08-12"
        self.assertTrue(policy._candidate_has_fresh_agency_source(item, window))

if __name__ == "__main__":
    unittest.main()
