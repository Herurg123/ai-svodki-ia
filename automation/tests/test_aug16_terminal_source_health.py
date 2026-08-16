from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


normalizer = load_module("normalize_aug16_terminal", SCRIPTS / "normalize_digest_artifact.py")
coverage = load_module("coverage_policy_aug16_terminal", SCRIPTS / "ensure_story_coverage_policy.py")
status = load_module("status_aug16_terminal", SCRIPTS / "summarize_production_status.py")


def primary_report(*, completed: int = 1) -> dict:
    return {
        "search_window": {
            "start_at": "2026-08-14T06:48:32+03:00",
            "end_at": "2026-08-16T02:34:19+03:00",
        },
        "directions": [
            {
                "direction_id": "major_agencies",
                "web_search_calls_completed": completed,
                "api": {"consulted_sources": [{"url": "https://www.bloomberg.com/ai"}]},
            },
            {
                "direction_id": "business",
                "web_search_calls_completed": 1,
                "api": {"consulted_sources": [{"url": "https://techcrunch.com/example"}]},
            },
        ],
    }


class Aug16TerminalSourceHealthTests(unittest.TestCase):
    def test_completed_agency_route_without_fresh_candidate_warns_not_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir)
            (artifact / "primary-recall.json").write_text(
                json.dumps(primary_report(), ensure_ascii=False), encoding="utf-8"
            )
            warning = normalizer.validate_primary_source_health(artifact)
            self.assertIsInstance(warning, str)
            self.assertIn("source-health warning", warning)
            self.assertIn("не самостоятельной причиной блокировки", warning)

    def test_incomplete_major_agencies_route_remains_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir)
            (artifact / "primary-recall.json").write_text(
                json.dumps(primary_report(completed=0), ensure_ascii=False), encoding="utf-8"
            )
            with self.assertRaises(normalizer.NormalizationError):
                normalizer.validate_primary_source_health(artifact)

    def test_editorial_rerun_error_keeps_captured_child_output(self) -> None:
        exc = subprocess.CalledProcessError(
            1,
            ["python", "run_digest_preview.py"],
            output="Пустой раздел «Китайские лидеры ИИ» не должен присутствовать",
        )
        rendered = coverage._format_exception_with_output(exc)
        self.assertIn("CalledProcessError", rendered)
        self.assertIn("Китайские лидеры ИИ", rendered)

    def test_terminal_normalization_reason_beats_old_recovery_error(self) -> None:
        previous_cwd = Path.cwd()
        previous_root = status.REPORT_ROOT
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                daily = root / "automation" / "preview" / "production-daily"
                publication = root / "automation" / "preview" / "2026-08-16"
                daily.mkdir(parents=True)
                publication.mkdir(parents=True)
                (daily / "recovery.json").write_text(
                    json.dumps({"status": "error", "error": "old recovery error"}), encoding="utf-8"
                )
                (publication / "artifact-normalization.json").write_text(
                    json.dumps({"status": "error", "error": "terminal normalization error"}), encoding="utf-8"
                )
                os.chdir(root)
                status.REPORT_ROOT = Path("automation/preview/production-daily")
                stage, reason = status.locate_reason("2026-08-16")
                self.assertEqual(stage, "Нормализация editorial artifact")
                self.assertEqual(reason, "terminal normalization error")
        finally:
            os.chdir(previous_cwd)
            status.REPORT_ROOT = previous_root


if __name__ == "__main__":
    unittest.main()
