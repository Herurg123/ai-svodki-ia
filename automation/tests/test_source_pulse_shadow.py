from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

AUTOMATION_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = AUTOMATION_ROOT / "scripts"
for module_name in ("source_pulse", "story_coverage"):
    if module_name not in sys.modules:
        path = SCRIPTS_ROOT / f"{module_name}.py"
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

MODULE_PATH = SCRIPTS_ROOT / "source_pulse_shadow.py"
spec = importlib.util.spec_from_file_location("source_pulse_shadow", MODULE_PATH)
shadow = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = shadow
spec.loader.exec_module(shadow)
sp = sys.modules["source_pulse"]


def candidate(cid: str, title: str, url: str, published_date: str) -> dict:
    return {
        "id": cid,
        "title": title,
        "published_date": published_date,
        "recommendation": "consider",
        "primary_source": {"title": title, "publisher": "Example", "url": url},
    }


def lead(
    source_id: str, title: str, url: str, published_date: str,
    *, tier: str = "A", region: str = "global",
    cutoff_ambiguous: bool = False, archive_duplicate: bool = False,
) -> dict:
    day = datetime.fromisoformat(published_date).date()
    return {
        "source_id": source_id,
        "tier": tier,
        "region": region,
        "role": "official" if tier == "A" else "lead_only",
        "title": title,
        "url": url,
        "published_date": published_date,
        "published_at": None,
        "time_precision": "date",
        "cutoff_ambiguous": cutoff_ambiguous,
        "source_item_id": url,
        "event_fingerprint": sp.event_fingerprint(title, day),
        "exact_fingerprint": sp.exact_fp(title, url, day),
        "archive_url_duplicate": archive_duplicate,
    }


class SourcePulseFusionTests(unittest.TestCase):
    def test_exact_match_pulse_only_and_search_only_are_separated(self):
        research = {
            "candidates": [
                candidate("cand-001", "NVIDIA Groq 3 LPX full production", "https://nvidia.example/groq", "2026-08-24"),
                candidate("cand-002", "Search-only event", "https://search.example/only", "2026-08-24"),
            ]
        }
        snapshot = {
            "leads": [
                lead("nvidia", "NVIDIA Groq 3 LPX full production", "https://nvidia.example/groq?utm_source=rss", "2026-08-24"),
                lead("ithome", "Alibaba Wan3.0 AI video full launch", "https://ithome.example/wan3", "2026-08-24", tier="B", region="china_asia"),
            ]
        }
        result = shadow.build_fusion_diagnostics(snapshot, research)
        dispositions = {row["source_id"]: row["disposition"] for row in result["pulse_leads"]}
        self.assertEqual(dispositions["nvidia"], "both_exact_url")
        self.assertEqual(dispositions["ithome"], "pulse_only")
        self.assertEqual(result["summary"]["both_count"], 1)
        self.assertEqual(result["summary"]["pulse_only_count"], 1)
        self.assertEqual(result["summary"]["search_only_count"], 1)
        self.assertEqual(result["search_only_candidate_ids"], ["cand-002"])

    def test_cutoff_and_archive_rows_never_become_actionable_shadow_leads(self):
        snapshot = {
            "leads": [
                lead("a", "Cutoff event", "https://a.example/x", "2026-08-25", cutoff_ambiguous=True),
                lead("b", "Archived event", "https://b.example/x", "2026-08-24", archive_duplicate=True),
            ]
        }
        result = shadow.build_fusion_diagnostics(snapshot, {"candidates": []})
        by_source = {row["source_id"]: row for row in result["pulse_leads"]}
        self.assertEqual(by_source["a"]["disposition"], "cutoff_ambiguous")
        self.assertFalse(by_source["a"]["actionable_shadow_lead"])
        self.assertEqual(by_source["b"]["disposition"], "archive_duplicate")
        self.assertFalse(by_source["b"]["actionable_shadow_lead"])
        self.assertEqual(result["summary"]["pulse_only_count"], 0)


class SourcePulseShadowRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.artifact = root / "artifact"
        self.output = root / "production-daily"
        self.artifact.mkdir(parents=True)
        self.archive = root / "archive.json"
        self.registry = root / "registry.json"
        self.archive.write_text('{"items": []}\n', encoding="utf-8")
        self.registry.write_text(
            json.dumps(
                {
                    "version": 1,
                    "mode": "production_shadow",
                    "production_integration": True,
                    "candidate_influence": False,
                    "repoll_on_recovery": False,
                    "sources": [
                        {
                            "id": "x",
                            "tier": "A",
                            "region": "global",
                            "role": "official",
                            "adapter": "html_index",
                            "url": "https://x.example/news",
                            "allowed_hosts": ["x.example"],
                        }
                    ],
                }
            ) + "\n",
            encoding="utf-8",
        )
        (self.artifact / "candidates.json").write_text(
            json.dumps(
                {
                    "search_window": {
                        "start_at": "2026-08-24T00:00:00+00:00",
                        "end_at": "2026-08-25T00:00:00+00:00",
                    },
                    "candidates": [],
                }
            ) + "\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_snapshot_is_idempotently_reused_without_second_poll(self):
        calls = []
        pulse_lead = lead("x", "Current important event", "https://x.example/news/event", "2026-08-24")

        def collector(**kwargs):
            calls.append(kwargs)
            return {
                "version": 1,
                "mode": "research_only",
                "production_integration": False,
                "paid_api_calls": 0,
                "web_search_operations": 0,
                "snapshot_hash": "abc",
                "summary": {"lead_count": 1, "sources_ok": 1},
                "leads": [pulse_lead],
                "sources": [],
            }

        first = shadow.run_source_pulse_shadow(
            artifact_dir=self.artifact,
            archive_path=self.archive,
            publication_date="2026-08-25",
            output_root=self.output,
            registry_path=self.registry,
            collector_fn=collector,
        )
        second = shadow.run_source_pulse_shadow(
            artifact_dir=self.artifact,
            archive_path=self.archive,
            publication_date="2026-08-25",
            output_root=self.output,
            registry_path=self.registry,
            collector_fn=collector,
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(first["state"], "completed")
        self.assertTrue(second["reused_snapshot"])
        self.assertFalse(first["candidate_influence"])
        persisted = json.loads((self.artifact / "source-pulse.json").read_text(encoding="utf-8"))
        self.assertEqual(persisted["snapshot"]["mode"], "production_shadow")
        self.assertTrue(persisted["snapshot"]["production_integration"])
        self.assertEqual(persisted["fusion"]["summary"]["pulse_only_count"], 1)

    def test_collector_failure_is_nonfatal_and_preserves_candidates(self):
        original = (self.artifact / "candidates.json").read_bytes()

        def collector(**kwargs):
            raise RuntimeError("network exploded")

        result = shadow.run_source_pulse_shadow(
            artifact_dir=self.artifact,
            archive_path=self.archive,
            publication_date="2026-08-25",
            output_root=self.output,
            registry_path=self.registry,
            collector_fn=collector,
        )
        self.assertEqual(result["state"], "error_nonfatal")
        self.assertEqual(result["status"], "complete_with_gaps")
        self.assertEqual((self.artifact / "candidates.json").read_bytes(), original)
        self.assertEqual(result["paid_api_calls"], 0)
        self.assertEqual(result["web_search_operations"], 0)

    def test_fetch_started_prior_is_not_repolled(self):
        report = {
            "version": 1,
            "strategy": "source_pulse_shadow",
            "publication_date": "2026-08-25",
            "status": "running",
            "state": "fetch_started",
            "candidate_influence": False,
        }
        (self.artifact / "source-pulse.json").write_text(json.dumps(report) + "\n", encoding="utf-8")

        def collector(**kwargs):
            self.fail("collector must not be called after fetch_started state")

        result = shadow.run_source_pulse_shadow(
            artifact_dir=self.artifact,
            archive_path=self.archive,
            publication_date="2026-08-25",
            output_root=self.output,
            registry_path=self.registry,
            collector_fn=collector,
        )
        self.assertEqual(result["state"], "interrupted_no_repoll")
        self.assertTrue(result["reused_snapshot"])


    def test_invalid_shadow_contract_fails_open_without_polling(self):
        payload = json.loads(self.registry.read_text(encoding="utf-8"))
        payload["candidate_influence"] = True
        self.registry.write_text(json.dumps(payload) + "\n", encoding="utf-8")

        def collector(**kwargs):
            self.fail("collector must not run with invalid shadow contract")

        result = shadow.run_source_pulse_shadow(
            artifact_dir=self.artifact,
            archive_path=self.archive,
            publication_date="2026-08-25",
            output_root=self.output,
            registry_path=self.registry,
            collector_fn=collector,
        )
        self.assertEqual(result["state"], "error_nonfatal")
        self.assertIn("candidate_influence", result["error"])

    def test_saved_snapshot_gets_post_hybrid_fusion_without_repoll(self):
        pulse_lead = lead("x", "Current important event", "https://x.example/news/event", "2026-08-24")
        calls = []

        def collector(**kwargs):
            calls.append(1)
            return {
                "version": 1, "snapshot_hash": "abc", "summary": {"lead_count": 1},
                "leads": [pulse_lead], "sources": [], "paid_api_calls": 0,
                "web_search_operations": 0,
            }

        first = shadow.run_source_pulse_shadow(
            artifact_dir=self.artifact, archive_path=self.archive, publication_date="2026-08-25",
            output_root=self.output, registry_path=self.registry, collector_fn=collector,
        )
        self.assertEqual(first["fusion_pre_hybrid"]["summary"]["pulse_only_count"], 1)
        research = {
            "candidates": [candidate("cand-001", "Current important event", "https://x.example/news/event", "2026-08-24")]
        }
        updated = shadow.refresh_post_hybrid_fusion(
            artifact_dir=self.artifact, output_root=self.output, publication_date="2026-08-25", research=research
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(updated["fusion_post_hybrid"]["summary"]["both_count"], 1)
        self.assertEqual(updated["fusion_post_hybrid"]["summary"]["pulse_only_count"], 0)


class SourcePulseShadowArchitectureTests(unittest.TestCase):
    def test_hybrid_owns_shadow_integration_before_gap_planning(self):
        text = (SCRIPTS_ROOT / "hybrid_search_completeness.py").read_text(encoding="utf-8")
        self.assertIn("run_source_pulse_shadow", text)
        rescue_position = text.index("_pre_hybrid_source_freshness_gate(", text.index("def run_hybrid_completeness"))
        pulse_position = text.index("run_source_pulse_shadow(", rescue_position)
        gaps_position = text.index("gaps = _regional_gaps(research)", pulse_position)
        self.assertLess(rescue_position, pulse_position)
        self.assertLess(pulse_position, gaps_position)
        workflow = (AUTOMATION_ROOT.parent / ".github" / "workflows" / "daily-production.yml").read_text(encoding="utf-8")
        self.assertNotIn("source_pulse_shadow.py", workflow)
        self.assertNotIn("source_pulse.py", workflow)


if __name__ == "__main__":
    unittest.main()
