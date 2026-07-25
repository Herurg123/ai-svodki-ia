from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from recover_digest_artifact import FULL_REQUIRED_FILES, recover  # noqa: E402


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class ImageCompleteRecoveryTests(unittest.TestCase):
    def test_recovery_restores_valid_paid_cover(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            recovery_root = root / "recovery"
            editorial = recovery_root / "2026-07-25"
            editorial.mkdir(parents=True)
            for name in FULL_REQUIRED_FILES:
                path = editorial / name
                if name == "run-info.json":
                    write_json(
                        path,
                        {
                            "publication_date": "2026-07-25",
                            "finished_at": "2026-07-25T05:31:14+00:00",
                            "research": {"status": "ok"},
                        },
                    )
                elif name == "candidates.json":
                    write_json(
                        path,
                        {"publication_date": "2026-07-25", "candidates": []},
                    )
                else:
                    write_json(path, {"publication_date": "2026-07-25"})

            image = recovery_root / "production-daily" / "image" / "2026-07-25"
            shutil.copytree(editorial, image)
            (image / "article.html").write_text("<p>test</p>", encoding="utf-8")
            (image / "cover.png").write_bytes(b"paid-cover")
            cover_sha = hashlib.sha256(b"paid-cover").hexdigest()
            write_json(
                image / "image-manifest.json",
                {
                    "status": "ok",
                    "sha256": cover_sha,
                    "publication_date": "2026-07-25",
                },
            )
            write_json(image / "cover-validation.json", {"status": "ok"})

            target = root / "target"
            image_target = root / "image-target"
            report_path = root / "report.json"
            report = recover(
                recovery_root,
                target,
                "2026-07-25",
                report_path,
                "Europe/Moscow",
                image_target,
            )
            self.assertTrue(report["image_recovered"])
            self.assertEqual((image_target / "cover.png").read_bytes(), b"paid-cover")
            self.assertEqual(
                report["recovered_image"]["cover_sha256"],
                cover_sha,
            )


if __name__ == "__main__":
    unittest.main()
