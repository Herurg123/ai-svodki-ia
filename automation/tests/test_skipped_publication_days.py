
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from production_daily_common import runtime_context  # noqa: E402


def config(**overrides):
    value = {
        "timezone": "Europe/Moscow",
        "first_publication_date": "2026-07-24",
        "feed_url": "https://rybalka.one/posts/rss.xml",
        "site_base_url": "https://rybalka.one/posts",
        "publication_hour_local": 6,
        "require_previous_day_in_rss": False,
        "allow_skipped_publication_days": True,
    }
    value.update(overrides)
    return value


def rss(latest_date: str):
    return {
        "self_url": "https://rybalka.one/posts/rss.xml",
        "latest_date": latest_date,
        "latest_item": {
            "date": latest_date,
            "link": f"https://rybalka.one/posts/{latest_date}/",
        },
        "items": [
            {
                "date": latest_date,
                "link": f"https://rybalka.one/posts/{latest_date}/",
            },
        ],
    }


class SkippedPublicationDaysTests(unittest.TestCase):
    def test_uses_last_published_release_after_skipped_day(self) -> None:
        context = runtime_context(
            config=config(),
            rss=rss("2026-07-25"),
            now_iso="2026-07-27T06:17:00+03:00",
            publication_date_override="2026-07-27",
        )
        self.assertEqual(
            context["previous_published_date"],
            "2026-07-25",
        )
        self.assertEqual(context["missed_calendar_days"], 1)
        self.assertEqual(
            context["search_window_start_date"],
            "2026-07-25",
        )

    def test_strict_mode_still_rejects_gap(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            "previous calendar day",
        ):
            runtime_context(
                config=config(
                    require_previous_day_in_rss=True,
                    allow_skipped_publication_days=False,
                ),
                rss=rss("2026-07-25"),
                publication_date_override="2026-07-27",
            )

    def test_future_or_same_day_release_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            "RSS already contains|не может быть датирован",
        ):
            runtime_context(
                config=config(),
                rss=rss("2026-07-27"),
                publication_date_override="2026-07-27",
            )


if __name__ == "__main__":
    unittest.main()
