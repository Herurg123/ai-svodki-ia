from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

workflow = ROOT / ".github/workflows/daily-production.yml"
text = workflow.read_text(encoding="utf-8")
old = '''              stream.write("reused=true
")
              stream.write(
                  "image_recovered="
                  + ("true" if report.get("image_recovered") else "false")
                  + "
"
              )
'''
new = '''              stream.write("reused=true\\n")
              stream.write(
                  "image_recovered="
                  + ("true" if report.get("image_recovered") else "false")
                  + "\\n"
              )
'''
if text.count(old) != 1:
    raise RuntimeError(f"expected one malformed recovery output block, got {text.count(old)}")
workflow.write_text(text.replace(old, new, 1), encoding="utf-8")

reliability = ROOT / "automation/tests/test_production_reliability_patch.py"
text = reliability.read_text(encoding="utf-8")
old = "        self.assertIn('reused=true', workflow)\n"
new = '''        self.assertIn(r'stream.write("reused=true\\n")', workflow)
        self.assertIn(r'+ "\\n"', workflow)
'''
if text.count(old) != 1:
    raise RuntimeError("reliability assertion changed unexpectedly")
reliability.write_text(text.replace(old, new, 1), encoding="utf-8")

sync_test = ROOT / "automation/tests/test_production_contract_sync.py"
text = sync_test.read_text(encoding="utf-8")
needle = '''        self.assertIn('echo "reused=false" >> "${GITHUB_OUTPUT}"', workflow)
        self.assertIn("candidate_pool_after", workflow)
'''
replacement = '''        self.assertIn('echo "reused=false" >> "${GITHUB_OUTPUT}"', workflow)
        self.assertIn(r'stream.write("reused=true\\n")', workflow)
        self.assertIn(r'+ "\\n"', workflow)
        self.assertIn("candidate_pool_after", workflow)
'''
if text.count(needle) != 1:
    raise RuntimeError("contract sync assertion block changed unexpectedly")
sync_test.write_text(text.replace(needle, replacement, 1), encoding="utf-8")

validator = ROOT / "automation/scripts/validate_production_daily_contract.py"
text = validator.read_text(encoding="utf-8")
old = '''        (
            "successful recovery output",
            'reused=true',
        ),
'''
new = '''        (
            "successful recovery output",
            r'stream.write("reused=true\\n")',
        ),
        (
            "recovered image output newline",
            r'+ "\\n"',
        ),
'''
if text.count(old) != 1:
    raise RuntimeError("contract validator recovery output check changed unexpectedly")
validator.write_text(text.replace(old, new, 1), encoding="utf-8")
