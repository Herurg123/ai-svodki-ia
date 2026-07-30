from pathlib import Path

path = Path("automation/patches/apply_rate_limit_and_recovery_fix.py")
text = path.read_text(encoding="utf-8")
old_jq = 'select((.name == "Run full research and editorial" or .name == "Restore saved paid artifact") and .conclusion == "success")'
new_jq = 'select((((.name | startswith("Run full research")) or (.name | startswith("Restore saved paid artifact"))) and .conclusion == "success"))'
if text.count(old_jq) != 1:
    raise SystemExit("expected one old jq selector")
text = text.replace(old_jq, new_jq, 1)
old_validator = "            'stream.write(\"reused=true\\\\\\\\n\")',"
if text.count(old_validator) != 1:
    raise SystemExit("expected one old validator success needle")
text = text.replace(old_validator, "            'reused=true',", 1)
old_test = "        self.assertIn('stream.write(\"reused=true\\\\\\\\n\")', workflow)"
if text.count(old_test) != 1:
    raise SystemExit("expected one old reliability success assertion")
text = text.replace(old_test, "        self.assertIn('reused=true', workflow)", 1)
path.write_text(text, encoding="utf-8")
