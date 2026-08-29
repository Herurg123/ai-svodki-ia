from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import retrieval_routing_audit as audit

FIXTURE = ROOT / "automation" / "fixtures" / "recall" / "provider-routing-2026-08-29.json"


class RetrievalRoutingAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_production_controls_fail_before_post_retrieval_normalization(self) -> None:
        report = audit.audit_fixture(self.payload)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["classification_counts"]["provider_source_pool_miss"], 6)
        self.assertEqual(report["classification_counts"]["source_metadata_unavailable"], 1)
        self.assertNotIn("candidate_omission_after_retrieval", report["classification_counts"])

    def test_reuters_missing_sources_metadata_is_not_a_zero_source_claim(self) -> None:
        row = next(
            item for item in self.payload["production_observations"]
            if item["route"] == "agency:reuters_rescue_v4"
        )
        self.assertTrue(row["search_completed"])
        self.assertFalse(row["source_metadata_available"])
        self.assertIsNone(row["raw_action_sources"])
        self.assertEqual(audit.classify_observation(row), "source_metadata_unavailable")

    def test_query_contract_covers_all_three_fixed_controls(self) -> None:
        report = audit.audit_fixture(self.payload)
        self.assertEqual(report["uncovered_controls"], [])
        for control_id in ("yandex-sim", "ai-alliance-copyright", "tencent-hy4"):
            self.assertTrue(report["query_control_coverage"][control_id]["covered"])

    def test_query_contract_does_not_add_searches(self) -> None:
        report = audit.audit_fixture(self.payload)
        self.assertTrue(report["budget_unchanged"])
        self.assertEqual(report["ordinary_pipeline_maximum"], 24)
        self.assertEqual(report["double_regional_gap_maximum"], 25)
        self.assertEqual(report["p3_additional_searches"], 0)

    def test_missing_control_anchor_is_detected(self) -> None:
        control = self.payload["controls"]["tencent-hy4"]
        self.assertFalse(audit.query_covers_control("latest China AI models releases", control))
        self.assertTrue(
            audit.query_covers_control(
                "latest China AI models releases Tencent Hunyuan Qwen open source",
                control,
            )
        )


if __name__ == "__main__":
    unittest.main()
