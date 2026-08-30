from __future__ import annotations

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


coverage = load_module(
    "aug30_source_health_targetability",
    SCRIPTS / "ensure_story_coverage_v8.py",
)

SEARCH_WINDOW = {
    "start_at": "2026-08-28T05:16:40+03:00",
    "end_at": "2026-08-30T04:15:21+03:00",
}


def candidate(
    cid: str,
    *,
    recommendation: str,
    category: str,
    event_type: str,
    publisher: str,
    url: str,
    score: int = 4,
) -> dict[str, object]:
    return {
        "id": cid,
        "title": f"Aug 30 regression {cid}",
        "organization": f"Org {cid}",
        "published_date": "2026-08-29",
        "published_at": None,
        "time_precision": "date",
        "event_type": event_type,
        "category": category,
        "recommendation": recommendation,
        "verification_status": "verified",
        "freshness_status": "new_event",
        "significance_score": score,
        "primary_source": {
            "title": f"Source {cid}",
            "publisher": publisher,
            "url": url,
        },
    }


def aug30_pool() -> list[dict[str, object]]:
    # Production-shaped state from run 33285232043. The excluded Bloomberg
    # model row does not satisfy source health; the three usable rows are legal
    # or coding events and therefore are intentionally outside the agency
    # corroboration selector's finance/deal/infrastructure scope.
    return [
        candidate(
            "cand-001",
            recommendation="include",
            category="legal",
            event_type="lawsuit filed",
            publisher="TechCrunch",
            url="https://techcrunch.com/2026/08/29/example/",
        ),
        candidate(
            "cand-002",
            recommendation="exclude",
            category="models",
            event_type="model release",
            publisher="Bloomberg",
            url="https://www.bloomberg.com/latest/the-ai-race",
            score=3,
        ),
        candidate(
            "cand-003",
            recommendation="include",
            category="coding",
            event_type="product release / developer-tool update",
            publisher="Havoptic",
            url="https://www.havoptic.com/r/claude-code-example",
            score=3,
        ),
        candidate(
            "cand-004",
            recommendation="consider",
            category="coding",
            event_type="product release / developer-tool update",
            publisher="Havoptic",
            url="https://www.havoptic.com/r/codex-example",
            score=2,
        ),
    ]


def completed_six_pass_plan() -> dict[str, object]:
    return {
        "audit_status": "complete_with_gaps",
        "checked_directions": list(coverage.AUDIT_DIRECTION_IDS),
        "partial_directions": [],
        "unchecked_directions": [],
        "directions": [],
        "attempts": [],
        "candidates": [],
        "search_budget": {
            "maximum_calls": 7,
            "minimum_required_calls": 6,
            "response_attempts": 6,
            "observed_call_items": 12,
            "completed_calls": 6,
            "remaining_calls": 1,
            "exhausted": False,
            "search_budget_exhausted": False,
            "response_attempt_limit_exhausted": False,
            "provider_overrun": False,
            "stop_reason": "all_required_directions_checked",
        },
        "api": {"status": "completed"},
    }


def eligible_count(rows):
    return sum(
        1
        for item in rows or []
        if isinstance(item, dict)
        and item.get("recommendation") in {"include", "consider"}
    )


class Aug30SourceHealthTargetabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        coverage._set_last_agency_rescue(None)
        coverage._set_last_recall_sentinel(None)

    def test_real_failure_shape_is_not_a_fatal_agency_rescue(self) -> None:
        pool = aug30_pool()
        self.assertFalse(
            coverage._policy._candidates_have_fresh_agency_source(
                pool, SEARCH_WINDOW
            )
        )
        self.assertIsNone(coverage._select_agency_corroboration_target(pool))

        with mock.patch.object(
            coverage,
            "_BASE_EXECUTE_AUDIT_PLAN",
            return_value=completed_six_pass_plan(),
        ), mock.patch.object(
            coverage._base,
            "_eligible_candidate_count",
            side_effect=eligible_count,
        ), mock.patch.object(
            coverage._base,
            "_policy_audit_request",
        ) as paid_search:
            result = coverage.execute_audit_plan(
                api_key="unused",
                model="gpt-5.6-terra",
                template="unused",
                publication_date="2026-08-30",
                search_window=SEARCH_WINDOW,
                missing_total=4,
                maximum_web_search_calls=7,
                existing_candidates=pool,
                archive={"items": []},
                source_health_rescue_needed=True,
            )

        paid_search.assert_not_called()
        self.assertEqual(result["audit_status"], "complete_with_gaps")
        self.assertEqual(
            result["search_budget"]["stop_reason"],
            "agency_rescue_not_applicable",
        )
        self.assertEqual(result["search_budget"]["completed_calls"], 6)
        self.assertEqual(result["search_budget"]["remaining_calls"], 1)
        self.assertEqual(
            coverage._LAST_AGENCY_RESCUE["status"], "not_applicable"
        )

    def test_targetable_funding_event_still_requires_rescue(self) -> None:
        pool = aug30_pool()
        funding = candidate(
            "cand-005",
            recommendation="include",
            category="investment",
            event_type="funding",
            publisher="TechCrunch",
            url="https://techcrunch.com/2026/08/29/funding-example/",
            score=5,
        )
        pool.append(funding)
        target = coverage._select_agency_corroboration_target(pool)
        self.assertIsNotNone(target)
        self.assertEqual(target["id"], "cand-005")

    def test_report_marks_non_targetable_gap_as_not_applicable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "coverage-audit.json"
            report_path.write_text(
                json.dumps(
                    {
                        "source_health_rescue_needed": True,
                        "audit_status": "complete_with_gaps",
                    }
                ),
                encoding="utf-8",
            )
            coverage._set_last_agency_rescue(
                {
                    "status": "not_applicable",
                    "version": coverage.AGENCY_RESCUE_VERSION,
                    "search_strategy": coverage.AGENCY_RESCUE_STRATEGY,
                    "reason": "no targetable event",
                }
            )
            coverage._finalize_source_health_report(report_path)
            payload = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(
            payload["source_health_contract_version"],
            coverage.SOURCE_HEALTH_CONTRACT_VERSION,
        )
        self.assertTrue(payload["source_health_gap_detected"])
        self.assertFalse(payload["source_health_rescue_applicable"])
        self.assertFalse(payload["source_health_rescue_needed"])
        self.assertEqual(payload["agency_rescue"]["status"], "not_applicable")

    def test_source_health_contract_version_is_bumped(self) -> None:
        self.assertGreater(coverage.SOURCE_HEALTH_CONTRACT_VERSION, 7)
        self.assertEqual(
            coverage._policy.SOURCE_HEALTH_CONTRACT_VERSION,
            coverage.SOURCE_HEALTH_CONTRACT_VERSION,
        )


if __name__ == "__main__":
    unittest.main()
