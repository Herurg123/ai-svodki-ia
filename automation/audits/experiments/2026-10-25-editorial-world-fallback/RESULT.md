# Неоднозначная рубрика: World fallback вместо остановки выпуска

## Scope / boundary

Изменение только deterministic editorial layout после research, candidate-to-source mapping и semantic duplicate gate, но до итоговой проверки статьи. Primary, Terra, Coverage, Search budgets, time-window, Source/Event Freshness, архив, PR workflow, paid request journaling и публикационные защиты не меняются. Новых API вызовов **0**. Terra не использовалась: семантика поиска и запросов не затронута.

## Предложенное правило

- Надёжный ведущий China actor без противоречий -> Китай.
- `geography=russia` -> Россия, без override по вспомогательным названиям.
- Основной субъект неоднозначен, либо org/title дают противоречащие сигналы China/World, либо China-вендор присутствует лишь во второстепенной роли -> **World**, с предупреждением `article_html.section_fallback` в policy normalization и `section_fallback` в editorial notes; независимый `validate_article_policy` возвращает warning.
- Безопасно source-mapped, структурно корректные HTML story blocks целиком переносятся под нужный h2. При однозначной структуре отсутствующий обязательный World h2 вставляется.
- Ошибки ссылок/атрибуции, повторов, нарушений свежести и архива, повреждённого HTML, прочих публикационных требований сохраняют **fail-closed** поведение.

## Независимый read-only эксперимент с оригиналом 25.10

Использован исходный GitHub Actions archive `daily-production-2026-10-25-original.zip` из run 40149481587 (восстановлен в предыдущей задаче; исходный артефакт неизменён). Независимый standalone Python evaluator прочитал оригинальные `candidates.json` и `editorial-output-raw.json`. Результаты:

- Оригинальный файл: 7 selected / 7 h3, все в `Мировые лидеры ИИ`.
- `cand-002` (CyberCartel; Anthropic; xAI; Moonshot AI; Straiker) -> **World**, reason `asia_mentioned_without_clear_leading_actor`. Исходное размещение корректно, публикационный блок из-за China снят без изменения текста или источников.
- `cand-001,003,004,005,007,010` -> World без fallback. Лишних перенаправлений 0.
- Отдельные контроли на conflicting MiniMax/OpenAI, direct MiniMax release, Russia authoritative, clear world leading actor, incidental Qwen: 5/5 ожидаемых исходов.
- Это независимый тест принятия решения по исходным данным и управляемым контрольным случаям, **не** полный сетевой production replay. Проверка интеграции возложена на regression tests и PR Gate.

## Постоянные регрессии и инварианты

`automation/tests/test_editorial_policy.py`:
1. Incidental Moonshot -> World; warning есть, policy errors нет.
2. Leading MiniMax vs title-leading OpenAI -> World + warning + перенос целого HTML сюжета, source URLs сохранились, candidate identity однозначна.
3. Отсутствующий World заголовок при известной структуре -> автоматически восстанавливается без потери h3.
4. Надёжный China lead остаётся China; Russia geography не меняется на China из-за постороннего упоминания.
5. Повторная normalizer pass идемпотентна; цитаты и весь текст сохранены.

Существующие тесты: Oct21 semantic repeat / fixed hash reconciliation, semantic source mapping, event/source freshness, time boundaries, archive dedupe, region health, editorial recovery at-most-once, workflow budgets и publication validators. При неожиданной регрессии PR не сливать.

## Риски / архитектурная оценка

Fallback намеренно использует conservative leading-actor heuristics; при неполной или конфликтной атрибуции статья может оказаться в более широком World, чем в узком China. Это допустимый редакционный компромисс, потому что полнота и безопасность выпуска не зависят от рубрики. Критические gates не изменены. Warning доступен в сохранённой нормализации, редакционных заметках и result validator, что предотвращает скрытую деградацию классификации.

Чужой URL, неразрешённое сопоставление сюжета, повреждённый HTML или неподтверждённая свежесть не считаются ошибкой рубрики и остаются блокирующими. Нельзя менять только error -> warning в validators без ремонта исходного HTML/проверки candidate identity.

## Заключение

Локальная правка рубрикации не изменяет поисковую архитектуру, бюджеты и публикационные запреты. Для merge требуется green Required PR Gate на **последнем** commit PR. Merge разрешён владельцем в текущем запросе, но никаких production re-runs или платных расходов этот merge не включает.
