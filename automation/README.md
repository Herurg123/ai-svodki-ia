# Автоматизация ИИ-Сводок

Каталог содержит production-конвейер ежедневной публикации ИИ-Сводок. Главный
принцип текущей retrieval-архитектуры: **fresh primary сначала максимально
надёжно обнаруживает потенциально важные события, а строгая редакционная
фильтрация применяется после discovery**. Для этого 12-search primary budget
распределяется детерминированно между обязательными направлениями.

## Постоянный baseline старого поиска

Состояние проекта непосредственно перед включением hybrid completeness
сохранено как постоянная контрольная точка:

- branch: `archive/search-baseline-pre-hybrid-2026-08-09`;
- commit: `d926a3abf8b9443f58f303d984ef79fdc289fc3e`;
- manifest: `archive/search-baselines/2026-08-09-pre-hybrid.md`.

Commit SHA является канонической неизменяемой идентичностью старой механики.
Archive-ветка не используется для разработки, не должна перемещаться или
удаляться и отдельно защищена в `repository_hygiene_policy.py` классификацией
`protected / permanent_archive_branch`.

## Основные каталоги

- `content/YYYY-MM-DD/` — структурированные материалы выпусков;
- `archive/index.json` — редакционный архив для дедупликации и material updates;
- `archive/search-baselines/` — manifests постоянных retrieval-baseline;
- `config/` — production-, editorial-, site- и image-конфигурация;
- `prompts/primary_recall_pass.md` — активный prompt одного Primary Recall v2
  прохода;
- `prompts/research_candidates.md` — legacy monolithic primary prompt для
  истории/rollback, не активный путь свежего production;
- `prompts/` — также editorial и fallback coverage prompts;
- `fixtures/recall/` — исторические retrieval regression windows;
- `specs/` — канонические редакционные и технические контракты;
- `scripts/primary_recall_search.py` — deterministic primary orchestrator;
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
- `daily-production.yml` — ежедневный Primary Recall v2, hybrid completeness,
  editorial, fallback coverage, обложка, сборка и публикация;
- `repository-cleanup.yml` — 32-дневная очистка контента;
- `repository-hygiene.yml` — инженерная уборка безопасных GitHub-объектов;
- `deploy-posts.yml` — FTP-синхронизация точного состояния `posts/` выбранного
  commit.

Основной cron production: `23:17 UTC` предыдущего календарного дня, то есть
`02:17 Europe/Moscow` даты выпуска. Резервный внешний запуск остаётся в
cron-job.org. Gate до платных API проверяет, нужен ли новый выпуск, no-op или
только FTP-redeploy.

## Retrieval: Primary Recall v2 + hybrid completeness

### 1. Primary Recall v2

Fresh production больше не передаёт все 12 Web Search одному агентному вызову.
`run_digest_preview.py` запускает `primary_recall_search.py`, который выполняет
**ровно 12 обязательных one-search Responses calls**. Каждый получает
`max_tool_calls=1`, общий hard cap primary остаётся **12 Web Search**.

Фиксированная матрица:

1. `global_breaking` — широкий мировой discovery;
2. `major_agencies` — Reuters, AP, Bloomberg, FT и сопоставимые агентские
   сигналы;
3. `models_products_agents` — модели, продукты, агенты, research;
4. `infrastructure_chips_cloud` — чипы, дата-центры, cloud, energy, inference;
5. `business_investment_partnerships` — инвестиции, M&A, financing,
   партнёрства, enterprise;
6. `china_asia_models` — модели, релизы, open-weight, chips/cloud региона;
7. `china_asia_integrations` — продуктовые интеграции, deployment и
   партнёрства в Китае/Азии;
8. `russia` — российские компании, исследования, внедрения, инфраструктура,
   regulation/security;
9. `developer_tools` — coding agents, IDE, CLI и agentic development;
10. `security_safety` — инциденты, prompt injection, sandbox, red teaming,
    frontier evaluations;
11. `legal_regulation` — крупные legal/copyright/regulatory события;
12. `independent_missing_events` — независимый last-mile поиск крупных событий,
    которых нет в уже собранном пуле.

Окно начинается от фактического `search_cutoff_at` последнего успешно
опубликованного выпуска и заканчивается новым pre-research cutoff.
`search_window.end_at` является авторитетным текущим временем. Системная дата
модели и UTC-дата среды исполнения не имеют права сдвигать окно.

Primary использует **discovery-first** семантику. Потенциально значимое свежее
и проверяемое событие сохраняется как `consider`, если его финальная
редакционная значимость ещё не очевидна. Агрессивно отсекаются лишь очевидное
вне окна, старые перепечатки без update, не-ИИ материалы, слабые/непроверяемые
источники и явный шум. Затем все кандидаты проходят существующий
`story_coverage.merge_candidates`: окно, freshness, verification, legal,
curiosity и URL/semantic dedupe.

Обычный `maximum_candidates` **не применяется по мере выполнения слотов**.
Каждый обязательный pass сначала получает место в расширенном validated
and deduplicated discovery-pool. Только после завершения всех 12 направлений
код применяет финальный cap глобально: сначала сохраняет сильнейший уникальный
вклад каждого направления, затем заполняет оставшиеся места общим ранжированием.
Это предотвращает ситуацию, когда первые широкие проходы занимают все места до
China/Asia, Russia, security, legal или missing-events. Это fairness retrieval-
пула, а не квота на публикацию. Diagnostics отдельно сохраняют размер полного
validated pool и события, отброшенные только финальным cap.

Два China/Asia-прохода являются намеренным контрактом. Regression-эксперимент
на историческом окне 2026-08-08 02:48:25+03:00 → 2026-08-11
02:50:46+03:00 показал: одна широкая regional-проверка обнаружила 5 из 6
контрольных событий, но пропустила Apple/Qwen integration. Отдельный
`china_asia_integrations` pass поднял шестое событие без увеличения бюджета.
Fixture: `fixtures/recall/2026-08-11.json`.

Все 12 проходов обязательны. Если любой Responses call технически не завершил
ровно один Web Search, fresh primary завершается красным. Такой сбой нельзя
превращать в «low news volume». Успешно завершённый pass вправе вернуть ноль
кандидатов. Диагностика сохраняет actual queries, consulted sources, raw
candidates, model rejections и validator rejections каждого направления.

Primary сохраняет:

- `preview/production-daily/primary-recall-research-<DATE>.json` — канонический
  research-input для existing generator/editorial;
- `preview/production-daily/primary-recall-<DATE>.json` — полная траектория
  матрицы и бюджета;
- `preview/<DATE>/primary-recall.json` — копия diagnostics внутри release
  artifact после генератора.

`run_digest_preview.py` передаёт новый research существующему
`generate_digest_preview.py` через `--research-input`, а не дублирует editorial
pipeline. Caller-supplied `--research-input` остаётся признаком recovery или
editorial-only rerun и полностью пропускает fresh paid primary.

### 2. Hybrid completeness v1

После **свежего** Primary Recall v2 запускается независимый
`hybrid_search_completeness.py`. Внутренне injected primary research-input не
считается recovery и поэтому разрешает этот один completeness-pass; любой
caller-supplied `--research-input` hybrid пропускает.

Три фиксированных прохода выполняются всегда и получают ровно по одному Web
Search (`max_tool_calls=1`):

1. `models_products_research`;
2. `infrastructure_business`;
3. `safety_policy_regions`.

После трёх проходов код считает тематическое покрытие объединённого primary +
completeness пула. Если целый кластер пуст, разрешается один `adaptive_gap`.
Поэтому ordinary completeness budget равен **3 searches**, absolute hard cap —
**4 searches**. API domain filter отсутствует намеренно; `open_page` и
`find_in_page` остаются диагностикой и не считаются search operation.

Все NEW-only hybrid candidates проходят те же строгие проверки. Editorial
повторяется только если принят хотя бы один кандидат. Перед rerun primary
artifact сохраняется снимком; если rerun падает, он восстанавливается. При этом
внутренний Primary Recall `--research-input` заменяется merged path, а не
дублируется в argv.

### 3. Диагностика hybrid

Каждый запуск сохраняет:

- `preview/<DATE>/hybrid-completeness.json`;
- `preview/production-daily/hybrid-completeness-<DATE>.json`;
- при принятых NEW-only кандидатах:
  `preview/production-daily/hybrid-completeness-merged-<DATE>.json`.

Report фиксирует версию стратегии, фактические запросы и источники, completed
search count, cluster counts, adaptive decision, accepted/rejected candidates и
факт editorial rerun.

## Fallback coverage для короткого/нулевого пула

`ensure_story_coverage.py` остаётся последним тяжёлым fallback. Если после
primary + hybrid выпуск не достигает обычной цели, запускаются шесть
обязательных one-search направлений с общим потолком **до 7 coverage** search
operations, где седьмой слот резервируется для retry первой технически
незавершённой проверки.

Обязательные направления:

1. `security_world`;
2. `security_russia`;
3. `security_asia`;
4. `legal_copyright_scraping`;
5. `curiosity`;
6. `general_coverage_gaps` — авторитетный last-mile sweep.

Если все шесть завершены, но пригодный пул нулевой, свободный седьмой слот
используется как recall sentinel v7. Sentinel работает без API domain filter и
остаётся аварийным regression-probe, а не основным retrieval-механизмом.

Fallback fail-closed: технически неполный audit блокирует Image API, commit и
deploy; те же правила действуют для `partial`, `budget_exhausted` и `error`.
Полностью завершённый поиск с нулевым итоговым пулом становится зелёным
`editorial_stop` без публикации.

## Поисковый бюджет

Потолки считаются по завершённым search operations:

- Primary Recall v2: ровно 12 для fresh production;
- hybrid completeness: обычно 3, максимум 4;
- fallback coverage: максимум 7, только если итог после primary + hybrid
  короткий/нулевой.

Формула production-контракта: **12 primary + до 4 hybrid + до 7 coverage**.
Теоретический worst case: **23** search operations. Primary v2 повышает recall
перераспределением существующего бюджета, а не скрытым увеличением расходов.

## Recovery

Ручной `workflow_dispatch`: `publish` — по умолчанию `false`; необязательный
`recovery_run_id` позволяет явно выбрать сохранённый production artifact.
Recovery без явного ID предпочитает наиболее полный artifact той же даты и не
повторяет уже оплаченные стадии без необходимости.

- готовый выпуск может быть только redeployed;
- готовый текст не требует повторного text API;
- fresh Primary Recall v2 получает hybrid один раз;
- caller-supplied `--research-input` пропускает fresh primary и hybrid;
- internally injected primary research-input не считается recovery;
- primary/hybrid diagnostics и объединённый candidate pool остаются частью
  production artifact;
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
  поиска даёт no-publish, а не искусственное наполнение;
- legal требует масштаба `major`, высокой значимости и надёжного источника;
- curiosity необязателен и ограничен одним выбранным сюжетом;
- research source metadata не может произвольно переписываться editorial.

## Repository hygiene

`repository-hygiene.yml` запускается в `12:43 UTC` (`15:43 МСК`). Плановый
запуск применяет только доказуемо безопасные операции, ручной запуск по
умолчанию audit-only.

Постоянная ветка `archive/search-baseline-pre-hybrid-2026-08-09` всегда
защищена. Для остальных веток действуют стандартные lifecycle-правила; tracked
source files scanner только диагностирует и никогда не удаляет автоматически.
Подробности production/CI artifacts, orphan workflows и completed runs описаны
в root `README.md` и `AGENTS.md`.

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
