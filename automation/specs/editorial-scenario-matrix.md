# Офлайн-матрица редакционных сценариев

Этот набор не меняет каноническую редакционную политику. Он закрепляет её текущие требования регрессионными проверками без сети и без OpenAI API.

Источник списка сценариев:

`automation/fixtures/editorial-scenarios/manifest.json`

Исполнитель:

`automation/scripts/validate_editorial_scenarios.py`

Отчёт:

`automation/preview/editorial-scenario-matrix.json`

Матрица проверяет обычный и короткий выпуск, нулевой выпуск, правила Meta, обновления, российский раздел, editorial_notes, diversity overrides, порядок кандидатов, антидубли и archive update, только процитированные источники, диапазоны абзацев и выводов, а также терминологию.

Ни один сценарий не пишет в `posts/`, не изменяет request-файлы, не обращается к сети и не использует OpenAI.
