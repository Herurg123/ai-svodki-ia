from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


recovery = load("coverage_optional_slot_recovery", "recover_digest_artifact.py")
guard = sys.modules["coverage_slot_guard"]


class CoverageOptionalSlotRecoveryTests(unittest.TestCase):
    def _saved_state(self, evidence_root: Path, date: str = "2026-09-11"):
        state_dir = evidence_root / "production-daily"
        reservation = guard.prepare_slot(
            state_dir=state_dir,
            publication_date=date,
            owner="unresolved_high_signal_resolution",
            search_window={"start_at": "a", "end_at": "b"},
            request_contract={"query": "exact saved query"},
            bundle_identity={"bundle": "selected"},
        )
        reservation.mark_request_started()
        reservation.save_raw_response({"id": "resp-1", "status": "completed"})
        return reservation

    def test_only_selected_bundle_optional_slot_state_is_restored(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            selected = root / "bundle-selected" / "preview"
            other = root / "bundle-other" / "preview"
            target = root / "target" / "production-daily"
            target.mkdir(parents=True)
            selected.mkdir(parents=True)
            other.mkdir(parents=True)
            self._saved_state(other)

            original = recovery._base._ACTIVE_EVIDENCE_ROOT
            try:
                recovery._base._ACTIVE_EVIDENCE_ROOT = selected
                result = recovery._restore_optional_slot(
                    recovery_root=root,
                    report_path=target / "recovery-report.json",
                    publication_date="2026-09-11",
                )
            finally:
                recovery._base._ACTIVE_EVIDENCE_ROOT = original

            self.assertEqual(result["status"], "not_present")
            self.assertFalse(
                guard.journal_path(target, "2026-09-11").exists(),
                "state from another same-date bundle must never be mixed in",
            )

    def test_selected_bundle_restores_journal_and_response(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            selected = root / "bundle-selected" / "preview"
            target = root / "target" / "production-daily"
            target.mkdir(parents=True)
            selected.mkdir(parents=True)
            self._saved_state(selected)

            original = recovery._base._ACTIVE_EVIDENCE_ROOT
            try:
                recovery._base._ACTIVE_EVIDENCE_ROOT = selected
                result = recovery._restore_optional_slot(
                    recovery_root=root,
                    report_path=target / "recovery-report.json",
                    publication_date="2026-09-11",
                )
            finally:
                recovery._base._ACTIVE_EVIDENCE_ROOT = original

            self.assertEqual(result["status"], "restored")
            self.assertEqual(result["state"], "response_saved")
            self.assertTrue(guard.journal_path(target, "2026-09-11").is_file())
            self.assertTrue(guard.response_path(target, "2026-09-11").is_file())

    def test_corrupt_selected_response_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            selected = root / "bundle-selected" / "preview"
            target = root / "target" / "production-daily"
            target.mkdir(parents=True)
            selected.mkdir(parents=True)
            self._saved_state(selected)
            guard.response_path(selected / "production-daily", "2026-09-11").write_text(
                '{"tampered":true}\n', encoding="utf-8"
            )

            original = recovery._base._ACTIVE_EVIDENCE_ROOT
            try:
                recovery._base._ACTIVE_EVIDENCE_ROOT = selected
                with self.assertRaises(recovery.RecoveryError):
                    recovery._restore_optional_slot(
                        recovery_root=root,
                        report_path=target / "recovery-report.json",
                        publication_date="2026-09-11",
                    )
            finally:
                recovery._base._ACTIVE_EVIDENCE_ROOT = original

    def test_divergent_existing_target_journal_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            selected = root / "bundle-selected" / "preview"
            target = root / "target" / "production-daily"
            selected.mkdir(parents=True)
            target.mkdir(parents=True)
            self._saved_state(selected)
            existing = guard.prepare_slot(
                state_dir=target,
                publication_date="2026-09-11",
                owner="unresolved_high_signal_resolution",
                search_window={"start_at": "different", "end_at": "window"},
                request_contract={"query": "different query"},
                bundle_identity={"bundle": "different"},
            )
            before = guard.journal_path(target, "2026-09-11").read_bytes()

            original = recovery._base._ACTIVE_EVIDENCE_ROOT
            try:
                recovery._base._ACTIVE_EVIDENCE_ROOT = selected
                with self.assertRaises(recovery.RecoveryError):
                    recovery._restore_optional_slot(
                        recovery_root=root,
                        report_path=target / "recovery-report.json",
                        publication_date="2026-09-11",
                    )
            finally:
                recovery._base._ACTIVE_EVIDENCE_ROOT = original

            self.assertEqual(before, guard.journal_path(target, "2026-09-11").read_bytes())
            self.assertEqual(existing.state, "reserved")


if __name__ == "__main__":
    unittest.main()
