#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECOVERY = ROOT / "automation/scripts/recover_digest_artifact.py"
TEST = ROOT / "automation/tests/test_recovery_completed_audit.py"


def main() -> None:
    text = RECOVERY.read_text(encoding="utf-8")

    function_anchor = "def sha256_file(path: Path) -> str:\n"
    function = '''def restore_completed_coverage_audit(
    recovery_root: Path,
    report_path: Path,
    publication_date: str,
) -> dict[str, Any] | None:
    """Restore a completed paid coverage audit beside the recovery report.

    ensure_story_coverage.py reads this exact path before deciding whether a
    targeted web search is needed. Restoring the report prevents a manual
    recovery run from paying for the same completed audit twice.
    """

    target = report_path.parent / "coverage-audit.json"
    matches = sorted(
        path for path in recovery_root.rglob("coverage-audit.json") if path.is_file()
    )
    for path in matches:
        try:
            payload = read_json(path)
        except RecoveryError:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("publication_date") != publication_date:
            continue
        api = payload.get("api")
        if payload.get("web_search_performed") is not True:
            continue
        if not isinstance(api, dict) or api.get("status") != "completed":
            continue
        write_json(target, payload)
        return {
            "source": str(path),
            "target": str(target),
            "web_search_calls": api.get("web_search_calls"),
        }
    return None


'''
    if "def restore_completed_coverage_audit(" not in text:
        if function_anchor not in text:
            raise RuntimeError("sha256_file anchor not found")
        text = text.replace(function_anchor, function + function_anchor, 1)

    call_anchor = '''    merged_research = restore_merged_coverage_research(
        recovery_root,
        target_dir,
        publication_date,
    )

    recovered_image, image_diagnostics = restore_reusable_image(
'''
    call_replacement = '''    merged_research = restore_merged_coverage_research(
        recovery_root,
        target_dir,
        publication_date,
    )
    completed_coverage_audit = restore_completed_coverage_audit(
        recovery_root,
        report_path,
        publication_date,
    )

    recovered_image, image_diagnostics = restore_reusable_image(
'''
    if "completed_coverage_audit = restore_completed_coverage_audit(" not in text:
        if call_anchor not in text:
            raise RuntimeError("recover call anchor not found")
        text = text.replace(call_anchor, call_replacement, 1)

    report_anchor = '        "merged_coverage_research": merged_research,\n'
    report_replacement = (
        report_anchor
        + '        "completed_coverage_audit": completed_coverage_audit,\n'
    )
    if '"completed_coverage_audit": completed_coverage_audit' not in text:
        if report_anchor not in text:
            raise RuntimeError("report anchor not found")
        text = text.replace(report_anchor, report_replacement, 1)

    RECOVERY.write_text(text, encoding="utf-8")

    TEST.write_text(
        '''from __future__ import annotations

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
                json.dumps(payload, ensure_ascii=False) + "\\n",
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
                + "\\n",
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
''',
        encoding="utf-8",
    )

    print("Manual recovery audit reuse fix applied")


if __name__ == "__main__":
    main()
