from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import hybrid_search_completeness as hybrid


DATE = "2026-08-23"
WINDOW = {
    "start_at": "2026-08-21T02:37:50+03:00",
    "end_at": "2026-08-23T02:35:04+03:00",
    "start_date": "2026-08-21",
    "end_date": "2026-08-23",
}


def candidate(title: str, *, rescue: bool = False) -> dict:
    item = {
        "id": "cand-001",
        "title": title,
        "organization": title.split()[0],
        "published_date": "2026-08-22",
        "published_at": "2026-08-22T19:21:00+00:00",
        "time_precision": "datetime",
        "topic": "AI infrastructure",
        "event_type": "pricing_update",
        "keywords": ["AI", "servers"],
        "geography": "world",
        "category": "infrastructure",
        "source_type": "news_agency",
        "primary_source": {
            "title": title,
            "publisher": "Reuters",
            "url": "https://www.reuters.com/technology/example/",
        },
        "supporting_sources": [],
        "event_summary": "Fresh event.",
        "verified_facts": ["Fact one", "Fact two"],
        "significance": "Material event.",
        "significance_score": 5,
        "limitations": "",
        "archive_status": "none",
        "archive_reason": "Not published.",
        "recommendation": "include",
        "verification_status": "verified",
        "verification_notes": "Verified.",
        "freshness_status": "new_event",
        "freshness_reason": "Inside window.",
        "legal_scale": "not_applicable",
        "legal_scale_reason": "",
        "curiosity_eligible": False,
        "curiosity_verification": "",
    }
    if rescue:
        item["audit_direction"] = "agency_discovery_rescue"
    return item


def rescue_report(runtime: Path, diagnostic: Path) -> dict:
    return {
        "version": 1,
        "search_strategy": "agency_discovery_rescue",
        "publication_date": DATE,
        "state": "completed",
        "status": "complete",
        "added_count": 1,
        "accepted_count": 1,
        "accepted_candidates": [candidate("Nvidia pricing", rescue=True)],
        "merged_research_path": str(runtime),
        "diagnostic_merged_research_path": str(diagnostic),
        "search_operation_count_contribution": 1,
    }


class PreHybridAgencyFreshnessTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path, Path, dict]:
        # The production helper only mutates generated files underneath the
        # repository root. Treat this temp directory as that root so cleanup
        # assertions exercise the real safety boundary instead of an impossible
        # out-of-repository path.
        old_repository_root = hybrid.REPOSITORY_ROOT
        hybrid.REPOSITORY_ROOT = root
        self.addCleanup(setattr, hybrid, "REPOSITORY_ROOT", old_repository_root)

        artifact = root / "artifact"
        output = root / "output"
        runtime = root / "runtime.json"
        diagnostic = root / "diagnostic.json"
        artifact.mkdir()
        research = {
            "search_window": copy.deepcopy(WINDOW),
            "candidates": [
                candidate("Primary event"),
                candidate("Nvidia pricing", rescue=True),
            ],
        }
        (artifact / "candidates.json").write_text(
            json.dumps(research), encoding="utf-8"
        )
        runtime.write_text(json.dumps(research), encoding="utf-8")
        diagnostic.write_text(json.dumps(research), encoding="utf-8")
        return artifact, output, runtime, rescue_report(runtime, diagnostic)

    def test_fresh_rescue_survives_and_updates_runtime_before_hybrid(self):
        with tempfile.TemporaryDirectory() as temp:
            artifact, output, runtime, report = self._fixture(Path(temp))

            def verify(payload):
                return copy.deepcopy(payload), {
                    "status": "complete",
                    "eligible_before": 1,
                    "eligible_after": 1,
                    "verified_fresh": 1,
                }

            result = hybrid._pre_hybrid_source_freshness_gate(
                rescue=report,
                artifact_dir=artifact,
                publication_date=DATE,
                output_root=output,
                verify_fn=verify,
            )
            self.assertEqual(result["added_count"], 1)
            self.assertEqual(result["source_freshness_gate"]["status"], "complete")
            research = json.loads((artifact / "candidates.json").read_text())
            self.assertEqual(len(research["candidates"]), 2)
            self.assertEqual(
                research["candidates"][1]["audit_direction"],
                "agency_discovery_rescue",
            )
            persisted = json.loads(runtime.read_text())
            self.assertEqual(len(persisted["candidates"]), 2)

    def test_stale_rescue_is_removed_before_hybrid_can_count_it(self):
        with tempfile.TemporaryDirectory() as temp:
            artifact, output, runtime, report = self._fixture(Path(temp))

            def verify(payload):
                verified = copy.deepcopy(payload)
                verified["candidates"][0]["recommendation"] = "exclude"
                verified["candidates"][0]["freshness_status"] = "old_reprint"
                return verified, {
                    "status": "complete",
                    "eligible_before": 1,
                    "eligible_after": 0,
                    "excluded_outside_window": 1,
                }

            result = hybrid._pre_hybrid_source_freshness_gate(
                rescue=report,
                artifact_dir=artifact,
                publication_date=DATE,
                output_root=output,
                verify_fn=verify,
            )
            self.assertEqual(result["added_count"], 0)
            self.assertEqual(result["state"], "completed_no_addition")
            research = json.loads((artifact / "candidates.json").read_text())
            self.assertEqual([row["title"] for row in research["candidates"]], ["Primary event"])
            self.assertFalse(runtime.exists())
            self.assertNotIn("merged_research_path", result)

    def test_freshness_error_drops_only_supplemental_rescue_row(self):
        with tempfile.TemporaryDirectory() as temp:
            artifact, output, runtime, report = self._fixture(Path(temp))

            def verify(_payload):
                raise RuntimeError("publisher date unavailable")

            result = hybrid._pre_hybrid_source_freshness_gate(
                rescue=report,
                artifact_dir=artifact,
                publication_date=DATE,
                output_root=output,
                verify_fn=verify,
            )
            self.assertEqual(result["added_count"], 0)
            self.assertEqual(
                result["source_freshness_gate"]["status"], "error_nonfatal"
            )
            research = json.loads((artifact / "candidates.json").read_text())
            self.assertEqual([row["title"] for row in research["candidates"]], ["Primary event"])
            self.assertEqual(research["candidates"][0]["id"], "cand-001")
            self.assertFalse(runtime.exists())


if __name__ == "__main__":
    unittest.main()
