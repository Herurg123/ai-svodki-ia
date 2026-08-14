from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import primary_recall_search as primary  # noqa: E402


class PrimaryRecallSourceRouteTests(unittest.TestCase):
    def test_three_high_signal_routes_use_disjoint_api_domain_filters(self) -> None:
        routes = {
            str(item["id"]): tuple(item.get("allowed_domains", ()))
            for item in primary.PRIMARY_DIRECTIONS
        }
        self.assertEqual(routes["global_breaking"], ("reuters.com",))
        self.assertEqual(routes["major_agencies"], ("bloomberg.com", "ft.com"))
        self.assertEqual(routes["independent_missing_events"], ("apnews.com", "ap.org"))
        for direction_id, domains in routes.items():
            if direction_id not in {"global_breaking", "major_agencies", "independent_missing_events"}:
                self.assertEqual(domains, (), direction_id)

    def test_agency_health_domain_set_covers_all_three_routes(self) -> None:
        self.assertEqual(
            set(primary.AGENCY_DOMAINS),
            {"reuters.com", "bloomberg.com", "ft.com", "apnews.com", "ap.org"},
        )


if __name__ == "__main__":
    unittest.main()
