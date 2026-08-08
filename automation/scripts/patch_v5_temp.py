from pathlib import Path

path = Path('automation/scripts/ensure_story_coverage.py')
text = path.read_text(encoding='utf-8')
text = text.replace('RECALL_SENTINEL_VERSION = 4', 'RECALL_SENTINEL_VERSION = 5', 1)
text = text.replace('RECALL_SENTINEL_DOMAINS: tuple[str, ...] = ("reuters.com",)', 'RECALL_SENTINEL_DOMAINS: tuple[str, ...] = ()', 1)
text = text.replace('required_query = f"OpenAI cybersecurity {query_date}"', 'required_query = f"OpenAI cybersecurity Reuters {query_date}"', 1)
text = text.replace('API уже ограничивает поиск доменом Reuters.\n', 'API-доменный фильтр намеренно отключён после подтверждённого случая, когда Reuters-only filter возвращал пустую выдачу. Reuters фиксируется прямо в коротком запросе.\n', 1)
text = text.replace('Reuters OpenAI security recall sentinel v4', 'Reuters unfiltered OpenAI recall sentinel v5')
path.write_text(text, encoding='utf-8')

test = Path('automation/tests/test_recall_sentinel.py')
t = test.read_text(encoding='utf-8')
t = t.replace('Reuters OpenAI security recall sentinel v4', 'Reuters unfiltered OpenAI recall sentinel v5')
t = t.replace('tuple(kwargs["allowed_domains"]), ("reuters.com",)', 'tuple(kwargs["allowed_domains"]), ()', 1)
t = t.replace('"OpenAI cybersecurity August 7 2026",', '"OpenAI cybersecurity Reuters August 7 2026",', 1)
t = t.replace('"checked by v4"', '"checked by v5"')
test.write_text(t, encoding='utf-8')

note='''\n\n### Retrieval note: recall sentinel v5\n\nВерсия 5 сохраняет один седьмой search operation, но отключает API domain filter, потому что production v4 выполнил точный `OpenAI cybersecurity August 7 2026` с `allowed_domains=[reuters.com]` и получил пустой список источников. Запрос теперь `OpenAI cybersecurity Reuters <UTC date>`; Reuters задаётся текстом запроса, а не фильтром провайдера. Zero-pool artifact старой версии возобновляется только для этого одного поиска.\n'''
for name in ('README.md','automation/README.md'):
    p=Path(name); d=p.read_text(encoding='utf-8')
    d=d.replace('версии 4','версии 5').replace('sentinel v4','sentinel v5').replace('sentinel версии 4','sentinel версии 5').replace('`recall_sentinel_version: 4`','`recall_sentinel_version: 5`')
    d=d.replace('API-фильтром `reuters.com`','без API domain filter, с Reuters в тексте короткого запроса')
    if '### Retrieval note: recall sentinel v5' not in d: d += note
    p.write_text(d,encoding='utf-8')
