from __future__ import annotations

import json
import shutil
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import generate_digest_preview as generator
import run_digest_preview as wrapper


class PrimaryRuntimeIngressTests(unittest.TestCase):
    def setUp(self):
        self.runtime_root = ROOT / "automation" / "fixtures" / "research" / ".runtime"
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.runtime_file = self.runtime_root / "unit-primary-runtime.json"
        payload = {
            "status": "ok",
            "error_message": None,
            "publication_date": "2026-08-12",
            "search_window": {
                "start_at": "2026-08-10T02:50:46+03:00",
                "end_at": "2026-08-12T02:59:49+03:00",
                "latest_archive_at": "2026-08-11T02:50:46+03:00",
                "start_date": "2026-08-10",
                "end_date": "2026-08-12",
                "latest_archive_date": "2026-08-11",
            },
            "coverage": [],
            "candidates": [],
            "rejected_as_duplicates": [],
            "research_notes": "unit runtime ingress",
        }
        self.runtime_file.write_text(json.dumps(payload), encoding="utf-8")
        self.original_expected_search_window = generator.expected_search_window

    def tearDown(self):
        generator.expected_search_window = self.original_expected_search_window
        try:
            self.runtime_file.unlink()
        except FileNotFoundError:
            pass
        try:
            self.runtime_root.rmdir()
        except OSError:
            pass

    def test_generator_accepts_internal_runtime_subtree_without_weakening_guard(self):
        relative = self.runtime_file.relative_to(ROOT)
        resolved = generator.resolve_research_input(str(relative))
        self.assertEqual(resolved, self.runtime_file.resolve())
        with self.assertRaises(RuntimeError):
            generator.resolve_research_input(
                "automation/preview/production-daily/primary-recall-research-2026-08-12.json"
            )

    def test_wrapper_applies_saved_effective_window_only_for_trusted_runtime_input(self):
        relative = self.runtime_file.relative_to(ROOT)
        applied = wrapper.patch_trusted_runtime_window(generator, str(relative))
        self.assertTrue(applied)
        start_at, end_at = generator.expected_search_window(
            object(), {}, {}, cutoff_at=None
        )
        self.assertEqual(start_at.isoformat(), "2026-08-10T02:50:46+03:00")
        self.assertEqual(end_at.isoformat(), "2026-08-12T02:59:49+03:00")

    def test_wrapper_refuses_to_patch_window_for_normal_fixture_or_preview_path(self):
        self.assertFalse(
            wrapper.patch_trusted_runtime_window(
                generator,
                "automation/fixtures/research/some-normal-fixture.json",
            )
        )
        self.assertFalse(
            wrapper.patch_trusted_runtime_window(
                generator,
                "automation/preview/production-daily/anything.json",
            )
        )


if __name__ == "__main__":
    unittest.main()
