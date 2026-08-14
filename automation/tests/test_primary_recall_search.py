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
        "start_at": "2026-08-10T02:50:46+03:00",
        "end_at": "2026-08-12T02:59:49+03:00",
        "latest_archive_at": "2026-08-11T02:50:46+03:00",
        "start_date": "2026-08-10",
        "end_date": "2026-08-12",
        "latest_archive_date": "2026-08-11",
    }


def metadata(direction_id: str) -> dict:
    return {
        "status": "completed",
        "web_search_calls_completed": 1,
        "web_search_call_items_total": 3,
        "web_search_navigation_items_total": 2,
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

    def test_prompt_is_discovery_first_fresh_and_navigation_aware(self):
        template = prs.PROMPT_PATH.read_text(encoding="utf-8")
        prompt = prs.build_prompt(
            template,
            publication_date="2026-08-12",
            search_window=search_window(),
            direction=prs.PRIMARY_DIRECTIONS[6],
            existing_candidates=[],
            archive={"items": []},
        )
        self.assertIn("discovery-first", prompt)
        self.assertIn("РОВНО ОДНУ поисковую операцию Web Search", prompt)
        self.assertIn("open_page", prompt)
        self.assertIn("find_in_page", prompt)
        self.assertIn("after:", prompt)
        self.assertIn("before:", prompt)
        self.assertIn("2026-08-12T02:59:49+03:00", prompt)
        label = prs.PRIMARY_DIRECTIONS[6]["label"].lower()
        self.assertIn("integrations", label)
        self.assertIn("partnerships", label)

    def test_broad_safety_nets_are_source_neutral_and_agency_route_is_additive(self):
        directions = {item["id"]: item for item in prs.PRIMARY_DIRECTIONS}
        self.assertEqual(tuple(directions["global_breaking"].get("allowed_domains") or ()), ())
        self.assertEqual(
            tuple(directions["major_agencies"].get("allowed_domains") or ()),
            prs.BLOOMBERG_FT_DOMAINS,
        )
        self.assertEqual(tuple(directions["independent_missing_events"].get("allowed_domains") or ()), ())
        self.assertEqual(
            set(prs.AGENCY_DOMAINS),
            set(prs.REUTERS_DOMAINS + prs.BLOOMBERG_FT_DOMAINS + prs.AP_DOMAINS),
        )

    def test_all_twelve_passes_run_once_and_final_pass_sees_existing_pool(self):
        seen: list[str] = []
        seen_domains: dict[str, tuple[str, ...]] = {}
        final_prompt = ""

        def request_fn(**kwargs):
            nonlocal final_prompt
            direction = kwargs["direction_id"]
            seen.append(direction)
            seen_domains[direction] = tuple(kwargs.get("allowed_domains") or ())
            rows = [candidate("Alpha Model")] if direction == "global_breaking" else []
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
            publication_date="2026-08-12",
            search_window=search_window(),
            archive={"items": []},
            api_key="test-key",
            model="test-model",
            maximum_candidates=20,
            search_runner=request_fn,
        )
        self.assertEqual(seen, [item["id"] for item in prs.PRIMARY_DIRECTIONS])
        self.assertEqual(report["search_budget"]["completed_calls"], 12)
        self.assertEqual(report["search_budget"]["search_operations_per_pass"], 1)
        self.assertGreater(report["search_budget"]["maximum_total_tool_calls_per_pass"], 1)
        self.assertEqual(len(research["coverage"]), 12)
        self.assertEqual(len(research["candidates"]), 1)
        self.assertIn("Alpha Model", final_prompt)
        self.assertEqual(seen_domains["global_breaking"], ())
        self.assertEqual(seen_domains["major_agencies"], prs.BLOOMBERG_FT_DOMAINS)
        self.assertEqual(seen_domains["independent_missing_events"], ())
        self.assertEqual(seen_domains["models_products_agents"], ())

    def test_final_candidate_cap_cannot_starve_late_direction(self):
        early_ids = {item["id"] for item in prs.PRIMARY_DIRECTIONS[:5]}

        def request_fn(**kwargs):
            direction = kwargs["direction_id"]
            if direction in early_ids:
                rows = [candidate(f"{direction} Story {index}") for index in range(1, 5)]
            elif direction == "china_asia_integrations":
                rows = [candidate("Qwen China Integration")]
            else:
                rows = []
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
            publication_date="2026-08-12",
            search_window=search_window(),
            archive={"items": []},
            api_key="test-key",
            model="test-model",
            maximum_candidates=20,
            search_runner=request_fn,
        )
        titles = {item["title"] for item in research["candidates"]}
        self.assertEqual(report["validated_unique_candidate_count"], 21)
        self.assertEqual(len(research["candidates"]), 20)
        self.assertIn("Qwen China Integration", titles)
        self.assertTrue(report["candidate_budget"]["cap_applied_after_all_passes"])
        self.assertEqual(len(report["final_cap_dropped"]), 1)

    def test_exact_archive_source_url_is_rejected_even_inside_overlap(self):
        already_published = "https://example.com/already-published"
        archive = {
            "items": [
                {
                    "date": "2026-08-11",
                    "source_urls": [already_published],
                    "stories": [],
                }
            ]
        }

        def request_fn(**kwargs):
            direction = kwargs["direction_id"]
            rows = [candidate("Already Published", url=already_published)] if direction == "global_breaking" else []
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
            publication_date="2026-08-12",
            search_window=search_window(),
            archive=archive,
            api_key="test-key",
            model="test-model",
            search_runner=request_fn,
        )
        self.assertEqual(research["candidates"], [])
        self.assertTrue(
            any(
                "уже опубликован" in " ".join(item.get("errors", []))
                for item in report["validator_rejections"]
            )
        )

    def test_primary_pass_has_structured_output_headroom_for_broad_last_mile(self):
        self.assertEqual(prs.PRIMARY_MAX_OUTPUT_TOKENS_PER_PASS, 6000)
        source = (SCRIPT_DIR / "primary_recall_search.py").read_text(encoding="utf-8")
        self.assertIn("max_output_tokens=PRIMARY_MAX_OUTPUT_TOKENS_PER_PASS", source)
        self.assertIn('metadata["configured_max_output_tokens"]', source)

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
                publication_date="2026-08-12",
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

    def test_august_12_fixture_captures_real_zero_pool_regression(self):
        fixture_path = ROOT / "automation" / "fixtures" / "recall" / "2026-08-12.json"
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        must_ids = {item["id"] for item in payload["must_discover"]}
        backfill_ids = {item["id"] for item in payload["backfill_controls"]}
        self.assertEqual(payload["incident_run_id"], 31548550639)
        self.assertEqual(len(must_ids), 3)
        self.assertIn("ibm-together-ai-nvidia-inference-cluster", must_ids)
        self.assertIn("nvidia-nemotron-35-lightning-nemo-switchyard", must_ids)
        self.assertIn("coreweave-capex-ai-cloud-demand", must_ids)
        self.assertIn("meta-muse-glimmer", backfill_ids)
        self.assertEqual(payload["effective_lookback_hours"], prs.PRIMARY_LOOKBACK_HOURS)


if __name__ == "__main__":
    unittest.main()
