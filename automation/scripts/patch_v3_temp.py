from pathlib import Path
import textwrap

path = Path('automation/scripts/ensure_story_coverage.py')
text = path.read_text(encoding='utf-8')
if 'from datetime import datetime, timezone\n' not in text:
    text = text.replace(
        'from pathlib import Path\n',
        'from datetime import datetime, timezone\nfrom pathlib import Path\n',
        1,
    )
text = text.replace('RECALL_SENTINEL_VERSION = 2', 'RECALL_SENTINEL_VERSION = 3', 1)

start = text.index('def build_recall_sentinel_prompt(')
end = text.index('\n\ndef _existing_recall_sentinel', start)
replacement = textwrap.dedent(r'''\
def build_recall_sentinel_prompt(
    *,
    publication_date: str,
    search_window: dict[str, Any],
    existing_candidates: list[Any],
    archive: dict[str, Any],
) -> str:
    del publication_date
    existing = [
        {
            "title": item.get("title"),
            "organization": item.get("organization"),
            "primary_url": (
                item.get("primary_source", {}).get("url")
                if isinstance(item.get("primary_source"), dict)
                else None
            ),
        }
        for item in existing_candidates
        if isinstance(item, dict)
    ]
    recent_archive = _base._compact_recent_archive(archive)
    start_at = str(search_window.get("start_at") or "")
    end_at = str(search_window.get("end_at") or "")
    try:
        end_utc = datetime.fromisoformat(
            end_at.replace("Z", "+00:00")
        ).astimezone(timezone.utc)
        query_date = f"{end_utc.strftime('%B')} {end_utc.day} {end_utc.year}"
    except ValueError:
        query_date = str(search_window.get("start_date") or "")
    required_query = f"artificial intelligence {query_date} cybersecurity model"

    return f"""Ты — финальный Reuters security recall sentinel редакции «ИИ-сводки».

Строгое редакционное окно: {start_at} → {end_at}
Идентификатор направления: general_coverage_gaps
Версия sentinel: {RECALL_SENTINEL_VERSION}

Основной research и шесть обязательных coverage-проходов уже завершились, но
пригодный пул всё ещё равен нулю. API уже ограничивает поиск доменом Reuters.
Выполни РОВНО ОДИН Web Search. Не расширяй и не переписывай поисковую строку.
Фактический поисковый запрос должен быть точно:
`{required_query}`

Это намеренно короткий safety/security probe. Production-регрессия показала,
что перечисление множества компаний, классов событий и издателей превращает
поиск в чрезмерно узкую конъюнкцию и может дать ноль результатов даже при
наличии свежей Reuters-новости. После поиска открой все релевантные свежие
Reuters-страницы из результатов и проверь их против строгого окна.

Пригодны самостоятельные ИИ-события высокой новостной ценности, связанные с
cybersecurity, безопасностью frontier-моделей, sandbox escape, jailbreak,
несанкционированными действиями агентов, эксплуатацией уязвимостей или
существенным изменением защитных мер. Путь URL и рубрика Reuters не определяют
редакционную категорию: событие о киберриске остаётся `category=security`, даже
если URL расположен в `/legal/` или `/litigation/`. `legal` используй только
для реального суда, иска, copyright/scraping или регуляторно-правового события.

Событие и основной источник обязаны попадать в окно. Старую перепечатку без
нового развития отклоняй. Для include/consider нужны
`verification_status=verified` и `freshness_status` new_event/material_update.
Если точного времени публикации нет, ставь `published_at=null` и
`time_precision=date`; время не выдумывай. Не добивай количество слабым
материалом.

Уже найденные кандидаты:
{json.dumps(existing, ensure_ascii=False, indent=2)}

Недавний архив для дедупликации:
{json.dumps(recent_archive, ensure_ascii=False, indent=2)}

Если достойные события найдены, верни до 3 кандидатов по заданной JSON-схеме.
Если нет, верни пустой `candidates` и status=complete_with_gaps. `direction_id`
должен быть строго `general_coverage_gaps`. Верни только JSON по схеме."""
''')
text = text[:start] + replacement + text[end:]
text = text.replace(
    'Reuters high-signal recall sentinel v2',
    'Reuters security recall sentinel v3',
)
path.write_text(text, encoding='utf-8')

test = Path('automation/tests/test_recall_sentinel.py')
t = test.read_text(encoding='utf-8')
t = t.replace(
    'Reuters high-signal recall sentinel v2',
    'Reuters security recall sentinel v3',
)
old = '''            self.assertIn("РОВНО ОДИН Web Search", kwargs["prompt"])
            self.assertIn("без `site:`", kwargs["prompt"])
            self.assertIn("без `OR`", kwargs["prompt"])
            self.assertIn("Путь URL и рубрика Reuters не определяют", kwargs["prompt"])
'''
new = '''            self.assertIn("РОВНО ОДИН Web Search", kwargs["prompt"])
            self.assertIn(
                "artificial intelligence August 7 2026 cybersecurity model",
                kwargs["prompt"],
            )
            self.assertIn("Не расширяй и не переписывай", kwargs["prompt"])
            self.assertIn("Путь URL и рубрика Reuters не определяют", kwargs["prompt"])
'''
if old not in t:
    raise SystemExit('sentinel prompt assertions not found')
t = t.replace(old, new, 1)
t = t.replace(
    'test_stale_v1_sentinel_is_removed_and_budget_restored',
    'test_stale_sentinel_is_removed_and_budget_restored',
)
t = t.replace('"checked by v2"', '"checked by v3"')
test.write_text(t, encoding='utf-8')

note = textwrap.dedent('''

### Retrieval note: recall sentinel v3

Для нулевого пула версия 3 использует один короткий Reuters-only security-запрос вида `artificial intelligence <UTC date> cybersecurity model`. Дата берётся из UTC-даты конца редакционного окна. Это устраняет подтверждённый регрессионный случай, когда длинная строка с перечнем компаний и тем возвращала ноль результатов. Версия хранится в artifact; zero-pool artifact старой версии возобновляется только для этого одного седьмого поиска.
''')
for name in ('README.md', 'automation/README.md'):
    p = Path(name)
    d = p.read_text(encoding='utf-8')
    d = d.replace('версии 2', 'версии 3')
    d = d.replace('sentinel v2', 'sentinel v3')
    d = d.replace('sentinel версии 2', 'sentinel версии 3')
    d = d.replace('`recall_sentinel_version: 2`', '`recall_sentinel_version: 3`')
    if '### Retrieval note: recall sentinel v3' not in d:
        d += note
    p.write_text(d, encoding='utf-8')
