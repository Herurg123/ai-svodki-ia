"""Офлайн-контроли разового Sol shadow; OpenAI API никогда не вызывается."""
import importlib.util
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

    def test_budget_is_one_dollar_and_retry_is_approval_gated(self):
        self.assertEqual(shadow.MAX_DOLLARS, 1.0)
        self.assertLessEqual(shadow.MAX_NEW_REQUEST_RESERVE, shadow.MAX_DOLLARS)
        process = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT,
            env={k: v for k, v in os.environ.items()
                 if k not in ("OPENAI_API_KEY", "SOL_SHADOW_OWNER_APPROVAL_USD")},
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("OFFLINE ONLY", process.stdout)

if __name__ == "__main__":
    unittest.main()
