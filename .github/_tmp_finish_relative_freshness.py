from pathlib import Path

# Keep Primary direction prose consistent with actual routing.
p = Path('automation/scripts/primary_recall_search.py')
text = p.read_text(encoding='utf-8')
old = '''        "guidance": (\n            "Отдельно ищи свежие ИИ-события у Reuters, Associated Press, Bloomberg "\n            "и Financial Times. Нужны не только релизы моделей, но также чипы, "\n            "инфраструктура, инвестиции, M&A, партнёрства, policy, legal и security."\n        ),\n        "allowed_domains": BLOOMBERG_FT_DOMAINS,'''
new = '''        "guidance": (\n            "Отдельный high-signal sweep Bloomberg и Financial Times: модели, "\n            "чипы, инфраструктура, инвестиции, M&A, партнёрства, policy, legal "\n            "и security. Это дополнительный publisher route, не мировой catch-all."\n        ),\n        "allowed_domains": BLOOMBERG_FT_DOMAINS,'''
if old not in text:
    raise SystemExit('major_agencies guidance block not found')
p.write_text(text.replace(old, new, 1), encoding='utf-8')

# AGENTS: remove obsolete publisher-locked routing bullets.
p = Path('AGENTS.md')
text = p.read_text(encoding='utf-8')
old = '''High-signal routing must stay source-diverse without increasing the 12-search\nbudget:\n\n- `global_breaking` uses a source-neutral funding/acquisition/M&A/major-business\n  query inside a `reuters.com` API filter;\n- `major_agencies` uses a source-neutral compact major-AI/date query inside a\n  `bloomberg.com` + `ft.com` API filter;\n- `independent_missing_events` uses a source-neutral consumer-AI /\n  major-technology / policy sweep inside an `apnews.com` + `ap.org` API filter\n  after seeing the current candidate pool.\n\nThese are ranking routes, not a candidate whitelist. A stronger official primary\nsource or other authoritative source may still be the final source of a\ncandidate. The remaining Primary directions stay broad.'''
new = '''High-signal routing stays source-diverse without increasing the 12-search\nbudget:\n\n- `global_breaking` is a source-neutral broad current-AI catch-all without an API\n  domain filter;\n- `major_agencies` is an additional date-free `bloomberg.com` + `ft.com` sweep;\n- `independent_missing_events` is a source-neutral broad missing-events sweep\n  after seeing the current candidate pool.\n\nThese are ranking routes, not a candidate whitelist. A stronger official primary\nsource or other authoritative source may still be the final source of a\ncandidate. All non-`major_agencies` Primary directions remain without API domain\nfilters.'''
if old not in text:
    raise SystemExit('AGENTS obsolete routing block not found')
p.write_text(text.replace(old, new, 1), encoding='utf-8')

# Root README: repair the operator-facing mechanics rather than appending a contradictory note.
p = Path('README.md')
text = p.read_text(encoding='utf-8')
start = text.index('6. `major_agencies`')
end = text.index('\n7. Китай/Азия', start)
block = '''6. Broad safety nets `global_breaking` и `independent_missing_events` работают\n   без API domain filter. `major_agencies` остаётся дополнительным high-signal\n   проходом только по `bloomberg.com` + `ft.com`. Фактический query во всех\n   Primary-направлениях должен быть короткой date-free natural-language фразой\n   с relative-freshness cue (`latest`/`recent`/`current`/`breaking`). Календарные\n   даты, годы, названия месяцев, `after:`/`before:`, длинные Boolean `OR`-цепочки,\n   скобки и огромные списки компаний в query запрещены. Полное effective window\n   остаётся строгой post-retrieval границей допустимости кандидата; `latest` сам\n   по себе не считается доказательством свежести.''' 
text = text[:start] + block + text[end:]
p.write_text(text, encoding='utf-8')

# Automation README: replace the still-dated retrieval explanation and old route map.
p = Path('automation/README.md')
text = p.read_text(encoding='utf-8')
old = '''Effective window теперь имеет две разные роли. Первые 24 часа от effective start\nдо continuity anchor являются **healing overlap**. Основной continuity-период\nидёт от anchor до текущего cutoff. Полное effective window остаётся допустимой\nграницей кандидатов, но search query в Primary, Hybrid и Coverage должен прежде\nвсего ранжировать основной continuity-период, чтобы overlap не забивал свежую\nвыдачу предыдущими сутками.\n\nPrompt каждого Primary pass получает точные границы effective window.\n**Фактическая поисковая строка должна быть коротким natural-language query с\nкалендарными датами основного continuity-периода после healing overlap**, без\n`after:`/`before:`, длинных Boolean `OR`-цепочек, скобок и перечней из десятков\nкомпаний. Для `major_agencies` достаточно source-neutral компактного AI/date\nquery, потому что Reuters/AP/Bloomberg/FT уже ограничены API domain filter.\nФинальная свежесть всё равно проверяется по фактической дате/timestamp источника\nотносительно полного сохранённого effective window.\n\nHigh-signal source routing не дублирует один издатель в нескольких broad slots:\n`global_breaking` использует source-neutral funding/acquisition/M&A/major\nbusiness query внутри `reuters.com` filter; `major_agencies` использует\nsource-neutral major-AI query внутри `bloomberg.com` + `ft.com` filter;\n`independent_missing_events` выполняет source-neutral consumer/major-technology/\npolicy sweep внутри `apnews.com` + `ap.org` filter. Это независимые\nranking-шансы, а не whitelist кандидатов или региональная/издательская квота.\nОстальные Primary directions по-прежнему ищут широко.'''
new = '''Effective window имеет две роли. Первые 24 часа от effective start до continuity\nanchor являются **healing overlap**, а весь window остаётся допустимой границей\nкандидатов. Но Web Search ranking больше не пытается кодировать эти границы\nкалендарными датами. Primary, Hybrid и Coverage используют короткие date-free\nrelative-freshness queries (`latest`/`recent`/`current`/`breaking`), после чего\nфактическая дата/timestamp источника строго валидируется против полного effective\nwindow. Так overlap остаётся доступен для healing, а слово `latest` не получает\nложный статус редакционного фильтра.\n\nBroad safety nets `global_breaking` и `independent_missing_events` не имеют API\ndomain filter. `major_agencies` остаётся отдельным дополнительным sweep по\n`bloomberg.com` + `ft.com`. Это ranking-шансы, а не whitelist кандидатов или\nиздательская квота; остальные Primary directions также остаются широкими.'''
if old not in text:
    raise SystemExit('automation README dated routing block not found')
p.write_text(text.replace(old, new, 1), encoding='utf-8')

# Rewrite the old continuity/date-oriented regression test to the new tested contract.
Path('automation/tests/test_fresh_source_routing_contract.py').write_text('''from __future__ import annotations\n\nimport sys\nimport unittest\nfrom pathlib import Path\n\nAUTOMATION = Path(__file__).resolve().parents[1]\nSCRIPTS = AUTOMATION / "scripts"\nsys.path.insert(0, str(SCRIPTS))\n\nimport hybrid_search_completeness as hybrid  # noqa: E402\n\n\nclass FreshSourceRoutingContractTests(unittest.TestCase):\n    def test_primary_prompt_is_date_free_and_keeps_broad_safety_nets(self) -> None:\n        text = (AUTOMATION / "prompts" / "primary_recall_pass.md").read_text(encoding="utf-8")\n        self.assertIn("healing overlap", text)\n        self.assertIn("latest", text)\n        self.assertIn("календарные даты, годы, названия", text)\n        self.assertIn("source-neutral broad discovery", text)\n        self.assertIn("`bloomberg.com` + `ft.com`", text)\n        self.assertIn("source-neutral адаптивным last-mile", text)\n\n    def test_coverage_prompt_is_date_free_but_window_strict(self) -> None:\n        text = (AUTOMATION / "prompts" / "coverage_audit.md").read_text(encoding="utf-8")\n        self.assertIn("healing overlap", text)\n        self.assertIn("после retrieval", text)\n        self.assertIn("`latest`, `recent`, `current`, `breaking`", text)\n        self.assertIn("source-neutral запрос", text)\n        self.assertIn("Reuters/AP/Bloomberg/Financial Times", text)\n\n    def test_hybrid_time_hint_keeps_exact_window_only_for_validation(self) -> None:\n        hint = hybrid._time_hint({\n            "start_at": "2026-08-12T02:58:08+03:00",\n            "end_at": "2026-08-14T02:58:31+03:00",\n        })\n        self.assertIn("2026-08-12T02:58:08+03:00", hint)\n        self.assertIn("2026-08-14T02:58:31+03:00", hint)\n        self.assertIn("date-free", hint)\n        self.assertIn("latest / recent / current / breaking", hint)\n        self.assertIn("строго проверяй", hint)\n\n\nif __name__ == "__main__":\n    unittest.main()\n''', encoding='utf-8')

# Fail fast if the maintained docs still claim the removed publisher locks or dated search-query contract.
checks = {
    'AGENTS.md': ['inside a `reuters.com` API filter', 'inside an `apnews.com` + `ap.org` API filter'],
    'README.md': ['`global_breaking` использует source-neutral funding/M&A/business query внутри', 'Reuters, AP, Bloomberg и Financial Times'],
    'automation/README.md': ['календарными датами основного continuity-периода', 'business query внутри `reuters.com` filter'],
}
for path, forbidden in checks.items():
    value = Path(path).read_text(encoding='utf-8')
    for phrase in forbidden:
        if phrase in value:
            raise SystemExit(f'{path}: stale retrieval contract remains: {phrase}')

Path('.github/_tmp_finish_relative_freshness.py').unlink()
