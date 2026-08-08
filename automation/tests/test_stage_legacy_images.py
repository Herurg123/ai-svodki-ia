from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation.scripts.stage_legacy_images import stage_images_best_effort


class StageLegacyImagesTests(unittest.TestCase):
    def test_missing_legacy_source_is_a_non_blocking_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = stage_images_best_effort(
                root / "missing",
                root / "target",
                dry_run=False,
            )

        self.assertEqual(report["status"], "warning")
        self.assertFalse(report["blocking"])
        self.assertTrue(report["warnings"])

    def test_too_small_legacy_set_is_a_non_blocking_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            for index in range(3):
                (source / f"ai-svodka-2026-07-{index + 1:02d}.png").write_bytes(b"png")

            report = stage_images_best_effort(source, root / "target", dry_run=False)

        self.assertEqual(report["status"], "warning")
        self.assertFalse(report["blocking"])
        self.assertIn("Expected at least 10 legacy images", report["warnings"][0])

    def test_valid_legacy_set_is_staged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            for index in range(10):
                (source / f"ai-svodka-2026-07-{index + 1:02d}.png").write_bytes(
                    f"image-{index}".encode("ascii")
                )

            report = stage_images_best_effort(source, target, dry_run=False)

            self.assertEqual(report["status"], "ok")
            self.assertFalse(report["blocking"])
            self.assertEqual(len(report["copied"]), 10)
            self.assertEqual(len(list(target.glob("ai-svodka-*.png"))), 10)

    def test_repository_legacy_set_is_stageable_in_dry_run(self) -> None:
        repo = Path(__file__).resolve().parents[2]
        report = stage_images_best_effort(
            repo / "posts" / "dzen-test" / "images",
            repo / "posts" / "images",
            dry_run=True,
        )

        self.assertEqual(report["status"], "ok", report.get("warnings"))
        self.assertGreaterEqual(report["source_images"], 10)


if __name__ == "__main__":
    unittest.main()
