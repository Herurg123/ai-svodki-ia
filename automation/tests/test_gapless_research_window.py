from __future__ import annotations

import sys
import types
import unittest
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

openai_stub = types.ModuleType("openai")
openai_stub.OpenAI = object
sys.modules.setdefault("openai", openai_stub)

from generate_digest_preview import expected_search_window  # noqa: E402


class GaplessResearchWindowTests(unittest.TestCase):
    def test_event_after_prior_cutoff_before_nominal_publish_enters_next_run(self) -> None:
        config = {"timezone": "Europe/Moscow", "publication_hour": 6}
        archive = {
            "items": [
                {
                    "date": "2026-08-05",
                    "published_at": "2026-08-05T06:00:00+03:00",
                    "search_cutoff_at": "2026-08-05T03:14:42+03:00",
                }
            ]
        }
        current_cutoff = datetime.fromisoformat("2026-08-06T02:50:00+03:00")
        start_at, end_at = expected_search_window(
            date.fromisoformat("2026-08-06"),
            archive,
            config,
            cutoff_at=current_cutoff,
        )
        aisi_reuters_publication = datetime.fromisoformat(
            "2026-08-05T03:41:00+03:00"
        )

        self.assertEqual(start_at.isoformat(), "2026-08-05T03:14:42+03:00")
        self.assertEqual(end_at, current_cutoff)
        self.assertLess(start_at, aisi_reuters_publication)
        self.assertLessEqual(aisi_reuters_publication, end_at)


if __name__ == "__main__":
    unittest.main()
