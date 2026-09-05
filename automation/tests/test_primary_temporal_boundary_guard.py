from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


primary = load("primary_temporal_boundary_guard_test", "primary_recall_search.py")


class PrimaryTemporalBoundaryGuardTests(unittest.TestCase):
    def _prompt(self, direction_id: str) -> str:
        direction = next(
            item for item in primary.PRIMARY_DIRECTIONS if item["id"] == direction_id
        )
        return primary.build_prompt(
            "base prompt",
            publication_date="2026-09-05",
            search_window={
                "start_at": "2026-09-03T03:58:49+03:00",
                "end_at": "2026-09-05T03:57:22+03:00",
            },
            direction=direction,
            existing_candidates=[],
            archive={"items": []},
        )

    def test_guard_is_applied_to_every_primary_direction(self):
        for direction in primary.PRIMARY_DIRECTIONS:
            prompt = self._prompt(direction["id"])
            self.assertIn("Temporal boundary guard v1", prompt)
            self.assertIn("deterministic Source Freshness Proof", prompt)
            self.assertIn("2026-09-04T19:21:00+03:00", prompt)
            self.assertIn("а НЕ 5 сентября", prompt)

    def test_guard_does_not_change_search_budget_or_business_query(self):
        self.assertEqual(primary.DEFAULT_MAXIMUM_SEARCH_CALLS, 12)
        prompt = self._prompt(primary.BUSINESS_QUERY_DIRECTION_ID)
        self.assertIn(primary.BUSINESS_QUERY_TREATMENT, prompt)
        self.assertEqual(prompt.count(primary.BUSINESS_QUERY_TREATMENT), 1)
        self.assertIn("не меняет search query", prompt)
        self.assertIn("не меняет search query", self._prompt("global_breaking"))

    def test_diagnostics_record_zero_cost_guard(self):
        research, report = primary._annotate(
            {"candidates": []},
            {"directions": []},
        )
        for payload in (research, report):
            guard = payload["temporal_boundary_guard"]
            self.assertEqual(guard["version"], 1)
            self.assertEqual(guard["scope"], "all_primary_directions")
            self.assertFalse(guard["query_changed"])
            self.assertEqual(guard["additional_search_operations"], 0)
            self.assertTrue(guard["downstream_freshness_fail_closed"])


if __name__ == "__main__":
    unittest.main()
