
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from verify_previous_release import verify


class Response:
    def __init__(self, status: int):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class PreviousReleaseVerificationTests(unittest.TestCase):
    def test_repository_and_live_site_are_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            posts = Path(temporary)
            (posts / "2026-07-25").mkdir()
            (posts / "2026-07-25/index.html").write_text(
                "ok",
                encoding="utf-8",
            )
            (posts / "images").mkdir()
            (posts / "images/ai-svodka-2026-07-25.png").write_bytes(
                b"png"
            )

            opened = []

            def opener(request, timeout):
                opened.append((request.full_url, timeout))
                return Response(200)

            report = verify(
                config={
                    "site_base_url": "https://rybalka.one/posts",
                    "verify_previous_release_on_live_site": True,
                },
                rss={
                    "latest_item": {
                        "date": "2026-07-25",
                        "link": (
                            "https://rybalka.one/posts/2026-07-25/"
                        ),
                    }
                },
                posts_root=posts,
                publication_date="2026-07-27",
                opener=opener,
            )

            self.assertEqual(
                report["previous_published_date"],
                "2026-07-25",
            )
            self.assertEqual(report["missed_calendar_days"], 1)
            self.assertEqual(len(opened), 2)


if __name__ == "__main__":
    unittest.main()
