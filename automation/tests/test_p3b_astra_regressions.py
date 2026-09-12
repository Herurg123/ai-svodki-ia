from __future__ import annotations

import copy
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
FIXTURE = ROOT / "automation" / "fixtures" / "recall" / "weak-source-signal-retention-2026-09-11.json"
TEMPLATE = (ROOT / "automation" / "prompts" / "coverage_audit.md").read_text(encoding="utf-8")
sys.path.insert(0, str(SCRIPTS))

import ensure_story_coverage as coverage
import primary_recall_search as primary

DATE = "2026-09-11"
MODEL = "gpt-5.6-terra"
WINDOW = {
    "start_at": "2026-09-09T00:00:00+00:00",
    "end_at": "2026-09-11T00:00:00+00:00",
    "start_date": "2026-09-09",
    "end_date": "2026-09-11",
}
_fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
SIGNAL = primary.collect_unresolved_signals([
    {
        "direction_id": _fixture["positive_control"]["direction_id"],
        "model_rejections": [_fixture["positive_control"]["rejection"]],
    }
])[0]


def direction_from_prompt(prompt: str) -> str:
    for direction in coverage.AUDIT_DIRECTION_IDS:
        if f"Идентификатор направления: {direction}" in prompt:
            return direction
    raise AssertionError("mandatory Coverage direction missing from prompt")


def mandatory_success(direction: str):
    query = f"{direction} latest artificial intelligence"
    return (
        {
            "status": "complete_with_gaps",
            "error_message": None,
            "direction_id": direction,
            "candidates": [],
            "rejections": [],
            "notes": "offline mandatory control",
        },
        {
            "status": "completed",
            "web_search_calls": 1,
            "web_search_calls_completed": 1,
            "web_search_call_items_total": 1,
            "actual_queries": [query],
            "consulted_sources": [],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    )


def candidate() -> dict:
    return {
        "title": "DeepSeek replaces V4 Pro with V4.1 Flash",
        "organization": "DeepSeek",
        "published_date": "2026-09-10",
        "published_at": "2026-09-10T06:30:00+00:00",
        "time_precision": "datetime",
        "topic": "models",
        "event_type": "release",
        "keywords": ["V4 Pro", "V4.1 Flash"],
        "geography": "world",
        "category": "models",
        "source_type": "official",
        "primary_source": {
            "title": "DeepSeek replaces V4 Pro with V4.1 Flash",
            "publisher": "DeepSeek",
            "url": "https://www.deepseek.com/en/news/deepseek-v4-1-flash/",
        },
        "supporting_sources": [],
        "event_summary": "DeepSeek replaces V4 Pro with V4.1 Flash",
        "verified_facts": ["Provider facts are not independent proof."],
        "significance": "Material model event",
        "significance_score": 4,
        "limitations": "",
        "archive_status": "none",
        "archive_reason": "",
        "recommendation": "include",
        "verification_status": "verified",
        "verification_notes": "runtime must verify page",
        "freshness_status": "new_event",
        "freshness_reason": "runtime must verify date",
        "legal_scale": "not_applicable",
        "legal_scale_reason": "",
        "curiosity_eligible": False,
        "curiosity_verification": "",
    }


def page_html(published: str = "2026-09-10T06:30:00+00:00") -> str:
    title = "DeepSeek replaces V4 Pro with V4.1 Flash"
    return (
        "<html><head>"
        f"<title>{title}</title>"
        f"<meta property='og:title' content='{title}'>"
        f"<meta property='article:published_time' content='{published}'>"
        "</head><body>"
        f"<h1>{title}</h1><p>{title}</p>"
        "</body></html>"
    )


class AstraP3bRuntimeRegressions(unittest.TestCase):
    def _real_six_plan(self, state: Path) -> tuple[dict, int]:
        calls = 0
        def fake_request(**kwargs):
            nonlocal calls
            calls += 1
            return mandatory_success(direction_from_prompt(str(kwargs["prompt"])))
        with (
            mock.patch.object(coverage, "STATE_DIR", state),
            mock.patch.object(coverage, "run_audit_request", side_effect=fake_request),
            mock.patch.object(coverage._pre, "_required_signals", return_value=[]),
        ):
            plan = coverage._P3A_EXECUTE_AUDIT_PLAN(
                api_key="offline",
                model=MODEL,
                template=TEMPLATE,
                publication_date=DATE,
                search_window=copy.deepcopy(WINDOW),
                missing_total=7,
                maximum_web_search_calls=6,
                existing_candidates=[],
                archive={"items": []},
            )
        self.assertEqual(calls, 6)
        self.assertEqual(set(plan["checked_directions"]), set(coverage.AUDIT_DIRECTION_IDS))
        return plan, calls

    def _reservation(self, state: Path, plan: dict):
        query = coverage.build_p3b_query(SIGNAL)
        prompt = coverage.build_p3b_prompt(
            search_window=WINDOW,
            signal=SIGNAL,
            archive=coverage._runtime._compact_recent_archive({"items": []}),
        )
        return coverage.prepare_slot(
            state_dir=state,
            publication_date=DATE,
            owner=coverage.P3B_SLOT_OWNER,
            search_window=WINDOW,
            request_contract=coverage._request_contract_v2(
                model=MODEL, query=query, prompt=prompt, signal=SIGNAL
            ),
            bundle_identity=coverage._bundle_identity(plan),
        )

    def test_ordinary_real_scheduler_passes_date_and_starts_p3b_as_seventh_search(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            mandatory_calls = []
            p3b_calls = []

            def fake_mandatory(**kwargs):
                mandatory_calls.append(kwargs)
                return mandatory_success(direction_from_prompt(str(kwargs["prompt"])))

            def fake_p3b(runtime, reservation, **kwargs):
                p3b_calls.append(kwargs)
                reservation.mark_request_started()
                reservation.save_raw_response({"id": "resp-astra-date", "status": "completed"})
                query = coverage.build_p3b_query(SIGNAL)
                snapshot = {
                    "payload": {"status": "complete", "candidates": [candidate()], "rejections": []},
                    "metadata": {
                        "response_id": "resp-astra-date",
                        "status": "completed",
                        "actual_queries": [query],
                        "consulted_sources": [],
                        "web_search_calls": 1,
                        "web_search_calls_completed": 1,
                        "web_search_call_items_total": 1,
                    },
                    "output_text": "{}",
                    "validation_error": None,
                }
                reservation.save_result_snapshot(snapshot)
                return types.SimpleNamespace(
                    payload=copy.deepcopy(snapshot["payload"]),
                    metadata=copy.deepcopy(snapshot["metadata"]),
                )

            with (
                mock.patch.object(coverage, "STATE_DIR", state),
                mock.patch.object(coverage, "run_audit_request", side_effect=fake_mandatory),
                mock.patch.object(coverage, "protected_policy_audit_request", side_effect=fake_p3b),
                mock.patch.object(coverage._pre, "_required_signals", return_value=[]),
                mock.patch.object(coverage, "_p3b_signals", return_value=[copy.deepcopy(SIGNAL)]),
                mock.patch.object(
                    coverage._source_freshness,
                    "fetch_source_html",
                    side_effect=lambda url: (page_html(), url, 200),
                ),
            ):
                result = coverage.execute_audit_plan(
                    api_key="offline",
                    model=MODEL,
                    template=TEMPLATE,
                    publication_date=DATE,
                    search_window=copy.deepcopy(WINDOW),
                    missing_total=1,
                    maximum_web_search_calls=7,
                    existing_candidates=[{"title": "existing", "recommendation": "include"}],
                    archive={"items": []},
                )

            self.assertEqual(len(mandatory_calls), 6)
            self.assertEqual(len(p3b_calls), 1)
            self.assertEqual(coverage.journal_state(state, DATE), "processed")
            self.assertEqual(result["weak_source_exact_binding"]["status"], "bound_candidate")
            self.assertEqual(result["search_budget"]["completed_calls"], 7)
            self.assertEqual(result["search_budget"]["remaining_calls"], 0)

    def test_request_started_recovery_runs_real_legacy_scheduler_without_eighth_search(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            plan, _ = self._real_six_plan(state)
            reservation = self._reservation(state, plan)
            reservation.mark_request_started()
            with (
                mock.patch.object(coverage, "STATE_DIR", state),
                mock.patch.object(
                    coverage,
                    "run_audit_request",
                    side_effect=AssertionError("legacy sentinel/retry would be an eighth search"),
                ) as search,
                mock.patch.object(
                    coverage,
                    "protected_policy_audit_request",
                    side_effect=AssertionError("ambiguous P3b request must never retry"),
                ) as provider,
                mock.patch.object(coverage._pre, "_required_signals", return_value=[]),
                mock.patch.object(coverage, "_p3b_signals", return_value=[copy.deepcopy(SIGNAL)]),
            ):
                result = coverage.execute_audit_plan(
                    api_key="offline",
                    model=MODEL,
                    template=TEMPLATE,
                    publication_date=DATE,
                    search_window=copy.deepcopy(WINDOW),
                    missing_total=7,
                    maximum_web_search_calls=7,
                    existing_candidates=[],
                    archive={"items": []},
                    prior_plan=copy.deepcopy(plan),
                )
            self.assertEqual(search.call_count, 0)
            self.assertEqual(provider.call_count, 0)
            self.assertEqual(coverage.journal_state(state, DATE), "request_started")
            self.assertIn(result["weak_source_exact_binding"]["status"], {"indeterminate", "deferred"})
            self.assertLessEqual(result["search_budget"]["effective_consumed_calls"], 7)
            self.assertEqual(result["search_budget"]["remaining_calls"], 0)

    def test_response_saved_recovery_runs_real_scheduler_and_replays_without_search(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            plan, _ = self._real_six_plan(state)
            reservation = self._reservation(state, plan)
            reservation.mark_request_started()
            reservation.save_raw_response({"id": "resp-astra-saved", "status": "completed"})
            query = coverage.build_p3b_query(SIGNAL)
            reservation.save_result_snapshot({
                "payload": {"status": "complete_with_gaps", "candidates": [], "rejections": []},
                "metadata": {
                    "response_id": "resp-astra-saved",
                    "status": "completed",
                    "actual_queries": [query],
                    "consulted_sources": [],
                    "web_search_calls": 1,
                    "web_search_calls_completed": 1,
                    "web_search_call_items_total": 1,
                },
                "output_text": "{}",
                "validation_error": None,
            })
            with (
                mock.patch.object(coverage, "STATE_DIR", state),
                mock.patch.object(coverage, "run_audit_request", side_effect=AssertionError("recovery must not search")) as search,
                mock.patch.object(coverage, "protected_policy_audit_request", side_effect=AssertionError("saved response must not retry provider")) as provider,
                mock.patch.object(coverage._pre, "_required_signals", return_value=[]),
                mock.patch.object(coverage, "_p3b_signals", return_value=[copy.deepcopy(SIGNAL)]),
                mock.patch.object(coverage._source_freshness, "fetch_source_html", side_effect=AssertionError("saved replay must not refetch mutable page")),
            ):
                result = coverage.execute_audit_plan(
                    api_key="offline",
                    model=MODEL,
                    template=TEMPLATE,
                    publication_date=DATE,
                    search_window=copy.deepcopy(WINDOW),
                    missing_total=7,
                    maximum_web_search_calls=7,
                    existing_candidates=[],
                    archive={"items": []},
                    prior_plan=copy.deepcopy(plan),
                )
            self.assertEqual(search.call_count, 0)
            self.assertEqual(provider.call_count, 0)
            self.assertEqual(coverage.journal_state(state, DATE), "processed")
            self.assertEqual(result["weak_source_exact_binding"]["status"], "unresolved")
            self.assertEqual(result["search_budget"]["remaining_calls"], 0)

    def test_archive_same_event_different_url_is_independent_duplicate_proof(self) -> None:
        item = candidate()
        query = coverage.build_p3b_query(SIGNAL)
        title = item["title"]
        html = page_html()
        archive = {
            "items": [{
                "date": "2026-09-10",
                "source_urls": ["https://example.org/other-copy"],
                "stories": [{
                    "headline": title,
                    "organization": "DeepSeek",
                    "event_type": "release",
                    "sources": [{"url": "https://example.org/archived-source"}],
                }],
            }]
        }
        result = coverage._process_p3b_payload_v2(
            base_plan={
                "publication_date": DATE,
                "audit_status": "complete_with_gaps",
                "checked_directions": list(coverage.AUDIT_DIRECTION_IDS),
                "attempts": [],
                "candidates": [],
                "search_budget": {"maximum_calls": 7, "completed_calls": 6, "remaining_calls": 1},
            },
            signal=copy.deepcopy(SIGNAL),
            query=query,
            prompt="archive proof",
            payload={"status": "complete", "candidates": [item], "rejections": []},
            metadata={
                "status": "completed",
                "actual_queries": [query],
                "web_search_calls_completed": 1,
                "web_search_call_items_total": 1,
            },
            slot_state="response_saved",
            search_window=copy.deepcopy(WINDOW),
            archive=archive,
            allow_page_fetch=True,
            page_fetcher=lambda url: (html, url, 200),
        )
        self.assertEqual(result["candidates"], [])
        self.assertTrue(any(
            row.get("reason") == "archive_exact_event_duplicate"
            for row in result["attempts"][-1]["binding_rejections"]
        ))

    def test_cli_installs_hardened_execute_not_v1_execute(self) -> None:
        active = coverage._impl
        observed = {}
        def fake_p3a_main():
            observed["execute"] = active._v2._v1._pre.execute_audit_plan
            return 0
        with mock.patch.object(active._v2._v1, "_P3A_MAIN", side_effect=fake_p3a_main):
            self.assertEqual(coverage.main(), 0)
        self.assertIs(observed["execute"], active.execute_audit_plan)
        self.assertIsNot(observed["execute"], active._v2._v1.execute_audit_plan)


if __name__ == "__main__":
    unittest.main()
