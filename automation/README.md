# Автоматизация ИИ-Сводок

Каталог содержит production-конвейер ежедневной публикации ИИ-Сводок. Главный
принцип текущей retrieval-архитектуры: **не заменять проверенный primary search,
а дополнять его небольшим независимым completeness-слоем**.

## Постоянный baseline старого поиска

Состояние проекта непосредственно перед включением hybrid completeness
сохранено как постоянная контрольная точка:

- branch: `archive/search-baseline-pre-hybrid-2026-08-09`;
- commit: `d926a3abf8b9443f58f303d984ef79fdc289fc3e`;
- manifest: `archive/search-baselines/2026-08-09-pre-hybrid.md`.

Commit SHA является канонической неизменяемой идентичностью старой механики.
Archive-ветка не используется для разработки, не должна перемещаться или
удаляться и отдельно защищена в `repository_hygiene_policy.py` классификацией
`protected / permanent_archive_branch`. Новые исторические точки создаются под
новыми именами, старые не переписываются.

## Основные каталоги

- `content/YYYY-MM-DD/` — структурированные материалы выпусков;
- `archive/index.json` — редакционный архив для дедупликации и определения
  material updates;
- `archive/search-baselines/` — manifests постоянных retrieval-baseline;
- `config/` — production-, editorial-, site- и image-конфигурация;
- `prompts/` — primary research, editorial и fallback coverage prompts;
- `specs/` — канонические редакционные и технические контракты;
- `scripts/` — production, recovery, hybrid completeness, cleanup и validators;
- `tests/` — офлайн-регрессии;
- `preview/` — временные результаты production/CI, в Git не входят;
- `recovery/` — временно восстановленные Actions artifacts, в Git не входят.

Исторические `content/YYYY-MM-DD/` старше 32 дней компактируются, но
`meta.json` и `stories.json` сохраняются для редакционной памяти. Та же
32-дневная граница применяется к публичным страницам и связанным картинкам.

## Workflow

В репозитории пять канонических Actions workflow:

- `ci.yml` — бесплатные офлайн-проверки;
- `daily-production.yml` — ежедневный research, hybrid completeness, editorial,
  fallback coverage, обложка, сборка и публикация;
- `repository-cleanup.yml` — 32-дневная очистка контента;
- `repository-hygiene.yml` — инженерная уборка безопасных GitHub-объектов;
- `deploy-posts.yml` — FTP-синхронизация точного состояния `posts/` выбранного
  commit.

Основной cron production: `23:17 UTC` предыдущего календарного дня, то есть
`02:17 Europe/Moscow` даты выпуска. Резервный внешний запуск остаётся в
cron-job.org. Gate до платных API проверяет, нужен ли новый выпуск, no-op или
только FTP-redeploy.

## Retrieval: primary + hybrid completeness

### 1. Primary research

Primary-механика **не изменена и не заменена**. Она по-прежнему ограничена 12
завершёнными Web Search operations и использует существующую последовательность
мирового discovery, агентств, Китай/Азия, Россия, тематических проходов и
условного last-mile. Ее artifacts остаются основной контрольной точкой для
сравнения с историческими выпусками.

`search_window.end_at` является авторитетным текущим временем. Системная дата
модели и UTC-дата среды исполнения не имеют права сдвигать редакционное окно.

### 2. Hybrid completeness v1

После **свежего** primary `run_digest_preview.py` запускает независимый
`hybrid_search_completeness.py`. Слой предназначен только для поиска крупных
пропусков и никогда не выкидывает primary-кандидаты.

Три фиксированных прохода выполняются всегда и получают ровно по одному Web
Search (`max_tool_calls=1`):

1. `models_products_research` — модели, продукты, агенты, coding, research,
   multimodal, robotics, open-weight/open-source;
2. `infrastructure_business` — чипы, HBM, дата-центры, облака, M&A,
   инвестиции, существенные enterprise/earnings события;
3. `safety_policy_regions` — safety/security, тестирование frontier-моделей,
   регулирование, крупные legal-события и значимые региональные пробелы.

После трёх проходов код считает тематическое покрытие объединённого
`primary + completeness` пула. Если целый кластер остаётся пуст, разрешается
один `adaptive_gap` Web Search по этим пробелам. Поэтому:

- обычный completeness-бюджет: **3 searches**;
- абсолютный hard cap: **4 searches**;
- значение выше 4 программно зажимается до 4;
- API domain filter отсутствует намеренно;
- `open_page`/`find_in_page` остаются диагностикой и не считаются search
  operation.

Широкий retrieval не означает слабую редакционную фильтрацию. Все NEW-only
кандидаты проходят существующие проверки окна, `verified`, freshness,
значимости, legal/curiosity правил, дедупликации и maximum candidate pool через
`story_coverage.merge_candidates`.

Если принят хотя бы один новый кандидат, создаётся объединённый research и
editorial повторяется на нём. Если новых пригодных кандидатов нет, старый
primary artifact остаётся без изменений.

### 3. Fail-open относительно старой механики

Hybrid completeness является дополнительным recall-слоем, поэтому его
техническая ошибка не должна уничтожать результат старого search.

- transport/validation failure completeness сохраняется как warning;
- перед editorial-rerun baseline artifact снимком сохраняется;
- если rerun на объединённом research падает, baseline primary artifact
  восстанавливается;
- invocation с `--research-input` не запускает hybrid повторно, поэтому
  editorial rerun и recovery не создают рекурсивную плату.

Это означает, что дополнительный слой может улучшить recall, но сам по себе не
должен сделать пригодный старый primary хуже.

### 4. Диагностика hybrid

Каждый запуск сохраняет:

- `preview/<DATE>/hybrid-completeness.json`;
- `preview/production-daily/hybrid-completeness-<DATE>.json`;
- при наличии принятых NEW-only кандидатов:
  `preview/production-daily/hybrid-completeness-merged-<DATE>.json`.

Report фиксирует версию стратегии, фактические запросы и источники каждого
прохода, completed search count, primary/final cluster counts, решение об
adaptive query, accepted/rejected candidates и факт необходимости editorial
rerun. Эти поля нужны для последующего сравнения качества и цены retrieval.

## Fallback coverage для короткого/нулевого пула

Существующий `ensure_story_coverage.py` не удаляется. Если после primary +
hybrid выпуск всё ещё не достигает обычной цели, запускается прежний усиленный
fallback: шесть обязательных одно-search направлений с общим потолком 7
операций, где седьмой слот резервируется для retry незавершённого направления.

Обязательные направления остаются:

1. `security_world`;
2. `security_russia`;
3. `security_asia`;
4. `legal_copyright_scraping`;
5. `curiosity`;
6. `general_coverage_gaps`.

Если все шесть завершены, но итоговый пригодный пул равен нулю, свободный
седьмой слот используется как recall sentinel v7. Его адресный запрос
`OpenAI cybersecurity <UTC date>` сохранён как последний regression-probe для
подтверждённого исторического класса security-пропусков. Sentinel работает без
API domain filter и не является основным completeness-механизмом.

Fallback по-прежнему fail-closed: технические `partial`, `budget_exhausted` и
`error` блокируют Image API, commit и deploy. Полностью завершённый поиск с
нулевым итоговым пулом становится зелёным `editorial_stop` без публикации.

## Поисковый бюджет

Потолки считаются по **завершённым search operations**, а не по навигационным
web tool items:

- primary: максимум 12;
- hybrid completeness: обычно 3, максимум 4;
- fallback coverage: максимум 7 и запускается только если итог после primary +
  hybrid остаётся коротким/нулевым.

Теоретический worst case составляет **23** search operations. Это не обычный
дневной расход: полный выпуск после primary + hybrid не запускает тяжёлый
fallback, а четвёртый hybrid search выполняется только при полностью пустом
тематическом кластере.

## Recovery

Recovery предпочитает наиболее полный artifact той же даты и не повторяет уже
оплаченные стадии без необходимости. В частности:

- готовый выпуск может быть только redeployed;
- готовый текст не требует повторного text API;
- fresh primary получает hybrid один раз;
- `--research-input` editorial rerun пропускает hybrid;
- сохранённый объединённый candidate pool и `hybrid-completeness.json` остаются
  частью production artifact;
- завершённый fallback audit и актуальный sentinel переиспользуются;
- partial fallback продолжает только незавершённые направления;
- доказанный zero-pool `editorial_stop` переиспользуется без новой оплаты.

## Редакционный контракт короткого выпуска

Канонические правила находятся в `specs/editorial-policy.md`:

- обычная цель — 7–12 сюжетов;
- для публикации достаточно одного достойного сюжета;
- числовых региональных квот нет;
- выпуск из 1–6 сюжетов получает пометку «Новостей сегодня меньше, чем обычно»;
- отсутствие достойных сюжетов после полностью завершённого обязательного
  поиска даёт no-publish, а не искусственное наполнение выпуска;
- legal требует масштаба `major`, высокой значимости и надёжного источника;
- curiosity необязателен и ограничен одним выбранным сюжетом;
- research source metadata не может произвольно переписываться editorial.

## Repository hygiene

`repository-hygiene.yml` запускается в `12:43 UTC` (`15:43 МСК`). Плановый
запуск применяет только доказуемо безопасные операции, ручной запуск по
умолчанию audit-only.

Постоянная ветка `archive/search-baseline-pre-hybrid-2026-08-09` является
исключением из обычного lifecycle веток и всегда защищена. Для остальных веток
действуют стандартные правила: последние merged PR защищаются максимум 7 дней,
stale closed-unmerged может удаляться после 14 дней только при неизменном HEAD,
ветки без доказуемой истории остаются `review_only`.

Production artifacts, CI artifacts, orphan workflows и их завершённые runs
обрабатываются по отдельным безопасным правилам, описанным в root `README.md` и
`AGENTS.md`. Tracked source files scanner только диагностирует и никогда не
удаляет автоматически.

## Локальная проверка

Основной бесплатный набор:

```bash
python -m compileall automation/scripts automation/tests
python -m unittest discover -s automation/tests -v
python automation/scripts/validate_editorial_contract.py
python automation/scripts/validate_archive.py
```

Main CI дополнительно проверяет production workflow contract, committed archive,
RSS, sitemap, Schema.org и отсутствие изменений защищённых путей. Точный
актуальный набор команд задаётся `.github/workflows/ci.yml`.
