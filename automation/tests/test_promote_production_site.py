from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMOTE = ROOT / "automation/scripts/promote_production_site.py"


def write_rss(path: Path, items: list[tuple[str, str]]) -> None:
    body = "\n".join(
        f"""    <item>
      <title>{publication_date}</title>
      <link>{link}</link>
      <pubDate>{pub_date}</pubDate>
    </item>"""
        for link, publication_date, pub_date in (
            (
                link,
                link.rstrip("/").rsplit("/", 1)[-1],
                "Mon, 31 Aug 2026 03:00:00 +0300"
                if link.endswith("2026-08-31/")
                else "Sun, 30 Aug 2026 03:00:00 +0300",
            )
            for link, _ in items
        )
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test feed</title>
    <link>https://rybalka.one/posts</link>
"""
        + body
        + "\n  </channel>\n</rss>\n",
        encoding="utf-8",
    )


class PromoteProductionSiteTests(unittest.TestCase):
    def prepare_repo(self, root: Path, *, preserve_existing: bool) -> dict[str, Path]:
        live = root / "posts"
        candidate = root / "automation/preview/candidate/posts"
        source = root / "automation/preview/source"
        content_root = root / "automation/content"
        report = root / "automation/preview/promotion.json"
        config = root / "production-daily.json"

        live.mkdir(parents=True)
        candidate.mkdir(parents=True)
        source.mkdir(parents=True)
        content_root.mkdir(parents=True)
        config.write_text(
            json.dumps(
                {
                    "content_root": "automation/content",
                    "site_base_url": "https://rybalka.one/posts",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        old_link = "https://rybalka.one/posts/2026-08-30/"
        new_link = "https://rybalka.one/posts/2026-08-31/"
        write_rss(live / "rss.xml", [(old_link, "2026-08-30")])
        candidate_items = [(new_link, "2026-08-31")]
        if preserve_existing:
            candidate_items.append((old_link, "2026-08-30"))
        write_rss(candidate / "rss.xml", candidate_items)

        return {
            "config": config,
            "candidate": candidate,
            "live": live,
            "source": source,
            "content_root": content_root,
            "report": report,
        }

    def run_promotion(self, root: Path, paths: dict[str, Path]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(PROMOTE),
                "--config",
                str(paths["config"]),
                "--candidate-posts",
                str(paths["candidate"]),
                "--live-posts",
                str(paths["live"]),
                "--source-dir",
                str(paths["source"]),
                "--content-root",
                str(paths["content_root"]),
                "--publication-date",
                "2026-08-31",
                "--report",
                str(paths["report"]),
                "--dry-run",
            ],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_dry_run_accepts_config_without_retired_legacy_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = self.prepare_repo(root, preserve_existing=True)
            completed = self.run_promotion(root, paths)
            diagnostics = f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}"
            self.assertEqual(completed.returncode, 0, diagnostics)
            report = json.loads(paths["report"].read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "ok")
            self.assertTrue(report["dry_run"])
            self.assertNotIn("legacy_items", report)

    def test_dry_run_still_rejects_loss_of_existing_rss_link(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = self.prepare_repo(root, preserve_existing=False)
            completed = self.run_promotion(root, paths)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Candidate RSS lost existing links", completed.stderr)


if __name__ == "__main__":
    unittest.main()
