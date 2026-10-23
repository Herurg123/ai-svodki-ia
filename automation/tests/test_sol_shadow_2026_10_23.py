"""Fail-closed offline controls for the 2026-10-23 Sol shadow runner."""
import importlib.util
import pathlib
import subprocess
import sys
import unittest
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT/"automation/audits/experiments/2026-10-23-sol-shadow/run_primary.py"
spec = importlib.util.spec_from_file_location("sol_shadow_23", SCRIPT)
shadow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shadow)

class SolOct23Tests(unittest.TestCase):
    def test_pinned_contract(self):
        self.assertEqual(shadow.DATE, "2026-10-23")
        self.assertEqual(shadow.MAX_REQUESTS, 12)
        self.assertEqual(shadow.MAX_ESTIMATE_USD, 1.0)
        self.assertEqual(shadow.CUTOFF, "2026-10-23T04:31:19+03:00")

    def test_tier_price_not_invoice(self):
        class U:
            input_tokens=100000
            output_tokens=10000
            input_tokens_details=SimpleNamespace(cached_tokens=20000,
                                                  cache_write_tokens=10000)
        discounted=SimpleNamespace(usage=U(), service_tier="incentivized-tier")
        normal=SimpleNamespace(usage=U(), service_tier="default")
        std, inc, tier = shadow.cost(discounted, 1)
        self.assertEqual(tier, "incentivized-tier")
        self.assertAlmostEqual(inc, 0.01)
        self.assertAlmostEqual(std, 0.277)
        self.assertEqual(shadow.cost(normal,1)[1], std)

    def test_no_api_without_paid_approval(self):
        p=subprocess.run([sys.executable,str(SCRIPT)], cwd=ROOT,
                         capture_output=True,text=True,timeout=10)
        self.assertEqual(p.returncode,2)

    def test_only_manual_branch_has_paid_ci(self):
        content=(ROOT/".github/workflows/ci.yml").read_text(encoding="utf-8")
        job=content.split("  sol-shadow-23-once:",1)[1]
        self.assertIn("github.event_name == 'workflow_dispatch'",job)
        self.assertIn("github.ref == 'refs/heads/experiment/sol-shadow-2026-10-23'",job)
        self.assertIn("secrets.OPENAI_API_KEY",job)
        self.assertIn("needs: validate",job)
        self.assertIn("cancel-in-progress: false",job)
        self.assertNotIn("contents: write",job)
        self.assertNotIn("push:",job)

if __name__=="__main__":
    unittest.main()
