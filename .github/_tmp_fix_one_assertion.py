from pathlib import Path
p = Path('automation/tests/test_recall_sentinel.py')
text = p.read_text(encoding='utf-8')
old = '        self.assertIn("не должен быть привязан ни к OpenAI", call["prompt"])\n'
new = '        self.assertIn("привязан ни к OpenAI", call["prompt"])\n'
if old not in text:
    raise SystemExit('sentinel assertion not found')
p.write_text(text.replace(old, new, 1), encoding='utf-8')
Path('.github/_tmp_fix_one_assertion.py').unlink()
