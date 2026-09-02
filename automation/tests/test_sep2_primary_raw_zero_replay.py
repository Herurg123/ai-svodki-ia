from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import primary_zero_outcome as pzo

FIXTURE = ROOT / "automation" / "fixtures" / "recall" / "primary-raw-zero-2026-09-02.json"


class Sep2PrimaryRawZeroReplayTests(unittest.TestCase):
    def test_all_saved_raw_zero_lanes_classify_as_rejections_only(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(fixture["completed_primary_searches"], 12)
        self.assertEqual(fixture["raw_zero_direction_count"], 8)
        self.assertFalse(fixture["event_level_causality_claim"])

        for saved in fixture["directions"]:
            rejection = {
                "title": "saved rejection evidence",
                "url": "https://example.com/rejected",
                "reason_code": "other",
                "reason": "saved model rejection row",
            }
            source = {
                "title": "saved provider source evidence",
                "url": "https://example.com/source",
            }
            row = {
                "direction_id": saved["direction_id"],
                "status": "complete_with_gaps",
                "raw_candidates": [],
                "accepted_count": saved["accepted_count"],
                "model_rejections": [rejection] * saved["model_rejection_count"],
                "validator_rejections": [],
                "web_search_calls_completed": 1,
                "api": {
                    "web_search_calls_completed": 1,
                    "consulted_sources": [source] * saved["consulted_source_count"],
                    "web_search_call_items": [
                        {
                            "id": "ws-1",
                            "status": "completed",
                            "action_type": "search",
                            "action": {"type": "search", "sources": [source]},
                        }
                    ],
                },
            }
            classified = pzo.classify_direction(row)
            self.assertEqual(
                classified["outcome"], fixture["expected_raw_zero_outcome"], saved["direction_id"]
            )
            self.assertEqual(classified["source_metadata_state"], "present")
            self.assertGreater(classified["consulted_source_count"], 0)

    def test_replay_cost_is_zero(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(fixture["paid_api_calls_for_replay"], 0)
        self.assertEqual(fixture["web_search_operations_for_replay"], 0)


if __name__ == "__main__":
    unittest.main()
