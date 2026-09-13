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

import ensure_story_coverage as coverage
import weak_source_exact_binding_v3 as binder
import test_p3b_astra_regressions as controls

DATE = controls.DATE
MODEL = controls.MODEL
WINDOW = controls.WINDOW
TEMPLATE = controls.TEMPLATE
BASE_SIGNAL = controls.SIGNAL


class SimulatedProcessStop(BaseException):
    pass


def launch_signal() -> dict:
    signal = copy.deepcopy(BASE_SIGNAL)
    signal["title"] = "DeepSeek launches V4.1 Flash"
    signal["organization"] = "DeepSeek"
    signal["product_version_anchors"] = ["V4.1 Flash"]
    signal["lifecycle_action_anchors"] = ["launch"]
    return signal


def update_signal() -> dict:
    signal = copy.deepcopy(BASE_SIGNAL)
    signal["title"] = "DeepSeek updates V4.1 Flash from 32K to 64K context"
    signal["organization"] = "DeepSeek"
    signal["product_version_anchors"] = ["V4.1 Flash"]
    signal["lifecycle_action_anchors"] = ["update"]
    return signal


def launch_candidate() -> dict:
    item = controls.candidate()
    item["title"] = "DeepSeek launches V4.1 Flash"
    item["event_type"] = "launch"
    item["keywords"] = ["V4.1 Flash"]
    item["event_summary"] = item["title"]
    item["primary_source"] = {
        "title": item["title"],
        "publisher": "DeepSeek",
        "url": "https://www.deepseek.com/en/news/v4-1-flash-launch/",
    }
    return item


def page_html(surface: str) -> str:
    return (
        "<html><head>"
        f"<title>{surface}</title>"
        f"<meta property='og:title' content='{surface}'>"
        "<meta property='article:published_time' content='2026-09-10T06:30:00+00:00'>"
        "</head><body>"
        f"<h1>{surface}</h1><p>{surface}</p>"
        "</body></html>"
    )


def process_candidate(*, signal: dict, candidate: dict, surface: str, archive: dict | None = None) -> dict:
    query = coverage.build_p3b_query(signal)
    return coverage._process_p3b_payload_v2(
        base_plan={
            "publication_date": DATE,
            "audit_status": "complete_with_gaps",
            "checked_directions": list(coverage.AUDIT_DIRECTION_IDS),
            "attempts": [],
            "candidates": [],
            "search_budget": {
                "maximum_calls": 7,
                "completed_calls": 6,
                "remaining_calls": 1,
            },
        },
        signal=copy.deepcopy(signal),
        query=query,
        prompt="Astra second-review regression",
        payload={"status": "complete", "candidates": [copy.deepcopy(candidate)], "rejections": []},
        metadata={
            "status": "completed",
            "actual_queries": [query],
            "web_search_calls": 1,
            "web_search_calls_completed": 1,
            "web_search_call_items_total": 1,
        },
        slot_state="response_saved",
        search_window=copy.deepcopy(WINDOW),
        archive=copy.deepcopy(archive or {"items": []}),
        allow_page_fetch=True,
        page_fetcher=lambda url: (page_html(surface), url, 200),
    )


class AstraSecondReviewRegressions(unittest.TestCase):
    @staticmethod
    def required_signal() -> dict:
        return {
            "signal_id": "required-rillet",
            "status": "unresolved",
            "title": "Rillet Lands $100M to Scale AI ERP",
            "origin_direction": "business_investment_partnerships",
            "reason_code": "unverified",
            "evidence_reason": "Unverified funding round",
            "likely_significance_score": 4,
            "entities": ["Rillet"],
            "anchors": ["$100M"],
            "resolution_required": True,
        }

    def test_public_runtime_is_v5_with_v3_binder(self) -> None:
        self.assertEqual(coverage._impl.__name__, "ensure_story_coverage_p3b_v5")
        self.assertIs(coverage._exact_binding, binder)
        self.assertIs(coverage._impl._v2._binding_v2, binder)

    def test_p3b_to_required_legacy_handoff_stays_durable_after_transport_crash(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            helper = controls.AstraP3bRuntimeRegressions()
            plan, _ = helper._real_six_plan(state)
            reservation = helper._reservation(state, plan)
            self.assertEqual(reservation.state, "reserved")
            required = [self.required_signal()]
            protected_calls: list[str] = []

            def crash_after_admission(runtime, reservation, **kwargs):
                protected_calls.append("started")
                reservation.mark_request_started()
                raise SimulatedProcessStop("simulated process stop after transport admission")

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
            with (
                mock.patch.object(coverage, "STATE_DIR", state),
                mock.patch.object(
                    coverage,
                    "run_audit_request",
                    side_effect=AssertionError("six completed mandatory passes must not rerun"),
                ),
                mock.patch.object(
                    coverage,
                    "protected_policy_audit_request",
                    side_effect=crash_after_admission,
                ),
                mock.patch.object(coverage._pre, "_required_signals", return_value=required),
                mock.patch.object(coverage, "_p3b_signals", return_value=[copy.deepcopy(BASE_SIGNAL)]),
            ):
                with self.assertRaisesRegex(SimulatedProcessStop, "simulated process stop"):
                    coverage.execute_audit_plan(**common)

            journal = coverage.load_journal(state, DATE)
            self.assertEqual(journal["state"], "request_started")
            self.assertEqual(protected_calls, ["started"])

            with (
                mock.patch.object(coverage, "STATE_DIR", state),
                mock.patch.object(
                    coverage,
                    "run_audit_request",
                    side_effect=AssertionError("recovery must not run an eighth search"),
                ) as ordinary,
                mock.patch.object(
                    coverage,
                    "protected_policy_audit_request",
                    side_effect=AssertionError("request_started legacy slot must not retry"),
                ) as protected,
                mock.patch.object(coverage._pre, "_required_signals", return_value=required),
                mock.patch.object(coverage, "_p3b_signals", return_value=[copy.deepcopy(BASE_SIGNAL)]),
            ):
                recovered = coverage.execute_audit_plan(**common)

            self.assertEqual(ordinary.call_count, 0)
            self.assertEqual(protected.call_count, 0)
            self.assertEqual(coverage.load_journal(state, DATE)["state"], "request_started")
            self.assertEqual(recovered["search_budget"]["remaining_calls"], 0)
            self.assertLessEqual(recovered["search_budget"]["effective_consumed_calls"], 7)

    def test_actor_action_and_model_must_share_one_event_relation(self) -> None:
        signal = launch_signal()
        item = launch_candidate()
        bad_surfaces = (
            "DeepSeek launches R2 while OpenAI launches V4.1 Flash",
            "DeepSeek's competitor launches V4.1 Flash",
            "DeepSeek confirms openai launches V4.1 Flash",
        )
        for surface in bad_surfaces:
            with self.subTest(surface=surface):
                result = process_candidate(signal=signal, candidate=item, surface=surface)
                self.assertEqual(result["candidates"], [])
                self.assertNotEqual(
                    result["weak_source_exact_binding"]["status"],
                    "bound_candidate",
                )

        positive = process_candidate(
            signal=signal,
            candidate=item,
            surface="DeepSeek launches V4.1 Flash for developers",
        )
        self.assertEqual(len(positive["candidates"]), 1)

    def test_planned_cancelled_modal_and_explicit_year_events_fail_closed(self) -> None:
        signal = launch_signal()
        item = launch_candidate()
        for surface in (
            "DeepSeek plans to launch V4.1 Flash",
            "DeepSeek cancels launch of V4.1 Flash",
            "DeepSeek might launch V4.1 Flash",
            "In 2025, DeepSeek launched V4.1 Flash",
        ):
            with self.subTest(surface=surface):
                result = process_candidate(signal=signal, candidate=item, surface=surface)
                self.assertEqual(result["candidates"], [])

    def test_authoritative_page_with_both_replacement_directions_is_rejected(self) -> None:
        signal = copy.deepcopy(BASE_SIGNAL)
        item = controls.candidate()
        for surface in (
            "DeepSeek replaces V4 Pro with V4.1 Flash while DeepSeek replaces V4.1 Flash with V4 Pro",
            "DeepSeek replaces V4 Pro with V4.1 Flash; DeepSeek replaces V4.1 Flash with V4 Pro",
        ):
            with self.subTest(surface=surface):
                result = process_candidate(signal=signal, candidate=item, surface=surface)
                self.assertEqual(result["candidates"], [])
                reasons = {
                    row.get("reason")
                    for row in result["attempts"][-1]["binding_rejections"]
                }
                self.assertIn(
                    "authoritative_page_replacement_direction_conflict",
                    reasons,
                )

    def test_unknown_lowercase_version_continuations_are_not_exact(self) -> None:
        signal = launch_signal()
        item = launch_candidate()
        for suffix in ("v2", "experimental"):
            with self.subTest(suffix=suffix):
                surface = f"DeepSeek launches V4.1 Flash {suffix}"
                result = process_candidate(signal=signal, candidate=item, surface=surface)
                self.assertEqual(result["candidates"], [])
        self.assertEqual(
            binder.exact_event_identity(
                "DeepSeek launches V4.1 Flash for developers",
                signal,
            ),
            (True, "exact_event_identity"),
        )

    def test_mutable_archive_detail_preserves_change_direction(self) -> None:
        signal = update_signal()
        candidate = launch_candidate()
        candidate["title"] = "DeepSeek updates V4.1 Flash from 32K to 64K context"
        candidate["event_type"] = "update"
        candidate["event_summary"] = candidate["title"]
        candidate["primary_source"]["url"] = "https://www.deepseek.com/en/news/v4-context-64k/"
        reverse = {
            "items": [{
                "date": "2026-09-09",
                "source_urls": ["https://example.org/reverse"],
                "stories": [{
                    "headline": "DeepSeek updates V4.1 Flash from 64K to 32K context",
                    "organization": "DeepSeek",
                    "event_type": "update",
                    "event_summary": "DeepSeek updates V4.1 Flash from 64K to 32K context",
                    "sources": [{"url": "https://example.org/reverse"}],
                }],
            }]
        }
        self.assertFalse(coverage._archive_exact_event(reverse, candidate, signal))

        same = copy.deepcopy(reverse)
        same["items"][0]["stories"][0]["headline"] = candidate["title"]
        same["items"][0]["stories"][0]["event_summary"] = candidate["title"]
        self.assertTrue(coverage._archive_exact_event(same, candidate, signal))

    def test_structured_archive_org_cannot_reassign_lowercase_or_role_actor(self) -> None:
        signal = launch_signal()
        candidate = launch_candidate()
        for headline in (
            "openai launches V4.1 Flash",
            "its competitor launches V4.1 Flash",
        ):
            with self.subTest(headline=headline):
                archive = {
                    "items": [{
                        "date": "2026-09-09",
                        "source_urls": ["https://example.org/archive"],
                        "stories": [{
                            "headline": headline,
                            "organization": "DeepSeek",
                            "event_type": "launch",
                            "event_summary": headline,
                            "sources": [{"url": "https://example.org/archive"}],
                        }],
                    }]
                }
                self.assertFalse(
                    coverage._archive_exact_event(archive, candidate, signal)
                )


if __name__ == "__main__":
    unittest.main()
