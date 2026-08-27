from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RSS = ROOT / "posts" / "rss.xml"
WORKFLOWS = ROOT / ".github" / "workflows"
SCRIPTS = ROOT / "automation" / "scripts"
ARCHIVE = ROOT / "automation" / "archive" / "video-rss-enrichment-2026-08"


class RssVideoBoundaryTests(unittest.TestCase):
    def test_committed_rss_contains_no_video_payload(self) -> None:
        text = RSS.read_text(encoding="utf-8")
        self.assertNotIn("/posts/video/", text)
        root = ET.fromstring(text)
        offenders: list[tuple[str, dict[str, str]]] = []
        for element in root.iter():
            medium = (element.get("medium") or "").strip().casefold()
            media_type = (element.get("type") or "").strip().casefold()
            url = (element.get("url") or "").strip()
            if medium == "video" or media_type.startswith("video/") or "/posts/video/" in url:
                offenders.append((element.tag, dict(element.attrib)))
        self.assertEqual(offenders, [], f"RSS contains video payload: {offenders}")

    def test_retired_video_rss_production_paths_are_absent(self) -> None:
        self.assertFalse((WORKFLOWS / "video-rss-enrichment.yml").exists())
        self.assertFalse((SCRIPTS / "video_rss_enrichment.py").exists())
        self.assertFalse((SCRIPTS / "repository_hygiene_video_rss_runs.py").exists())
        self.assertTrue((ARCHIVE / "video-rss-enrichment.workflow.yml").exists())
        self.assertTrue((ARCHIVE / "video_rss_enrichment.py").exists())

    def test_active_workflows_do_not_reintroduce_video_rss_mutation(self) -> None:
        forbidden = (
            "video_rss_enrichment.py",
            "video-rss-enrichment",
            "/posts/video/",
            'medium="video"',
            'type="video/mp4"',
        )
        offenders: dict[str, list[str]] = {}
        for path in sorted(WORKFLOWS.glob("*.yml")):
            text = path.read_text(encoding="utf-8").casefold()
            hits = [token for token in forbidden if token.casefold() in text]
            if hits:
                offenders[path.name] = hits
        self.assertEqual(
            offenders,
            {},
            f"Production workflows reference retired video-RSS path: {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
