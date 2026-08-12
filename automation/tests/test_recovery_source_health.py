from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import recover_digest_artifact as recovery


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def make_research_source(root: Path, *, primary: bool = False) -> Path:
    source = root / "source"
    source.mkdir(parents=True)
    write_json(
        source / "run-info.json",
        {
            "publication_date": "2026-08-12",
            "finished_at": "2026-08-12T05:30:00+00:00",
            "research": {
                "status": "ok",
                "temporal_anchor_version": 1,
                "response": {"response_status": "completed", "web_search_calls": 12},
            },
        },
    )
    write_json(
        source / "candidates.json",
        {
            "publication_date": "2026-08-12",
            "search_window": {
                "start_at": "2026-08-10T02:50:46+03:00",
                "end_at": "2026-08-12T02:59:49+03:00",
            },
            "coverage": [],
            "candidates": [{"id": "cand-001"}],
        },
    )
    write_json(source / "research-output-raw.json", {"candidates": [{"id": "cand-001"}]})
    if primary:
        write_json(
            source / "primary-recall.json",
            {
                "directions": [
                    {
                        "direction_id": "major_agencies",
                        "web_search_calls_completed": 1,
                        "api": {"consulted_sources": []},
                    }
                ]
            },
        )
    return source


class RecoverySourceHealthTests(unittest.TestCase):
    def test_prior_validation_error_makes_research_unusable(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = make_research_source(Path(tmp))
            write_json(
                source / "artifact-validation.json",
                {"status": "error", "errors": [{"code": "broken"}]},
            )
            reusable, reason = recovery.research_is_reusable(source)
            self.assertFalse(reusable)
            self.assertIn("artifact-validation.json", reason or "")

    def test_prior_normalization_error_makes_research_unusable(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = make_research_source(Path(tmp))
            write_json(
                source / "artifact-normalization.json",
                {"status": "error", "error": "source-health degraded"},
            )
            reusable, reason = recovery.research_is_reusable(source)
            self.assertFalse(reusable)
            self.assertIn("artifact-normalization.json", reason or "")

    def test_saved_primary_without_agency_sources_is_unusable(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = make_research_source(Path(tmp), primary=True)
            reusable, reason = recovery.research_is_reusable(source)
            self.assertFalse(reusable)
            self.assertIn("major_agencies", reason or "")

    def test_full_source_no_longer_bypasses_research_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = make_research_source(root)
            for name in recovery.FULL_REQUIRED_FILES:
                path = source / name
                if path.exists():
                    continue
                write_json(path, {})
            write_json(source / "artifact-validation.json", {"status": "error", "errors": ["bad"]})
            with self.assertRaises(recovery.RecoveryError):
                recovery.choose_source(root, "2026-08-12")

    def test_healthy_legacy_research_without_primary_report_remains_reusable(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = make_research_source(Path(tmp))
            reusable, reason = recovery.research_is_reusable(source)
            self.assertTrue(reusable, reason)


if __name__ == "__main__":
    unittest.main()
