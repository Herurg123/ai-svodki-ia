from pathlib import Path

workflow = Path('.github/workflows/daily-production.yml')
text = workflow.read_text(encoding='utf-8')
old = '''          temporal_anchor_current = (
              data.get("temporal_anchor_version") == 1
              and (data.get("recall_sentinel") or {}).get("version") == 8
          )
          terminal = (
              temporal_anchor_current
              and data.get("status") in {"error", "editorial_stop"}
'''
new = '''          temporal_anchor_current = (
              data.get("temporal_anchor_version") == 1
              and (data.get("recall_sentinel") or {}).get("version") == 8
          )
          retrieval_quality_current = (
              data.get("retrieval_quality_contract_version") == 1
              and isinstance(data.get("retrieval_quality"), dict)
              and data["retrieval_quality"].get("status") == "complete"
          )
          terminal = (
              temporal_anchor_current
              and retrieval_quality_current
              and data.get("status") in {"error", "editorial_stop"}
'''
if old not in text:
    raise SystemExit('terminal reuse contract anchor not found')
text = text.replace(old, new, 1)
old_import = 'from ensure_story_coverage_runtime_base import completed_prior_audit\n                      prior_complete = completed_prior_audit(prior)'
new_import = 'from ensure_story_coverage import completed_quality_audit\n                      prior_complete = completed_quality_audit(prior)'
if old_import not in text:
    raise SystemExit('coverage recovery import anchor not found')
workflow.write_text(text.replace(old_import, new_import, 1), encoding='utf-8')

validator = Path('automation/scripts/validate_production_daily_contract.py')
vtext = validator.read_text(encoding='utf-8')
anchor = '        ("bounded audit searches", "--maximum-audit-web-search-calls 7"),\n'
addition = anchor + '''        ("retrieval quality terminal reuse", "retrieval_quality_contract_version"),
        (
            "retrieval quality full recovery gate",
            "from ensure_story_coverage import completed_quality_audit",
        ),
'''
if '"retrieval quality terminal reuse"' not in vtext:
    if anchor not in vtext:
        raise SystemExit('validator coverage anchor not found')
    validator.write_text(vtext.replace(anchor, addition, 1), encoding='utf-8')

section = '''\n\n## Retrieval Quality v1: unresolved-сигналы и региональная полнота\n\nС 2026-08-16 production сохраняет важный `unverified` след из Primary Recall как отдельный `unresolved_signal`, вместо того чтобы безвозвратно оставлять его в обычных rejections. Сигнал становится обязательным для targeted resolution только при строгом high-signal пороге; слабый `unverified` остаётся диагностикой и не блокирует выпуск.\n\n`entities`, `anchors` и `source_hint` являются только evidence для построения короткого запроса. Это **не** company whitelist, не обязательный AND-набор и не publisher whitelist. Resolution выполняет один source-neutral Web Search без API domain filter и может подтвердить событие любым авторитетным первичным или вторичным источником. Reuters остаётся одним из возможных источников, а не центром поисковой архитектуры.\n\nЕсли Primary Recall технически завершил оба China/Asia-направления или Russia-направление с нулём принятых кандидатов, существующий optional 4-й Hybrid slot превращается в региональный recall-health check. Ноль после такой проверки допустим: это контроль достаточности поиска, **не квота на публикацию** и не требование искусственно добавлять российскую или азиатскую историю.\n\nAdaptive приоритет сохраняет стоимость: mandatory Coverage retry имеет приоритет над unresolved resolution; затем при отсутствии unresolved-сигнала работают прежние fresh-agency rescue / zero-pool sentinel. Максимум не меняется: **12 Primary + до 4 Hybrid + до 7 Coverage = 23 Web Search operations на выпуск**.\n\n`retrieval_quality_contract_version=1` участвует в same-day recovery. Старый modern artifact без завершённого Retrieval Quality v1 не считается terminal-quality-complete: уже оплаченные валидные mandatory-проходы переиспользуются, но свободный quality-slot должен быть выполнен по новой семантике. Live Terra smoke используется как диагностическая pre-release проверка; наличие конкретной Reuters URL по-прежнему не является детерминированным CI-gate из-за недетерминированного ранжирования поиска.\n'''
for name in ('README.md', 'automation/README.md'):
    path = Path(name)
    body = path.read_text(encoding='utf-8')
    if '## Retrieval Quality v1: unresolved-сигналы и региональная полнота' not in body:
        path.write_text(body.rstrip() + section + '\n', encoding='utf-8')

agents = Path('AGENTS.md')
body = agents.read_text(encoding='utf-8')
agent_section = '''\n\n## Retrieval Quality v1\n\n- Не терять потенциально крупный `unverified` discovery: сохранять его в `unresolved_signals`; обязательный resolver разрешён только для strict high-signal evidence, слабые сигналы не блокируют выпуск.\n- `entities`, `anchors`, `source_hint` являются hints/evidence, а не обязательными поисковыми фильтрами. Запрещено превращать их в company whitelist, publisher whitelist или длинный AND-query.\n- Targeted unresolved resolution использует только существующий 7-й Coverage slot, source-neutral Web Search и не увеличивает Coverage budget выше 7.\n- Приоритет 7-го Coverage slot: сначала обязательный technical retry; затем high-signal unresolved resolution; если unresolved нет, действуют существующие fresh-agency rescue / zero-pool sentinel правила.\n- Russia/Asia zero-result проверяется как completeness-health через существующий optional 4-й Hybrid slot. Это не региональная story quota: отсутствие достойной новости после достаточного поиска является допустимым результатом.\n- Общий production search ceiling остаётся 23: 12 Primary + до 4 Hybrid + до 7 Coverage.\n- Modern same-day recovery обязан учитывать `retrieval_quality_contract_version=1`; старый artifact не может обойти новую quality-стадию. Переиспользовать уже оплаченные валидные mandatory-проходы, а не повторять их без необходимости.\n- Live Terra smoke применять как диагностическую проверку query architecture. Не требовать конкретную live Reuters/AP/Bloomberg/FT URL в deterministic CI.\n'''
if '## Retrieval Quality v1\n' not in body:
    agents.write_text(body.rstrip() + agent_section + '\n', encoding='utf-8')

test = Path('automation/tests/test_retrieval_quality_workflow_contract.py')
test.write_text('''from pathlib import Path\n\n\ndef test_workflow_requires_current_retrieval_quality_for_terminal_reuse():\n    text = Path(".github/workflows/daily-production.yml").read_text(encoding="utf-8")\n    assert 'data.get("retrieval_quality_contract_version") == 1' in text\n    assert 'data["retrieval_quality"].get("status") == "complete"' in text\n    assert "and retrieval_quality_current" in text\n\n\ndef test_workflow_uses_strict_quality_gate_for_full_recovery():\n    text = Path(".github/workflows/daily-production.yml").read_text(encoding="utf-8")\n    assert "from ensure_story_coverage import completed_quality_audit" in text\n    assert "prior_complete = completed_quality_audit(prior)" in text\n\n\ndef test_documented_search_ceiling_remains_23():\n    for path in (Path("README.md"), Path("automation/README.md"), Path("AGENTS.md")):\n        text = path.read_text(encoding="utf-8")\n        assert "23" in text\n        assert "Retrieval Quality v1" in text\n''', encoding='utf-8')
