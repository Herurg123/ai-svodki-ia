from pathlib import Path

path = Path('automation/scripts/ensure_story_coverage.py')
text = path.read_text(encoding='utf-8')
text = text.replace('RECALL_SENTINEL_VERSION = 3', 'RECALL_SENTINEL_VERSION = 4', 1)
text = text.replace(
    'required_query = f"artificial intelligence {query_date} cybersecurity model"',
    'required_query = f"OpenAI cybersecurity {query_date}"',
    1,
)
text = text.replace(
    'Ты — финальный Reuters security recall sentinel редакции «ИИ-сводки».',
    'Ты — финальный Reuters OpenAI security recall sentinel редакции «ИИ-сводки».',
    1,
)
text = text.replace(
    'Это намеренно короткий safety/security probe. Production-регрессия показала,\nчто перечисление множества компаний, классов событий и издателей превращает\nпоиск в чрезмерно узкую конъюнкцию и может дать ноль результатов даже при\nналичии свежей Reuters-новости. После поиска открой все релевантные свежие\nReuters-страницы из результатов и проверь их против строгого окна.',
    'Это намеренно адресный safety/security probe для подтверждённого класса\nпропусков вокруг OpenAI. Production-регрессия показала, что и широкий Reuters\nзапрос, и общий security-запрос могут возвращать пустую выдачу, тогда как\nкороткий запрос по организации и теме поднимает свежий Reuters-материал. После\nпоиска открой все релевантные свежие Reuters-страницы из результатов и проверь\nих против строгого окна.',
    1,
)
text = text.replace(
    'Reuters security recall sentinel v3',
    'Reuters OpenAI security recall sentinel v4',
)
path.write_text(text, encoding='utf-8')

test = Path('automation/tests/test_recall_sentinel.py')
t = test.read_text(encoding='utf-8')
t = t.replace(
    'Reuters security recall sentinel v3',
    'Reuters OpenAI security recall sentinel v4',
)
t = t.replace(
    '"artificial intelligence August 7 2026 cybersecurity model",',
    '"OpenAI cybersecurity August 7 2026",',
    1,
)
t = t.replace('"checked by v3"', '"checked by v4"')
test.write_text(t, encoding='utf-8')

note = '''\n\n### Retrieval note: recall sentinel v4\n\nДля подтверждённого zero-pool security regression версия 4 использует один Reuters-only запрос `OpenAI cybersecurity <UTC date>`. Дата берётся из UTC-даты конца редакционного окна. Такой запрос намеренно адресный: предыдущая версия с общими словами `artificial intelligence ... cybersecurity model` завершалась технически успешно, но встроенный Web Search возвращал пустую выдачу, тогда как контрольный поиск `OpenAI cybersecurity <date>` находит нужный свежий Reuters-материал. Версия хранится в artifact; zero-pool artifact старой версии возобновляется только для этого одного седьмого поиска.\n'''
for name in ('README.md', 'automation/README.md'):
    p = Path(name)
    d = p.read_text(encoding='utf-8')
    d = d.replace('версии 3', 'версии 4')
    d = d.replace('sentinel v3', 'sentinel v4')
    d = d.replace('sentinel версии 3', 'sentinel версии 4')
    d = d.replace('`recall_sentinel_version: 3`', '`recall_sentinel_version: 4`')
    if '### Retrieval note: recall sentinel v4' not in d:
        d += note
    p.write_text(d, encoding='utf-8')
