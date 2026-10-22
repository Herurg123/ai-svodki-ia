# Sol API: эксперимент на выпуске 22 октября 2026 года

**Состояние:** старая платная попытка аварийно прервана; семь ответов сохранены.
`main` и семь штатных GitHub Actions workflows не меняем. Экспериментальный
[PR #213](https://github.com/Herurg123/ai-svodki-ia/pull/213) — **draft**, не сливать.

## Факты и первичные доказательства

- Production Terra: [run 39706110827](https://github.com/Herurg123/ai-svodki-ia/actions/runs/39706110827).
- Неудавшийся Sol: [run 39726774610](https://github.com/Herurg123/ai-svodki-ia/actions/runs/39726774610), artifact `12402559662`.
- Полный сохранённый ZIP имеет SHA-256
  `ada53d88eadb3aac9e2508d1a04a5e8b5eb7ed72d1e9aa391a87e336f92a3cc3`.
- Frozen archive до ночного релиза: SHA-256
  `ef01085d0ef74dd2f0b80a5c1ba89dd99d8dafc85c25e8ac5fa4c3ea3a4a4568`.
- Семь завершённых Primary responses: 6 сырых, 5 принятых кандидатов,
  21 модельное отклонение; 7 поисков, 21 navigation, 7 сохранённых usage.
- Восьмой ответ уже был обработан API, но response/usage не зафиксированы:
  нельзя объявлять его нулевым расходом либо восстанавливать задним числом.
- `gpt-6.1-sol / medium` фактически запрашивался через SDK, но результаты
  относятся только к Search/Primary, не к готовой публикации.

## Что исправлено в коде PR

- `web_search_call.action.type=search` считается платным поиском.
  `open_page` и `find_in_page` не потребляют search-операцию.
- Сохранение usage/response id происходит **до** проверок лимита.
- `load_frozen_replay` требует исходный ZIP, совпадение модели, окна,
  frozen archive, семи направлений и usable response usage.
- `build_replay_runner` не платит повторно за 7 сохранённых ответов.
- `--offline-verify` использует исходный архив и реальный
  `primary_recall_search.run_primary_recall_matrix`: семь сохранённых и
  **пять только имитированных** ответов, без API.
- Последующее выполнение `--paid` при отдельном разрешении запускает
  только Primary 12/12: семь replay + пять новых запросов; Editorial,
  Hybrid, Coverage, image/FTP/commit не запускаются.
- SDK retries = 0. В бюджете 1 USD используется client-side оценка,
  которая не является жёстким биллинговым пределом провайдера.
- Запуск без `--paid` и
  `SOL_SHADOW_OWNER_APPROVAL_USD=1.00` завершается с ошибкой **до API**.

## Безопасная последовательность оператора

1. Скачайте original artifact `12402559662` из GitHub Actions и
   сохраните как ZIP, не перепаковывая оригинальные JSON.
2. На отдельной временной копии ветки #213 установите Python 3.12,
   `openai==2.45.0`. Секрет `OPENAI_API_KEY` задаётся **локально/в
   защищённом окружении**, ни в issue, ни в PR, ни в чат не вставляется.
3. `SOL_SHADOW_REPLAY_ARTIFACT=/path/to/original.zip
   python automation/audits/experiments/2026-10-22-sol-api-shadow/run_shadow.py --offline-verify`
   (Linux/macOS; в PowerShell задайте переменную `$env:...`).
   Результат: `offline_pass`, 7 replay, 5 mocked, 0 paid.
4. Не выполнять `--paid`, пока не проверен реальный offline replay и не
   согласованы новая попытка/лимит. Никакой штатный workflow не должен
   запускать платный Sol автоматически.
5. После отдельного разрешения, в изолированном рабочем окружении, задайте
   `SOL_SHADOW_OWNER_APPROVAL_USD=1.00`, `SOL_SHADOW_REPLAY_ARTIFACT`,
   `OPENAI_API_KEY` и выполните `run_shadow.py --paid` ровно один раз.
   При частичной ошибке сохранить `automation/preview/sol-shadow-2026-10-22`,
   не повторять весь запуск.
6. Только после Primary 12/12 сравнить события Terra/Sol по event origin,
   значимости, достоверности, потере кандидатов на схеме/merge и архивной
   уникальности. Не объявлять победителя по числу сырых ссылок.

## Два контрольных выпуска после октябрьского replay

Для 23 и 24 октября требуется **новая зафиксированная база**: ровно один
production Terra research/run на дату, снимок pre-publication archive, identical
cutoff и prompt/candidate schema, Sol Primary без публикации и сохранённый
original artifact каждой модели. Для честного сравнения запускать Sol близко к
Terra во времени. В обоих днях проверять ошибочную свежесть и category schema
отдельно от качества модели.

Критерий решения фиксируется **до запуска**: если Sol даст лучший
recall подтверждённых и значимых уникальных событий в двух из трёх
контрольных выпусков, без сопоставимых значимых потерь Terra и без ухудшения
точности и стабильности, Sol — кандидат на замену. При примерно равном
результате оставляем Terra, при дополняемости — испытываем ограниченный
Sol catch-up вместо полной миграции.

Продолжение оплачиваемых запусков требует отдельного явного согласия на расходы
и рабочего безопасного dispatch. Подключённый GitHub connector не предоставляет
метод workflow_dispatch; изменение canonical Main CI ради платного job запрещено
тестами `test_workflow_hygiene`. Поэтому ни один автоматический платный прогон
не заложен в этот PR. `workflow.DISABLED.yml` — исторический неактивный
шаблон, а не запускаемый GitHub Action.
