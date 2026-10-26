# Sol API: эксперимент на выпуске 22 октября 2026 года

**Состояние:** первоначальный paid run аварийно прервался; затем пять оставшихся
Primary-запросов успешно выполнены в Actions run 39748548566, семь старых
ответов переиспользованы. Оплачиваемый одноразовый job удалён.
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

## Исходный результат и повторный запуск

- Manual Main CI: https://github.com/Herurg123/ai-svodki-ia/actions/runs/39748548566
- Saved result artifact: 12412378520, 12/12 Primary, five new API calls, seven replay.
- Artifact ZIP SHA-256: 82585fff3216e5375e8333569e56276204185b0fd73d3af10905ada7fd9a50a6.
- Оценка пяти новых API-вызовов по справочному Standard: $0.587131; консервативный guard $0.7056275. Реальную стоимость определить по биллингу, эти числа не invoice.
- После success временный оплачиваемый job удалён из CI. Не повторять старый run и не использовать локальный --paid без отдельного решения.
- Аналитические выводы: [RESULT.md](RESULT.md).

## Офлайн-сопоставление Terra/Sol после Primary 12/12

Инструмент `compare_primary.py` принимает два отчёта
`primary-recall.json` и выдаёт JSON-статус и CSV для ручной
проверки по событию:

```bash
python automation/audits/experiments/2026-10-22-sol-api-shadow/compare_primary.py \
  --terra automation/content/2026-10-22/primary-recall.json \
  --sol automation/preview/production-daily/primary-recall-2026-10-22.json \
  --output-prefix automation/preview/sol-shadow-2026-10-22/ab-review
```

Скрипт **останавливается с ненулевым кодом** до 12/12 по обоим
направлениям. Совпадение URL отмечает только совпадение *источника*, а не
события; URL двух разных публикаций одного события требует ручной
event-identity adjudication. Никаких победителей по сырому числу URL.

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

Два следующих синхронных контрольных выпуска ещё не запускались.
Новый экспериментальный API-расход требует отдельного согласия и безопасного
одноразового workflow, который отсутствует после очистки.
