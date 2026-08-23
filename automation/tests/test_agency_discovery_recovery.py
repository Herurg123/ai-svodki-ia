from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import agency_discovery_recovery_entry as recovery_entry
import recover_digest_artifact as recovery


DATE = "2026-08-23"


def primary_report(*, raw_count: int = 0, accepted_count: int = 0) -> dict:
    return {
        "publication_date": DATE,
        "directions": [
            {
                "direction_id": "major_agencies",
                "status": "complete",
                "raw_candidates": [{"title": "raw"}] * raw_count,
                "accepted_count": accepted_count,
            }
        ],
    }


class AgencyDiscoveryRecoveryTests(unittest.TestCase):
    def test_full_recovery_with_trigger_and_no_rescue_state_needs_upgrade(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "primary-recall.json").write_text(
                json.dumps(primary_report()), encoding="utf-8"
            )
            needed, reason = recovery.agency_discovery_upgrade_needed(
                source, root, DATE
            )
            self.assertTrue(needed)
            self.assertEqual(reason, "agency_discovery_first_attempt_pending")

    def test_nonempty_major_agencies_does_not_force_recovery_upgrade(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "primary-recall.json").write_text(
                json.dumps(primary_report(raw_count=1, accepted_count=1)),
                encoding="utf-8",
            )
            needed, reason = recovery.agency_discovery_upgrade_needed(
                source, root, DATE
            )
            self.assertFalse(needed)
            self.assertEqual(reason, "major_agencies_not_triggered")

    def test_search_started_is_not_retried_or_upgraded_to_new_search(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "primary-recall.json").write_text(
                json.dumps(primary_report()), encoding="utf-8"
            )
            (source / "agency-discovery-rescue.json").write_text(
                json.dumps(
                    {
                        "publication_date": DATE,
                        "search_strategy": "agency_discovery_rescue",
                        "state": "search_started",
                    }
                ),
                encoding="utf-8",
            )
            needed, reason = recovery.agency_discovery_upgrade_needed(
                source, root, DATE
            )
            self.assertFalse(needed)
            self.assertEqual(reason, "agency_discovery_indeterminate_no_retry")

    def test_saved_search_response_requires_text_runtime_for_merge_and_editorial(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "primary-recall.json").write_text(
                json.dumps(primary_report()), encoding="utf-8"
            )
            (source / "agency-discovery-rescue.json").write_text(
                json.dumps(
                    {
                        "publication_date": DATE,
                        "search_strategy": "agency_discovery_rescue",
                        "state": "search_completed",
                    }
                ),
                encoding="utf-8",
            )
            needed, reason = recovery.agency_discovery_upgrade_needed(
                source, root, DATE
            )
            self.assertTrue(needed)
            self.assertEqual(
                reason, "agency_discovery_resume_pending:search_completed"
            )

    def test_freshness_error_cleanup_removes_only_rescue_candidates(self):
        research = {
            "candidates": [
                {"id": "cand-001", "title": "Primary"},
                {
                    "id": "cand-002",
                    "title": "Rescue",
                    "audit_direction": "agency_discovery_rescue",
                },
                {"id": "cand-003", "title": "Hybrid"},
            ]
        }
        cleaned = recovery_entry._without_rescue_candidates(research)
        self.assertEqual(
            [item["title"] for item in cleaned["candidates"]],
            ["Primary", "Hybrid"],
        )
        self.assertEqual(
            [item["id"] for item in cleaned["candidates"]],
            ["cand-001", "cand-002"],
        )


if __name__ == "__main__":
    unittest.main()
