from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import run_digest_preview as runner


class RunDigestPreviewHybridTests(unittest.TestCase):
    def test_research_input_is_detected_for_paid_rerun_guard(self):
        argv = [
            "run_digest_preview.py",
            "--publication-date",
            "2026-08-09",
            "--research-input",
            "automation/preview/production-daily/merged.json",
        ]
        self.assertEqual(
            runner.research_input_from_argv(argv),
            "automation/preview/production-daily/merged.json",
        )

    def test_fresh_primary_has_no_research_input_guard(self):
        argv = [
            "run_digest_preview.py",
            "--publication-date",
            "2026-08-09",
        ]
        self.assertIsNone(runner.research_input_from_argv(argv))

    def test_hybrid_rollback_code_preserves_merged_candidates_for_coverage(self):
        source = (SCRIPT_DIR / "run_digest_preview.py").read_text(encoding="utf-8")
        self.assertIn('coverage_handoff_preserved', source)
        self.assertIn('_write_json(output_dir / "candidates.json", merged_payload)', source)
        self.assertIn('merged candidates preserved for coverage', source)


if __name__ == "__main__":
    unittest.main()
