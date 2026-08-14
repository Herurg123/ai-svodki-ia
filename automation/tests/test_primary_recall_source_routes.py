from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import primary_recall_search as primary  # noqa: E402


class PrimaryRecallSourceRouteTests(unittest.TestCase):
    def test_broad_and_gap_passes_are_source_neutral(self) -> None:
        routes = {str(item["id"]): tuple(item.get("allowed_domains", ())) for item in primary.PRIMARY_DIRECTIONS}
        self.assertEqual(routes["global_breaking"], ())
        self.assertEqual(routes["major_agencies"], ("bloomberg.com", "ft.com"))
        self.assertEqual(routes["independent_missing_events"], ())
        for direction_id, domains in routes.items():
            if direction_id != "major_agencies":
                self.assertEqual(domains, (), direction_id)

    def test_agency_health_domain_set_remains_available_for_diagnostics(self) -> None:
        self.assertEqual(set(primary.AGENCY_DOMAINS), {"reuters.com", "bloomberg.com", "ft.com", "apnews.com", "ap.org"})


if __name__ == "__main__":
    unittest.main()
