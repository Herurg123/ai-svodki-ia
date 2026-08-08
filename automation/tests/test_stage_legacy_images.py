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

    def test_small_legacy_set_is_staged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            for index in range(3):
                (source / f"ai-svodka-2026-07-{index + 1:02d}.png").write_bytes(b"png")

            report = stage_images_best_effort(source, target, dry_run=False)

            self.assertEqual(report["status"], "ok")
            self.assertFalse(report["blocking"])
            self.assertEqual(report["source_images"], 3)
            self.assertEqual(len(report["copied"]), 3)
            self.assertEqual(len(list(target.glob("ai-svodka-*.png"))), 3)

    def test_empty_legacy_set_is_not_a_release_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()

            report = stage_images_best_effort(source, root / "target", dry_run=False)

        self.assertEqual(report["status"], "ok")
        self.assertFalse(report["blocking"])
        self.assertEqual(report["source_images"], 0)
        self.assertEqual(report["copied"], [])

    def test_existing_canonical_image_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            target.mkdir()
            name = "ai-svodka-2026-07-01.png"
            (source / name).write_bytes(b"legacy")
            (target / name).write_bytes(b"canonical")

            report = stage_images_best_effort(source, target, dry_run=False)

            self.assertEqual(report["status"], "ok")
            self.assertEqual((target / name).read_bytes(), b"canonical")
            self.assertEqual(report["already_present"], [name])
            self.assertEqual(len(report["different_existing"]), 1)

    def test_repository_legacy_set_is_stageable_in_dry_run(self) -> None:
        repo = Path(__file__).resolve().parents[2]
        report = stage_images_best_effort(
            repo / "posts" / "dzen-test" / "images",
            repo / "posts" / "images",
            dry_run=True,
        )

        self.assertEqual(report["status"], "ok", report.get("warnings"))
        self.assertGreaterEqual(report["source_images"], 0)


if __name__ == "__main__":
    unittest.main()
