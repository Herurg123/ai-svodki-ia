from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import primary_recall_search as prs


def candidate(title: str, category: str = "models", *, url: str | None = None) -> dict:
    url = url or f"https://example.com/{title.lower().replace(' ', '-')}"
    return {
        "title": title,
        "organization": title.split()[0],
        "published_date": "2026-08-10",
        "published_at": None,
        "time_precision": "date",
        "topic": title,
        "event_type": "product_update",
        "keywords": [title.lower(), "ai"],
        "geography": "world",
        "category": category,
        "source_type": "news_agency",
        "primary_source": {
            "title": title,
            "publisher": "Example News",
            "url": url,
        },
        "supporting_sources": [],
        "event_summary": f"Verified event about {title}.",
        "verified_facts": ["Fact one", "Fact two"],
        "significance": "Material AI development.",
        "significance_score": 4,
        "limitations": "",
        "archive_status": "none",
        "archive_reason": "No matching archive story.",
        "recommendation": "consider",
        "verification_status": "verified",
        "verification_notes": "Verified against source.",
        "freshness_status": "new_event",
        "freshness_reason": "Published inside the current window.",
        "legal_scale": "not_applicable",
        "legal_scale_reason": "",
        "curiosity_eligible": False,
        "curiosity_verification": "",
    }


def search_window() -> dict:
    return {
        "start_at": "2026-08-08T02:48:25+03:00",
        "end_at": "2026-08-11T02:50:46+03:00",
        "latest_archive_at": "2026-08-08T06:00:00+03:00",
        "start_date": "2026-08-08",
        "end_date": "2026-08-11",
        "latest_archive_date": "2026-08-08",
    }


def metadata(direction_id: str) -> dict:
    return {
        "status": "completed",
        "web_search_calls_completed": 1,
        "web_search_call_items_total": 1,
        "actual_queries": [direction_id],
        "consulted_sources": [{"url": "https://example.com"}],
    }


class PrimaryRecallSearchTests(unittest.TestCase):
    def test_matrix_has_exactly_twelve_fixed_unique_directions(self):
        ids = [item["id"] for item in prs.PRIMARY_DIRECTIONS]
        self.assertEqual(len(ids), 12)
        self.assertEqual(len(set(ids)), 12)
        self.assertEqual(ids[-1], "independent_missing_events")
        self.assertIn("china_asia_models", ids)
        self.assertIn("china_asia_integrations", ids)

    def test_prompt_is_discovery_first_and_one_search_only(self):
        template = prs.PROMPT_PATH.read_text(encoding="utf-8")
        prompt = prs.build_prompt(
            template,
            publication_date="2026-08-11",
            search_window=search_window(),
            direction=prs.PRIMARY_DIRECTIONS[6],
            existing_candidates=[],
            archive={"items": []},
        )
        self.assertIn("discovery-first", prompt)
        self.assertIn("РОВНО ОДИН Web Search", prompt)
        self.assertIn("2026-08-11T02:50:46+03:00", prompt)
        self.assertIn("product integrations", prs.PRIMARY_DIRECTIONS[6]["label"].lower())

    def test_all_twelve_passes_run_once_and_final_pass_sees_existing_pool(self):
        seen: list[str] = []
        final_prompt = ""

        def request_fn(**kwargs):
            nonlocal final_prompt
            direction = kwargs["direction_id"]
            seen.append(direction)
            if direction == "global_breaking":
                rows = [candidate("Alpha Model")]
            else:
                rows = []
            if direction == "independent_missing_events":
                final_prompt = kwargs["prompt"]
            return (
                {
                    "status": "complete" if rows else "complete_with_gaps",
                    "error_message": None,
                    "direction_id": direction,
                    "candidates": rows,
                    "rejections": [],
                    "notes": "Checked.",
                },
                metadata(direction),
            )

        research, report = prs.run_primary_recall_matrix(
            publication_date="2026-08-11",
            search_window=search_window(),
            archive={"items": []},
            api_key="test-key",
            model="test-model",
            maximum_candidates=20,
            search_runner=request_fn,
        )
        self.assertEqual(seen, [item["id"] for item in prs.PRIMARY_DIRECTIONS])
        self.assertEqual(report["search_budget"]["completed_calls"], 12)
        self.assertEqual(len(research["coverage"]), 12)
        self.assertEqual(len(research["candidates"]), 1)
        self.assertIn("Alpha Model", final_prompt)

    def test_mandatory_pass_failure_is_fail_closed(self):
        calls = 0

        def request_fn(**kwargs):
            nonlocal calls
            calls += 1
            if kwargs["direction_id"] == "china_asia_models":
                raise RuntimeError("search transport failed")
            return (
                {
                    "status": "complete_with_gaps",
                    "error_message": None,
                    "direction_id": kwargs["direction_id"],
                    "candidates": [],
                    "rejections": [],
                    "notes": "Checked.",
                },
                metadata(kwargs["direction_id"]),
            )

        with self.assertRaises(prs.PrimaryRecallResponseError) as ctx:
            prs.run_primary_recall_matrix(
                publication_date="2026-08-11",
                search_window=search_window(),
                archive={"items": []},
                api_key="test-key",
                model="test-model",
                search_runner=request_fn,
            )
        self.assertIn("china_asia_models", str(ctx.exception))
        self.assertLess(calls, 12)

    def test_august_11_fixture_preserves_control_events(self):
        fixture_path = ROOT / "automation" / "fixtures" / "recall" / "2026-08-11.json"
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        must_ids = {item["id"] for item in payload["must_discover"]}
        should_ids = {item["id"] for item in payload["should_discover"]}
        self.assertEqual(len(must_ids), 4)
        self.assertEqual(len(should_ids), 2)
        self.assertIn("apple-alibaba-qwen-china-integration", must_ids)
        self.assertEqual(
            payload["experiment_result"]["refined_matrix_with_separate_china_integrations"],
            "6_of_6_control_events",
        )


if __name__ == "__main__":
    unittest.main()
