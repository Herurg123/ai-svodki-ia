from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation" / "scripts"))

import ensure_story_coverage as coverage
import recover_digest_artifact as recovery

CROSS_MIDNIGHT = {
    "start_at": "2026-08-08T02:48:25+03:00",
    "end_at": "2026-08-09T02:44:13+03:00",
}
SAME_UTC_DATE = {
    "start_at": "2026-08-08T02:48:25+03:00",
    "end_at": "2026-08-08T20:44:13+03:00",
}


class TemporalAnchorContractTests(unittest.TestCase):
    def test_research_prompt_declares_authoritative_now(self) -> None:
        text = (ROOT / "automation/prompts/research_candidates.md").read_text(encoding="utf-8")
        self.assertIn("Авторитетное текущее время этой исследовательской задачи", text)
        self.assertIn("{{SEARCH_WINDOW_END_AT}}", text)
        self.assertIn("не является будущим", text)

    def test_coverage_prompt_declares_authoritative_now(self) -> None:
        text = (ROOT / "automation/prompts/coverage_audit.md").read_text(encoding="utf-8")
        self.assertIn("Авторитетное текущее время этого audit-прохода", text)
        self.assertIn("не является будущим", text)

    def test_versions_are_current(self) -> None:
        self.assertEqual(coverage.TEMPORAL_ANCHOR_VERSION, 1)
        self.assertEqual(coverage.RECALL_SENTINEL_VERSION, 8)
        self.assertEqual(recovery.TEMPORAL_ANCHOR_VERSION, 1)

    def _write_research(self, root: Path, *, version: int | None, window: dict) -> None:
        research = {"status": "ok"}
        if version is not None:
            research["temporal_anchor_version"] = version
        (root / "run-info.json").write_text(json.dumps({"research": research}), encoding="utf-8")
        (root / "candidates.json").write_text(
            json.dumps({"candidates": [], "search_window": window}), encoding="utf-8"
        )

    def test_legacy_cross_midnight_research_is_not_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_research(root, version=None, window=CROSS_MIDNIGHT)
            usable, reason = recovery.research_is_reusable(root)
            self.assertFalse(usable)
            self.assertIn("temporal anchor", reason or "")

    def test_current_cross_midnight_research_is_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_research(root, version=1, window=CROSS_MIDNIGHT)
            usable, reason = recovery.research_is_reusable(root)
            self.assertTrue(usable)
            self.assertIsNone(reason)

    def test_legacy_same_utc_date_research_remains_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_research(root, version=None, window=SAME_UTC_DATE)
            usable, reason = recovery.research_is_reusable(root)
            self.assertTrue(usable)
            self.assertIsNone(reason)

    def test_legacy_cross_midnight_coverage_plan_is_discarded(self) -> None:
        plan = {"attempts": [], "search_budget": {"maximum_calls": 7}}
        self.assertIsNone(coverage._prepare_prior_plan(plan, CROSS_MIDNIGHT))

    def test_current_cross_midnight_coverage_plan_can_be_reused(self) -> None:
        plan = {
            "temporal_anchor_version": 1,
            "attempts": [],
            "search_budget": {"maximum_calls": 7},
        }
        prepared = coverage._prepare_prior_plan(plan, CROSS_MIDNIGHT)
        self.assertIsInstance(prepared, dict)
        self.assertEqual(prepared.get("temporal_anchor_version"), 1)

    def test_sentinel_prompt_uses_authoritative_now(self) -> None:
        prompt = coverage.build_recall_sentinel_prompt(
            publication_date="2026-08-09",
            search_window=CROSS_MIDNIGHT,
            existing_candidates=[],
            archive={"items": []},
        )
        self.assertIn("Авторитетное текущее время этого sentinel-прохода", prompt)
        self.assertIn(CROSS_MIDNIGHT["end_at"], prompt)
        self.assertIn("не является будущим", prompt)

    def test_workflow_refuses_legacy_terminal_stop(self) -> None:
        workflow = (ROOT / ".github/workflows/daily-production.yml").read_text(encoding="utf-8")
        self.assertIn('data.get("temporal_anchor_version") == 1', workflow)
        self.assertIn('(data.get("recall_sentinel") or {}).get("version") == 8', workflow)

    def test_main_research_persists_temporal_version(self) -> None:
        source = (ROOT / "automation/scripts/generate_digest_preview.py").read_text(encoding="utf-8")
        self.assertIn('TEMPORAL_ANCHOR_VERSION = 1', source)
        self.assertIn('run_info["research"]["temporal_anchor_version"]', source)


if __name__ == "__main__":
    unittest.main()
