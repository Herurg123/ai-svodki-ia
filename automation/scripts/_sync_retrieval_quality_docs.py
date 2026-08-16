from pathlib import Path

section = '''

## Retrieval Quality v1: unresolved-сигналы и региональная полнота

С 2026-08-16 production сохраняет важный `unverified` след из Primary Recall как отдельный `unresolved_signal`, вместо того чтобы безвозвратно оставлять его в обычных rejections. Targeted resolution обязателен только для strict high-signal evidence; слабый `unverified` остаётся диагностикой и сам по себе не блокирует выпуск.

`entities`, `anchors` и `source_hint` являются только evidence для построения короткого запроса. Это **не** company whitelist, не обязательный AND-набор и не publisher whitelist. Resolution выполняет один source-neutral Web Search без API domain filter и может подтвердить событие любым авторитетным первичным или вторичным источником. Reuters остаётся одним из возможных источников, а не центром поисковой архитектуры.

Если Primary Recall технически завершил China/Asia- или Russia-направление с нулём принятых кандидатов, существующий optional 4-й Hybrid slot может стать региональным recall-health check. Ноль после такой проверки допустим: это контроль достаточности поиска, **не квота на публикацию** и не требование искусственно добавлять российскую или азиатскую историю.

Adaptive-приоритет сохраняет стоимость: mandatory Coverage retry имеет приоритет над unresolved resolution; при отсутствии unresolved-сигнала действуют прежние fresh-agency rescue / zero-pool sentinel. Максимум не меняется: **12 Primary + до 4 Hybrid + до 7 Coverage = 23 Web Search operations на выпуск**.

`retrieval_quality_contract_version=1` участвует в recovery. Modern full artifact без завершённого Retrieval Quality v1 понижается до partial editorial recovery: уже оплаченные валидные mandatory-проходы переиспользуются, а свободный quality-slot выполняется по новой семантике. Legacy zero-pool terminal artifact старого контракта не используется между разными датами выпуска, потому что recovery выбирается строго по `daily-production-YYYY-MM-DD`. Live Terra smoke остаётся диагностической pre-release проверкой; наличие конкретной Reuters URL не является детерминированным CI-gate из-за недетерминированного ранжирования поиска.
'''

for name in ('README.md', 'automation/README.md'):
    path = Path(name)
    body = path.read_text(encoding='utf-8')
    marker = '## Retrieval Quality v1: unresolved-сигналы и региональная полнота'
    if marker not in body:
        path.write_text(body.rstrip() + section.rstrip() + '\n', encoding='utf-8')

agents = Path('AGENTS.md')
body = agents.read_text(encoding='utf-8')
agent_section = '''

## Retrieval Quality v1

- Не терять потенциально крупный `unverified` discovery: сохранять его в `unresolved_signals`; обязательный resolver разрешён только для strict high-signal evidence, слабые сигналы не блокируют выпуск.
- `entities`, `anchors`, `source_hint` являются hints/evidence, а не обязательными поисковыми фильтрами. Запрещено превращать их в company whitelist, publisher whitelist или длинный AND-query.
- Targeted unresolved resolution использует только существующий 7-й Coverage slot, source-neutral Web Search и не увеличивает Coverage budget выше 7.
- Приоритет adaptive Coverage slot: сначала обязательный technical retry; затем high-signal unresolved resolution; если unresolved нет, действуют существующие fresh-agency rescue / zero-pool sentinel правила.
- Russia/Asia zero-result проверяется как completeness-health через существующий optional 4-й Hybrid slot. Это не региональная story quota: отсутствие достойной новости после достаточного поиска является допустимым результатом.
- Общий production search ceiling остаётся 23: 12 Primary + до 4 Hybrid + до 7 Coverage.
- Modern full recovery без `retrieval_quality_contract_version=1` понижать до partial editorial recovery: переиспользовать уже оплаченные валидные mandatory-проходы и выполнить отсутствующий quality-slot, а не повторять весь research.
- Recovery artifacts привязаны к точной дате `daily-production-YYYY-MM-DD`; не переносить terminal/research artifacts между календарными выпусками.
- Live Terra smoke применять как диагностическую проверку query architecture. Не требовать конкретную live Reuters/AP/Bloomberg/FT URL в deterministic CI.
'''
if '## Retrieval Quality v1\n' not in body:
    agents.write_text(body.rstrip() + agent_section.rstrip() + '\n', encoding='utf-8')
