from pathlib import Path

# Primary Responses output headroom: search budget stays 12; this only prevents a
# completed broad search + navigation sequence from being discarded because the
# structured response cannot finish inside the old 3500-token ceiling.
p = Path('automation/scripts/primary_recall_search.py')
text = p.read_text(encoding='utf-8')
anchor = 'PRIMARY_NAVIGATION_TOOL_ALLOWANCE = 3\nPRIMARY_MAX_TOOL_CALLS_PER_PASS = 1 + PRIMARY_NAVIGATION_TOOL_ALLOWANCE\n'
replacement = anchor + 'PRIMARY_MAX_OUTPUT_TOKENS_PER_PASS = 6000\n'
if anchor not in text:
    raise SystemExit('primary constants anchor not found')
text = text.replace(anchor, replacement, 1)
old = '        max_output_tokens=3500,\n'
if text.count(old) != 1:
    raise SystemExit(f'expected one Primary max_output_tokens=3500, found {text.count(old)}')
text = text.replace(old, '        max_output_tokens=PRIMARY_MAX_OUTPUT_TOKENS_PER_PASS,\n', 1)
old = '    metadata["navigation_tool_allowance"] = PRIMARY_NAVIGATION_TOOL_ALLOWANCE\n'
new = old + '    metadata["configured_max_output_tokens"] = PRIMARY_MAX_OUTPUT_TOKENS_PER_PASS\n'
if old not in text:
    raise SystemExit('primary metadata anchor not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

# Regression: the Aug-14 live smoke reached the final pass search successfully,
# then response.status became incomplete solely because max_output_tokens=3500.
p = Path('automation/tests/test_primary_recall_search.py')
text = p.read_text(encoding='utf-8')
insert = '''\n    def test_primary_pass_has_structured_output_headroom_for_broad_last_mile(self):\n        self.assertEqual(prs.PRIMARY_MAX_OUTPUT_TOKENS_PER_PASS, 6000)\n        source = (SCRIPT_DIR / "primary_recall_search.py").read_text(encoding="utf-8")\n        self.assertIn("max_output_tokens=PRIMARY_MAX_OUTPUT_TOKENS_PER_PASS", source)\n        self.assertIn('metadata["configured_max_output_tokens"]', source)\n'''
marker = '\n    def test_mandatory_pass_failure_is_fail_closed(self):\n'
if marker not in text:
    raise SystemExit('primary test insertion marker not found')
text = text.replace(marker, insert + marker, 1)
p.write_text(text, encoding='utf-8')

# Maintained contracts: search-operation budget is unchanged; output ceiling is
# headroom, not another retrieval call.
p = Path('AGENTS.md')
text = p.read_text(encoding='utf-8')
needle = 'A second search action or a batched multi-query search is a contract violation.\n'
addition = needle + '\nEach Primary Responses pass has `max_output_tokens=6000`. This is structured-output/reasoning headroom, not additional Web Search budget: the pass still must complete exactly one search operation. The 2026-08-14 live relative-freshness smoke showed the final `independent_missing_events` search and all three navigation actions completing successfully, but the response becoming `incomplete` solely at the former 3500-token ceiling.\n'
if needle not in text:
    raise SystemExit('AGENTS Primary budget paragraph not found')
text = text.replace(needle, addition, 1)
p.write_text(text, encoding='utf-8')

p = Path('automation/README.md')
text = p.read_text(encoding='utf-8')
needle = 'Второй search или batched multi-query считается нарушением контракта.\n'
addition = needle + '\nResponses-output ceiling для каждого Primary pass равен **6000 tokens**. Это запас для reasoning и завершения строгого JSON после search/navigation, а не дополнительный search-бюджет; лимит остаётся ровно один search operation на pass. Старый потолок 3500 был повышен после live-smoke 2026-08-14, где финальный broad pass успел выполнить search и три navigation action, но API завершил ответ как `incomplete / max_output_tokens`.\n'
if needle not in text:
    raise SystemExit('automation README Primary budget paragraph not found')
text = text.replace(needle, addition, 1)
p.write_text(text, encoding='utf-8')

# Root README was reviewed; keep operator-level detail concise but explicit.
p = Path('README.md')
text = p.read_text(encoding='utf-8')
needle = '   или batched multi-query считается нарушением контракта.\n'
addition = needle + '   Responses-output ceiling одного Primary pass — 6000 tokens; это headroom для reasoning/JSON после уже выполненного поиска и не увеличивает 12-search budget.\n'
if needle not in text:
    raise SystemExit('root README Primary budget paragraph not found')
text = text.replace(needle, addition, 1)
p.write_text(text, encoding='utf-8')

Path('.github/_tmp_fix_primary_output_headroom.py').unlink()
