from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runtime = load_module("agency_rescue_runtime", SCRIPTS / "ensure_story_coverage.py")

SEARCH_WINDOW = {
    "start_at": "2026-08-12T02:58:08+03:00",
    "end_at": "2026-08-14T08:03:43+03:00",
}


def metadata(query: str) -> dict[str, object]:
    return {
        "status": "completed",
        "web_search_calls": 1,
        "web_search_calls_completed": 1,
        "web_search_call_items_total": 1,
        "web_search_call_statuses": {"completed": 1},
        "web_search_search_statuses": {"completed": 1},
        "web_search_action_type_counts": {"search": 1},
        "web_search_navigation_items_total": 0,
        "actual_queries": [query],
        "consulted_sources": [
            {
                "title": "Reuters AI story",
                "url": "https://www.reuters.com/world/china/fresh-ai-story-2026-08-13/",
            }
        ],
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    }


def attempt(direction_id: str) -> dict[str, object]:
    return {
        "direction_id": direction_id,
        "label": direction_id,
        "required": True,
        "attempt": 1,
        "search_strategy": "targeted_topic_search",
        "allowed_domains": [],
        "status": "checked_with_gaps",
        "outcome": "no_news_found",
        "actual_queries": [f"{direction_id} query"],
        "sources": [],
        "candidate_count": 0,
        "candidates": [],
        "rejections": [],
        "notes": "checked",
        "api": metadata(f"{direction_id} query"),
        "error": None,
    }


def complete_plan() -> dict[str, object]:
    attempts = [attempt(item) for item in runtime.AUDIT_DIRECTION_IDS]
    return {
        "audit_status": "complete_with_gaps",
        "required_directions": list(runtime.AUDIT_DIRECTION_IDS),
        "checked_directions": list(runtime.AUDIT_DIRECTION_IDS),
        "partial_directions": [],
        "unchecked_directions": [],
        "directions": copy.deepcopy(attempts),
        "attempts": attempts,
        "search_budget": {
            "maximum_calls": 7,
            "minimum_required_calls": 6,
            "response_attempts": 6,
            "observed_call_items": 6,
            "completed_calls": 6,
            "remaining_calls": 1,
            "exhausted": False,
            "search_budget_exhausted": False,
            "response_attempt_limit_exhausted": False,
            "provider_overrun": False,
            "stop_reason": "all_required_directions_checked",
        },
        "api": {"status": "completed"},
        "candidates": [],
        "time_precision_warnings": [],
    }


def candidate(*, publisher: str, url: str, title: str = "AI event") -> dict[str, object]:
    return {
        "title": title,
        "organization": "Example AI",
        "published_date": "2026-08-13",
        "published_at": "2026-08-13T12:00:00+00:00",
        "time_precision": "datetime",
        "topic": "AI",
        "event_type": "model_launch",
        "keywords": ["AI", "launch"],
        "geography": "world",
        "category": "models",
        "source_type": "news_agency" if "reuters.com" in url else "technology_media",
        "primary_source": {"title": title, "publisher": publisher, "url": url},
        "supporting_sources": [],
        "event_summary": "Fresh event.",
        "verified_facts": ["Fact one.", "Fact two."],
        "significance": "Major event.",
        "significance_score": 5,
        "limitations": "",
        "archive_status": "none",
        "archive_reason": "Not in archive.",
        "recommendation": "include",
        "verification_status": "verified",
        "verification_notes": "Verified.",
        "freshness_status": "new_event",
        "freshness_reason": "Inside window.",
        "legal_scale": "not_applicable",
        "legal_scale_reason": "",
        "curiosity_eligible": False,
        "curiosity_verification": "",
    }


class AgencyRescueTests(unittest.TestCase):
    def test_nonzero_tech_media_pool_uses_seventh_slot_for_reuters_ap_rescue(self):
        existing = [
            candidate(
                publisher="TechCrunch",
                url="https://techcrunch.com/2026/08/13/existing-ai-story/",
                title="Existing TechCrunch story",
            )
        ]
        rescued = candidate(
            publisher="Reuters",
            url="https://www.reuters.com/world/china/new-ai-model-2026-08-13/",
            title="New Reuters story",
        )

        def fake_request(**kwargs):
            return (
                {
                    "status": "complete",
                    "error_message": None,
                    "direction_id": "general_coverage_gaps",
                    "candidates": [rescued],
                    "rejections": [],
                    "notes": "Found independent missing event.",
                },
                metadata("latest major artificial intelligence news"),
            )

        with (
            mock.patch.object(
                runtime, "_BASE_EXECUTE_AUDIT_PLAN", return_value=complete_plan()
            ),
            mock.patch.object(runtime, "run_audit_request", side_effect=fake_request) as request,
        ):
            result = runtime.execute_audit_plan(
                api_key="secret",
                model="gpt-5.6-terra",
                template="unused",
                publication_date="2026-08-14",
                search_window=SEARCH_WINDOW,
                missing_total=0,
                maximum_web_search_calls=7,
                existing_candidates=existing,
                archive={"items": []},
            )

        self.assertEqual(request.call_count, 1)
        call = request.call_args.kwargs
        self.assertEqual(tuple(call["allowed_domains"]), runtime.AGENCY_RESCUE_DOMAINS)
        self.assertEqual(call["maximum_web_search_calls"], 1)
        self.assertIn("latest major artificial intelligence news", call["prompt"])
        self.assertIn("НЕТ в текущем пуле", call["prompt"])
        rescue = result["attempts"][-1]
        self.assertEqual(rescue["search_strategy"], runtime.AGENCY_RESCUE_STRATEGY)
        self.assertEqual(rescue["agency_rescue_version"], runtime.AGENCY_RESCUE_VERSION)
        self.assertEqual(rescue["candidate_count"], 1)
        self.assertEqual(result["candidates"][-1]["audit_direction"], "agency_rescue")
        self.assertEqual(result["search_budget"]["completed_calls"], 7)
        self.assertEqual(result["search_budget"]["remaining_calls"], 0)

    def test_fresh_agency_candidate_does_not_spend_seventh_slot(self):
        existing = [
            candidate(
                publisher="Reuters",
                url="https://www.reuters.com/technology/current-ai-story-2026-08-13/",
            )
        ]
        with (
            mock.patch.object(
                runtime, "_BASE_EXECUTE_AUDIT_PLAN", return_value=complete_plan()
            ),
            mock.patch.object(runtime, "run_audit_request") as request,
        ):
            result = runtime.execute_audit_plan(
                api_key="secret",
                model="gpt-5.6-terra",
                template="unused",
                publication_date="2026-08-14",
                search_window=SEARCH_WINDOW,
                missing_total=0,
                maximum_web_search_calls=7,
                existing_candidates=existing,
                archive={"items": []},
            )
        self.assertEqual(request.call_count, 0)
        self.assertEqual(result["search_budget"]["completed_calls"], 6)

    def test_legacy_nonzero_audit_is_replayed_once_under_source_health_contract(self):
        report = complete_plan()
        report.update(
            {
                "audit_state": "completed_usable",
                "web_search_performed": True,
                "candidate_pool_after": {"total": 7},
            }
        )
        self.assertFalse(runtime.completed_prior_audit(report))
        report["source_health_contract_version"] = runtime.SOURCE_HEALTH_CONTRACT_VERSION
        self.assertTrue(runtime.completed_prior_audit(report))


if __name__ == "__main__":
    unittest.main()
