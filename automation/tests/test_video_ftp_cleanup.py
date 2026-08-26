from __future__ import annotations

import ftplib
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import cleanup_video_ftp as video_cleanup  # noqa: E402


class FakeFtp:
    def __init__(
        self,
        entries: dict[str, dict[str, str]],
        *,
        mlsd_supported: bool = True,
        delete_effective: bool = True,
    ) -> None:
        self.entries = dict(entries)
        self.mlsd_supported = mlsd_supported
        self.delete_effective = delete_effective
        self.cwd_calls: list[str] = []
        self.deleted: list[str] = []

    def cwd(self, path: str) -> None:
        self.cwd_calls.append(path)

    def mlsd(self):
        if not self.mlsd_supported:
            raise ftplib.error_perm("500 MLSD not understood")
        return list(self.entries.items())

    def nlst(self):
        return [f"/video/{name}" for name in self.entries]

    def delete(self, name: str) -> None:
        self.deleted.append(name)
        if self.delete_effective:
            self.entries.pop(name, None)


class VideoFtpCleanupTests(unittest.TestCase):
    @staticmethod
    def managed(name: str, size: int = 100) -> dict[str, str]:
        return {"type": "file", "size": str(size)}

    def test_strict_cutoff_and_dry_run(self) -> None:
        ftp = FakeFtp(
            {
                "ai-svodka-2026-07-29.mp4": self.managed("old"),
                "ai-svodka-2026-07-29.png": self.managed("old"),
                "ai-svodka-2026-07-30.mp4": self.managed("boundary"),
                "notes.txt": self.managed("other"),
            }
        )
        report = video_cleanup.run_cleanup(
            ftp,
            reference_date=date(2026, 8, 31),
            retention_days=32,
            apply=False,
        )
        self.assertEqual(report["cutoff_date"], "2026-07-30")
        self.assertEqual(
            [row["name"] for row in report["expired_files"]],
            [
                "ai-svodka-2026-07-29.mp4",
                "ai-svodka-2026-07-29.png",
            ],
        )
        self.assertEqual(
            [row["name"] for row in report["retained_files"]],
            ["ai-svodka-2026-07-30.mp4"],
        )
        self.assertEqual(ftp.deleted, [])
        self.assertEqual(ftp.cwd_calls, ["video"])

    def test_apply_deletes_old_pair_and_orphan_independently(self) -> None:
        ftp = FakeFtp(
            {
                "ai-svodka-2026-07-01.mp4": self.managed("old-mp4", 1000),
                "ai-svodka-2026-07-01.png": self.managed("old-png", 200),
                "ai-svodka-2026-07-02.mp4": self.managed("orphan", 900),
                "ai-svodka-2026-08-30.png": self.managed("new", 300),
            }
        )
        report = video_cleanup.run_cleanup(
            ftp,
            reference_date=date(2026, 8, 31),
            retention_days=32,
            apply=True,
        )
        self.assertEqual(
            ftp.deleted,
            [
                "ai-svodka-2026-07-01.mp4",
                "ai-svodka-2026-07-01.png",
                "ai-svodka-2026-07-02.mp4",
            ],
        )
        self.assertEqual(report["deleted_count"], 3)
        self.assertTrue(report["changes_applied"])
        self.assertEqual(report["removed_bytes_known"], 2100)

    def test_unknown_files_and_directories_are_never_targets(self) -> None:
        ftp = FakeFtp(
            {
                "random.mp4": self.managed("random"),
                "ai-svodka-2026-07-01.jpg": self.managed("jpg"),
                "archive": {"type": "dir"},
                "ai-svodka-2026-07-01.mp4": self.managed("managed"),
            }
        )
        report = video_cleanup.run_cleanup(
            ftp,
            reference_date=date(2026, 8, 31),
            retention_days=32,
            apply=True,
        )
        self.assertEqual(ftp.deleted, ["ai-svodka-2026-07-01.mp4"])
        self.assertEqual(
            {row["name"] for row in report["ignored_entries"]},
            {"random.mp4", "ai-svodka-2026-07-01.jpg", "archive"},
        )

    def test_invalid_managed_date_fails_before_first_delete(self) -> None:
        ftp = FakeFtp(
            {
                "ai-svodka-2026-07-01.mp4": self.managed("old"),
                "ai-svodka-2026-02-30.png": self.managed("invalid"),
            }
        )
        with self.assertRaisesRegex(
            video_cleanup.VideoFtpCleanupError,
            "invalid dates",
        ):
            video_cleanup.run_cleanup(
                ftp,
                reference_date=date(2026, 8, 31),
                retention_days=32,
                apply=True,
            )
        self.assertEqual(ftp.deleted, [])

    def test_nlst_fallback_uses_basename_and_hard_video_directory(self) -> None:
        ftp = FakeFtp(
            {"ai-svodka-2026-07-01.mp4": self.managed("old")},
            mlsd_supported=False,
        )
        report = video_cleanup.run_cleanup(
            ftp,
            reference_date=date(2026, 8, 31),
            retention_days=32,
            apply=True,
        )
        self.assertEqual(report["listing_mode"], "nlst")
        self.assertEqual(ftp.cwd_calls, ["video"])
        self.assertEqual(ftp.deleted, ["ai-svodka-2026-07-01.mp4"])
        self.assertNotIn("/", ftp.deleted[0])

    def test_post_delete_verification_fails_closed(self) -> None:
        ftp = FakeFtp(
            {"ai-svodka-2026-07-01.mp4": self.managed("old")},
            delete_effective=False,
        )
        with self.assertRaisesRegex(
            video_cleanup.VideoFtpCleanupError,
            "should have been deleted",
        ):
            video_cleanup.run_cleanup(
                ftp,
                reference_date=date(2026, 8, 31),
                retention_days=32,
                apply=True,
            )

    def test_minimum_retention_cannot_be_bypassed(self) -> None:
        ftp = FakeFtp({})
        with self.assertRaisesRegex(
            video_cleanup.VideoFtpCleanupError,
            "at least 32",
        ):
            video_cleanup.run_cleanup(
                ftp,
                reference_date=date(2026, 8, 31),
                retention_days=31,
                apply=False,
            )

    def test_summary_distinguishes_dry_run_and_apply(self) -> None:
        ftp = FakeFtp(
            {"ai-svodka-2026-07-01.mp4": self.managed("old")}
        )
        dry_report = video_cleanup.run_cleanup(
            ftp,
            reference_date=date(2026, 8, 31),
            retention_days=32,
            apply=False,
        )
        dry_summary = video_cleanup.render_github_summary(
            dry_report,
            outcome="success",
        )
        self.assertIn("dry-run", dry_summary)
        self.assertIn("ничего не удалено", dry_summary)

        applied_report = video_cleanup.run_cleanup(
            ftp,
            reference_date=date(2026, 8, 31),
            retention_days=32,
            apply=True,
        )
        applied_summary = video_cleanup.render_github_summary(
            applied_report,
            outcome="success",
        )
        self.assertIn("Старые MP4/PNG удалены", applied_summary)

    def test_workflow_integration_is_after_public_cleanup_and_narrow(self) -> None:
        workflow = (
            ROOT / ".github" / "workflows" / "repository-cleanup.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("video_ftp_cleanup:", workflow)
        self.assertIn("cleanup_video_ftp.py", workflow)
        self.assertIn("needs.cleanup.outputs.reference_date", workflow)
        self.assertIn("needs.cleanup.outputs.retention_days", workflow)
        self.assertIn("needs.deploy.result == 'skipped'", workflow)
        self.assertIn("FTP_SERVER: ${{ secrets.FTP_SERVER }}", workflow)
        self.assertIn("FTP_USERNAME: ${{ secrets.FTP_USERNAME }}", workflow)
        self.assertIn("FTP_PASSWORD: ${{ secrets.FTP_PASSWORD }}", workflow)
        self.assertNotIn("automation/notebooklm-video", workflow)

        script = (SCRIPTS / "cleanup_video_ftp.py").read_text(encoding="utf-8")
        self.assertIn('REMOTE_DIR = "video"', script)
        self.assertNotIn("rss.xml", script.casefold())
        self.assertNotIn("OPENAI_API_KEY", script)


if __name__ == "__main__":
    unittest.main()
