from __future__ import annotations

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
                + "-\${{ steps.runtime.outputs.publication_date }}-attempt-\${{ github.run_attempt }}",
                self.text,
            )
        self.assertIn("daily-production-checkpoint-research-\${PUBLICATION_DATE}-attempt-", self.text)
        self.assertIn("daily-production-checkpoint-coverage-\${PUBLICATION_DATE}-attempt-", self.text)
        self.assertIn("daily-production-checkpoint-image-\${PUBLICATION_DATE}-attempt-", self.text)

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
                "automation/preview/\${{ steps.runtime.outputs.publication_date }}/",
                block,
            )
            self.assertIn("retention-days: 14", block)
            self.assertIn("if-no-files-found: error", block)

    def test_selected_checkpoint_name_is_downloaded_exactly(self) -> None:
        self.assertIn('echo "artifact_name=\${best_artifact_name}" >> "\${GITHUB_OUTPUT}"', self.text)
        self.assertIn(
            "name: \${{ steps.recovery_source.outputs.artifact_name }}",
            self.text,
        )
        self.assertIn(
            'RECOVERY_ARTIFACT_NAME: \${{ steps.recovery_source.outputs.artifact_name }}',
            self.text,
        )

    def test_final_always_artifact_remains_as_last_resort_snapshot(self) -> None:
        self.assertIn(
            "- uses: actions/upload-artifact@v7\\n"
            "        if: always()\\n"
            "        with:\\n"
            "          name: daily-production-\${{ steps.runtime.outputs.publication_date || github.run_id }}",
            self.text,
        )

    def test_search_and_coverage_budgets_are_not_changed_by_checkpointing(self) -> None:
        self.assertIn("--maximum-research-web-search-calls 12", self.text)
        self.assertIn("--maximum-audit-web-search-calls 7", self.text)
        self.assertIn("--usual-total 7", self.text)


if __name__ == "__main__":
    unittest.main()
