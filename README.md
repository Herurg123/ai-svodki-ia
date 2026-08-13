# ИИ-Сводки

Production-конвейер ежедневных аналитических выпусков об искусственном
интеллекте. GitHub хранит редакционный архив и статический сайт; успешный выпуск
сначала собирается и валидируется, затем фиксируется в `main` и только после
этого синхронизируется на FTP.

Публичные адреса:

- [Дзен](https://dzen.ru/rybv)
- [сайт выпусков](https://rybalka.one/posts/)
- [RSS для Дзена](https://rybalka.one/posts/rss.xml)
- [sitemap](https://rybalka.one/posts/sitemap.xml)

## Production contract

Production запускается из `main`, использует `Europe/Moscow` и нормализует время
выпуска к 06:00 МСК. Пропущенные календарные дни допустимы. Каноническая
continuity-точка исследования — `search_cutoff_at` последнего успешно
опубликованного выпуска; правой границей текущего research является cutoff,
зафиксированный непосредственно перед поиском.

Fresh Primary Recall использует bounded **24-hour healing overlap** перед
continuity anchor, чтобы крупный материал, пропущенный вчера, не исчезал
навсегда. Archive anchor назад не двигается, exact URL и semantic duplicates
отсекаются, поэтому overlap не разрешает бесконечный backfill или повторную
публикацию старых сюжетов.

| Workflow | Назначение |
|---|---|
| `.github/workflows/ci.yml` | Бесплатные офлайн-проверки PR и `main`. |
| `.github/workflows/daily-production.yml` | Gate → Primary Recall → Hybrid → editorial → fallback coverage → cover → site → commit → deploy. |
| `.github/workflows/repository-cleanup.yml` | 32-дневная очистка публичного/редакционного dated content. |
| `.github/workflows/repository-hygiene.yml` | Безопасная уборка ephemeral GitHub objects. |
| `.github/workflows/deploy-posts.yml` | FTP-синхронизация точного `posts/` выбранного commit. |

Точный набор CI-команд задаётся `.github/workflows/ci.yml`.

## Постоянный baseline старого поиска

Состояние непосредственно до hybrid completeness сохранено навсегда:

- branch: `archive/search-baseline-pre-hybrid-2026-08-09`;
- commit: `d926a3abf8b9443f58f303d984ef79fdc289fc3e`;
- manifest: `automation/archive/search-baselines/2026-08-09-pre-hybrid.md`.

Эта ветка является защищённой аналитической/rollback-точкой, не двигается и не
удаляется repository hygiene.

## Ежедневный цикл

1. Gate до платных API определяет новый выпуск, no-op или FTP-redeploy.
2. Архив и effective search window строятся от последнего успешного
   `search_cutoff_at`; exact `search_window.end_at` является авторитетным
   «сейчас» для всех research слоёв.
3. Fresh **Primary Recall v2** выполняет ровно 12 обязательных one-search passes.
4. Независимый **Hybrid Completeness v1** выполняет 3 fixed searches и при
   очевидном пустом кластере максимум 1 adaptive search.
5. Editorial выбирает publishable stories из validated candidate pool.
6. Если пул остаётся коротким/нулевым, fallback coverage выполняет 6 mandatory
   one-search passes и максимум 1 retry/sentinel slot.
7. Technical partial/error state fail-closed. Только полностью доказанный
   zero-pool становится успешным no-publish.
8. Для publishable digest генерируется/валидируется cover, строятся статические
   файлы, release фиксируется в `main`, затем выполняется FTP deployment.

## Primary Recall v2

Жёсткий budget = **12 completed Web Search search operations**. Направления:

1. `global_breaking`;
2. `major_agencies`;
3. `models_products_agents`;
4. `infrastructure_chips_cloud`;
5. `business_investment_partnerships`;
6. `china_asia_models`;
7. `china_asia_integrations`;
8. `russia`;
9. `developer_tools`;
10. `security_safety`;
11. `legal_regulation`;
12. `independent_missing_events`.

Каждый pass обязан выполнить ровно один `action.type=search` и один logical
query. После него допускается bounded navigation (`open_page`/`find_in_page`)
для проверки дат и фактов. Navigation не расходует search-operation budget.

Primary работает **discovery-first**: потенциально значимое свежее событие можно
сохранить как `consider`, а строгая editorial значимость решается позже. Final
candidate cap применяется только после всех 12 passes и сохраняет fairness между
направлениями.

### Query discipline и source-focused routing

Production-инцидент 2026-08-13 показал, что один generic multi-domain agency
query может формально завершиться, вернуть старые служебные страницы и при этом
пропустить свежие крупные новости. Поэтому фактические search queries во всех
retrieval слоях должны быть короткими natural-language фразами, обычно **6–18
значимых слов**, с календарными датами обычным текстом.

Запрещены retrieval-конструкции `after:`, `before:`, `site:`, длинные Boolean
`OR` chains, скобки и огромные lists компаний/доменов. Точная свежесть
проверяется после retrieval по сохранённому effective window.

Без увеличения 12-search Primary budget три broad slots получили разные
high-signal retrieval anchors:

- `global_breaking`: Reuters-focused business/funding/cloud/infrastructure;
- `major_agencies`: Reuters-focused models/products/chips/infrastructure, при
  сохранённом API filter Reuters/AP/Bloomberg/FT;
- `independent_missing_events`: Associated Press-focused consumer AI / major
  technology / policy gaps после просмотра уже найденного pool.

Source anchor влияет только на ranking/discovery и не является whitelist для
кандидатов. Остальные passes остаются тематически широкими. Крупный запуск
consumer-device/OS/service считается релевантным для product pass, если AI-layer
является существенной частью анонса.

`major_agencies` остаётся единственным primary API-domain-filtered pass. Общего
project-wide whitelist нет.

### Исторические recall regressions

- `automation/fixtures/recall/2026-08-11.json`: отдельный China integrations
  pass recovered Apple/Qwen и довёл benchmark до 6/6 controls.
- `automation/fixtures/recall/2026-08-12.json`: false-zero/runtime-ingress
  incident; controls IBM/Together, Nvidia Nemotron/NeMo, CoreWeave и Meta Muse
  Glimmer backfill.
- `automation/fixtures/recall/2026-08-13.json`: run `31652757802` имел ровно 4
  raw candidates и 4 published stories, значит editorial ничего крупного не
  отбрасывал. Независимые source-focused Reuters/AP experiments recovered Pixel
  11/Gemini, Nebius, River AI, IBM/Together и Nvidia Nemotron controls без
  увеличения поискового бюджета.

## Source-health gate

Технически completed search не считается автоматически здоровым. Перед
publication fresh Primary должен доказать:

- `major_agencies` завершил search и имеет хотя бы один consulted source;
- по всем 12 passes есть минимум два consulted URL вне Wikipedia/Reddit/arXiv;
- modern diagnostics с `search_window` содержат хотя бы одно **свежее agency
  evidence внутри effective window** среди broad source-anchor passes.

Dated Reuters/Bloomberg/FT URL либо verified in-window Reuters/AP/Bloomberg/FT
raw candidate считается evidence. Старые author/newsletter/event/document pages
не считаются. Это health check, не квота на агентские stories.

Normalizer также канонизирует доказанный fresh Primary до
`pipeline=primary_recall_v2_then_editorial` и
`research.settings.source=trusted_runtime_primary_recall`. Caller-supplied
recovery input не получает такой rewrite.

## Hybrid Completeness

Hybrid выполняет:

1. models/products/agents/research;
2. infrastructure/chips/business;
3. safety/security/policy/major regional gaps;
4. optional `adaptive_gap` для полностью пустого кластера.

Ordinary budget = **3 searches**, hard cap = **4**. Каждый pass имеет один search
и bounded navigation. После 2026-08-13 Hybrid использует ту же natural-language
query discipline и больше не подталкивает модель к `after:/before:`.

Hybrid candidates проходят общий validator/dedupe; editorial rerun происходит
только при реально принятом новом candidate.

## Fallback coverage

Если после Primary + Hybrid достойных сюжетов мало, fallback проверяет:

1. `security_world`;
2. `security_russia`;
3. `security_asia`;
4. `legal_copyright_scraping`;
5. `curiosity`;
6. `general_coverage_gaps`.

Максимум = **7 completed search operations**, включая один retry. Coverage prompt
также запрещает `after:`, `before:`, `site:` и huge OR chains. Для
`general_coverage_gaps` уже существует authoritative API domain filter, поэтому
он не должен вручную строить `site:foo OR site:bar ...`.

## Search budget

Worst-case invariant не изменился:

- Primary: 12;
- Hybrid: до 4;
- Coverage: до 7.

Итого максимум **23 completed search operations**. Navigation calls не меняют
этот потолок. Recall улучшается маршрутизацией/ranking существующих searches, а
не скрытым ростом расходов.

## Recovery и fail-closed

Recovery не должен повторно оплачивать уже завершённые стадии и не должен
воскрешать известный плохой artifact.

- caller-supplied `--research-input` означает recovery/editorial rerun и
  пропускает fresh Primary/Hybrid;
- internally generated `.runtime` research-input recovery не считается;
- artifacts с `artifact-normalization.json.status=error` или
  `artifact-validation.json.status=error` не переиспользуются;
- saved artifact с `primary-recall.json` повторно проходит current source-health;
- completed coverage/sentinel и доказанный zero-pool `editorial_stop` могут
  переиспользоваться без повторной оплаты.

Technical search/audit partial/error state блокирует публикацию. Нулевой pool
считается нормальным no-publish только после полного доказанного search contract.

## Публикация, retention и footer

Исторический публичный/структурированный dated content хранится по 32-дневному
контракту. `posts/_footer-scr.png` является постоянным asset и не удаляется
cleanup. Новые страницы и RSS заканчиваются linked footer image на Дзен; FTP
проверяет remote presence и восстанавливает asset при необходимости.

Подробные machine-facing правила находятся в `AGENTS.md`, а automation-specific
операционные детали и локальные проверки — в `automation/README.md`.
