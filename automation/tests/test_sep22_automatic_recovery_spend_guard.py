from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "daily-production.yml"
RECOVERY = ROOT / "automation" / "scripts" / "recover_digest_artifact.py"


class Sep22AutomaticRecoverySpendGuardTests(unittest.TestCase):
    def _write_paid_research_artifact(self, root: Path) -> Path:
        source = root / "2026-09-22"
        source.mkdir(parents=True)
        candidates = {
            "status": "ok",
            "publication_date": "2026-09-22",
            "search_window": {
                "start_at": "2026-09-20T06:00:00+03:00",
                "end_at": "2026-09-22T06:00:00+03:00",
            },
            "coverage": [{"area": "world", "status": "covered", "notes": "saved"}],
            "candidates": [{"id": "cand-001"}],
            "rejected_as_duplicates": [],
            "research_notes": "saved paid research",
        }
        run_info = {
            "status": "error",
            "publication_date": "2026-09-22",
            "finished_at": "2026-09-21T10:00:00+00:00",
            "research": {
                "status": "ok",
                "temporal_anchor_version": 1,
                "response": {
                    "response_status": "completed",
                    "web_search_calls": 12,
                },
            },
            "editorial": {"status": "error"},
        }
        (source / "run-info.json").write_text(
            json.dumps(run_info, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        for name in ("candidates.json", "research-output-raw.json"):
            (source / name).write_text(
                json.dumps(candidates, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        return source

    def test_selected_paid_artifact_recovery_failure_blocks_fresh_research(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            recovery_root = root / "recovery"
            recovery_root.mkdir()
            self._write_paid_research_artifact(recovery_root)
            report = root / "recovery-report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(RECOVERY),
                    "--recovery-root",
                    str(recovery_root),
                    "--target-dir",
                    str(root / "target"),
                    "--publication-date",
                    "2026-09-22",
                    "--timezone",
                    "Europe/Moscow",
                    "--report",
                    str(report),
                ],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "error")
            self.assertIn("устарел", payload["error"])

        workflow = WORKFLOW.read_text(encoding="utf-8")
        restore_start = workflow.index("- name: Restore saved paid artifact")
        restore_end = workflow.index("- name: Install pinned OpenAI SDK", restore_start)
        restore_step = workflow[restore_start:restore_end]
        self.assertIn(
            "Свежий paid research автоматически не запускается",
            restore_step,
        )
        self.assertIn('exit "${recovery_status}"', restore_step)
        self.assertNotIn(
            "Будет выполнен свежий research",
            restore_step,
        )
        self.assertIn(
            "- name: Run full research and editorial\n"
            "        if: steps.recovery_source.outputs.run_id == '' && steps.terminal_reuse.outputs.stop != 'true'",
            workflow,
        )

    def test_explicit_force_fresh_still_allows_new_research(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        marker = (
            'if [[ "${EVENT_NAME}" == "workflow_dispatch" && '
            '"${FORCE_FRESH_RESEARCH}" == "true" ]]; then'
        )
        start = workflow.index(marker)
        end = workflow.index('elif [[ -z "${run_id}" ]]; then', start)
        forced_block = workflow[start:end]
        self.assertIn('run_id=""', forced_block)
        self.assertIn('source="none"', forced_block)


if __name__ == "__main__":
    unittest.main()
