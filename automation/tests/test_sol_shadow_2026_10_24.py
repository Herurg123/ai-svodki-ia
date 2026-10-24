"""Controls for the final Sol 24-Oct one-shot Primary experiment, no API."""
from __future__ import annotations
import ast,importlib.util,pathlib,subprocess,sys,unittest
from types import SimpleNamespace
ROOT=pathlib.Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"automation/audits/experiments/2026-10-24-sol-shadow/run_primary.py"
spec=importlib.util.spec_from_file_location("sol24",SCRIPT)
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
class SolOct24Contract(unittest.TestCase):
    def test_date_model_window_and_archive(self):
        self.assertEqual(runner.DATE,"2026-10-24")
        self.assertEqual(runner.CUTOFF,"2026-10-24T04:35:28+03:00")
        self.assertEqual(runner.START,"2026-10-22T04:31:19+03:00")
        self.assertEqual(runner.FROZEN_CODE,"14a62d313dfb153174f410450d023186f8f8ac75")
        self.assertEqual(runner.MODEL,"gpt-6.1-sol")
        self.assertEqual(runner.MAX_REQUESTS,12)
    def test_no_dollar_gate_and_auditable_cost(self):
        code=SCRIPT.read_text(encoding="utf-8")
        ast.parse(code)
        self.assertNotIn("MAX_ESTIMATE_USD",code)
        self.assertNotIn("NEXT_RESERVE_USD",code)
        self.assertNotIn("SOL_SHADOW_OWNER_APPROVAL_USD",code)
        self.assertIn('STATE["api_request_count"] >= MAX_REQUESTS',code)
        self.assertIn('kwargs["max_retries"] = 0',code)
        self.assertTrue(runner.STATE["owner_removed_dollar_guard"])
        self.assertIn("tier_adjusted_estimate_usd",code)
    def test_manual_only_exact_ref(self):
        ci=(ROOT/".github/workflows/ci.yml").read_text(encoding="utf-8")
        paid=ci.split("  sol-24-paid-once:",1)[1].split("  sol-24-offline-proof:",1)[0]
        self.assertIn("github.event_name == 'workflow_dispatch'",paid)
        self.assertIn("github.ref == 'refs/heads/experiment/sol-shadow-2026-10-24'",paid)
        self.assertIn("secrets.OPENAI_API_KEY",paid)
        self.assertIn("UNCAPPED_12_ONLY",paid)
        self.assertIn("cancel-in-progress: false",paid)
        self.assertIn("needs: validate",paid)
        self.assertNotIn("contents: write",paid)
        self.assertIn("sol-24-offline-proof:",ci)
        self.assertIn("5240a7a12c9759ce0bd48e260e80faddb17d5e9dff9fb90ec3608729788f56fe",ci)
    def test_no_run_without_explicit_mode(self):
        p=subprocess.run([sys.executable,str(SCRIPT)],cwd=ROOT,
                         capture_output=True,text=True,timeout=10)
        self.assertEqual(p.returncode,2)
    def test_usage_estimator(self):
        u=SimpleNamespace(input_tokens=100000,output_tokens=10000,
                          input_tokens_details=SimpleNamespace(
                              cached_tokens=20000,cache_write_tokens=10000))
        regular=SimpleNamespace(usage=u,service_tier="default")
        promo=SimpleNamespace(usage=u,service_tier="incentivized-tier")
        self.assertAlmostEqual(runner.cost(regular,1)[0],0.277)
        self.assertEqual(runner.cost(regular,1)[0],runner.cost(regular,1)[1])
        self.assertAlmostEqual(runner.cost(promo,1)[1],0.01)
if __name__=="__main__": unittest.main()
