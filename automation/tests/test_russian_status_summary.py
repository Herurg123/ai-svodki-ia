
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import summarize_production_status as status  # noqa: E402


class RussianStatusSummaryTests(unittest.TestCase):
    def test_partial_audit_is_reported_as_failed_and_unchecked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            old = Path.cwd()
            os.chdir(temporary)
            try:
                report_dir = Path("automation/preview/production-daily")
                report_dir.mkdir(parents=True)
                (report_dir / "coverage-audit.json").write_text(
                    json.dumps(
                        {
                            "status": "error",
                            "audit_needed": True,
                            "audit_status": "partial",
                            "required_directions": ["security_world", "security_russia"],
                            "checked_directions": ["security_world"],
                            "partial_directions": ["security_russia"],
                            "unchecked_directions": [],
                            "search_budget": {
                                "completed_calls": 5,
                                "maximum_calls": 7,
                            },
                            "audit_added_candidates": 0,
                            "editorial_rerun_performed": False,
                            "time_precision_warnings": [{"title": "Date-only"}],
                            "error": (
                                "Обязательный coverage audit не завершён: "
                                "security_russia не проверен"
                            ),
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                markdown, annotation = status.build_summary(
                    job_status="failure",
                    publication_date="2026-08-01",
                    publish="true",
                    recovery_run_id="",
                    run_url="https://github.test/run",
                    commit_sha="abc",
                )
            finally:
                os.chdir(old)

        self.assertIsNotNone(annotation)
        self.assertIn("ИИ-Сводка не опубликована", markdown)
        self.assertIn("partial", markdown)
        self.assertIn("1/2", markdown)
        self.assertIn("security_russia", markdown)
        self.assertIn("предел 7", markdown)
        self.assertIn("time_precision", markdown)

    def test_zero_story_stop_is_translated_and_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            old = Path.cwd()
            os.chdir(temporary)
            try:
                report_dir = Path(
                    "automation/preview/production-daily"
                )
                report_dir.mkdir(parents=True)
                (report_dir / "coverage-audit.json").write_text(
                    json.dumps(
                        {
                            "status": "error",
                            "error": (
                                "RuntimeError: После основного и дополнительного "
                                "поиска не осталось ни одного достойного сюжета"
                            ),
                            "web_search_performed": True,
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                markdown, annotation = status.build_summary(
                    job_status="failure",
                    publication_date="2026-07-26",
                    publish="true",
                    recovery_run_id="",
                    run_url="https://github.test/run",
                    commit_sha="",
                )
            finally:
                os.chdir(old)

        self.assertIn("ИИ-Сводка не опубликована", markdown)
        self.assertIn(
            "не найдено ни одного достойного сюжета",
            markdown,
        )
        self.assertIn(
            "не техническая авария",
            markdown,
        )
        self.assertIsNotNone(annotation)

    def test_insufficient_quota_is_explicit_and_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            old = Path.cwd()
            os.chdir(temporary)
            try:
                report_dir = Path("automation/preview/production-daily")
                report_dir.mkdir(parents=True)
                (report_dir / "research-error.json").write_text(
                    json.dumps(
                        {
                            "status": "error",
                            "stage": "primary_recall",
                            "publication_date": "2026-08-25",
                            "reason_code": "openai_insufficient_quota",
                            "error_type": "PrimaryRecallResponseError",
                            "error_message": (
                                "Error code: 429 - {'error': {'message': "
                                "'You have no credits remaining. Add credits to continue using the API.', "
                                "'type': 'insufficient_quota', "
                                "'code': 'credit_balance_exhausted'}}"
                            ),
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                markdown, annotation = status.build_summary(
                    job_status="failure",
                    publication_date="2026-08-25",
                    publish="true",
                    recovery_run_id="",
                    run_url="https://github.test/run",
                    commit_sha="",
                )
            finally:
                os.chdir(old)

        self.assertIsNotNone(annotation)
        self.assertIn("Research API / Primary Recall", markdown)
        self.assertIn("Недостаточно средств на балансе OpenAI API", markdown)
        self.assertIn("429", markdown)
        self.assertIn("insufficient_quota", markdown)
        self.assertIn("credit_balance_exhausted", markdown)
        self.assertIn("publication_date=2026-08-25", markdown)
        self.assertIn("publish=true", markdown)
        self.assertIn("force_fresh_research=true", markdown)
        self.assertIn("recovery_run_id", markdown)


if __name__ == "__main__":
    unittest.main()
