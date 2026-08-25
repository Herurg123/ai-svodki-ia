from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import primary_recall_search as primary  # noqa: E402


class PrimaryFailureSummaryBridgeTests(unittest.TestCase):
    def test_quota_failure_is_persisted_for_final_summary(self) -> None:
        message = (
            "Error code: 429 - {'error': {'message': 'You have no credits remaining.', "
            "'type': 'insufficient_quota', 'code': 'credit_balance_exhausted'}}"
        )
        with tempfile.TemporaryDirectory() as temporary:
            old_root = primary.PRODUCTION_PREVIEW_ROOT
            primary.PRODUCTION_PREVIEW_ROOT = Path(temporary)
            try:
                primary._persist_primary_failure(
                    "2026-08-25",
                    RuntimeError(message),
                )
                payload = json.loads(
                    (Path(temporary) / "research-error.json").read_text(
                        encoding="utf-8"
                    )
                )
            finally:
                primary.PRODUCTION_PREVIEW_ROOT = old_root

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["stage"], "primary_recall")
        self.assertEqual(payload["publication_date"], "2026-08-25")
        self.assertEqual(payload["reason_code"], "openai_insufficient_quota")
        self.assertEqual(payload["error_type"], "RuntimeError")
        self.assertIn("credit_balance_exhausted", payload["error_message"])

    def test_non_quota_failure_keeps_generic_primary_reason_code(self) -> None:
        self.assertEqual(
            primary._primary_failure_reason_code("temporary transport failure"),
            "primary_recall_error",
        )


if __name__ == "__main__":
    unittest.main()
