
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from validate_search_window_continuity import validate  # noqa: E402


class SearchWindowContinuityTests(unittest.TestCase):
    def test_archive_starts_window_at_last_successful_release(self) -> None:
        report = validate(
            runtime={
                "publication_date": "2026-07-27",
                "previous_published_date": "2026-07-25",
                "missed_calendar_days": 1,
            },
            archive={
                "items": [
                    {
                        "date": "2026-07-25",
                        "published_at": "2026-07-25T06:00:00+03:00",
                    },
                    {
                        "date": "2026-07-24",
                        "published_at": "2026-07-24T06:00:00+03:00",
                    },
                ]
            },
            timezone_name="Europe/Moscow",
            publication_hour=6,
        )
        self.assertEqual(
            report["search_window_start_at"],
            "2026-07-25T06:00:00+03:00",
        )
        self.assertEqual(
            report["policy"],
            "from_last_successfully_published_release",
        )

    def test_archive_rss_mismatch_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            "не совпадает с RSS",
        ):
            validate(
                runtime={
                    "publication_date": "2026-07-27",
                    "previous_published_date": "2026-07-25",
                },
                archive={
                    "items": [
                        {
                            "date": "2026-07-24",
                            "published_at": "2026-07-24T06:00:00+03:00",
                        }
                    ]
                },
                timezone_name="Europe/Moscow",
                publication_hour=6,
            )


if __name__ == "__main__":
    unittest.main()
