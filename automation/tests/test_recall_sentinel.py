from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
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


runtime = load_module(
    "recall_sentinel_runtime",
    SCRIPTS / "ensure_story_coverage.py",
)


SEARCH_WINDOW = {
    "start_at": "2026-08-07T01:53:00+03:00",
    "end_at": "2026-08-08T02:48:00+03:00",
    "start_date": "2026-08-07",
    "end_date": "2026-08-08",
}


def api_metadata(query: str) -> dict[str, object]:
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
                "url": "https://www.reuters.com/example",
            }
        ],
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    }


def base_attempt(direction_id: str, attempt: int = 1) -> dict[str, object]:
    return {
        "direction_id": direction_id,
        "label": direction_id,
        "required": True,
        "attempt": attempt,
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
        "api": api_metadata(f"{direction_id} query"),
        "error": None,
    }


def complete_zero_plan() -> dict[str, object]:
    attempts = [base_attempt(item) for item in runtime.AUDIT_DIRECTION_IDS]
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


def candidate(*, legal_scale: str = "not_applicable") -> dict[str, object]:
    return {
        "title": "OpenAI flags possible critical cybersecurity risk",
        "organization": "OpenAI",
        "published_date": "2026-08-07",
        "published_at": "2026-08-07T17:46:59+00:00",
        "time_precision": "datetime",
        "topic": "cybersecurity risk",
        "event_type": "security_disclosure",
        "keywords": ["OpenAI", "cybersecurity", "Astra"],
        "geography": "world",
        "category": "security",
        "source_type": "news_agency",
        "primary_source": {
            "title": "OpenAI flags possible critical cybersecurity risk",
            "publisher": "Reuters",
            "url": "https://www.reuters.com/legal/litigation/openai-flags-possible-critical-cybersecurity-risk-upcoming-model-tightens-2026-08-07/",
        },
        "supporting_sources": [],
        "event_summary": "OpenAI tightened safeguards around an upcoming model.",
        "verified_facts": [
            "Reuters reported the disclosure.",
            "OpenAI tightened safeguards.",
        ],
        "significance": "Potential critical cyber capability at a frontier lab.",
        "significance_score": 5,
        "limitations": "No public model release yet.",
        "archive_status": "none",
        "archive_reason": "Not present in archive.",
        "recommendation": "include",
        "verification_status": "verified",
        "verification_notes": "Reuters report within the editorial window.",
        "freshness_status": "new_event",
        "freshness_reason": "Fresh public disclosure inside the window.",
        "legal_scale": legal_scale,
        "legal_scale_reason": "URL looked legal" if legal_scale != "not_applicable" else "",
        "curiosity_eligible": False,
        "curiosity_verification": "",
    }


def current_sentinel_attempt() -> dict[str, object]:
    sentinel = base_attempt("general_coverage_gaps", attempt=2)
    sentinel.update(
        {
            "label": "Source-neutral broad recall sentinel v8",
            "search_strategy": runtime.RECALL_SENTINEL_STRATEGY,
            "recall_sentinel_version": runtime.RECALL_SENTINEL_VERSION,
            "allowed_domains": [],
        }
    )
    return sentinel


class RecallSentinelTests(unittest.TestCase):
    def run_plan(self, plan, fake_request, *, existing_candidates=None):
        with (
            mock.patch.object(
                runtime,
                "_BASE_EXECUTE_AUDIT_PLAN",
                return_value=copy.deepcopy(plan),
            ),
            mock.patch.object(
                runtime,
                "run_audit_request",
                side_effect=fake_request,
            ) as request,
        ):
            result = runtime.execute_audit_plan(
                api_key="secret",
                model="gpt-5.6-terra",
                template="unused by stub",
                publication_date="2026-08-08",
                search_window=SEARCH_WINDOW,
                missing_total=7,
                maximum_web_search_calls=7,
                existing_candidates=existing_candidates or [],
                archive={"items": []},
            )
        return result, request

    def test_seventh_slot_is_one_source_agnostic_search(self) -> None:
        def fake_request(**kwargs):
            self.assertEqual(kwargs["maximum_web_search_calls"], 1)
            self.assertEqual(tuple(kwargs["allowed_domains"]), ())
            self.assertIn("РОВНО ОДИН Web Search", kwargs["prompt"])
            self.assertIn(
                "latest major artificial intelligence news",
                kwargs["prompt"],
            )
            self.assertNotIn(
                "Reuters latest major artificial intelligence news",
                kwargs["prompt"],
            )
            self.assertIn("Не расширяй и не переписывай", kwargs["prompt"])
            self.assertIn("source-neutral recall sentinel", kwargs["prompt"])
            self.assertIn("не должен быть привязан ни к OpenAI", kwargs["prompt"])
            story = candidate(legal_scale="major")
            story["source_type"] = "technology_media"
            story["primary_source"] = {
                "title": "Exclusive: OpenAI slows release of Astra model citing cyber capabilities",
                "publisher": "Axios",
                "url": "https://www.axios.com/2026/08/07/openai-astra-model-delay-cybersecurity-risks",
            }
            story["verification_notes"] = "Axios report within the editorial window."
            return (
                {
                    "status": "complete",
                    "error_message": None,
                    "direction_id": "general_coverage_gaps",
                    "candidates": [story],
                    "rejections": [],
                    "notes": "High-signal source-neutral story found.",
                },
                api_metadata("latest major artificial intelligence news"),
            )

        result, request = self.run_plan(complete_zero_plan(), fake_request)

        self.assertEqual(request.call_count, 1)
        self.assertEqual(len(result["attempts"]), 7)
        sentinel = result["attempts"][-1]
        self.assertEqual(sentinel["search_strategy"], runtime.RECALL_SENTINEL_STRATEGY)
        self.assertEqual(
            sentinel["recall_sentinel_version"], runtime.RECALL_SENTINEL_VERSION
        )
        self.assertEqual(sentinel["allowed_domains"], [])
        self.assertEqual(sentinel["candidate_count"], 1)
        found = result["candidates"][0]
        self.assertEqual(found["audit_direction"], "recall_sentinel")
        self.assertEqual(found["category"], "security")
        self.assertEqual(found["primary_source"]["publisher"], "Axios")
        self.assertEqual(found["legal_scale"], "not_applicable")
        self.assertEqual(found["legal_scale_reason"], "")
        self.assertEqual(result["search_budget"]["completed_calls"], 7)
        self.assertEqual(result["search_budget"]["remaining_calls"], 0)

    def test_sentinel_is_not_used_when_pool_is_nonzero(self) -> None:
        existing = [{"recommendation": "include"}]
        result, request = self.run_plan(
            complete_zero_plan(),
            lambda **kwargs: self.fail("sentinel must not run"),
            existing_candidates=existing,
        )
        self.assertEqual(request.call_count, 0)
        self.assertEqual(len(result["attempts"]), 6)
        self.assertEqual(result["search_budget"]["remaining_calls"], 1)

    def test_sentinel_is_not_used_until_mandatory_audit_is_complete(self) -> None:
        plan = complete_zero_plan()
        plan["audit_status"] = "partial"
        plan["checked_directions"] = list(runtime.AUDIT_DIRECTION_IDS[:-1])
        plan["unchecked_directions"] = [runtime.AUDIT_DIRECTION_IDS[-1]]
        result, request = self.run_plan(
            plan,
            lambda **kwargs: self.fail("sentinel must not run"),
        )
        self.assertEqual(request.call_count, 0)
        self.assertEqual(result["audit_status"], "partial")

    def test_empty_successful_sentinel_makes_zero_pool_terminal_reliable(self) -> None:
        def fake_request(**kwargs):
            return (
                {
                    "status": "complete_with_gaps",
                    "error_message": None,
                    "direction_id": "general_coverage_gaps",
                    "candidates": [],
                    "rejections": [],
                    "notes": "No high-signal source-neutral story found.",
                },
                api_metadata("latest major artificial intelligence news"),
            )

        result, request = self.run_plan(complete_zero_plan(), fake_request)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(result["audit_status"], "complete_with_gaps")
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["attempts"][-1]["outcome"], "no_news_found")
        self.assertEqual(result["search_budget"]["completed_calls"], 7)

    def test_failed_sentinel_blocks_zero_pool_stop_but_is_retryable(self) -> None:
        def fake_request(**kwargs):
            raise RuntimeError("transport failed")

        result, request = self.run_plan(complete_zero_plan(), fake_request)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(result["audit_status"], "partial")
        self.assertEqual(len(result["attempts"]), 6)
        self.assertEqual(result["search_budget"]["completed_calls"], 6)
        self.assertEqual(result["search_budget"]["remaining_calls"], 1)
        self.assertEqual(
            result["search_budget"]["stop_reason"],
            "recall_sentinel_incomplete",
        )
        self.assertEqual(runtime._LAST_RECALL_SENTINEL["status"], "error")
        self.assertEqual(
            runtime._LAST_RECALL_SENTINEL["version"],
            runtime.RECALL_SENTINEL_VERSION,
        )

    def test_current_sentinel_is_reused_from_recovery(self) -> None:
        plan = complete_zero_plan()
        sentinel = current_sentinel_attempt()
        plan["attempts"].append(sentinel)
        plan["search_budget"]["response_attempts"] = 7
        plan["search_budget"]["completed_calls"] = 7
        plan["search_budget"]["remaining_calls"] = 0

        result, request = self.run_plan(
            plan,
            lambda **kwargs: self.fail("reused sentinel must not run"),
        )
        self.assertEqual(request.call_count, 0)
        self.assertEqual(len(result["attempts"]), 7)
        self.assertEqual(runtime._LAST_RECALL_SENTINEL["status"], "reused")
        self.assertEqual(
            runtime._LAST_RECALL_SENTINEL["version"],
            runtime.RECALL_SENTINEL_VERSION,
        )

    def test_stale_sentinel_is_removed_and_budget_restored(self) -> None:
        plan = complete_zero_plan()
        plan["temporal_anchor_version"] = runtime.TEMPORAL_ANCHOR_VERSION
        stale = base_attempt("general_coverage_gaps", attempt=2)
        stale.update(
            {
                "search_strategy": runtime.RECALL_SENTINEL_STRATEGY,
                "recall_sentinel_version": 5,
                "allowed_domains": [],
            }
        )
        plan["attempts"].append(stale)
        plan["search_budget"].update(
            {
                "response_attempts": 7,
                "completed_calls": 7,
                "remaining_calls": 0,
                "stop_reason": "recall_sentinel_completed",
            }
        )
        plan["recall_sentinel"] = {
            "status": "complete_with_gaps",
            "version": 5,
            "search_strategy": runtime.RECALL_SENTINEL_STRATEGY,
            "allowed_domains": [],
        }

        captured = {}

        def fake_base(**kwargs):
            captured["prior"] = copy.deepcopy(kwargs["prior_plan"])
            return complete_zero_plan()

        def fake_request(**kwargs):
            return (
                {
                    "status": "complete_with_gaps",
                    "error_message": None,
                    "direction_id": "general_coverage_gaps",
                    "candidates": [],
                    "rejections": [],
                    "notes": "checked by v8",
                },
                api_metadata("latest major artificial intelligence news"),
            )

        with (
            mock.patch.object(runtime, "_BASE_EXECUTE_AUDIT_PLAN", side_effect=fake_base),
            mock.patch.object(runtime, "run_audit_request", side_effect=fake_request),
        ):
            runtime.execute_audit_plan(
                api_key="secret",
                model="gpt-5.6-terra",
                template="unused",
                publication_date="2026-08-08",
                search_window=SEARCH_WINDOW,
                missing_total=7,
                maximum_web_search_calls=7,
                existing_candidates=[],
                archive={"items": []},
                prior_plan=plan,
            )

        prepared = captured["prior"]
        self.assertEqual(len(prepared["attempts"]), 6)
        self.assertEqual(prepared["search_budget"]["completed_calls"], 6)
        self.assertEqual(prepared["search_budget"]["remaining_calls"], 1)
        self.assertNotIn("recall_sentinel", prepared)

    def test_zero_pool_completion_requires_current_sentinel_version(self) -> None:
        report = complete_zero_plan()
        report.update(
            {
                "audit_state": "completed_usable",
                "web_search_performed": True,
                "candidate_pool_after": {"total": 0},
            }
        )
        self.assertFalse(runtime.completed_prior_audit(report))

        stale = base_attempt("general_coverage_gaps", attempt=2)
        stale["search_strategy"] = runtime.RECALL_SENTINEL_STRATEGY
        stale["recall_sentinel_version"] = 5
        report["attempts"].append(stale)
        report["recall_sentinel"] = {
            "status": "complete_with_gaps",
            "version": 5,
            "search_strategy": runtime.RECALL_SENTINEL_STRATEGY,
        }
        self.assertFalse(runtime.completed_prior_audit(report))

        current = current_sentinel_attempt()
        report["attempts"][-1] = current
        report["recall_sentinel"] = {
            "status": "complete_with_gaps",
            "version": runtime.RECALL_SENTINEL_VERSION,
            "search_strategy": runtime.RECALL_SENTINEL_STRATEGY,
            "allowed_domains": [],
        }
        self.assertTrue(runtime.completed_prior_audit(report))

        runtime._sync_policy_overrides()
        self.assertIs(
            runtime._policy.completed_prior_audit,
            runtime.completed_prior_audit,
        )

    def test_nonzero_completed_legacy_audit_remains_reusable(self) -> None:
        report = complete_zero_plan()
        report.update(
            {
                "audit_state": "completed_usable",
                "web_search_performed": True,
                "candidate_pool_after": {"total": 2},
            }
        )
        self.assertTrue(runtime.completed_prior_audit(report))

    def test_primary_search_diagnostics_exposes_query_batching(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "automation" / "preview" / "2026-08-08"
            target.mkdir(parents=True)
            trajectory = {
                "completed_calls": 3,
                "actual_queries": [f"q{i}" for i in range(12)],
                "calls": [
                    {
                        "action_type": "search",
                        "action": {
                            "type": "search",
                            "queries": [f"q{i}" for i in range(start, start + 4)],
                        },
                    }
                    for start in (0, 4, 8)
                ],
            }
            (target / "research-search-trajectory.json").write_text(
                json.dumps(trajectory), encoding="utf-8"
            )
            with mock.patch.object(runtime, "REPOSITORY_ROOT", root):
                diagnostics = runtime._primary_search_diagnostics("2026-08-08")

        self.assertEqual(diagnostics["search_operation_count"], 3)
        self.assertEqual(diagnostics["logical_query_count"], 12)
        self.assertEqual(diagnostics["queries_per_search_operation"], [4, 4, 4])
        self.assertTrue(diagnostics["query_batching_detected"])


if __name__ == "__main__":
    unittest.main()
