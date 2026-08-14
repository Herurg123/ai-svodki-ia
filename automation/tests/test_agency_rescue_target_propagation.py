from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_PATH = ROOT / "automation" / "scripts" / "ensure_story_coverage.py"
SPEC = importlib.util.spec_from_file_location(
    "ensure_story_coverage_agency_target_regression",
    RUNTIME_PATH,
)
assert SPEC and SPEC.loader
runtime = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runtime
SPEC.loader.exec_module(runtime)


class AgencyRescueTargetPropagationTests(unittest.TestCase):
    def test_normalizer_preserves_corroboration_target(self) -> None:
        source = {
            "id": "agency-candidate",
            "category": "business",
            "primary_source": {
                "publisher": "Reuters",
                "url": "https://www.reuters.com/example",
            },
        }

        normalized = runtime._normalize_agency_rescue_candidate(
            source,
            target_id="cand-003",
        )

        self.assertEqual(normalized["corroboration_target_id"], "cand-003")
        self.assertEqual(normalized["audit_direction"], "agency_rescue")
        self.assertEqual(normalized["legal_scale"], "not_applicable")
        self.assertNotIn("corroboration_target_id", source)

    def test_money_anchor_query_stays_publisher_neutral(self) -> None:
        target = {
            "organization": "Databricks",
            "title": "Databricks привлекла $5 млрд при оценке $190 млрд",
            "event_type": "funding",
            "keywords": ["Databricks", "funding"],
        }

        self.assertEqual(
            runtime._agency_corroboration_query(target),
            "Databricks $5 billion $190 billion",
        )

    def test_rescue_contract_version_is_v7(self) -> None:
        self.assertEqual(runtime.AGENCY_RESCUE_VERSION, 7)


if __name__ == "__main__":
    unittest.main()
