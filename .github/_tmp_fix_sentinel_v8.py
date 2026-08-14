from pathlib import Path

# Fix accidental line-continuation artifact and preserve authoritative-now wording.
p = Path('automation/scripts/ensure_story_coverage.py')
text = p.read_text(encoding='utf-8')
text = text.replace('\n\\\ndef build_recall_sentinel_prompt(', '\n\ndef build_recall_sentinel_prompt(', 1)
old = 'Авторитетное текущее время этого sentinel-прохода: {end_at}.\nИдентификатор направления:'
new = ('Авторитетное текущее время этого sentinel-прохода: {end_at}. Всё, что опубликовано '\n       'не позже этого timestamp, не является будущим только из-за системной даты модели.\nИдентификатор направления:')
if old not in text:
    raise SystemExit('sentinel authoritative-now insertion point not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

# Recovery contract must accept only the new sentinel version.
p = Path('.github/workflows/daily-production.yml')
text = p.read_text(encoding='utf-8')
old = '(data.get("recall_sentinel") or {}).get("version") == 7'
if text.count(old) != 1:
    raise SystemExit(f'expected one workflow sentinel v7 occurrence, found {text.count(old)}')
text = text.replace(old, '(data.get("recall_sentinel") or {}).get("version") == 8', 1)
p.write_text(text, encoding='utf-8')

# Temporal contract tests track the canonical sentinel version and workflow guard.
p = Path('automation/tests/test_temporal_anchor_contract.py')
text = p.read_text(encoding='utf-8')
text = text.replace('self.assertEqual(coverage.RECALL_SENTINEL_VERSION, 7)', 'self.assertEqual(coverage.RECALL_SENTINEL_VERSION, 8)')
text = text.replace("self.assertIn('(data.get(\"recall_sentinel\") or {}).get(\"version\") == 7', workflow)", "self.assertIn('(data.get(\"recall_sentinel\") or {}).get(\"version\") == 8', workflow)")
p.write_text(text, encoding='utf-8')

# Sanity checks for the exact defects fixed here.
assert '\n\\\ndef build_recall_sentinel_prompt(' not in Path('automation/scripts/ensure_story_coverage.py').read_text(encoding='utf-8')
assert '(data.get("recall_sentinel") or {}).get("version") == 7' not in Path('.github/workflows/daily-production.yml').read_text(encoding='utf-8')
assert 'RECALL_SENTINEL_VERSION, 7' not in Path('automation/tests/test_temporal_anchor_contract.py').read_text(encoding='utf-8')

Path('.github/_tmp_fix_sentinel_v8.py').unlink()
