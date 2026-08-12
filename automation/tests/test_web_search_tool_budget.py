from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from ensure_story_coverage_policy import build_audit_api_metadata


class FakeAction:
    def __init__(self, action_type: str, **values):
        self.type = action_type
        for key, value in values.items():
            setattr(self, key, value)

    def model_dump(self):
        result = {"type": self.type}
        result.update({key: value for key, value in self.__dict__.items() if key != "type"})
        return result


class FakeItem:
    type = "web_search_call"

    def __init__(self, item_id: str, action: FakeAction):
        self.id = item_id
        self.status = "completed"
        self.action = action

    def model_dump(self):
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "action": self.action.model_dump(),
        }


class FakeResponse:
    id = "resp-test"
    status = "completed"
    model = "test-model"
    usage = None
    error = None
    incomplete_details = None

    def __init__(self):
        self.output = [
            FakeItem(
                "search-1",
                FakeAction(
                    "search",
                    query="AI news after:2026-08-10 before:2026-08-13",
                    sources=[{"url": "https://example.com/news"}],
                ),
            ),
            FakeItem(
                "open-1",
                FakeAction("open_page", url="https://example.com/news"),
            ),
            FakeItem(
                "find-1",
                FakeAction("find_in_page", url="https://example.com/news", pattern="August 11"),
            ),
        ]


class WebSearchToolBudgetTests(unittest.TestCase):
    def test_navigation_items_do_not_count_as_search_operations(self):
        metadata = build_audit_api_metadata(
            FakeResponse(),
            maximum_web_search_calls=1,
        )
        self.assertEqual(metadata["web_search_calls_completed"], 1)
        self.assertEqual(metadata["web_search_call_items_total"], 3)
        self.assertEqual(metadata["web_search_navigation_items_total"], 2)
        self.assertFalse(metadata["budget_overrun"])
        self.assertTrue(metadata["output_item_limit_exceeded"])
        self.assertEqual(
            metadata["web_search_action_type_counts"],
            {"search": 1, "open_page": 1, "find_in_page": 1},
        )
        self.assertEqual(len(metadata["actual_queries"]), 1)


if __name__ == "__main__":
    unittest.main()
