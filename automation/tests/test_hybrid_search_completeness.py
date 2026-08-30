from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import hybrid_search_completeness as hc
from story_coverage import write_json


def candidate(
    title: str,
    category: str,
    *,
    geography: str = "world",
    url: str | None = None,
) -> dict:
    url = url or f"https://example.com/{title.lower().replace(' ', '-')}"
    return {
        "title": title,
        "organization": title.split()[0],
        "published_date": "2026-08-08",
        "published_at": None,
        "time_precision": "date",
        "topic": title,
        "event_type": "product_update",
        "keywords": [title.lower(), "ai"],
        "geography": geography,
        "category": category,
        "source_type": "news_agency",
        "primary_source": {"title": title, "publisher": "Example News", "url": url},
        "supporting_sources": [],
        "event_summary": f"Verified event about {title}.",
        "verified_facts": ["Fact one", "Fact two"],
        "significance": "Material AI development.",
        "significance_score": 4,
        "limitations": "",
        "archive_status": "none",
        "archive_reason": "No matching archive story.",
        "recommendation": "include",
        "verification_status": "verified",
        "verification_notes": "Verified against source.",
        "freshness_status": "new_event",
        "freshness_reason": "Published inside the current window.",
        "legal_scale": "not_applicable",
        "legal_scale_reason": "",
        "curiosity_eligible": False,
        "curiosity_verification": "",
    }


def research(candidates: list[dict]) -> dict:
    rows = []
    for index, item in enumerate(candidates, start=1):
        value = dict(item)
        value["id"] = f"cand-{index:03d}"
        rows.append(value)
    return {
        "status": "ok",
        "error_message": None,
        "publication_date": "2026-08-09",
        "search_window": {
            "start_at": "2026-08-08T03:00:00+03:00",
            "end_at": "2026-08-09T02:00:00+03:00",
            "latest_archive_at": "2026-08-08T03:00:00+03:00",
            "start_date": "2026-08-08",
            "end_date": "2026-08-09",
            "latest_archive_date": "2026-08-08",
        },
        "coverage": [],
        "candidates": rows,
        "rejected_as_duplicates": [],
        "research_notes": "test",
    }


def metadata(query: str) -> dict:
    return {
        "status": "completed",
        "web_search_calls_completed": 1,
        "web_search_call_items_total": 3,
        "web_search_navigation_items_total": 2,
        "actual_queries": [query],
        "consulted_sources": [{"url": "https://example.com"}],
    }


class HybridSearchCompletenessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.artifact_dir = root / "artifact"
        self.output_root = root / "production"
        self.archive_path = root / "archive.json"
        self.artifact_dir.mkdir(parents=True)
        write_json(self.archive_path, {"items": []})

        self.old_rescue = hc.run_agency_discovery_rescue
        self.old_pulse = hc.run_source_pulse_shadow
        hc.run_agency_discovery_rescue = lambda **kwargs: {
            "version": 5,
            "search_strategy": "agency_discovery_rescue",
            "publication_date": "2026-08-09",
            "triggered": False,
            "executed": False,
            "state": "not_triggered",
            "status": "complete",
            "search_operation_count_contribution": 0,
            "added_count": 0,
            "accepted_count": 0,
        }
        hc.run_source_pulse_shadow = lambda **kwargs: {
            "version": 1,
            "strategy": "source_pulse_shadow",
            "publication_date": "2026-08-09",
            "state": "reused_snapshot",
            "status": "complete_with_gaps",
            "fusion": {"summary": {"pulse_only_count": 0, "both_count": 0}},
            "promotion": {"promoted_count": 0},
            "paid_api_calls": 0,
            "web_search_operations": 0,
        }

        # This suite is part of Main CI's offline contract. Fail immediately if a
        # future orchestration change leaks DNS or HTTPS through these unit tests.
        self.network_patchers = (
            patch(
                "socket.getaddrinfo",
                side_effect=AssertionError("offline Hybrid unit test attempted DNS"),
            ),
            patch(
                "socket.create_connection",
                side_effect=AssertionError("offline Hybrid unit test attempted network I/O"),
            ),
        )
        for patcher in self.network_patchers:
            patcher.start()

    def tearDown(self):
        hc.run_agency_discovery_rescue = self.old_rescue
        hc.run_source_pulse_shadow = self.old_pulse
        hc._sync_compatibility_hooks()
        for patcher in reversed(self.network_patchers):
            patcher.stop()
        self.tmp.cleanup()

    def _run(self, base_candidates, request_fn):
        write_json(self.artifact_dir / "candidates.json", research(base_candidates))
        return hc.run_hybrid_completeness(
            artifact_dir=self.artifact_dir,
            archive_path=self.archive_path,
            publication_date="2026-08-09",
            api_key="test-key",
            model="test-model",
            request_fn=request_fn,
            output_root=self.output_root,
        )

    def test_three_fixed_passes_are_the_normal_budget(self):
        base = [
            candidate("Model Alpha", "models"),
            candidate("Chip Beta", "chips"),
            candidate("Safety Gamma", "security"),
        ]
        seen: list[str] = []

        def request_fn(**kwargs):
            seen.append(kwargs["direction_id"])
            return (
                {
                    "status": "complete_with_gaps",
                    "error_message": None,
                    "direction_id": kwargs["direction_id"],
                    "candidates": [],
                    "rejections": [],
                    "notes": "No additional event.",
                },
                metadata(kwargs["direction_id"]),
            )

        report = self._run(base, request_fn)
        self.assertEqual(seen, [item["id"] for item in hc.COMPLETENESS_DIRECTIONS])
        self.assertFalse(report["adaptive_needed"])
        self.assertEqual(report["search_budget"]["completed_calls"], 3)
        self.assertEqual(report["search_budget"]["maximum_calls"], 4)
        self.assertGreater(report["search_budget"]["maximum_total_tool_calls_per_pass"], 1)

    def test_one_adaptive_pass_is_used_only_for_an_obvious_gap(self):
        base = [candidate("Model Alpha", "models")]
        seen: list[str] = []

        def request_fn(**kwargs):
            seen.append(kwargs["direction_id"])
            return (
                {
                    "status": "complete_with_gaps",
                    "error_message": None,
                    "direction_id": kwargs["direction_id"],
                    "candidates": [],
                    "rejections": [],
                    "notes": "No additional event.",
                },
                metadata(kwargs["direction_id"]),
            )

        report = self._run(base, request_fn)
        self.assertEqual(len(seen), 4)
        self.assertEqual(seen[-1], hc.ADAPTIVE_DIRECTION_ID)
        self.assertTrue(report["adaptive_needed"])
        self.assertEqual(report["search_budget"]["completed_calls"], 4)
        self.assertIn("infrastructure_business", report["missing_clusters_after_fixed"])
        self.assertIn("safety_policy_regions", report["missing_clusters_after_fixed"])

    def test_new_candidates_are_merged_without_replacing_primary(self):
        base = [candidate("Model Alpha", "models")]

        def request_fn(**kwargs):
            direction = kwargs["direction_id"]
            extra = []
            if direction == "infrastructure_business":
                extra = [candidate("Chip Delta", "chips")]
            elif direction == "safety_policy_regions":
                extra = [candidate("Safety Epsilon", "security")]
            return (
                {
                    "status": "complete",
                    "error_message": None,
                    "direction_id": direction,
                    "candidates": extra,
                    "rejections": [],
                    "notes": "Checked.",
                },
                metadata(direction),
            )

        report = self._run(base, request_fn)
        self.assertEqual(report["primary_candidate_count"], 1)
        self.assertEqual(len(report["accepted_candidates"]), 2)
        self.assertEqual(report["final_candidate_count"], 3)
        self.assertFalse(report["adaptive_needed"])
        self.assertTrue(report["editorial_rerun_needed"])
        runtime_path = Path(report["merged_research_path"])
        diagnostic_path = Path(report["diagnostic_merged_research_path"])
        self.assertTrue(runtime_path.is_file())
        self.assertTrue(diagnostic_path.is_file())
        self.assertEqual(runtime_path.parent.name, ".runtime")
        self.assertNotEqual(runtime_path, diagnostic_path)

    def test_prompt_uses_authoritative_window_one_search_and_navigation(self):
        payload = research([])
        prompt = hc.build_prompt(
            publication_date="2026-08-09",
            search_window=payload["search_window"],
            direction_id="models_products_research",
            direction_label="Models",
            direction_guidance="Find major model news.",
            existing_candidates=[],
            archive={"items": []},
        )
        self.assertIn("2026-08-09T02:00:00+03:00", prompt)
        self.assertIn("РОВНО ОДНУ поисковую операцию Web Search", prompt)
        self.assertIn("open_page", prompt)
        self.assertIn("find_in_page", prompt)
        self.assertIn("6–18 значимых слов", prompt)
        self.assertIn("date-free natural-language", prompt)
        self.assertIn("latest / recent / current / breaking", prompt)
        self.assertIn("Не добавляй в query календарные даты", prompt)
        self.assertNotIn("предпочтительная retrieval-подсказка: after:", prompt)
        self.assertIn("API domain filter отсутствует", prompt)

    def test_generic_other_does_not_close_safety_policy_region_gap(self):
        counts = hc.cluster_counts([candidate("Misc Zeta", "other")])
        self.assertEqual(counts["safety_policy_regions"], 0)

    def test_budget_cannot_be_configured_above_four(self):
        write_json(self.artifact_dir / "candidates.json", research([]))
        seen = []

        def request_fn(**kwargs):
            seen.append(kwargs["direction_id"])
            return (
                {
                    "status": "complete_with_gaps",
                    "error_message": None,
                    "direction_id": kwargs["direction_id"],
                    "candidates": [],
                    "rejections": [],
                    "notes": "No event.",
                },
                metadata(kwargs["direction_id"]),
            )

        report = hc.run_hybrid_completeness(
            artifact_dir=self.artifact_dir,
            archive_path=self.archive_path,
            publication_date="2026-08-09",
            api_key="test-key",
            model="test-model",
            maximum_search_calls=99,
            request_fn=request_fn,
            output_root=self.output_root,
        )
        self.assertEqual(report["search_budget"]["maximum_calls"], 4)
        self.assertLessEqual(len(seen), 4)


if __name__ == "__main__":
    unittest.main()