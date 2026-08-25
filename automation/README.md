# Автоматизация ИИ-Сводок

Каталог содержит production-конвейер ежедневной публикации ИИ-Сводок. Главный
принцип retrieval-архитектуры: **fresh primary сначала максимально надёжно
обнаруживает потенциально важные события, а строгая редакционная фильтрация
применяется после discovery**. Двенадцать обязательных Primary search operations
распределяются детерминированно; отдельный bounded agency discovery rescue может
добавить максимум одну search operation только при доказанном gap
`major_agencies`.

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
- `audits/independent-audit-journal.md` — канонический журнал независимых
  Freshness/Completeness аудитов;
- `audits/experiments/` — сохранённые architecture/retrieval эксперименты;
- `config/` — production-, editorial-, site- и image-конфигурация;
- `prompts/primary_recall_pass.md` — активный prompt одного Primary Recall v2
  прохода;
- `prompts/research_candidates.md` — legacy monolithic primary prompt для
  истории/rollback, не активный путь свежего production;
- `prompts/` — также editorial и fallback coverage prompts;
- `fixtures/recall/` — исторические retrieval regression windows и
  machine-readable контракты экспериментов;
- `fixtures/research/.runtime/` — ignored доверенный runtime ingress fresh
  primary/rescue/hybrid research в существующий generator; содержимое не
  коммитится;
- `specs/` — канонические редакционные и технические контракты;
- `scripts/primary_recall_search.py` — deterministic primary orchestrator;
- `scripts/agency_discovery_rescue.py` — условный missing-event Reuters-only
  discovery rescue;
- `scripts/agency_discovery_recovery_entry.py` — idempotent recovery-entry
  rescue перед Coverage;
- `scripts/` — production, recovery, hybrid completeness, cleanup и validators;
- `tests/` — офлайн-регрессии;
- `notebooklm-video/` — отдельный локальный Windows downstream-подпроект для
  NotebookLM-видео, PNG-превью и ограниченной FTP-доставки в `video`; он не
  участвует в ночном retrieval/editorial GitHub Actions production и меняется
  только задачами, явно адресованными этому подпроекту;
- `preview/` — временные диагностические результаты production/CI, в Git не
  входят;
- `recovery/` — временно восстановленные Actions artifacts, в Git не входят.

Исторические `content/YYYY-MM-DD/` старше 32 дней компактируются, но
`meta.json` и `stories.json` сохраняются для редакционной памяти. Та же
32-дневная граница применяется к публичным страницам и связанным картинкам.

## Workflow

В репозитории пять канонических Actions workflow:

- `ci.yml` — бесплатные офлайн-проверки;
- `daily-production.yml` — ежедневный Primary Recall v2, conditional agency
  discovery rescue, hybrid completeness, editorial, fallback coverage, обложка,
  сборка и публикация;
- `repository-cleanup.yml` — 32-дневная очистка контента;
- `repository-hygiene.yml` — инженерная уборка безопасных GitHub-объектов;
- `deploy-posts.yml` — FTP-синхронизация точного состояния `posts/` выбранного
  commit.

Основной cron production: `23:17 UTC` предыдущего календарного дня, то есть
`02:17 Europe/Moscow` даты выпуска. Резервный внешний запуск остаётся в
cron-job.org. Gate до платных API проверяет, нужен ли новый выпуск, no-op или
только FTP-redeploy.

## Retrieval: Primary Recall v2 + bounded agency rescue + Hybrid

### 1. Primary Recall v2

Fresh production больше не передаёт все 12 Web Search одному агентному вызову.
`run_digest_preview.py` запускает `primary_recall_search.py`, который выполняет
**ровно 12 обязательных one-search Responses calls**. Каждый pass обязан
завершить ровно одну `action.type=search` и один логический query. Hard cap
Primary остаётся **12 search operations**.

`max_tool_calls=1` не используется как эквивалент search-бюджета: `open_page` и
`find_in_page` тоже являются hosted tool calls. После единственного search pass
может использовать до трёх навигационных действий. Responses-output ceiling
каждого Primary pass равен **6000 tokens**; это reasoning/JSON headroom, а не
дополнительный поиск.

Фиксированная матрица:

1. `global_breaking`;
2. `major_agencies` — Reuters/AP/Bloomberg/FT high-signal route;
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

`global_breaking` и `independent_missing_events` являются source-neutral broad
catch-all проходами. `major_agencies` сохраняет отдельный Reuters/AP/Bloomberg/FT
API domain route с date-free query
`latest AI chips infrastructure financing earnings business deals policy security`.
Остальные направления остаются широкими.

Каноническая continuity-точка — фактический `search_cutoff_at` последнего
успешного выпуска. Fresh Primary строит effective discovery window с максимум
24-часовым healing overlap перед anchor. Archive anchor назад не двигается,
exact source URL уже опубликованных сюжетов отсекаются до merge, downstream
semantic dedupe остаётся обязательным.
Primary, bounded rescue, Hybrid и Coverage используют короткие date-free
relative-freshness queries (`latest`/`recent`/`current`/`breaking`). Exact
`search_window` является post-retrieval eligibility boundary, а не query text.

Два China/Asia-прохода сохраняются раздельно. `china_asia_models` отвечает за
model/product/release discovery. `china_asia_integrations` использует query
`latest China Asia AI business earnings revenue strategy cloud partnerships deployments`
и сохраняет integrations/partnership/deployment semantics вместе с
business/earnings/revenue/strategy. `russia` остаётся отдельным mandatory slot.

Primary использует discovery-first семантику; финальный `maximum_candidates`
применяется только после завершения всех 12 обязательных направлений, чтобы
ранние broad-проходы не вытесняли поздние China/Asia, Russia, security, legal и
missing-events routes.

Regression fixtures:

- `fixtures/recall/2026-08-11.json` — отдельный China integration route;
- `fixtures/recall/2026-08-12.json` — false-zero/runtime-ingress incident;
- `fixtures/recall/2026-08-13.json` — high-signal agency controls;
- `fixtures/recall/2026-08-21-agency-asia.json` — Broadcom/Google-Marvell/Alibaba
  и Asia business semantics;
- `fixtures/recall/2026-08-24-agency-recovery.json` — out-of-sample Alibaba
  placement, Reuters-only rescue routing и manual fresh-research recovery.

Source-health gate остаётся fail-closed для технически degraded Primary:
`major_agencies` обязан завершить свой search и иметь минимум один consulted
source, а вся матрица — минимум два non-junk consulted URL. Нулевой candidate
результат технически завершённого route сам по себе не является transport
ошибкой и может активировать следующий quality-layer.

Primary сохраняет диагностический и trusted runtime research, а существующий
editorial получает его через `--research-input`. Caller-supplied
`--research-input` остаётся recovery/editorial-only путём и не запускает свежий
Primary.

### 2. Bounded agency discovery rescue v3

После сохранённого Primary/provisional-editorial checkpoint и **до Hybrid**
`agency_discovery_rescue.py` проверяет только качество обязательного
`major_agencies`. Trigger разрешён, если этот route технически завершён и
`raw_count == 0` либо `accepted_count == 0`. Общий candidate/story count в
условии отсутствует, поэтому полный пул не маскирует слепоту agency route.

При trigger разрешена максимум **одна** дополнительная Web Search operation.
Фактический query фиксирован, date-free и publisher-neutral:

`latest AI chips infrastructure financing earnings business deals policy security`

API route ограничен `allowed_domains=["reuters.com"]`. Это отдельный более
узкий provider/source-pool, а не повтор обязательного
Reuters/AP/Bloomberg/FT `major_agencies`. Publisher names, `site:`, даты и
Boolean-цепочки в query не дублируются. В v3 `search_context_size` равен `high`.
Причина изменения узкая: fresh production run `32691255059` уже проверил v2 на
реальном Reuters-only route с тем же query и `medium`, но вернул
`consulted_sources=[]` и `raw_count=0`, хотя Alibaba share placement от
23 августа оставался in-window positive control и независимо находился
Reuters-focused поиском. Query, один search operation, Reuters-only domain
routing, downstream acceptance и общий потолок 24 не меняются. Отдельного
assistant-side Terra A/B с явным переключателем `medium/high` среда по-прежнему
не предоставляет, поэтому `high` фиксируется как минимальная следующая
production-supported reliability-гипотеза, а не как универсально доказанный
оптимум.

Downstream acceptance узкий: новый candidate должен иметь прямой
`reuters.com` primary URL. Yahoo, TradingView, MarketScreener, Investing и другие
syndication/aggregator URL не считаются прямым agency source. AP остаётся частью
обязательного Primary и downstream corroboration; второй AP rescue search не
добавляется.

Это **missing-event discovery**, а не downstream same-event corroboration.
Candidate проходит обычный `story_coverage` validator, exact archive URL check и
same-event guard по `organization + event_type + published_date`. Затем trusted
runtime path запускает неизменённый Source Freshness Proof и обычный editorial.
Reuters не повышает significance и не гарантирует публикацию. Stale, weak,
analysis/opinion-only, duplicate и zero-result остаются диагностикой и не ломают
ранее пригодный выпуск.

State machine persisted в `agency-discovery-rescue.json` до и после paid call.
`search_started` никогда не ретраится автоматически: неизвестно, успел ли
provider фактически потратить единственный search. `search_completed` и
`merge_failed` могут продолжить merge из сохранённого response без нового Web
Search. Если rescue добавил candidate, а Hybrid затем технически упал,
`run_digest_preview.py` сохраняет rescue merged runtime и всё равно передаёт его
Source Freshness Proof/editorial; Hybrid и rescue не ретраятся.

Диагностика:

- `preview/<DATE>/agency-discovery-rescue.json`;
- `preview/production-daily/agency-discovery-rescue-<DATE>.json`;
- при accepted candidate — diagnostic/runtime merged research.

Исторический source-open regression contract находится в
`fixtures/recall/2026-08-22-agency-discovery-rescue.json`. Текущий контракт
закреплён `fixtures/recall/2026-08-24-agency-recovery.json` и добавляет Alibaba
share placement вместе со stale/opinion/syndication/duplicate/after-cutoff/
quiet-window negative controls.

### 3. Hybrid completeness v1

После fresh Primary и conditional rescue запускается независимый
`hybrid_search_completeness.py`. Caller-supplied `--research-input` Hybrid
пропускает.

Три фиксированных прохода выполняются всегда:

1. `models_products_research`;
2. `infrastructure_business`;
3. `safety_policy_regions`.

После трёх проходов код считает тематическое покрытие объединённого Primary +
rescue + Hybrid pool. Если целый кластер пуст, разрешается один `adaptive_gap`.
Ordinary Hybrid budget равен **3**, absolute hard cap — **4 search operations**.
API domain filter отсутствует. Optional 4-й slot сохраняет regional-health
семантику Asia/Russia, если соответствующий Primary route законно нулевой.

Все NEW-only Hybrid candidates проходят те же проверки. Editorial повторяется
только если принят хотя бы один кандидат. При failure baseline artifact
восстанавливается, а валидный merged handoff сохраняется для Coverage; rescue
candidate, уже принятый перед Hybrid, отдельно защищён от потери.

### 4. Диагностика Hybrid

Каждый запуск сохраняет `hybrid-completeness.json`, production diagnostic report
и при accepted candidates diagnostic/runtime merged research. Report фиксирует
стратегию, queries, sources, completed search count, navigation items, cluster
counts, adaptive decision, accepted/rejected candidates и editorial rerun.

## Fallback Coverage

`ensure_story_coverage.py` остаётся последним тяжёлым fallback. Если после
Primary + conditional rescue + Hybrid выпуск не достигает обычной цели,
запускаются шесть обязательных one-search направлений с общим потолком
**до 7 Coverage search operations**.

Обязательные направления:

1. `security_world`;
2. `security_russia`;
3. `security_asia`;
4. `legal_copyright_scraping`;
5. `curiosity`;
6. `general_coverage_gaps`.

Седьмой слот сначала принадлежит retry технически незавершённого mandatory
направления. После полного mandatory plan он может быть использован только одной
из взаимоисключающих quality-семантик: unresolved high-signal resolution,
existing-event `fresh_agency_rescue` либо source-neutral zero-pool sentinel.
Pre-Hybrid `agency_discovery_rescue` сюда не переносится и считается отдельно.

Fallback fail-closed: `partial`, `budget_exhausted` и `error` блокируют Image API,
commit и deploy. Полностью завершённый поиск с нулевым итоговым pool становится
зелёным `editorial_stop` без публикации.

## Поисковый бюджет

Потолки считаются только по завершённым `action.type=search` operations:

- Primary Recall v2: ровно 12;
- bounded agency discovery rescue: 0 или 1;
- Hybrid completeness: обычно 3, максимум 4;
- fallback Coverage: максимум 7.

Текущий theoretical worst case: **12 + 1 + 4 + 7 = 24 search operations**.
Rescue не является 13-м mandatory Primary pass и не выполняется без
`major_agencies` trigger. Navigation hosted calls в этот потолок не входят.

Исторический experiment 2026-08-21 действительно сохранял потолок 23 и сначала
исправлял semantics существующих slots. Повтор Broadcom 22 августа и новые
out-of-sample misses 23–24 августа подтвердили, что semantic/source-open fix
недостаточен; Reuters-only bounded route сохраняет тот же единственный
conditional discovery slot и общий ceiling 24.

## Recovery

Ручной `workflow_dispatch`: `publish=false` по умолчанию;
`recovery_run_id` позволяет явно выбрать artifact. Automatic recovery предпочитает
наиболее полный artifact той же даты и не повторяет оплаченные стадии без
необходимости.

`force_fresh_research` — отдельный manual-only opt-out из automatic recovery с
default `false`. При `workflow_dispatch + force_fresh_research=true` workflow не
выбирает same-day automatic artifact, поэтому retrieval hotfix действительно
получает fresh research на текущем `main`. Scheduled/default behavior не
меняется. Явный `recovery_run_id` конфликтует с `force_fresh_research=true` и
завершает run до платных API. `publish` независим: false остаётся dry-run.

- готовый выпуск может быть только redeployed;
- fresh Primary получает conditional rescue/Hybrid один раз;
- caller-supplied `--research-input` не запускает свежий Primary/rescue/Hybrid;
- full modern artifact с `major_agencies` gap и без rescue state понижается до
  `partial_editorial`, чтобы text runtime был доступен для первого допустимого
  rescue attempt;
- `search_started` rescue считается indeterminate и не повторяется;
- `search_completed`/`merge_failed` repair завершается из persisted response без
  второго Web Search;
- после recovery rescue-origin candidate снова проходит Source Freshness Proof
  до editorial/Coverage decision; freshness failure удаляет supplemental rescue
  rows из candidate pool;
- pending merge/freshness/editorial делает text API/runtime реально нужным, даже
  если старый artifact имел полный story target;
- завершённый fallback audit и актуальный sentinel переиспользуются;
- partial fallback продолжает только незавершённые directions;
- доказанный zero-pool `editorial_stop` переиспользуется без новой оплаты, кроме
  явного manual `force_fresh_research=true` после разрешённого retrieval hotfix;
- artifact с `artifact-normalization.json.status=error` или
  `artifact-validation.json.status=error` не переиспользуется;
- сохранённый `primary-recall.json` обязан повторно пройти current source-health
  gate даже для `full` artifact.

Реальный fresh production rerun может расходовать `OPENAI_API_KEY`; исправление
кода само по себе не является разрешением его запускать. Эксперименты, A/B и
регрессионные проверки выполняются на assistant-owned ресурсах или offline.

## Редакционный контракт короткого выпуска

Канонические правила находятся в `specs/editorial-policy.md`:

- обычная цель — 7–12 сюжетов;
- для публикации достаточно одного достойного сюжета;
- числовых региональных квот нет;
- 1–6 сюжетов получают пометку «Новостей сегодня меньше, чем обычно»;
- отсутствие достойных сюжетов после завершённого обязательного поиска даёт
  no-publish, а не искусственное наполнение;
- legal требует масштаба `major`, высокой значимости и надёжного источника;
- curiosity необязателен и ограничен одним выбранным сюжетом;
- research source metadata не может произвольно переписываться editorial.

## Repository hygiene

`repository-hygiene.yml` запускается в `12:43 UTC` (`15:43 МСК`). Плановый
запуск применяет только доказуемо безопасные операции, ручной запуск по
умолчанию audit-only. Постоянная ветка
`archive/search-baseline-pre-hybrid-2026-08-09` всегда защищена. Tracked source
scanner только диагностирует и никогда не удаляет файлы автоматически.

## Локальная проверка

Основной бесплатный набор:
```bash
python -m compileall automation/scripts automation/tests
python -m unittest discover -s automation/tests -v
python automation/scripts/validate_editorial_contract.py
python automation/scripts/validate_archive.py
```

Main CI дополнительно проверяет production workflow contract, committed archive,
RSS, sitemap, Schema.org и защищённые пути. Точный набор команд задаётся
`.github/workflows/ci.yml`.

## Retrieval experiments 2026-08-21–24

Эксперимент 21 августа расширил `major_agencies` и второй China/Asia slot без
роста бюджета. Отчёт: `audits/experiments/2026-08-21-agency-asia-recall.md`,
contract: `fixtures/recall/2026-08-21-agency-asia.json`.

Наблюдение 22 августа показало повтор Broadcom после semantic patch.
Контролируемый bounded experiment подтвердил source-pool/ranking instability и
рекомендовал `major_agencies gap -> one bounded discovery rescue`. 23 августа
новый Reuters/Nvidia miss дал out-of-sample подтверждение.

Run `32674034063` за 24 августа завершил 12 Primary + 1 rescue + 4 Hybrid + 7
Coverage searches, но остался с нулевым pool. Его `major_agencies` имел
Reuters/AP/Bloomberg/FT filter, однако ranked stale Bloomberg/FT слой; source-open
rescue получил преимущественно aggregators/syndication. В том же effective
window Reuters опубликовал Alibaba share placement примерно на $10.2B с
назначением proceeds на full-stack AI. Assistant-side Reuters-focused replay
восстановил этот out-of-sample control и предыдущие Reuters controls без нового
search slot. Поэтому v2 сузил **существующий один** rescue до Reuters-only
provider route, сохранив freshness/Asia/Russia/editorial без изменений.

Fresh production run `32691255059` затем изолировал следующий дефект уже внутри
нового source route: v2 действительно выполнил Reuters-only search с тем же
publisher-neutral query и `search_context_size=medium`, но provider вернул
`consulted_sources=[]`, `raw_count=0`, и Alibaba снова не дошёл до candidate
pool. Это не downstream filtering failure. V3 меняет только context size на
`high`; query, `allowed_domains=["reuters.com"]`, one-search budget, direct-Reuters
acceptance, freshness, editorial и global ceiling 24 остаются прежними. Если
следующий fresh run снова даст ноль Reuters sources, отдельным следующим
экспериментом должен стать более короткий query, а не одновременное изменение
нескольких переменных.

Пользовательский production API для разработки и regression replay не
расходовался. Assistant-side replay не выдаётся за чистый Terra A/B, когда
standalone Terra tool недоступен; baseline evidence берётся из сохранённых
production artifacts. V3 `high` опирается на реальный v2 `medium` false-zero как
минимальную следующую reliability-гипотезу, но не описывается как доказанный
изолированный assistant-side `medium/high` A/B.

## Канонический независимый мониторинг

`audits/independent-audit-journal.md` хранит накопленную независимую историю
Freshness/Completeness. После каждого успешного выпуска проверяются exact
window, Primary/rescue/Hybrid/Coverage anatomy, editorial, Must Include misses,
source concentration, Asia/Russia и повторяющиеся defects. Один miss не меняет
архитектуру автоматически: сначала evidence, затем bounded experiment и
architecture-wide audit.

## Hygiene search diagnostics

Перед сохранением Primary/rescue/Hybrid/Coverage diagnostics URL очищаются от
временных credential/token/signature query-параметров, включая AWS signed URL.
Artifact secret-scanner остаётся fail-closed.

## Проверенный relative-freshness retrieval

Эксперимент 2026-08-14 показал: явные календарные даты в Web Search query могут
ухудшать ranking и приводить к false-zero. Поэтому все retrieval layers
используют date-free relative-freshness queries, а exact effective window
валидируется после retrieval. Broad safety nets не привязаны к одному издателю.

Source-health проверяет Reuters/AP/Bloomberg/FT evidence по всей Primary matrix;
mandatory `major_agencies` route не заменяется conditional rescue и обязан
технически завершиться сам.

## Recovery платных стадий и обложки

Успешный текстовый checkpoint сохраняет уже оплаченный retrieval/editorial. Ошибка
на обложке или позднем шаге не разрешает автоматически повторять Primary,
завершённый rescue, Hybrid или Coverage. После валидной обложки Images API также
не вызывается заново. Artifact upload выполняется `if: always()`.

`generate_image_preview.py` разделяет `image_request_id`, опциональный
`source_editorial_request_id` и provider `openai_request_id`. Один запуск обложки
делает максимум один Images API POST и не имеет retry-loop.

## Fresh-agency same-event corroboration

Coverage `fresh_agency_rescue` остаётся отдельной downstream механикой. Он
выбирает уже найденное include/consider событие и ищет сильный свежий
Reuters/AP/Bloomberg/FT source. Acceptance требует exact same-event match по
`organization`, `event_type`, `published_date`; подтверждение повышает source,
но не создаёт второй сюжет.

Это не то же самое, что pre-Hybrid `agency_discovery_rescue`: первый ищет
**источник для известного события**, второй ищет **само отсутствующее событие**.
Оба имеют максимум по одной операции в своих условных позициях; Coverage cap
остаётся 7, global cap теперь 24.

## Exact-cutoff agency validation

Agency evidence использует точный saved cutoff. Timezone-aware `published_at`
сравнивается с `start_at/end_at`; date-only evidence на cutoff-day fail-closed,
потому что не доказывает существование статьи до исходного cutoff. Эти правила
не ослабляются для rescue.

## Retrieval Quality v1

High-confidence `unverified` evidence Primary сохраняется как
`unresolved_signal`. Targeted resolution source-neutral и не превращает
`source_hint` в publisher whitelist. Optional Hybrid regional-health использует
существующий 4-й slot и не создаёт региональную story quota.

Coverage adaptive priority остаётся прежним; новый agency discovery расположен
раньше и имеет отдельный budget. Общий maximum: **24 search operations**.
Modern full artifact без завершённого Retrieval Quality либо с pending agency
discovery quality work понижается до partial editorial recovery.

## Source Freshness Proof v1

Trusted Primary/rescue/Hybrid/Coverage runtime перед editorial проходит
`scripts/source_freshness.py`. Verifier не вызывает OpenAI/Web Search: он открывает
только уже процитированные URL, извлекает `datePublished`/equivalent metadata и
сравнивает их Python timezone arithmetic с exact effective window.

Outside-window source переводит candidate в `exclude / old_reprint`; отсутствие
проверяемой даты даёт `unconfirmed`. Supporting source может стать primary, если
именно он доказывает freshness. Recovery rescue freshness-error удаляет rescue
rows, а не оставляет их в ранее пригодном candidate pool.

Диагностика: `preview/production-daily/source-freshness-YYYY-MM-DD.json`,
`paid_api_calls=0`. Source Freshness Proof не меняет search budget; рост общего
ceiling 23 → 24 вызван только conditional agency discovery rescue.

Ручная проверка сохранённого trusted research:

```bash
python automation/scripts/source_freshness.py \
  --research automation/fixtures/research/.runtime/<research>.json \
  --publication-date YYYY-MM-DD \
  --report automation/preview/production-daily/source-freshness-YYYY-MM-DD.json
```

## Cleanup resilience

`cleanup_public_posts.py` различает обязательный `posts/images/` и исторический
legacy-каталог. `repository_hygiene_github.py` имеет bounded retry только для
read-only `GET` после transient `500/502/503/504` или `URLError`; destructive
`DELETE`/`PUT` автоматически не повторяются.