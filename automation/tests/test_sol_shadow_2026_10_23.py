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

    def test_paid_one_shot_job_removed_after_success(self):
        content=(ROOT/".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertNotIn("sol-shadow-23-resume-four:",content)
        self.assertNotIn("sol-shadow-23-once:",content)
        self.assertNotIn("secrets.OPENAI_API_KEY",content)
        self.assertIn("sol-shadow-23-offline-proof:",content)
        self.assertIn("cancel-in-progress: true",content)

    def test_resume_runner_has_hard_four_call_limit_not_dollar_guard(self):
        import ast
        p=ROOT/"automation/audits/experiments/2026-10-23-sol-shadow/resume_four.py"
        code=p.read_text(encoding="utf-8")
        ast.parse(code)
        self.assertIn('S["new_count"]>=4',code)
        self.assertIn('frozen.EXPECTED_EXEC_SHA',code)
        self.assertIn("tier_estimate_usd",code)
        self.assertNotIn("MAX_ESTIMATE_USD",code)
        self.assertNotIn("NEXT_RESERVE_USD",code)

if __name__=="__main__":
    unittest.main()
