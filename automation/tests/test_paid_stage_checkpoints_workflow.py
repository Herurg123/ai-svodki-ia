from __future__ import annotations

import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "daily-production.yml"


class PaidStageCheckpointWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_completed_paid_stages_are_uploaded_before_later_work(self) -> None:
        research = self.text.index("- name: Run full research and editorial")
        research_checkpoint = self.text.index("- name: Save paid research checkpoint")
        coverage = self.text.index("- name: Complete mandatory coverage audit for a short digest")
        coverage_checkpoint = self.text.index("- name: Save paid coverage checkpoint")
        normalize = self.text.index("- name: Normalize and validate digest artifact")
        generate_image = self.text.index("- name: Generate one production cover")
        revalidate_image = self.text.index("- name: Revalidate recovered production cover")
        image_checkpoint = self.text.index("- name: Save paid image checkpoint")
        build_site = self.text.index("- name: Build and validate candidate site")

        self.assertLess(research, research_checkpoint)
        self.assertLess(research_checkpoint, coverage)
        self.assertLess(coverage, coverage_checkpoint)
        self.assertLess(coverage_checkpoint, normalize)
        self.assertLess(generate_image, image_checkpoint)
        self.assertLess(revalidate_image, image_checkpoint)
        self.assertLess(image_checkpoint, build_site)

    def test_checkpoint_names_are_unique_per_attempt_and_recovery_visible(self) -> None:
        for stage in ("research", "coverage", "image"):
            self.assertIn(
                "daily-production-checkpoint-"
                + stage
                + "-${{ steps.runtime.outputs.publication_date }}-attempt-${{ github.run_attempt }}",
                self.text,
            )
        self.assertIn("daily-production-checkpoint-research-${PUBLICATION_DATE}-attempt-", self.text)
        self.assertIn("daily-production-checkpoint-coverage-${PUBLICATION_DATE}-attempt-", self.text)
        self.assertIn("daily-production-checkpoint-image-${PUBLICATION_DATE}-attempt-", self.text)

    def test_checkpoint_uploads_preserve_the_recovery_bundle_shape(self) -> None:
        self.assertGreaterEqual(self.text.count("uses: actions/upload-artifact@v7"), 4)
        checkpoint_marker = "name: daily-production-checkpoint-"
        cursor = 0
        blocks = []
        for _ in range(3):
            pos = self.text.index(checkpoint_marker, cursor)
            start = self.text.rfind("- name:", 0, pos)
            end = self.text.find("- name:", pos)
            if end == -1:
                end = len(self.text)
            blocks.append(self.text[start:end])
            cursor = pos + len(checkpoint_marker)
        for block in blocks:
            self.assertIn("automation/preview/production-daily/", block)
            self.assertIn(
                "automation/preview/${{ steps.runtime.outputs.publication_date }}/",
                block,
            )
            self.assertIn("retention-days: 14", block)
            self.assertIn("if-no-files-found: error", block)

    def test_selected_checkpoint_name_is_downloaded_exactly(self) -> None:
        self.assertIn('echo "artifact_name=${best_artifact_name}" >> "${GITHUB_OUTPUT}"', self.text)
        self.assertIn(
            "name: ${{ steps.recovery_source.outputs.artifact_name }}",
            self.text,
        )
        self.assertIn(
            'RECOVERY_ARTIFACT_NAME: ${{ steps.recovery_source.outputs.artifact_name }}',
            self.text,
        )

    def test_final_always_artifact_remains_as_last_resort_snapshot(self) -> None:
        self.assertIn(
            "- uses: actions/upload-artifact@v7\n"
            "        if: always()\n"
            "        with:\n"
            "          name: daily-production-${{ steps.runtime.outputs.publication_date || github.run_id }}",
            self.text,
        )

    def _resolver_shell(self) -> str:
        start = self.text.index("- name: Resolve reusable artifact")
        run_marker = "        run: |\n"
        run_start = self.text.index(run_marker, start) + len(run_marker)
        run_end = self.text.index("\n      - name:", run_start)
        return textwrap.dedent(self.text[run_start:run_end])

    def _run_resolver(self, scenario: dict[str, object], **env_overrides: str) -> dict[str, str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fake_gh = root / "gh"
            fake_gh.write_text(
                """#!/usr/bin/env python3
import json
import os
import sys

scenario = json.loads(os.environ["FAKE_GH_SCENARIO"])
url = next((arg for arg in sys.argv[1:] if arg.startswith("/repos/")), "")
if "/actions/artifacts?" in url and "/actions/runs/" not in url:
    print("\\n".join(scenario.get("automatic_artifacts", [])))
elif "/actions/runs/" in url and "/artifacts?" in url:
    run_id = url.split("/actions/runs/", 1)[1].split("/", 1)[0]
    print("\\n".join(scenario.get("manual_artifacts", {}).get(run_id, [])))
elif "/actions/runs/" in url and "/jobs?" in url:
    run_id = url.split("/actions/runs/", 1)[1].split("/", 1)[0]
    print(scenario.get("run_ranks", {}).get(run_id, 0))
else:
    raise SystemExit("unexpected gh call: " + " ".join(sys.argv))
""",
                encoding="utf-8",
            )
            fake_gh.chmod(0o755)
            output = root / "github-output.txt"
            env = os.environ.copy()
            env.update(
                {
                    "PATH": str(root) + os.pathsep + env.get("PATH", ""),
                    "FAKE_GH_SCENARIO": json.dumps(scenario),
                    "GITHUB_OUTPUT": str(output),
                    "GITHUB_REPOSITORY": "Herurg123/ai-svodki-ia",
                    "GITHUB_RUN_ID": "999",
                    "PUBLICATION_DATE": "2026-09-22",
                    "EVENT_NAME": "schedule",
                    "MANUAL_RECOVERY_RUN_ID": "",
                    "FORCE_FRESH_RESEARCH": "false",
                }
            )
            env.update(env_overrides)
            completed = subprocess.run(
                ["bash", "-c", self._resolver_shell()],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            values: dict[str, str] = {}
            for line in output.read_text(encoding="utf-8").splitlines():
                key, value = line.split("=", 1)
                values[key] = value
            return values

    def test_resolver_prefers_most_complete_surviving_checkpoint(self) -> None:
        values = self._run_resolver(
            {
                "automatic_artifacts": [
                    "2026-09-22T01:44:43Z\t101\tdaily-production-checkpoint-research-2026-09-22-attempt-1",
                    "2026-09-22T01:46:00Z\t102\tdaily-production-checkpoint-coverage-2026-09-22-attempt-1",
                    "2026-09-22T01:47:00Z\t103\tdaily-production-checkpoint-image-2026-09-22-attempt-1",
                ],
                "run_ranks": {"101": 1, "102": 2, "103": 3},
            }
        )
        self.assertEqual(values["run_id"], "103")
        self.assertEqual(values["rank"], "3")
        self.assertEqual(
            values["artifact_name"],
            "daily-production-checkpoint-image-2026-09-22-attempt-1",
        )

    def test_final_failure_snapshot_beats_same_rank_research_checkpoint(self) -> None:
        values = self._run_resolver(
            {
                "automatic_artifacts": [
                    "2026-09-22T01:44:43Z\t101\tdaily-production-checkpoint-research-2026-09-22-attempt-1",
                    "2026-09-22T01:47:27Z\t101\tdaily-production-2026-09-22",
                ],
                "run_ranks": {"101": 1},
            }
        )
        self.assertEqual(values["artifact_name"], "daily-production-2026-09-22")
        self.assertEqual(values["rank"], "1")

    def test_checkpoint_name_cannot_claim_more_than_completed_run_steps(self) -> None:
        values = self._run_resolver(
            {
                "automatic_artifacts": [
                    "2026-09-22T01:47:00Z\t101\tdaily-production-checkpoint-image-2026-09-22-attempt-1",
                    "2026-09-22T01:46:00Z\t101\tdaily-production-checkpoint-coverage-2026-09-22-attempt-1",
                    "2026-09-22T01:44:43Z\t101\tdaily-production-checkpoint-research-2026-09-22-attempt-1",
                ],
                "run_ranks": {"101": 1},
            }
        )
        self.assertEqual(
            values["artifact_name"],
            "daily-production-checkpoint-research-2026-09-22-attempt-1",
        )
        self.assertEqual(values["rank"], "1")

    def test_manual_recovery_can_select_checkpoint_when_final_artifact_is_missing(self) -> None:
        values = self._run_resolver(
            {
                "manual_artifacts": {
                    "555": [
                        "2026-09-22T01:46:00Z\t555\tdaily-production-checkpoint-coverage-2026-09-22-attempt-2"
                    ]
                },
                "run_ranks": {"555": 2},
            },
            EVENT_NAME="workflow_dispatch",
            MANUAL_RECOVERY_RUN_ID="555",
        )
        self.assertEqual(values["source"], "manual")
        self.assertEqual(values["run_id"], "555")
        self.assertEqual(values["rank"], "2")

    def test_search_and_coverage_budgets_are_not_changed_by_checkpointing(self) -> None:
        self.assertIn("--maximum-research-web-search-calls 12", self.text)
        self.assertIn("--maximum-audit-web-search-calls 7", self.text)
        self.assertIn("--usual-total 7", self.text)


if __name__ == "__main__":
    unittest.main()
