from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"
VIDEO_ROOT = ROOT / "automation" / "notebooklm-video"


class VideoCiBoundaryTests(unittest.TestCase):
    def test_main_ci_excludes_video_only_changes(self) -> None:
        workflow = (WORKFLOW_ROOT / "ci.yml").read_text(encoding="utf-8")
        self.assertIn('!automation/notebooklm-video/**', workflow)
        self.assertIn('!.github/workflows/video-ci.yml', workflow)

    def test_video_ci_owns_video_checks(self) -> None:
        workflow = (WORKFLOW_ROOT / "video-ci.yml").read_text(encoding="utf-8")
        self.assertIn("name: Video CI", workflow)
        self.assertIn('automation/notebooklm-video/**', workflow)
        self.assertIn("Offline video checks", workflow)
        self.assertIn("node --check worker.js", workflow)
        self.assertIn("npm test", workflow)
        self.assertNotIn("OPENAI_API_KEY", workflow)
        self.assertNotIn("contents: write", workflow)

    def test_production_workflows_do_not_consume_video_subproject(self) -> None:
        for name in (
            "daily-production.yml",
            "deploy-posts.yml",
            "repository-cleanup.yml",
            "repository-hygiene.yml",
            "video-rss-enrichment.yml",
        ):
            text = (WORKFLOW_ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn(
                "automation/notebooklm-video",
                text,
                f"{name} must not depend on the local video subproject",
            )

    def test_video_package_tests_remain_offline(self) -> None:
        package = (VIDEO_ROOT / "package.json").read_text(encoding="utf-8")
        self.assertIn("video-boundary-smoke.js", package)
        workflow = (WORKFLOW_ROOT / "video-ci.yml").read_text(encoding="utf-8")
        self.assertNotIn("npm install", workflow)
        self.assertNotIn("npm ci", workflow)


if __name__ == "__main__":
    unittest.main()
