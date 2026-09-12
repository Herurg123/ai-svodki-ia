from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


primary = load("p3a_boundary_primary", "primary_recall_search.py")
prompt_context = load("p3a_boundary_prompt_context", "prompt_context.py")


class P3aDiagnosticBoundaryTests(unittest.TestCase):
    def test_malformed_weak_source_url_cannot_abort_completed_primary_matrix(self) -> None:
        research = {"status": "ok", "candidates": []}
        report = {
            "directions": [
                {
                    "direction_id": "independent_missing_events",
                    "status": "complete_with_gaps",
                    "accepted_count": 0,
                    "model_rejections": [
                        {
                            "title": "DeepSeek replaces V4 Pro with V4.1 Flash",
                            "url": "https://[bad",
                            "reason_code": "weak_source",
                            "reason": "Weak source provenance is malformed.",
                        }
                    ],
                }
            ]
        }
        original = primary._BASE_RUN_MATRIX
        try:
            primary._BASE_RUN_MATRIX = lambda *_a, **_k: (
                copy.deepcopy(research),
                copy.deepcopy(report),
            )
            annotated_research, annotated_report = primary.run_primary_recall_matrix()
        finally:
            primary._BASE_RUN_MATRIX = original

        self.assertEqual(annotated_research["candidates"], [])
        self.assertEqual(annotated_report["unresolved_signals"], [])
        self.assertEqual(annotated_research["unresolved_signals"], [])

    def test_weak_source_evidence_stays_out_of_editorial_research_context(self) -> None:
        research = {
            "status": "ok",
            "publication_date": "2026-09-11",
            "candidates": [{"id": "cand-001", "title": "Existing candidate"}],
        }
        unverified = {
            "title": "Nvidia eyes up to $3b in SB Energy for OpenAI data center",
            "url": "https://www.reuters.com/example",
            "reason_code": "unverified",
            "reason": "Fresh Reuters result indicates investment but direct verification was unavailable.",
        }
        weak = {
            "title": "DeepSeek Replaces V4 Pro With V4.1 Flash Following Superior Speed and Cost Tests",
            "url": "https://huggingnews.com/ai/update-deepseek-replaces-v4-pro-with-v41-flash-following-superior-speed-afb7de47",
            "reason_code": "weak_source",
            "reason": "Official release note was not obtained in this pass.",
        }

        def report_with(rows: list[dict]) -> dict:
            return {
                "directions": [
                    {
                        "direction_id": "independent_missing_events",
                        "status": "complete_with_gaps",
                        "accepted_count": 0,
                        "model_rejections": copy.deepcopy(rows),
                    }
                ]
            }

        baseline_research, baseline_report = primary._annotate(
            research,
            report_with([unverified]),
        )
        mixed_research, mixed_report = primary._annotate(
            research,
            report_with([unverified, weak]),
        )

        # generate_digest_preview passes compact_json(research) into the editorial
        # candidates context. Diagnostic-only weak evidence must therefore leave the
        # serialized research input exactly unchanged relative to the pre-P3a shape.
        self.assertEqual(
            prompt_context.compact_json(mixed_research),
            prompt_context.compact_json(baseline_research),
        )
        self.assertEqual(
            mixed_research["unresolved_signals"],
            baseline_research["unresolved_signals"],
        )
        self.assertTrue(mixed_research["unresolved_signals"])
        self.assertTrue(
            all(item.get("reason_code") == "unverified" for item in mixed_research["unresolved_signals"])
        )

        report_weak = [
            item
            for item in mixed_report["unresolved_signals"]
            if item.get("reason_code") == "weak_source"
        ]
        self.assertEqual(len(report_weak), 1)
        self.assertFalse(report_weak[0]["resolution_required"])
        self.assertFalse(report_weak[0]["candidate_eligible"])
        self.assertEqual(report_weak[0]["additional_search_operations"], 0)
        self.assertEqual(
            len(mixed_report["unresolved_signals"]),
            len(baseline_report["unresolved_signals"]) + 1,
        )


if __name__ == "__main__":
    unittest.main()
