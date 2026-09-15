from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
TESTS = ROOT / "automation" / "tests"
sys.path[:0] = [str(SCRIPTS), str(TESTS)]

import coverage_slot_handoff as handoff
import ensure_story_coverage as coverage
import test_p3b_astra_regressions as controls
import test_p3b_astra_second_review as second
import weak_source_exact_binding_v4 as binder

DATE = controls.DATE
MODEL = controls.MODEL
WINDOW = controls.WINDOW
TEMPLATE = controls.TEMPLATE
BASE_SIGNAL = controls.SIGNAL


class SimulatedProcessStop(BaseException):
    pass


class AstraThirdReviewRegressions(unittest.TestCase):
    def test_public_runtime_is_v6_with_v4_binder(self) -> None:
        self.assertEqual(coverage._impl.__name__, "ensure_story_coverage_p3b_v6")
        self.assertIs(coverage._exact_binding, binder)
        self.assertEqual(coverage.P3B_EXACT_BINDING_VERSION, 2)
        self.assertEqual(coverage.P3B_BINDER_EVIDENCE_VERSION, binder.EVIDENCE_VERSION)

    def test_passive_attribution_requires_signal_org_as_agent(self) -> None:
        signal = second.launch_signal()
        item = second.launch_candidate()
        for surface in (
            "DeepSeek: V4.1 Flash was launched by OpenAI",
            "V4.1 Flash was launched for DeepSeek",
        ):
            with self.subTest(surface=surface):
                result = second.process_candidate(signal=signal, candidate=item, surface=surface)
                self.assertEqual(result["candidates"], [])
        positive = second.process_candidate(
            signal=signal,
            candidate=item,
            surface="V4.1 Flash was launched by DeepSeek",
        )
        self.assertEqual(len(positive["candidates"]), 1)

    def test_suffix_negative_conditional_historical_and_rumor_fail_closed(self) -> None:
        signal = second.launch_signal()
        item = second.launch_candidate()
        surfaces = (
            "DeepSeek announces V4.1 Flash launch was cancelled",
            "DeepSeek announces V4.1 Flash launch is planned for 2027",
            "DeepSeek announces V4.1 Flash release has not happened",
            "If DeepSeek launches V4.1 Flash, developers could adopt it",
            "DeepSeek launched V4.1 Flash on September 1, 2025",
            "DeepSeek launched V4.1 Flash in 2025 and now discusses it",
            "DeepSeek launched V4.1 Flash for developers last year",
            "DeepSeek says V4.1 Flash launch is a rumor",
        )
        for surface in surfaces:
            with self.subTest(surface=surface):
                result = second.process_candidate(signal=signal, candidate=item, surface=surface)
                self.assertEqual(result["candidates"], [])
                self.assertNotEqual(
                    result["weak_source_exact_binding"]["status"], "bound_candidate"
                )

    def test_punctuation_version_continuations_fail_closed(self) -> None:
        signal = second.launch_signal()
        item = second.launch_candidate()
        for suffix in ("/v2", "+", "–v2"):
            with self.subTest(suffix=suffix):
                result = second.process_candidate(
                    signal=signal,
                    candidate=item,
                    surface=f"DeepSeek launches V4.1 Flash{suffix}",
                )
                self.assertEqual(result["candidates"], [])
        self.assertEqual(
            binder.exact_event_identity(
                "DeepSeek launches V4.1 Flash for developers", signal
            ),
            (True, "exact_event_identity"),
        )

    def test_ga_claim_cannot_simultaneously_be_preview(self) -> None:
        signal = second.launch_signal()
        signal["title"] = "DeepSeek general availability V4.1 Flash"
        signal["lifecycle_action_anchors"] = ["general_availability"]
        item = second.launch_candidate()
        item["title"] = signal["title"]
        item["event_summary"] = signal["title"]
        item["event_type"] = "general_availability"
        item["primary_source"]["title"] = signal["title"]

        bad = second.process_candidate(
            signal=signal,
            candidate=item,
            surface="DeepSeek V4.1 Flash general availability in preview",
        )
        self.assertEqual(bad["candidates"], [])
        good = second.process_candidate(
            signal=signal,
            candidate=item,
            surface="DeepSeek V4.1 Flash general availability",
        )
        self.assertEqual(len(good["candidates"]), 1)

    def test_single_digit_mutable_archive_direction_is_preserved(self) -> None:
        signal = second.update_signal()
        signal["title"] = "DeepSeek updates V4.1 Flash from 4 to 8 concurrent requests"
        candidate = second.launch_candidate()
        candidate["title"] = signal["title"]
        candidate["event_type"] = "update"
        candidate["event_summary"] = signal["title"]
        candidate["primary_source"]["url"] = "https://www.deepseek.com/en/news/concurrency-8/"
        reverse = {
            "items": [{
                "date": "2026-09-09",
                "source_urls": ["https://example.org/reverse"],
                "stories": [{
                    "headline": "DeepSeek updates V4.1 Flash from 8 to 4 concurrent requests",
                    "organization": "DeepSeek",
                    "event_type": "update",
                    "event_summary": "DeepSeek updates V4.1 Flash from 8 to 4 concurrent requests",
                    "sources": [{"url": "https://example.org/reverse"}],
                }],
            }]
        }
        self.assertFalse(coverage._archive_exact_event(reverse, candidate, signal))
        same = copy.deepcopy(reverse)
        same["items"][0]["stories"][0]["headline"] = signal["title"]
        same["items"][0]["stories"][0]["event_summary"] = signal["title"]
        self.assertTrue(coverage._archive_exact_event(same, candidate, signal))

    def test_positive_processed_snapshot_without_current_evidence_version_is_not_reused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            helper = controls.AstraP3bRuntimeRegressions()
            plan, _ = helper._real_six_plan(state)
            reservation = helper._reservation(state, plan)
            saved = copy.deepcopy(plan)
            stale_candidate = controls.candidate()
            stale_candidate["audit_direction"] = "weak_source_exact_binding"
            stale_candidate["resolution_signal_ids"] = [str(BASE_SIGNAL.get("signal_id") or "")]
            stale_candidate["p3b_exact_binding_version"] = coverage.P3B_EXACT_BINDING_VERSION
            stale_candidate["p3b_authoritative_page_url"] = stale_candidate["primary_source"]["url"]
            stale_candidate["p3b_authoritative_page_proof"] = (
                "current-event surface + deterministic Source/Event Freshness"
            )
            saved["candidates"] = [stale_candidate]
            saved["weak_source_exact_binding"] = {
                "version": 2,
                "mode": coverage.P3B_MODE,
                "status": "bound_candidate",
                "disposition": "positive_exact_binding",
                "candidate_count": 1,
            }
            reservation.mark_request_started()
            reservation.save_raw_response({"id": "old-positive", "status": "completed"})
            reservation.mark_processed(saved)

            common = dict(
                api_key="offline",
                model=MODEL,
                template=TEMPLATE,
                publication_date=DATE,
                search_window=copy.deepcopy(WINDOW),
                missing_total=1,
                maximum_web_search_calls=7,
                existing_candidates=[{"title": "existing", "recommendation": "include"}],
                archive={"items": []},
                prior_plan=copy.deepcopy(plan),
            )
            with (
                mock.patch.object(coverage, "STATE_DIR", state),
                mock.patch.object(
                    coverage, "run_audit_request",
                    side_effect=AssertionError("processed migration must not run ordinary search"),
                ) as ordinary,
                mock.patch.object(
                    coverage, "protected_policy_audit_request",
                    side_effect=AssertionError("processed migration must not retry paid search"),
                ) as protected,
                mock.patch.object(coverage._pre, "_required_signals", return_value=[]),
                mock.patch.object(coverage, "_p3b_signals", return_value=[copy.deepcopy(BASE_SIGNAL)]),
                mock.patch.object(
                    coverage._source_freshness, "fetch_source_html",
                    side_effect=AssertionError("processed migration must not refetch page"),
                ) as pages,
            ):
                result = coverage.execute_audit_plan(**common)

            self.assertEqual(ordinary.call_count, 0)
            self.assertEqual(protected.call_count, 0)
            self.assertEqual(pages.call_count, 0)
            self.assertEqual(result.get("candidates"), [])
            self.assertEqual(result["weak_source_exact_binding"]["status"], "unresolved")
            self.assertIn("predates", result["weak_source_exact_binding"]["reason"])
            self.assertEqual(result["search_budget"]["remaining_calls"], 0)

    def test_handoff_crash_after_atomic_transfer_leaves_legacy_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            helper = controls.AstraP3bRuntimeRegressions()
            plan, _ = helper._real_six_plan(state)
            helper._reservation(state, plan)
            required = [second.AstraSecondReviewRegressions.required_signal()]
            common = dict(
                api_key="offline",
                model=MODEL,
                template=TEMPLATE,
                publication_date=DATE,
                search_window=copy.deepcopy(WINDOW),
                missing_total=7,
                maximum_web_search_calls=7,
                existing_candidates=[{"title": "existing", "recommendation": "include"}],
                archive={"items": []},
                prior_plan=copy.deepcopy(plan),
            )

            def stop_after_transfer(_reservation):
                raise SimulatedProcessStop("crash after durable ownership transfer")

            with (
                mock.patch.object(coverage, "STATE_DIR", state),
                mock.patch.object(
                    coverage, "run_audit_request",
                    side_effect=AssertionError("six mandatory passes must not rerun"),
                ),
                mock.patch.object(
                    coverage, "protected_policy_audit_request",
                    side_effect=AssertionError("transport must not start before crash seam"),
                ),
                mock.patch.object(coverage._pre, "_required_signals", return_value=required),
                mock.patch.object(coverage, "_p3b_signals", return_value=[copy.deepcopy(BASE_SIGNAL)]),
                mock.patch.object(coverage, "_after_handoff_transfer", side_effect=stop_after_transfer),
            ):
                with self.assertRaisesRegex(SimulatedProcessStop, "durable ownership transfer"):
                    coverage.execute_audit_plan(**common)

            journal = coverage.load_journal(state, DATE)
            self.assertIsInstance(journal, dict)
            self.assertEqual(journal["state"], "reserved")
            self.assertEqual(journal["owner"], coverage._impl._P3A.OPTIONAL_SLOT_OWNER)

            protected_calls: list[str] = []

            def crash_after_admission(runtime, reservation, **kwargs):
                protected_calls.append("started")
                reservation.mark_request_started()
                raise SimulatedProcessStop("crash after legacy request admission")

            with (
                mock.patch.object(coverage, "STATE_DIR", state),
                mock.patch.object(
                    coverage, "run_audit_request",
                    side_effect=AssertionError("recovery must not run ordinary search"),
                ),
                mock.patch.object(
                    coverage, "protected_policy_audit_request", side_effect=crash_after_admission
                ),
                mock.patch.object(coverage._pre, "_required_signals", return_value=required),
                mock.patch.object(coverage, "_p3b_signals", return_value=[copy.deepcopy(BASE_SIGNAL)]),
            ):
                with self.assertRaisesRegex(SimulatedProcessStop, "legacy request admission"):
                    coverage.execute_audit_plan(**common)

            self.assertEqual(protected_calls, ["started"])
            self.assertEqual(coverage.load_journal(state, DATE)["state"], "request_started")

            with (
                mock.patch.object(coverage, "STATE_DIR", state),
                mock.patch.object(
                    coverage, "run_audit_request",
                    side_effect=AssertionError("request_started recovery must not search"),
                ) as ordinary,
                mock.patch.object(
                    coverage, "protected_policy_audit_request",
                    side_effect=AssertionError("request_started recovery must not retry"),
                ) as protected,
                mock.patch.object(coverage._pre, "_required_signals", return_value=required),
                mock.patch.object(coverage, "_p3b_signals", return_value=[copy.deepcopy(BASE_SIGNAL)]),
            ):
                recovered = coverage.execute_audit_plan(**common)
            self.assertEqual(ordinary.call_count, 0)
            self.assertEqual(protected.call_count, 0)
            self.assertEqual(recovered["search_budget"]["remaining_calls"], 0)

    def test_transfer_cannot_overwrite_already_started_p3b_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            helper = controls.AstraP3bRuntimeRegressions()
            plan, _ = helper._real_six_plan(state)
            reservation = helper._reservation(state, plan)
            expected = copy.deepcopy(reservation.journal)
            reservation.mark_request_started()

            required = [second.AstraSecondReviewRegressions.required_signal()]
            cluster = coverage._pre.resolution_cluster(required)
            query = coverage._pre.build_resolution_query(cluster)
            prompt = coverage._pre.build_resolution_prompt(
                search_window=copy.deepcopy(WINDOW), cluster=cluster, archive={"items": []}
            )
            contract = coverage._impl._P3A._request_contract(
                model=MODEL, query=query, prompt=prompt, cluster=cluster
            )
            moved = handoff.transfer_reserved_slot(
                state_dir=state,
                publication_date=DATE,
                expected_journal=expected,
                target_owner=coverage._impl._P3A.OPTIONAL_SLOT_OWNER,
                target_search_window=copy.deepcopy(WINDOW),
                target_request_contract=contract,
                target_bundle_identity=coverage._impl._P3A._bundle_identity(plan),
            )
            self.assertIsNone(moved)
            journal = coverage.load_journal(state, DATE)
            self.assertEqual(journal["state"], "request_started")
            self.assertEqual(journal["owner"], expected["owner"])


if __name__ == "__main__":
    unittest.main()
