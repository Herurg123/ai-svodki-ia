from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "daily-production.yml"


class ImageStageRecoveryContractTests(unittest.TestCase):
    def test_validated_digest_is_checkpointed_before_cover_generation(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        story = text.index("- name: Validate publishable story count and short digest marker")
        request = text.index("- name: Build runtime Image API request")
        cover = text.index("- name: Generate one production cover")
        self.assertLess(story, request)
        self.assertLess(request, cover)

    def test_late_cover_failure_keeps_a_reusable_rank_two_artifact(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            'elif any($steps[]; (.name == "Validate publishable story count and short digest marker" and .conclusion == "success")) then 2',
            text,
        )
        self.assertIn(
            "      - uses: actions/upload-artifact@v7\n"
            "        if: always()\n",
            text,
        )

    def test_recovered_cover_skips_another_image_call(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("steps.recovery.outputs.image_recovered != 'true'", text)
        self.assertIn("- name: Revalidate recovered production cover", text)


if __name__ == "__main__":
    unittest.main()
