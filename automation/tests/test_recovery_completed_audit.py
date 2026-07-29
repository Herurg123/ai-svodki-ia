from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "automation/scripts/recover_digest_artifact.py"
spec = importlib.util.spec_from_file_location("recover_completed_audit_test", MODULE_PATH)
assert spec and spec.loader
recovery = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = recovery
spec.loader.exec_module(recovery)


class CompletedCoverageAuditRecoveryTests(unittest.TestCase):
    def test_completed_audit_is_restored_for_manual_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recovery_root = root / "download"
            source = recovery_root / "production-daily" / "coverage-audit.json"
            source.parent.mkdir(parents=True)
            payload = {
                "status": "error",
                "publication_date": "2026-07-29",
                "web_search_performed": True,
                "api": {"status": "completed", "web_search_calls": 4},
            }
            source.write_text(
                json.dumps(payload, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            report_path = root / "preview" / "production-daily" / "recovery.json"

            restored = recovery.restore_completed_coverage_audit(
                recovery_root,
                report_path,
                "2026-07-29",
            )

            self.assertIsNotNone(restored)
            target = report_path.parent / "coverage-audit.json"
            self.assertTrue(target.is_file())
            self.assertEqual(
                json.loads(target.read_text(encoding="utf-8")),
                payload,
            )
            self.assertEqual(restored["web_search_calls"], 4)

    def test_incomplete_or_wrong_date_audit_is_not_restored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recovery_root = root / "download"
            source = recovery_root / "production-daily" / "coverage-audit.json"
            source.parent.mkdir(parents=True)
            source.write_text(
                json.dumps(
                    {
                        "publication_date": "2026-07-28",
                        "web_search_performed": True,
                        "api": {"status": "completed"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            report_path = root / "preview" / "production-daily" / "recovery.json"

            restored = recovery.restore_completed_coverage_audit(
                recovery_root,
                report_path,
                "2026-07-29",
            )

            self.assertIsNone(restored)
            self.assertFalse((report_path.parent / "coverage-audit.json").exists())


if __name__ == "__main__":
    unittest.main()
