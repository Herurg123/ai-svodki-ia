from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import discovery_health
import primary_zero_outcome as pzo


def row(
    *,
    direction_id: str = "business_investment_partnerships",
    status: str = "complete_with_gaps",
    raw: list[dict] | None = None,
    accepted: int = 0,
    model_rejections: list[dict] | None = None,
    validator_rejections: list[dict] | None = None,
    sources=...,
    completed: int = 1,
) -> dict:
    action = {"type": "search", "query": "latest AI business"}
    if sources is not ...:
        action["sources"] = sources
    api = {
        "web_search_calls_completed": completed,
        "web_search_call_items": [
            {
                "id": "ws-1",
                "status": "completed",
                "action_type": "search",
                "action": action,
            }
        ],
        "consulted_sources": sources if isinstance(sources, list) else [],
    }
    return {
        "direction_id": direction_id,
        "status": status,
        "raw_candidates": list(raw or []),
        "accepted_count": accepted,
        "model_rejections": list(model_rejections or []),
        "validator_rejections": list(validator_rejections or []),
        "web_search_calls_completed": completed,
        "api": api,
    }


class PrimaryZeroOutcomeTests(unittest.TestCase):
    def test_explicit_empty_source_list_is_provider_pool_empty(self):
        result = pzo.classify_direction(row(sources=[]))
        self.assertEqual(result["outcome"], "provider_source_pool_empty")
        self.assertEqual(result["source_metadata_state"], "empty")

    def test_missing_source_metadata_is_not_called_empty_pool(self):
        result = pzo.classify_direction(row(sources=...))
        self.assertEqual(result["outcome"], "provider_source_metadata_unavailable")
        self.assertEqual(result["source_metadata_state"], "unavailable")

    def test_nonempty_source_pool_with_zero_model_rows_is_distinct(self):
        sources = [{"title": "Source", "url": "https://example.com/a"}]
        result = pzo.classify_direction(row(sources=sources))
        self.assertEqual(result["outcome"], "provider_sources_present_no_candidate")
        self.assertEqual(result["consulted_source_count"], 1)

    def test_model_rejections_win_over_generic_raw_zero(self):
        result = pzo.classify_direction(
            row(
                sources=[{"url": "https://example.com/a"}],
                model_rejections=[
                    {
                        "title": "Weak item",
                        "url": "https://example.com/a",
                        "reason_code": "insufficient_significance",
                        "reason": "minor",
                    }
                ],
            )
        )
        self.assertEqual(result["outcome"], "model_rejected_all")

    def test_raw_candidate_validator_rejection_is_not_raw_zero(self):
        result = pzo.classify_direction(
            row(
                raw=[{"title": "Candidate"}],
                validator_rejections=[{"title": "Candidate", "errors": ["duplicate"]}],
                sources=[{"url": "https://example.com/a"}],
            )
        )
        self.assertFalse(result["raw_zero"])
        self.assertEqual(result["outcome"], "validator_rejected_all")

    def test_successful_candidate_is_classified_without_changing_health(self):
        good = row(
            direction_id="global_breaking",
            raw=[{"title": "Candidate"}],
            accepted=1,
            sources=[{"url": "https://example.com/a"}],
        )
        result = pzo.classify_direction(good)
        self.assertEqual(result["outcome"], "candidate_accepted")

        primary = {
            "status": "complete",
            "search_budget": {"completed_calls": 1, "maximum_calls": 1},
            "directions": [good],
        }
        health = discovery_health._primary_health(primary)
        self.assertEqual(health["status"], discovery_health.HEALTHY)
        self.assertEqual(
            health["details"]["primary_outcome_diagnostics"]["directions"][0]["outcome"],
            "candidate_accepted",
        )

    def test_diagnostics_are_zero_paid_and_do_not_mark_raw_zero_as_degraded(self):
        primary = {
            "status": "complete",
            "search_budget": {"completed_calls": 2, "maximum_calls": 2},
            "directions": [
                row(direction_id="major_agencies", sources=...),
                row(
                    direction_id="legal_regulation",
                    sources=[{"url": "https://example.com/reg"}],
                ),
            ],
        }
        health = discovery_health._primary_health(primary)
        diag = health["details"]["primary_outcome_diagnostics"]
        self.assertEqual(health["status"], discovery_health.HEALTHY)
        self.assertEqual(diag["openai_calls"], 0)
        self.assertEqual(diag["web_search_operations"], 0)
        self.assertEqual(diag["raw_zero_direction_count"], 2)
        self.assertEqual(
            diag["raw_zero_outcome_counts"],
            {
                "provider_source_metadata_unavailable": 1,
                "provider_sources_present_no_candidate": 1,
            },
        )

    def test_incomplete_search_is_technical_not_provider_zero(self):
        result = pzo.classify_direction(
            row(status="error", completed=0, sources=[])
        )
        self.assertEqual(result["outcome"], "technical_incomplete")


if __name__ == "__main__":
    unittest.main()
