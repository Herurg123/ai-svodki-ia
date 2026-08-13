from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "automation" / "fixtures" / "recall" / "2026-08-13.json"


class August13RecallExperimentTests(unittest.TestCase):
    def test_source_focused_experiment_recovers_all_controls(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        must_ids = {item["id"] for item in payload["must_discover"]}
        result = payload["experiment_result"]
        recovered = set(result["reuters_business_focused_query"])
        recovered.update(result["reuters_models_infrastructure_focused_query"])
        recovered.update(result["reuters_funding_focused_query"])
        recovered.update(result["ap_consumer_product_focused_query"])
        self.assertEqual(payload["incident_run_id"], 31652757802)
        self.assertEqual(payload["production_baseline"]["raw_candidate_count"], 4)
        self.assertEqual(len(must_ids), 5)
        self.assertEqual(recovered, must_ids)
        self.assertIn("without increasing", result["conclusion"])


if __name__ == "__main__":
    unittest.main()
