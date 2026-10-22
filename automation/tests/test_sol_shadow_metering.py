"""Офлайн-контроли разового Sol shadow; OpenAI API никогда не вызывается."""
import importlib.util
import json
import tempfile
import zipfile
import os
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "automation/audits/experiments/2026-10-22-sol-api-shadow/run_shadow.py"
SPEC = importlib.util.spec_from_file_location("sol_shadow_runner_offline_test", SCRIPT)
shadow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shadow)

def item(action, status="completed"):
    return SimpleNamespace(type="web_search_call", status=status,
                           action=SimpleNamespace(type=action))

class SolShadowOfflineRegression(unittest.TestCase):
    def test_only_search_is_billable(self):
        response = [item("search"), item("open_page"), item("find_in_page"),
                    item("search", status="in_progress")]
        self.assertEqual(shadow.count_billable_search_actions(response), 1)

    def test_false_navigation_budget_reproduces_original_failure(self):
        # Seven one-search responses had 21 completed navigation items.
        # Original bug counted 7+21>25 and stopped on the next response.
        sample = [item("search") for _ in range(7)]
        sample += [item("open_page") for _ in range(14)]
        sample += [item("find_in_page") for _ in range(7)]
        self.assertEqual(shadow.count_billable_search_actions(sample), 7)
        self.assertGreater(len(sample), 25)

    def test_cache_write_is_total_rate_not_additive_surcharge(self):
        self.assertAlmostEqual(shadow.estimate_standard_usd(
            51875, 3831, 18322, 0, 1), 0.161221, places=7)

    def test_reject_invalid_token_partitions(self):
        with self.assertRaises(ValueError):
            shadow.estimate_standard_usd(100, 4, 80, 30, 1)

    def test_replay_order_and_five_remaining_calls(self):
        directions = [
            "global_breaking", "major_agencies", "models_products_agents",
            "infrastructure_chips_cloud", "business_investment_partnerships",
            "china_asia_models", "china_asia_integrations",
        ]
        rows = [
            {"direction_id": d, "status": "complete", "notes": "",
             "raw_candidates": [], "model_rejections": [],
             "api": {"web_search_calls_completed": 1,
                     "model": shadow.MODEL, "status": "completed"}}
            for d in directions
        ]
        fresh = []
        def missing_runner(*, direction_id, **kwargs):
            fresh.append(direction_id)
            return ({"direction_id": direction_id, "status": "complete_with_gaps",
                     "notes": "", "candidates": [], "rejections": []},
                    {"web_search_calls_completed": 1,
                     "model": shadow.MODEL, "status": "completed"})
        runner, progress = shadow.build_replay_runner(rows, missing_runner)
        for d in directions:
            payload, api = runner(direction_id=d)
            self.assertEqual(payload["direction_id"], d)
            self.assertEqual(api["model"], shadow.MODEL)
        remaining = ["russia", "developer_tools", "security_safety",
                     "legal_regulation", "independent_missing_events"]
        for d in remaining:
            runner(direction_id=d)
        self.assertEqual(progress, {"replayed": 7, "new_queries": 5})
        self.assertEqual(fresh, remaining)

    def test_replay_wrong_direction_fails_closed(self):
        row = {"direction_id": "global_breaking", "status": "complete",
               "raw_candidates": [], "model_rejections": [],
               "api": {"model": shadow.MODEL}}
        def no_network(**kwargs):
            self.fail("Should not make paid or network call")
        runner, _ = shadow.build_replay_runner([row], no_network)
        with self.assertRaises(RuntimeError):
            runner(direction_id="major_agencies")

    def test_public_primary_matrix_12_passes_offline(self):
        # Exercise production Primary wrapper and downstream merge, using
        # seven synthetic frozen envelopes + five no-op future passes.
        # Separately execute --offline-verify against ORIGINAL ZIP to prove
        # actual Sol responses (this unit test does not claim live findings).
        import json
        sys.path.insert(0, str(ROOT / "automation" / "scripts"))
        import primary_recall_search as primary
        from primary_recall_search import PRIMARY_DIRECTIONS
        saved = [d["id"] for d in PRIMARY_DIRECTIONS]
        self.assertEqual(len(saved), 12)
        rows = [{"direction_id": name, "status": "complete_with_gaps",
                 "notes": "saved synthetic no-op", "raw_candidates": [],
                 "model_rejections": [],
                 "api": {"model": shadow.MODEL, "status": "completed",
                         "web_search_calls_completed": 1}}
                for name in saved[:7]]
        def future_stub(*, direction_id, **kwargs):
            return ({
                "direction_id": direction_id, "status": "complete_with_gaps",
                "notes": "offline future stub", "candidates": [],
                "rejections": []
            }, {"model": shadow.MODEL, "status": "completed",
                "web_search_calls_completed": 1})
        runner, progress = shadow.build_replay_runner(rows, future_stub)
        archive = json.loads(
            (ROOT / "automation" / "archive" / "index.json").read_text(encoding="utf-8"))
        research, report = primary.run_primary_recall_matrix(
            publication_date=shadow.DATE,
            search_window={"start_at": "2026-10-20T04:35:44+03:00",
                           "end_at": shadow.CUTOFF,
                           "latest_archive_at": "2026-10-21T04:35:44+03:00",
                           "start_date": "2026-10-20",
                           "end_date": shadow.DATE,
                           "latest_archive_date": "2026-10-21"},
            archive=archive, api_key="OFFLINE_NEVER_NETWORK", model=shadow.MODEL,
            maximum_candidates=20, search_runner=runner)
        self.assertEqual(progress, {"replayed": 7, "new_queries": 5})
        self.assertEqual(len(report["directions"]), 12)
        self.assertEqual([d["direction_id"] for d in report["directions"]], saved)
        self.assertEqual(report["search_budget"]["completed_calls"], 12)
        self.assertEqual(len(research["candidates"]), 0)

    def test_original_replay_schema_and_tamper_fails_closed(self):
        ids = shadow.EXPECTED_FROZEN_DIRECTION_IDS
        rows = [
            {"direction_id": direction, "status": "complete",
             "notes": "", "raw_candidates": [], "model_rejections": [],
             "accepted_count": 0,
             "api": {
                 "model": shadow.MODEL, "status": "completed",
                 "web_search_calls_completed": 1,
                 "web_search_search_operations_performed": 1,
                 "usage": {"input_tokens": 100, "output_tokens": 20},
             }}
            for direction in ids
        ]
        original = {
            "publication_date": shadow.DATE,
            "search_window": {
                "start_at": "2026-10-20T04:35:44+03:00",
                "end_at": shadow.CUTOFF,
            },
            "directions": rows
        }
        execution = {
            "model": shadow.MODEL, "request_count": 8,
            "frozen_archive_sha256": shadow.EXPECTED_FROZEN_ARCHIVE_SHA
        }
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "frozen.zip"
            def create_archive():
                with zipfile.ZipFile(p, "w") as f:
                    f.writestr("production-daily/primary-recall-2026-10-22.json",
                               json.dumps(original))
                    f.writestr("sol-shadow-2026-10-22/execution.json",
                               json.dumps(execution))
            create_archive()
            recovered, digest = shadow.load_frozen_replay(str(p))
            self.assertEqual(len(recovered), 7)
            self.assertEqual([r["direction_id"] for r in recovered], list(ids))
            self.assertEqual(len(digest), 64)
            original["directions"][4]["api"]["model"] = "gpt-5.6-terra"
            create_archive()
            with self.assertRaises(RuntimeError):
                shadow.load_frozen_replay(str(p))
            original["directions"][4]["api"]["model"] = shadow.MODEL
            original["directions"][3]["api"]["usage"] = {}
            create_archive()
            with self.assertRaises(RuntimeError):
                shadow.load_frozen_replay(str(p))

    @unittest.skipUnless(
        os.getenv("SOL_SHADOW_REPLAY_ARTIFACT"),
        "Exact prior paid artifact must be supplied explicitly"
    )
    def test_actual_saved_zip_full_primary_offline(self):
        report = shadow.verify_replay_offline(os.environ["SOL_SHADOW_REPLAY_ARTIFACT"])
        self.assertEqual(report["status"], "offline_pass")
        self.assertEqual(report["frozen_passes"], 7)
        self.assertEqual(report["simulated_future_passes"], 5)
        self.assertEqual(report["real_api_calls"], 0)
        self.assertEqual(report["first_seven_raw_candidates"], 6)
        self.assertEqual(report["first_seven_accepted"], 5)

    def test_budget_is_one_dollar_and_retry_is_approval_gated(self):
        self.assertEqual(shadow.MAX_DOLLARS, 1.0)
        self.assertLessEqual(shadow.MAX_NEW_REQUEST_RESERVE, shadow.MAX_DOLLARS)
        process = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT,
            env={k: v for k, v in os.environ.items()
                 if k not in ("OPENAI_API_KEY", "SOL_SHADOW_OWNER_APPROVAL_USD")},
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=10)
        self.assertEqual(process.returncode, 2, process.stderr)
        self.assertIn("OFFLINE ONLY", process.stdout)

if __name__ == "__main__":
    unittest.main()
