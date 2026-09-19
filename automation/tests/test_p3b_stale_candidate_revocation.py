from __future__ import annotations

import copy
import json
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
import story_coverage
import test_p3b_astra_regressions as controls

DATE = controls.DATE
MODEL = controls.MODEL
WINDOW = controls.WINDOW
TEMPLATE = controls.TEMPLATE
SIGNAL = controls.SIGNAL


def _raw_response(response_id: str) -> dict:
    payload = {
        "status": "complete_with_gaps",
        "direction_id": "general_coverage_gaps",
        "candidates": [],
        "rejections": [],
    }
    return {
        "id": response_id,
        "status": "completed",
        "model": MODEL,
        "output_text": json.dumps(payload, ensure_ascii=False),
        "output": [
            {
                "id": "search-1",
                "type": "web_search_call",
                "status": "completed",
                "action": {"type": "search", "query": "fixture exact query", "sources": []},
            }
        ],
    }



def _valid_candidate(*, title: str, url: str, audit_direction: str) -> dict:
    item = controls.candidate()
    item["title"] = title
    item["event_summary"] = title
    item["primary_source"]["title"] = title
    item["primary_source"]["url"] = url
    item["verified_facts"] = [
        "Offline control fact one.",
        "Offline control fact two.",
    ]
    item["audit_direction"] = audit_direction
    return item


def _p3b_candidate(*, title: str, url: str, signal_id: str) -> dict:
    item = _valid_candidate(
        title=title,
        url=url,
        audit_direction="weak_source_exact_binding",
    )
    item["resolution_signal_ids"] = [signal_id]
    item["p3b_exact_binding_version"] = coverage.P3B_EXACT_BINDING_VERSION
    item["p3b_authoritative_page_url"] = url
    item["p3b_authoritative_page_proof"] = (
        "current-event surface + deterministic Source/Event Freshness"
    )
    return item


class P3bStaleCandidateRevocationTests(unittest.TestCase):
    def _seven_pass_processed_plan(
        self,
        *,
        state: Path,
        binder_evidence_version: int,
        include_preservation_controls: bool,
    ) -> tuple[dict, dict, list[dict]]:
        helper = controls.AstraP3bRuntimeRegressions()
        plan, _ = helper._real_six_plan(state)

        budget = plan["search_budget"]
        self.assertEqual(budget["completed_calls"], 6)
        budget["maximum_calls"] = 7
        budget["reserved_or_spent_calls"] = 0
        budget["effective_consumed_calls"] = 6
        budget["remaining_calls"] = 1
        budget["exhausted"] = False
        budget["search_budget_exhausted"] = False
        budget.pop("stop_reason", None)

        reservation = helper._reservation(state, plan)
        stale = _p3b_candidate(
            title="stale P3b exact-binding candidate",
            url="https://www.deepseek.com/en/news/stale-p3b-control/",
            signal_id=str(SIGNAL.get("signal_id") or ""),
        )
        controls_to_preserve: list[dict] = []
        if include_preservation_controls:
            controls_to_preserve = [
                _valid_candidate(
                    title="independent mandatory Coverage candidate",
                    url="https://www.deepseek.com/en/news/mandatory-control/",
                    audit_direction="official_company_sources",
                ),
                _valid_candidate(
                    title="unrelated P3b-like marker data",
                    url="https://www.deepseek.com/en/news/p3b-like-control/",
                    audit_direction="regional_source_gap",
                ),
                _p3b_candidate(
                    title="different-signal P3b provenance",
                    url="https://www.deepseek.com/en/news/other-signal-control/",
                    signal_id="different-signal-id",
                ),
            ]
            controls_to_preserve[1]["p3b_exact_binding_version"] = (
                coverage.P3B_EXACT_BINDING_VERSION
            )

        saved = copy.deepcopy(plan)
        saved["candidates"] = [stale, *copy.deepcopy(controls_to_preserve)]
        saved["weak_source_exact_binding"] = {
            "version": coverage.P3B_EXACT_BINDING_VERSION,
            "mode": coverage.P3B_MODE,
            "signal_id": str(SIGNAL.get("signal_id") or ""),
            "binder_evidence_version": binder_evidence_version,
            "binder_implementation": "weak_source_exact_binding_v4",
            "status": "bound_candidate",
            "disposition": "positive_exact_binding",
            "candidate_count": 1,
        }
        coverage._impl._v2._v1._p3b_force_consumed(saved)
        self.assertEqual(saved["search_budget"]["maximum_calls"], 7)
        self.assertEqual(saved["search_budget"]["remaining_calls"], 0)
        self.assertGreaterEqual(
            max(
                int(saved["search_budget"].get("completed_calls", 0) or 0),
                int(saved["search_budget"].get("effective_consumed_calls", 0) or 0),
            ),
            7,
        )

        reservation.mark_request_started()
        raw_response = _raw_response(f"evidence-v{binder_evidence_version}")
        reservation.save_raw_response(raw_response)
        _parsed, result_snapshot = coverage.replay_raw_response(
            coverage._runtime,
            raw_response,
            maximum_web_search_calls=1,
        )
        reservation.save_result_snapshot(result_snapshot)
        reservation.mark_processed(saved)
        return saved, stale, controls_to_preserve

    def _recover_without_io(
        self,
        *,
        state: Path,
        prior_plan: dict,
        archive: dict | None = None,
    ) -> tuple[dict, tuple[int, int, int]]:
        common = dict(
            api_key="offline",
            model=MODEL,
            template=TEMPLATE,
            publication_date=DATE,
            search_window=copy.deepcopy(WINDOW),
            missing_total=1,
            maximum_web_search_calls=7,
            existing_candidates=[{"title": "existing", "recommendation": "include"}],
            archive=copy.deepcopy(archive if archive is not None else {"items": []}),
            prior_plan=copy.deepcopy(prior_plan),
        )
        with (
            mock.patch.object(coverage, "STATE_DIR", state),
            mock.patch.object(
                coverage,
                "run_audit_request",
                side_effect=AssertionError("processed recovery must not run ordinary search"),
            ) as ordinary,
            mock.patch.object(
                coverage,
                "protected_policy_audit_request",
                side_effect=AssertionError("processed recovery must not retry paid search"),
            ) as protected,
            mock.patch.object(coverage._pre, "_required_signals", return_value=[]),
            mock.patch.object(
                coverage,
                "_p3b_signals",
                return_value=[copy.deepcopy(SIGNAL)],
            ),
            mock.patch.object(
                coverage._source_freshness,
                "fetch_source_html",
                side_effect=AssertionError("processed recovery must not refetch page"),
            ) as pages,
        ):
            result = coverage.execute_audit_plan(**common)
        return result, (ordinary.call_count, protected.call_count, pages.call_count)

    def _assert_stale_revoked(
        self,
        *,
        result: dict,
        stale: dict,
        preserved: list[dict],
    ) -> None:
        titles = {
            str(item.get("title") or "")
            for item in result.get("candidates") or []
            if isinstance(item, dict)
        }
        self.assertNotIn(stale["title"], titles)
        for item in preserved:
            self.assertIn(item["title"], titles)

        diagnostic = result["weak_source_exact_binding"]
        self.assertEqual(diagnostic["status"], "unresolved")
        self.assertEqual(diagnostic["disposition"], "unresolved_deferred")
        self.assertEqual(diagnostic["candidate_count"], 0)
        self.assertIn("predates", diagnostic["reason"])

        budget = result["search_budget"]
        self.assertEqual(budget["maximum_calls"], 7)
        self.assertEqual(budget["remaining_calls"], 0)
        self.assertGreaterEqual(
            max(
                int(budget.get("completed_calls", 0) or 0),
                int(budget.get("effective_consumed_calls", 0) or 0),
            ),
            7,
        )

    def test_stale_evidence_revokes_only_signal_bound_candidate_and_keeps_slot_consumed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            saved, stale, preserved = self._seven_pass_processed_plan(
                state=state,
                binder_evidence_version=2,
                include_preservation_controls=True,
            )

            base = {
                "candidates": [],
                "search_window": copy.deepcopy(WINDOW),
                "research_notes": "offline downstream control",
            }
            _merged_before, accepted_before, _rejected_before = story_coverage.merge_candidates(
                base, [copy.deepcopy(stale)]
            )
            self.assertEqual(
                [item["title"] for item in accepted_before],
                [stale["title"]],
                "control must prove downstream merge would accept the stale candidate",
            )

            result, calls = self._recover_without_io(state=state, prior_plan=saved)

            self.assertEqual(calls, (0, 0, 0))
            self._assert_stale_revoked(result=result, stale=stale, preserved=preserved)

            merged_after, accepted_after, _rejected_after = story_coverage.merge_candidates(
                base, copy.deepcopy(result.get("candidates") or [])
            )
            merged_titles = {
                str(item.get("title") or "")
                for item in merged_after.get("candidates") or []
                if isinstance(item, dict)
            }
            accepted_titles = {
                str(item.get("title") or "")
                for item in accepted_after
                if isinstance(item, dict)
            }
            self.assertNotIn(stale["title"], merged_titles)
            self.assertNotIn(stale["title"], accepted_titles)

    def test_stale_evidence_cleanup_survives_archive_request_hash_drift(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            saved, stale, preserved = self._seven_pass_processed_plan(
                state=state,
                binder_evidence_version=2,
                include_preservation_controls=True,
            )
            changed_archive = {
                "items": [
                    {
                        "date": "2026-09-10",
                        "source_urls": ["https://example.com/unrelated-archive-entry"],
                        "stories": [
                            {
                                "headline": "Unrelated archived control event",
                                "organization": "Example Org",
                                "event_type": "release",
                                "sources": [
                                    {"url": "https://example.com/unrelated-archive-entry"}
                                ],
                            }
                        ],
                    }
                ]
            }

            result, calls = self._recover_without_io(
                state=state,
                prior_plan=saved,
                archive=changed_archive,
            )

            self.assertEqual(calls, (0, 0, 0))
            self._assert_stale_revoked(result=result, stale=stale, preserved=preserved)

    def test_current_evidence_processed_reuse_does_not_trigger_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            saved, current, _preserved = self._seven_pass_processed_plan(
                state=state,
                binder_evidence_version=coverage.P3B_BINDER_EVIDENCE_VERSION,
                include_preservation_controls=False,
            )

            result, calls = self._recover_without_io(state=state, prior_plan=saved)

            self.assertEqual(calls, (0, 0, 0))
            titles = {
                str(item.get("title") or "")
                for item in result.get("candidates") or []
                if isinstance(item, dict)
            }
            self.assertIn(current["title"], titles)
            diagnostic = result["weak_source_exact_binding"]
            self.assertEqual(diagnostic["status"], "bound_candidate")
            self.assertEqual(
                diagnostic["binder_evidence_version"],
                coverage.P3B_BINDER_EVIDENCE_VERSION,
            )
            self.assertEqual(result["search_budget"]["remaining_calls"], 0)


if __name__ == "__main__":
    unittest.main()
