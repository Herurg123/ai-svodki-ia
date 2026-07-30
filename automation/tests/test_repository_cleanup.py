from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cleanup_repository_content import CleanupError, run_cleanup  # noqa: E402


class RepositoryContentCleanupTests(unittest.TestCase):
    def write_release(
        self,
        root: Path,
        publication_date: str,
        *,
        complete: bool = True,
    ) -> Path:
        target = root / publication_date
        target.mkdir(parents=True)
        (target / "meta.json").write_text(
            json.dumps({"date": publication_date}),
            encoding="utf-8",
        )
        if complete:
            (target / "stories.json").write_text(
                json.dumps([{"headline": "Сюжет"}], ensure_ascii=False),
                encoding="utf-8",
            )
        (target / "article.html").write_text("<p>Статья</p>", encoding="utf-8")
        (target / "cover.png").write_bytes(b"png")
        nested = target / "raw"
        nested.mkdir()
        (nested / "response.json").write_text("{}", encoding="utf-8")
        return target

    def test_strict_cutoff_and_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            content = Path(temp)
            expired = self.write_release(content, "2026-07-29")
            boundary = self.write_release(content, "2026-07-30")

            preview = run_cleanup(
                content,
                reference_date=date(2026, 8, 31),
                retention_days=32,
                apply=False,
            )
            self.assertEqual(preview["cutoff_date"], "2026-07-30")
            self.assertEqual(preview["compacted_directories"], ["2026-07-29"])
            self.assertTrue((expired / "cover.png").is_file())
            self.assertTrue((boundary / "cover.png").is_file())

            applied = run_cleanup(
                content,
                reference_date=date(2026, 8, 31),
                retention_days=32,
                apply=True,
            )
            self.assertTrue(applied["changes_applied"])
            self.assertEqual(
                {path.name for path in expired.iterdir()},
                {"meta.json", "stories.json"},
            )
            self.assertTrue((boundary / "cover.png").is_file())

    def test_every_target_is_validated_before_any_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            content = Path(temp)
            valid = self.write_release(content, "2026-07-01")
            self.write_release(content, "2026-07-02", complete=False)

            with self.assertRaisesRegex(
                CleanupError,
                "stories.json",
            ):
                run_cleanup(
                    content,
                    reference_date=date(2026, 8, 31),
                    retention_days=32,
                    apply=True,
                )

            self.assertTrue((valid / "cover.png").is_file())
            self.assertTrue((valid / "article.html").is_file())

    def test_invalid_date_shaped_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            content = Path(temp)
            self.write_release(content, "2026-02-30")
            with self.assertRaisesRegex(
                CleanupError,
                "Invalid date-shaped",
            ):
                run_cleanup(
                    content,
                    reference_date=date(2026, 8, 31),
                    retention_days=32,
                    apply=False,
                )

    def test_minimum_retention_cannot_be_bypassed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(
                CleanupError,
                "at least 32",
            ):
                run_cleanup(
                    Path(temp),
                    reference_date=date(2026, 8, 31),
                    retention_days=31,
                    apply=False,
                )

    def test_already_compact_release_is_a_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            content = Path(temp)
            target = self.write_release(content, "2026-07-01")
            for path in list(target.iterdir()):
                if path.name in {"meta.json", "stories.json"}:
                    continue
                if path.is_dir():
                    for child in path.iterdir():
                        child.unlink()
                    path.rmdir()
                else:
                    path.unlink()

            report = run_cleanup(
                content,
                reference_date=date(2026, 8, 31),
                retention_days=32,
                apply=True,
            )
            self.assertFalse(report["changes_applied"])
            self.assertEqual(report["already_compact_directories"], ["2026-07-01"])

    def test_workflow_is_scoped_to_repository_content(self) -> None:
        workflow = (
            ROOT / ".github" / "workflows" / "repository-cleanup.yml"
        ).read_text(encoding="utf-8")
        self.assertIn('cron: "43 22 * * *"', workflow)
        self.assertIn("contents: write", workflow)
        self.assertIn("default: false", workflow)
        self.assertIn("--retention-days", workflow)
        self.assertIn("retention_days must be at least 32", workflow)
        self.assertIn("cleanup_repository_content.py", workflow)
        self.assertNotIn("posts/", workflow)
        self.assertNotIn("rss.xml", workflow)


if __name__ == "__main__":
    unittest.main()
