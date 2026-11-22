"""Offline replay of the 2026-11-22 Coverage->Editorial Repair failure.

The real Coverage policy public main() is exercised with a production-shaped
recovered report and saved research. The only replaced boundary is the
provider-facing editorial child, to guarantee zero paid requests.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import ensure_story_coverage_policy as policy  # noqa: E402

DATE = "2026-11-22"


class November22SealedCoveragePolicyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.artifact = self.root / "automation/preview" / DATE
        self.state = self.root / "automation/preview/production-daily"
        self.runtime = self.root / "automation/fixtures/research/.runtime"
        self.archive = self.root / "automation/archive/index.json"
        self.report = self.state / "coverage-audit.json"
        self.persisted = self.state / f"coverage-audit-merged-candidates-{DATE}.json"
        self.journal = self.state / f"editorial-repair-{DATE}.json"
        self.artifact.mkdir(parents=True)
        self.state.mkdir(parents=True)
        self.archive.parent.mkdir(parents=True)
        self.archive.write_text('{"items": []}\n', encoding="utf-8")
        self.base = {
            "publication_date": DATE,
            "search_window": {
                "start_at": "2026-11-21T06:00:00+03:00",
                "end_at": "2026-11-22T06:00:00+03:00",
                "start_date": "2026-11-21",
                "end_date": "2026-11-22",
            },
            "candidates": [{
                "id": "cand-001",
                "title": "Saved candidate",
                "geography": "world",
                "recommendation": "include",
                "primary_source": {
                    "title": "Saved candidate",
                    "publisher": "Example",
                    "url": "https://example.org/news/nov22",
                },
                "published_date": "2026-11-21",
                "organization": "Example",
                "topic": "Release",
                "category": "models",
            }],
            "research_notes": (
                "Primary recall saved.\n"
                "Targeted coverage audit добавил кандидатов: 2.\n"
                "Targeted coverage audit добавил кандидатов: 1."
            ),
        }
        self.report.write_text(json.dumps({
            "status": "error",
            "audit_status": "complete_with_gaps",
            "audit_state": "completed_usable",
            "api": {"status": "completed"},
            "web_search_performed": True,
            "checked_directions": list(policy.AUDIT_DIRECTION_IDS),
            "directions": [{
                "direction_id": "general_coverage_gaps",
                "candidates": [copy.deepcopy(self.base["candidates"][0])],
            }],
            "search_budget": {"completed_calls": 6, "maximum_calls": 7},
            "editorial_completion_required": True,
            "editorial_completion_performed": False,
        }, ensure_ascii=False), encoding="utf-8")
        self._save(self.artifact / "candidates.json", self.base)
        self._save(self.artifact / "editorial-output-raw.json", {
            "status": "error",
            "selected_candidate_ids": [],
        })

    @staticmethod
    def _save(path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")

    def _run(self, on_rerun):
        argv = [
            "ensure_story_coverage.py",
            "--artifact-dir", str(self.artifact),
            "--archive", str(self.archive),
            "--publication-date", DATE,
            "--model", "gpt-5.6-terra",
            "--report", str(self.report),
        ]
        with patch.object(sys, "argv", argv), \
             patch.object(policy, "RUNTIME_RESEARCH_ROOT", self.runtime), \
             patch.object(policy, "PERSISTED_RESEARCH_ROOT", self.state), \
             patch.object(policy, "rerun_editorial", side_effect=on_rerun):
            return policy.main()

    def test_recovered_complete_audit_keeps_sealed_research_bytes_unchanged(self):
        self._save(self.persisted, self.base)
        self._save(self.journal, {"state": "response_saved", "immutable": True})
        old_bytes = self.persisted.read_bytes()
        old_journal = self.journal.read_bytes()
        invocations = []

        def fake_editorial(**kwargs):
            invocations.append(kwargs)
            self.assertEqual(
                json.loads(kwargs["merged_research_path"].read_text()),
                self.base,
            )
            self._save(self.artifact / "stories.json", [
                {"geography": "world", "section": "world"}
            ])

        result = self._run(fake_editorial)
        self.assertEqual(result, 0)
        self.assertEqual(len(invocations), 1)
        self.assertEqual(self.persisted.read_bytes(), old_bytes)
        self.assertEqual(self.journal.read_bytes(), old_journal)
        self.assertEqual(
            json.loads(self.report.read_text())["prior_audit_reused"], True
        )

    def test_changed_replay_cannot_overwrite_saved_input_or_reissue_editorial(self):
        self._save(self.persisted, self.base)
        self._save(self.journal, {"state": "response_saved", "immutable": True})
        old_bytes = self.persisted.read_bytes()
        old_journal = self.journal.read_bytes()
        changed = copy.deepcopy(self.base)
        changed["research_notes"] += "\nInjected extra note."
        self._save(self.artifact / "candidates.json", changed)
        invocations = []
        result = self._run(lambda **kwargs: invocations.append(kwargs))
        self.assertEqual(result, 1)
        self.assertEqual(invocations, [])
        self.assertEqual(self.persisted.read_bytes(), old_bytes)
        self.assertEqual(self.journal.read_bytes(), old_journal)
        self.assertIn(
            "saved research is not overwritten",
            json.loads(self.report.read_text())["error"]
        )

    def test_missing_sealed_research_stops_before_provider(self):
        self._save(self.journal, {"state": "response_saved"})
        invocations = []
        self.assertEqual(
            self._run(lambda **kwargs: invocations.append(kwargs)), 1
        )
        self.assertFalse(invocations)
        self.assertFalse(self.persisted.exists())
        self.assertIn(
            "sealed Editorial Repair research is missing",
            json.loads(self.report.read_text())["error"]
        )

    def test_unsealed_first_pass_may_save_research_before_provider(self):
        invocations = []

        def fake_editorial(**kwargs):
            invocations.append(kwargs)
            self.assertTrue(self.persisted.is_file())
            self._save(self.artifact / "stories.json", [
                {"geography": "world", "section": "world"}
            ])

        self.assertEqual(self._run(fake_editorial), 0)
        self.assertEqual(len(invocations), 1)
        self.assertEqual(json.loads(self.persisted.read_text()), self.base)


if __name__ == "__main__":
    unittest.main()
