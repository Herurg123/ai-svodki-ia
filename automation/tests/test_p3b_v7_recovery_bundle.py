from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import recover_digest_artifact as recovery

DATE = "2026-09-17"


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _journal(evidence_version: int) -> dict:
    return {
        "version": 1,
        "publication_date": DATE,
        "state": "processed",
        "processed_snapshot": {
            "candidates": [
                {
                    "id": "stale",
                    "audit_direction": "weak_source_exact_binding",
                }
            ],
            "weak_source_exact_binding": {
                "status": "bound_candidate",
                "disposition": "positive_exact_binding",
                "candidate_count": 1,
                "binder_evidence_version": evidence_version,
            },
        },
    }


class P3bV7RecoveryBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.recovery_root = self.root / "recovery"
        self.evidence_root = self.recovery_root / "preview"
        self.source = self.evidence_root / DATE
        self.state = self.evidence_root / "production-daily"
        self.target_state = self.root / "current" / "production-daily"
        self.report = self.target_state / "recovery.json"
        self.source.mkdir(parents=True)
        self.state.mkdir(parents=True)

    @property
    def marker(self) -> Path:
        return self.state / f"coverage-p3b-v7-revocation-{DATE}.json"

    def _choose(self):
        def fake_choose(_root: Path, _date: str):
            recovery._base._ACTIVE_EVIDENCE_ROOT = self.evidence_root
            return self.source, "full", []

        with mock.patch.object(
            recovery, "_P0_CHOOSE_SOURCE", side_effect=fake_choose
        ):
            return recovery.choose_source(self.recovery_root, DATE)

    def test_pending_invalidated_marker_downgrades_full_recovery(self) -> None:
        _write(
            self.marker,
            {
                "publication_date": DATE,
                "state": "pending",
                "publication_snapshot_invalidated": True,
            },
        )

        source, mode, diagnostics = self._choose()

        self.assertEqual(source, self.source)
        self.assertEqual(mode, "partial_editorial")
        self.assertTrue(
            any(
                row.get("status") == "p3b-v7-recovery-rebuild-required"
                for row in diagnostics
            )
        )

    def test_pre_v7_stale_positive_journal_downgrades_but_current_or_completed_does_not(self) -> None:
        journal = self.state / f"{recovery.JOURNAL_PREFIX}{DATE}.json"
        _write(journal, _journal(5))
        self.assertEqual(self._choose()[1], "partial_editorial")

        _write(journal, _journal(recovery._P3B_CURRENT_BINDER_EVIDENCE_VERSION))
        self.assertEqual(self._choose()[1], "full")

        _write(journal, _journal(5))
        _write(
            self.marker,
            {
                "publication_date": DATE,
                "state": "completed",
                "publication_snapshot_invalidated": True,
            },
        )
        self.assertEqual(self._choose()[1], "full")

    def test_v7_marker_and_backups_restore_only_from_selected_bundle(self) -> None:
        marker_value = {
            "publication_date": DATE,
            "state": "blocked",
            "publication_snapshot_invalidated": True,
        }
        _write(self.marker, marker_value)
        backup = self.state / (
            f"coverage-p3b-v7-revocation-{DATE}.merged-research.original.json"
        )
        _write(backup, {"candidates": [{"id": "forensic"}]})
        recovery._base._ACTIVE_EVIDENCE_ROOT = self.evidence_root

        result = recovery._restore_p3b_v7_state(
            recovery_root=self.recovery_root,
            report_path=self.report,
            publication_date=DATE,
        )

        self.assertEqual(result["status"], "restored")
        restored_marker = self.target_state / self.marker.name
        restored_backup = self.target_state / backup.name
        self.assertEqual(
            json.loads(restored_marker.read_text(encoding="utf-8")), marker_value
        )
        self.assertTrue(restored_backup.is_file())

        # Existing divergent state must fail closed rather than mixing bundles.
        _write(restored_marker, {"publication_date": DATE, "state": "completed"})
        with self.assertRaises(recovery.RecoveryError):
            recovery._restore_p3b_v7_state(
                recovery_root=self.recovery_root,
                report_path=self.report,
                publication_date=DATE,
            )


if __name__ == "__main__":
    unittest.main()
