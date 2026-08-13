# Автоматизация ИИ-Сводок

Каталог содержит production-конвейер ежедневной публикации ИИ-Сводок. Текущая
retrieval-архитектура работает по принципу **discovery first, editorial second**:
сначала система старается не потерять потенциально важные свежие события, затем
строгие валидаторы и editorial решают, что действительно публиковать.

## Постоянный baseline старого поиска

Состояние непосредственно перед hybrid completeness сохранено навсегда:

- branch: `archive/search-baseline-pre-hybrid-2026-08-09`;
- commit: `d926a3abf8b9443f58f303d984ef79fdc289fc3e`;
- manifest: `archive/search-baselines/2026-08-09-pre-hybrid.md`.

Archive-ветка не используется для разработки, не перемещается и не удаляется.

## Основные каталоги

- `content/YYYY-MM-DD/` — структурированные материалы выпусков;
- `archive/index.json` — редакционный архив и память дедупликации;
- `archive/search-baselines/` — manifests постоянных retrieval-baseline;
- `config/` — production/editorial/site/image configuration;
- `prompts/primary_recall_pass.md` — активный prompt Primary Recall v2;
- `prompts/coverage_audit.md` — fallback coverage prompt;
- `prompts/research_candidates.md` — legacy monolithic research prompt для
  истории/rollback, не fresh production path;
- `fixtures/recall/` — исторические retrieval regression experiments;
- `fixtures/research/.runtime/` — ignored trusted ingress внутреннего fresh
  research в legacy generator;
- `specs/` — канонические редакционные и технические контракты;
- `scripts/primary_recall_search.py` — deterministic Primary Recall orchestrator;
- `scripts/hybrid_search_completeness.py` — независимая completeness-страховка;
- `scripts/ensure_story_coverage_policy.py` — fallback coverage;
- `scripts/normalize_digest_artifact.py` — metadata/prompt normalization и
  source-health gate;
- `tests/` — офлайн-регрессии;
- `preview/` и `recovery/` — временные диагностические данные, не коммитятся.

Исторический canonical content хранится по 32-дневному контракту; `meta.json` и
`stories.json` старых выпусков сохраняются для редакционной памяти.

## Workflow

Канонические GitHub Actions:

- `ci.yml` — бесплатные офлайн-проверки;
- `daily-production.yml` — research, editorial, coverage, обложка, сборка и
  публикация;
- `repository-cleanup.yml` — 32-дневная очистка content/public posts;
- `repository-hygiene.yml` — инженерная уборка безопасных GitHub-объектов;
- `deploy-posts.yml` — FTP-синхронизация точного `posts/` выбранного commit.

Основной production cron: `23:17 UTC` предыдущего календарного дня, то есть
`02:17 Europe/Moscow` даты выпуска. Внешний резервный запуск остаётся в
cron-job.org. Gate выполняется до платных API и различает новый выпуск, no-op и
FTP-redeploy.

## Retrieval architecture

### 1. Primary Recall v2

Fresh production выполняет **ровно 12 обязательных Web Search search operations**.
Каждый pass получает отдельный Responses-вызов, обязан сделать ровно один
`action.type=search` и один logical query. `open_page`/`find_in_page` считаются
navigation calls и могут использоваться после единственного search для проверки
даты и фактов. Второй search или batched multi-query запрещены.

Фиксированная матрица:

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

`major_agencies` имеет API domain filter `reuters.com`, `apnews.com`,
`bloomberg.com`, `ft.com`. Остальные primary passes не имеют общего whitelist.

Канонический continuity anchor — `search_cutoff_at` последнего опубликованного
выпуска. Новый pre-research cutoff является правой границей и авторитетным
текущим временем. Fresh Primary может расширить effective discovery window на
24 часа назад от continuity anchor для bounded healing пропусков. Уже
опубликованные exact URL и semantic duplicates не возвращаются.

### Query discipline после эксперимента 2026-08-13

Фактический query каждого слоя должен быть короткой natural-language фразой,
обычно **6–18 значимых слов**, с календарными датами обычным текстом. В search
query запрещены `after:`, `before:`, `site:`, длинные Boolean `OR`-цепочки,
скобки и огромные перечни компаний/доменов. Exact timestamp окна проверяется уже
после retrieval.

Production run `31652757802` за 2026-08-13 показал системный recall-дефект:
editorial получил ровно четыре кандидата и выбрал все четыре, тогда как один
общий agency-pass вернул ноль кандидатов и был заполнен старыми
Bloomberg author/newsletter/event страницами и старыми FT-документами.
Независимые source-focused эксперименты по тому же effective window подняли
значимые пропуски, поэтому без увеличения 12-search budget три broad slots теперь
получают разные retrieval anchors:

- `global_breaking` — Reuters-focused business/funding/cloud/infrastructure;
- `major_agencies` — Reuters-focused models/products/chips/infrastructure при
  сохранённом API filter Reuters/AP/Bloomberg/FT;
- `independent_missing_events` — Associated Press-focused consumer AI / major
  technology / policy sweep с учётом уже найденного пула.

Это **не candidate whitelist**. Source anchor нужен только для ranking/discovery;
после retrieval кандидат может быть подтверждён лучшим первоисточником.
`models_products_agents` отдельно учитывает крупные consumer-device/OS/service
launches, если AI-layer является существенной частью анонса.

Wikipedia и Reddit не используются как основное подтверждение свежей новости.
ArXiv допустим для действительно значимого research, но не как замена текущим
product/infrastructure/business/security/legal/policy событиям.

Primary остаётся discovery-first: проверяемое потенциально значимое событие можно
сохранить как `consider`; окончательная значимость решается downstream. Final
`maximum_candidates` применяется только после всех 12 passes и не позволяет
ранним broad searches вытеснить поздние China/Russia/security/legal/gap slots.

### Recall regression fixtures

- `fixtures/recall/2026-08-11.json` — отдельный China integration pass recovered
  Apple/Qwen, доведя исторический benchmark с 5/6 до 6/6 controls;
- `fixtures/recall/2026-08-12.json` — false-zero/runtime-ingress incident и
  controls IBM/Together, Nvidia Nemotron/NeMo, CoreWeave, Meta Muse Glimmer;
- `fixtures/recall/2026-08-13.json` — run `31652757802`, где 4 candidates = 4
  published stories; source-focused Reuters/AP experiment recovered recorded
  controls Pixel 11/Gemini, Nebius, River AI, IBM/Together и Nvidia Nemotron
  без увеличения primary budget.

### Source-health gate

Перед publication fresh Primary должен доказать минимальное здоровье retrieval:

- `major_agencies` завершил свой search и имеет хотя бы один consulted source;
- суммарно есть минимум два consulted URL вне Wikipedia/Reddit/arXiv;
- если modern `primary-recall.json` содержит `search_window`, широкие
  source-anchor passes должны показать хотя бы один **Reuters/AP/Bloomberg/FT
  материал внутри effective window**. Доказательством служит dated agency URL
  или verified raw candidate с in-window `published_date`.

Старые author/newsletter/event/document pages больше не считаются доказательством
свежего agency retrieval. Это не квота на агентские новости в выпуске и не
обязательство каждого pass вернуть candidate. Legacy Primary artifacts без
`search_window` сохраняют backward compatibility.

Fresh Primary metadata также нормализуется до
`pipeline=primary_recall_v2_then_editorial` и
`research.settings.source=trusted_runtime_primary_recall` только когда доказано
12 свежих searches. Caller-supplied recovery input не переписывается.

### 2. Hybrid completeness v1

После свежего Primary запускается независимый Hybrid:

1. `models_products_research`;
2. `infrastructure_business`;
3. `safety_policy_regions`;
4. optional `adaptive_gap`, только если целый кластер остаётся пустым.

Обычный budget = **3 searches**, absolute maximum = **4**. Каждый pass всё так же
имеет один search плюс bounded navigation, API domain filter отсутствует.

После инцидента 2026-08-13 Hybrid больше не генерирует retrieval-подсказки
`after:/before:`. Он использует те же короткие natural-language date queries и
явно запрещает `after:`, `before:`, `site:` и длинные OR-конструкции.

Hybrid candidates проходят общий validator/dedupe. Editorial повторяется только
при принятом новом candidate. Caller-supplied recovery input hybrid не запускает.

### 3. Fallback coverage

Если после Primary + Hybrid пул короткий/нулевой, `ensure_story_coverage.py`
выполняет шесть обязательных one-search направлений и максимум один retry:

1. `security_world`;
2. `security_russia`;
3. `security_asia`;
4. `legal_copyright_scraping`;
5. `curiosity`;
6. `general_coverage_gaps`.

Hard ceiling fallback = **7 completed search operations**. Production coverage
prompt теперь использует ту же natural-language query discipline. В частности,
`general_coverage_gaps` уже имеет authoritative API domain filter и не должен
строить гигантский `site:reuters.com OR site:apnews.com ...` query.

Technical partial/budget/error audit fail-closed и блокирует Image API, commit и
deploy. Только полностью завершённый поиск с нулевым publishable pool становится
зелёным `editorial_stop`.

## Поисковый бюджет

Потолки считаются по completed `action.type=search` operations:

- Primary Recall: ровно 12;
- Hybrid: обычно 3, максимум 4;
- fallback coverage: максимум 7, когда нужен.

Worst case остаётся **23 search operations**. Navigation calls повышают число
hosted tool invocations, но не поисковый потолок. Текущий recall fix меняет
распределение/ranking запросов, а не стоимость budget.

## Recovery

`workflow_dispatch` поддерживает `publish` (по умолчанию `false`) и опциональный
`recovery_run_id`. Recovery предпочитает наиболее полный пригодный artifact той
же даты и не повторяет оплаченные стадии без необходимости.

Ключевые правила:

- готовый выпуск может быть только redeployed;
- готовый текст не требует повторного text API;
- caller-supplied `--research-input` пропускает fresh Primary и Hybrid;
- внутренний `.runtime` input recovery не считается;
- completed coverage/sentinel и доказанный `editorial_stop` переиспользуются;
- artifact с `artifact-normalization.json.status=error` или
  `artifact-validation.json.status=error` не переиспользуется;
- saved artifact с `primary-recall.json` повторно проходит current source-health,
  включая fresh-agency evidence для modern diagnostics.

## Редакционный контракт

Канонические правила находятся в `specs/editorial-policy.md`:

- обычная цель 7–12 сюжетов;
- для публикации достаточно одного достойного сюжета;
- числовых региональных квот нет;
- 1–6 сюжетов получают пометку «Новостей сегодня меньше, чем обычно»;
- полностью здоровый zero-pool даёт no-publish, а не искусственное наполнение;
- legal требует масштаба `major`, высокой значимости и надёжного источника;
- curiosity необязателен и ограничен одним выбранным сюжетом.

## Repository hygiene и локальная проверка

`repository-hygiene.yml` запускается в `12:43 UTC` (`15:43 МСК`). Постоянная
archive-ветка baseline всегда защищена; tracked source scanner report-only.

Базовые бесплатные проверки:

```bash
python -m compileall automation/scripts automation/tests
python -m unittest discover -s automation/tests -v
python automation/scripts/validate_editorial_contract.py
python automation/scripts/validate_archive.py
```

Main CI дополнительно проверяет production workflow contract, archive, RSS,
sitemap, Schema.org и protected paths. Канонический список команд задаётся
`.github/workflows/ci.yml`.
