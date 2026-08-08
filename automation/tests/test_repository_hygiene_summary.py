from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from render_repository_hygiene_summary import render_report  # noqa: E402


class RepositoryHygieneSummaryTests(unittest.TestCase):
    def _report(self) -> dict:
        return {
            "summary": {
                "main_sha": "1234567890abcdef",
                "recent_merged_prs": [37, 36, 35, 34, 33],
                "source_watchlist": 2,
                "suspected_orphans": 1,
            },
            "plan": {
                "main_sha": "1234567890abcdef",
                "branches": [
                    {"classification": "protected"},
                    {"classification": "safe_delete"},
                    {"classification": "review_only"},
                ],
                "artifacts": [
                    {"id": 10, "name": "main-ci-old", "classification": "safe_delete"},
                    {"id": 11, "name": "production-2026-08-08", "classification": "protected"},
                    {"id": 12, "name": "repository-hygiene-audit-123", "classification": "review_only"},
                ],
                "workflows": [
                    {"id": 20, "name": "Old patch", "classification": "safe_disable"},
                    {"id": 21, "name": "Main CI", "classification": "protected"},
                ],
                "workflow_runs": [{"classification": "review_only"}],
            },
        }

    def test_audit_summary_is_human_readable(self) -> None:
        text = render_report(self._report())
        self.assertIn("Repository hygiene: аудит", text)
        self.assertIn("Статус:", text)
        self.assertIn("#37", text)
        self.assertIn("Состояние репозитория", text)
        self.assertIn("| Actions artifacts | 1 | 1 | 0 |", text)
        self.assertIn("Гарантированно не трогается", text)
        self.assertIn("retention: 2 дня", text)

    def test_branch_apply_lists_deleted_and_skipped(self) -> None:
        report = self._report()
        report["branch_apply"] = {
            "deleted": ["agent/old-branch"],
            "skipped": [{"name": "agent/reused", "reason": "head_changed"}],
        }
        text = render_report(report)
        self.assertIn("очистка веток", text)
        self.assertIn("Удалено доказанно устаревших merged-веток: **1**", text)
        self.assertIn("`agent/old-branch`", text)
        self.assertIn("head_changed", text)

    def test_actions_apply_resolves_ids_to_names(self) -> None:
        report = self._report()
        report["actions_apply"] = {
            "artifacts_deleted": [10],
            "workflows_disabled": [20],
            "artifact_skipped": [],
            "workflow_skipped": [],
        }
        text = render_report(report)
        self.assertIn("очистка Actions", text)
        self.assertIn("Удалено superseded artifacts: **1**", text)
        self.assertIn("`main-ci-old` (id 10)", text)
        self.assertIn("`Old patch` (id 20)", text)


if __name__ == "__main__":
    unittest.main()
