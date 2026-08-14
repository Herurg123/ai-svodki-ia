# Автоматизация ИИ-Сводок

Каталог содержит production-конвейер ежедневной публикации ИИ-Сводок. Главный
принцип текущей retrieval-архитектуры: **fresh primary сначала максимально
надёжно обнаруживает потенциально важные события, а строгая редакционная
фильтрация применяется после discovery**. Для этого 12-search primary budget
распределяется детерминированно между обязательными направлениями, а лимит
search operations отделён от навигационных hosted tool calls.

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
- `fixtures/research/.runtime/` — ignored доверенный runtime ingress fresh
  primary/hybrid research в существующий generator; содержимое не коммитится;
- `specs/` — канонические редакционные и технические контракты;
- `scripts/primary_recall_search.py` — deterministic primary orchestrator;
- `scripts/` — production, recovery, hybrid completeness, cleanup и validators;
- `tests/` — офлайн-регрессии;
- `preview/` — временные диагностические результаты production/CI, в Git не
  входят;
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
**ровно 12 обязательных one-search Responses calls**. Каждый pass обязан
завершить ровно одну `action.type=search` и один логический search query. Hard
cap primary остаётся **12 search operations**.

`max_tool_calls=1` больше не используется как эквивалент search-бюджета:
`open_page` и `find_in_page` тоже являются hosted tool calls. После единственного
search primary-pass может использовать до трёх навигационных действий для
проверки даты и фактов найденного источника. Диагностика отдельно считает
search operations, logical queries, total `web_search_call` items и navigation
items. Второй search или batched multi-query считается нарушением контракта.

Responses-output ceiling для каждого Primary pass равен **6000 tokens**. Это запас для reasoning и завершения строгого JSON после search/navigation, а не дополнительный search-бюджет; лимит остаётся ровно один search operation на pass. Старый потолок 3500 был повышен после live-smoke 2026-08-14, где финальный broad pass успел выполнить search и три navigation action, но API завершил ответ как `incomplete / max_output_tokens`.

Фиксированная матрица:

1. `global_breaking` — широкий мировой discovery;
2. `major_agencies` — дополнительный high-signal route по Bloomberg и FT;
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

`global_breaking` и `independent_missing_events` являются source-neutral broad
catch-all проходами без API domain filter. `major_agencies` сохраняет отдельный
`bloomberg.com` + `ft.com` high-signal filter; остальные направления также
остаются широкими.

Каноническая continuity-точка остаётся фактическим `search_cutoff_at`
последнего успешно опубликованного выпуска. Новый pre-research cutoff остаётся
правой границей и авторитетным текущим временем. Fresh Primary дополнительно
строит **effective discovery window**, начиная максимум на 24 часа раньше
continuity anchor. Этот bounded overlap предназначен только для healing крупных
пропусков предыдущего выпуска. Archive anchor назад не двигается, exact source
URL уже опубликованных сюжетов отсекаются до merge, а downstream semantic
archive dedupe остаётся обязательным. События за пределами 24-часового overlap
не воскресают бесконечно.

Effective window имеет две роли. Первые 24 часа от effective start до continuity
anchor являются **healing overlap**, а весь window остаётся допустимой границей
кандидатов. Но Web Search ranking больше не пытается кодировать эти границы
календарными датами. Primary, Hybrid и Coverage используют короткие date-free
relative-freshness queries (`latest`/`recent`/`current`/`breaking`), после чего
фактическая дата/timestamp источника строго валидируется против полного effective
window. Так overlap остаётся доступен для healing, а слово `latest` не получает
ложный статус редакционного фильтра.

Broad safety nets `global_breaking` и `independent_missing_events` не имеют API
domain filter. `major_agencies` остаётся отдельным дополнительным sweep по
`bloomberg.com` + `ft.com`. Это ranking-шансы, а не whitelist кандидатов или
издательская квота; остальные Primary directions также остаются широкими.

Wikipedia и Reddit не являются допустимым основным подтверждением свежего
новостного события. ArXiv остаётся нормальным первоисточником действительно
значимого исследования, но не должен вытеснять свежие product, infrastructure,
business, security, legal и policy события.

Primary использует **discovery-first** семантику. Потенциально значимое свежее
и проверяемое событие сохраняется как `consider`, если его финальная
редакционная значимость ещё не очевидна. Агрессивно отсекаются лишь очевидное
вне effective window, уже опубликованные дубли, старые перепечатки без update,
не-ИИ материалы, слабые/непроверяемые источники и явный шум. Затем все
кандидаты проходят существующий `story_coverage.merge_candidates`: window,
freshness, verification, legal, curiosity и URL/semantic dedupe.

Обычный `maximum_candidates` **не применяется по мере выполнения слотов**.
Каждый обязательный pass сначала получает место в расширенном validated and
deduplicated discovery-pool. Только после завершения всех 12 направлений код
применяет финальный cap глобально: сначала сохраняет сильнейший уникальный вклад
каждого направления, затем заполняет оставшиеся места общим ранжированием. Это
предотвращает ситуацию, когда первые широкие проходы занимают все места до
China/Asia, Russia, security, legal или missing-events. Это fairness retrieval-
пула, а не квота на публикацию. Diagnostics отдельно сохраняют размер полного
validated pool и события, отброшенные только финальным cap.

Два China/Asia-прохода являются намеренным контрактом. Regression-эксперимент
на историческом окне 2026-08-08 02:48:25+03:00 → 2026-08-11
02:50:46+03:00 показал: одна широкая regional-проверка обнаружила 5 из 6
контрольных событий, но пропустила Apple/Qwen integration. Отдельный
`china_asia_integrations` pass поднял шестое событие без увеличения бюджета.
Fixture: `fixtures/recall/2026-08-11.json`.

Второй обязательный regression fixture: `fixtures/recall/2026-08-12.json`.
Он фиксирует production run `31548550639`, где все 12 search actions завершились
с ложным нулевым candidate pool, после чего legacy generator отверг fresh
runtime research-input. MUST_DISCOVER-контроли включают свежие Reuters-сюжеты
IBM/Together AI/Nvidia, Nvidia Nemotron/NeMo и CoreWeave. Там же закреплён
bounded backfill-контроль Meta Muse Glimmer.

Live run `31566813147` выявил следующий класс проблемы: все 12 primary searches,
editorial и coverage завершились, но `major_agencies` не имел ни одного
consulted source, а найденный пул был практически целиком low-signal
Wikipedia/Reddit/arXiv. Поэтому перед publication normalizer выполняет
**source-health gate**: `major_agencies` обязан иметь минимум один consulted
source, а по всем двенадцати pass вместе требуется минимум два consulted URL вне
Wikipedia, Reddit и arXiv. Это не новый глобальный whitelist и не квота на
кандидатов; это минимальная защита от технически completed, но очевидно
деградировавшего retrieval.

Тот же run выявил metadata-seam доверенного runtime ingress. Legacy generator
видит внутренний `--research-input` и изначально записывает
`editorial_from_saved_research`, хотя search только что был выполнен Primary
Recall. Перед artifact validation normalizer для доказанного fresh Primary
(`research.mode=primary_recall_v2`, ровно 12 search operations) канонизирует
`pipeline=primary_recall_v2_then_editorial` и
`research.settings.source=trusted_runtime_primary_recall`. Caller-supplied
recovery input этот rewrite не получает.

Все 12 проходов обязательны. Если любой Responses call технически не завершил
ровно один search operation или сформировал больше одного logical query, fresh
primary завершается красным. Такой сбой нельзя превращать в «low news volume».
Успешно завершённый pass вправе вернуть ноль кандидатов. Диагностика сохраняет
actual queries, consulted sources, raw candidates, model rejections и validator
rejections каждого направления.

Primary сохраняет:

- `preview/production-daily/primary-recall-research-<DATE>.json` —
  диагностическая копия fresh research;
- `fixtures/research/.runtime/primary-recall-research-<DATE>.json` — ignored
  доверенный runtime input для existing generator/editorial;
- `preview/production-daily/primary-recall-<DATE>.json` — полная траектория
  матрицы и бюджета;
- `preview/<DATE>/primary-recall.json` — копия diagnostics внутри release
  artifact после генератора.

`run_digest_preview.py` передаёт новый research существующему
`generate_digest_preview.py` через `--research-input`, а не дублирует editorial
pipeline. Legacy security guard не ослабляется: произвольный preview path всё
ещё запрещён. Только internally generated ignored `.runtime` input может
пронести сохранённый effective overlap-window через sanitation/editorial
validation. Caller-supplied `--research-input` остаётся признаком recovery или
editorial-only rerun и полностью пропускает fresh paid primary.

### 2. Hybrid completeness v1

После **свежего** Primary Recall v2 запускается независимый
`hybrid_search_completeness.py`. Внутренне injected primary research-input не
считается recovery и поэтому разрешает этот один completeness-pass; любой
caller-supplied `--research-input` hybrid пропускает.

Три фиксированных прохода выполняются всегда и получают ровно по одной search
operation и одному logical query:

1. `models_products_research`;
2. `infrastructure_business`;
3. `safety_policy_regions`.

После трёх проходов код считает тематическое покрытие объединённого primary +
completeness пула. Если целый кластер пуст, разрешается один `adaptive_gap`.
Поэтому ordinary completeness budget равен **3 searches**, absolute hard cap —
**4 searches**. API domain filter отсутствует намеренно. Как и primary, каждый
hybrid pass может использовать до трёх navigation tool actions после своего
единственного search для source verification.

Hybrid `_time_hint` детерминированно сдвигает query start на 24 часа относительно
effective start, то есть обратно к continuity anchor. Поэтому даты поисковой
строки относятся к основному continuity-периоду; более ранний healing overlap
остаётся допустимым только для случайно найденного важного пропуска и не должен
доминировать ranking.

Все NEW-only hybrid candidates проходят те же строгие проверки. Editorial
повторяется только если принят хотя бы один кандидат. Перед rerun primary
artifact сохраняется снимком; если rerun падает, он восстанавливается.
Diagnostic merged research остаётся в `preview/production-daily/`, а рабочая
копия для rerun пишется в ignored trusted `fixtures/research/.runtime/`.
Внутренний Primary Recall `--research-input` заменяется runtime merged path, а
не дублируется в argv.

### 3. Диагностика hybrid

Каждый запуск сохраняет:

- `preview/<DATE>/hybrid-completeness.json`;
- `preview/production-daily/hybrid-completeness-<DATE>.json`;
- при принятых NEW-only кандидатах диагностический
  `preview/production-daily/hybrid-completeness-merged-<DATE>.json`;
- рабочую ignored runtime-копию merged research в
  `fixtures/research/.runtime/`.

Report фиксирует версию стратегии, фактические запросы и источники, completed
search count, total/navigation tool items, cluster counts, adaptive decision,
accepted/rejected candidates и факт editorial rerun.

## Fallback coverage для короткого/нулевого пула

`ensure_story_coverage.py` остаётся последним тяжёлым fallback. Если после
primary + hybrid выпуск не достигает обычной цели, запускаются шесть
обязательных one-search направлений с общим потолком **до 7 coverage search
operations**, где седьмой слот резервируется для retry первой технически
незавершённой проверки.

Production targeted passes получают одну search operation и до трёх navigation
tool calls для проверки найденных страниц. Это не расширяет search budget.
Исторические multi-search callers сохраняют прежний hard `max_tool_calls` cap и
не получают скрытого navigation allowance. Query discipline у Coverage та же,
что у Primary/Hybrid: search сначала ранжирует основной continuity-период после
первых 24 часов healing overlap, а полное effective window остаётся границей
пригодности кандидата.

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

Потолки считаются только по завершённым `action.type=search` operations:

- Primary Recall v2: ровно 12 для fresh production;
- hybrid completeness: обычно 3, максимум 4;
- fallback coverage: максимум 7, только если итог после primary + hybrid
  короткий/нулевой.

Формула production-контракта: **12 primary + до 4 hybrid + до 7 coverage**.
Теоретический worst case: **23 search operations**. Navigation tool calls
увеличивают общее число hosted tool invocations, но не этот поисковый потолок.
Primary v2 повышает recall перераспределением существующего search budget, а не
скрытым увеличением поисковых расходов.

## Recovery

Ручной `workflow_dispatch`: `publish` — по умолчанию `false`; необязательный
`recovery_run_id` позволяет явно выбрать сохранённый production artifact.
Recovery без явного ID предпочитает наиболее полный artifact той же даты и не
повторяет уже оплаченные стадии без необходимости.

- готовый выпуск может быть только redeployed;
- готовый текст не требует повторного text API;
- fresh Primary Recall v2 получает hybrid один раз;
- caller-supplied `--research-input` пропускает fresh primary и hybrid;
- internally generated `.runtime` primary research-input не считается recovery;
- primary/hybrid diagnostics и объединённый candidate pool остаются частью
  production artifact;
- завершённый fallback audit и актуальный sentinel переиспользуются;
- partial fallback продолжает только незавершённые направления;
- доказанный zero-pool `editorial_stop` переиспользуется без новой оплаты;
- artifact с `artifact-normalization.json.status=error` или
  `artifact-validation.json.status=error` **не переиспользуется**;
- сохранённый artifact с `primary-recall.json` обязан повторно пройти current
  source-health gate; это правило действует и для `full` artifact, поэтому
  поздний failed run не получает привилегию только за полноту файлов.

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

## Source-focused recall после production 2026-08-13 и 2026-08-14

Regression fixture `fixtures/recall/2026-08-13.json` фиксирует run
`31652757802`: candidate pool содержал 4 события и editorial опубликовал все 4,
поэтому пропуски локализованы в discovery. Независимые source-focused запросы по
тому же effective window восстановили пять controls: Pixel 11/Gemini, Nebius,
River AI, IBM/Together AI и Nvidia Nemotron.

Свежий production 14 августа выявил следующий класс miss: все 12 Primary, четыре
Hybrid и шесть Coverage searches технически завершились, однако почти все
фактические query использовали даты всего расширенного effective window, включая
24-часовой healing overlap. Ranking насыщался старыми материалами, а несколько
свежих событий основного continuity-периода не попали в candidate pool. Кроме
того, `global_breaking` и `major_agencies` оба были Reuters-focused, поэтому
high-signal slots частично повторяли один source-ranking bias.

Primary search budget остаётся 12, но routing теперь разделён без дублирования:
`global_breaking` использует source-neutral funding/acquisition/M&A/major-business
query внутри `reuters.com` API filter, `major_agencies` использует source-neutral
major-AI query внутри `bloomberg.com` + `ft.com` filter,
`independent_missing_events` делает source-neutral consumer-AI / major technology
/ policy sweep внутри `apnews.com` + `ap.org` filter после просмотра
существующего pool. Это source routing для ranking, не whitelist кандидатов.
`models_products_agents` также учитывает крупные consumer-device/OS/service
launches, если AI materially part of launch.

Primary, Hybrid и fallback Coverage используют одинаковую continuity-first query
discipline: первые 24 часа effective window до continuity anchor являются
healing overlap, а поисковая строка прежде всего использует календарные даты
основного периода после anchor до текущего cutoff. Кандидаты из overlap не
запрещены и всё ещё могут восстановить крупный пропуск предыдущего выпуска.
Queries остаются короткими natural-language фразами, ориентир 6–18 значимых
слов, без `after:`, `before:`, `site:`, длинных `OR`-цепочек, скобок и огромных
entity/domain lists. `general_coverage_gaps` использует существующий API domain
filter вместо ручного `site:`-мегазапроса.

Для modern `primary-recall.json` с `search_window` source-health дополнительно
требует хотя бы одно свежее in-window Reuters/AP/Bloomberg/FT evidence среди
`global_breaking`, `major_agencies`, `independent_missing_events`. Dated agency
URL или verified in-window agency candidate считается evidence; stale author,
newsletter, event или old document page не считается. Legacy diagnostics без
`search_window` сохраняют backward compatibility. Search ceiling не меняется:
12 Primary + до 4 Hybrid + до 7 Coverage = максимум 23 operations.


## Hygiene search diagnostics

Перед сохранением Primary, Hybrid и Coverage diagnostics URL, возвращённые search provider, очищаются от временных credential/token/signature query-параметров, включая AWS signed URL. Домен, путь и несекретные параметры сохраняются. Artifact secret-scanner остаётся fail-closed и не получает исключений для подписанных URL.


### Проверенный relative-freshness retrieval

Эксперимент 2026-08-14 на production-модели `gpt-5.6-terra` показал: явные
календарные даты в Web Search query ухудшают ranking и могут приводить к
false-zero. Поэтому Primary, Hybrid, Coverage и финальный zero-pool sentinel
используют date-free `latest`/`recent`/`current`/`breaking` запросы. Это только
ranking hint: фактическая дата/timestamp источника по-прежнему строго проверяется
против полного effective window. Broad safety nets не привязаны к одному
издателю. Если Hybrid добавил валидный candidate, но immediate editorial rerun
упал, объединённый pool всё равно передаётся Coverage.


Source-health после перехода на source-neutral routing проверяет свежую Reuters/AP/Bloomberg/FT evidence по **всей 12-pass Primary matrix**, а не только в `global_breaking`/`major_agencies`/`independent_missing_events`: тематический pass вправе первым обнаружить сильный agency-материал. При этом `major_agencies` всё равно обязан завершить свою search operation и иметь хотя бы один consulted source, а общий anti-junk gate по источникам не ослабляется.

## Recovery платных стадий и обложки

Успешный `Validate publishable story count and short digest marker` фиксирует
текстовый paid checkpoint. Ошибка на обложке или любом более позднем шаге не
разрешает автоматически повторять Primary/Hybrid/Coverage/editorial: следующий
run должен выбрать сохранённый artifact completeness rank 2 и продолжить с
Image API. После валидной обложки recovery использует image-complete artifact и
тоже не вызывает Images API заново. Artifact upload выполняется `if: always()`,
поэтому поздняя красная стадия не уничтожает уже оплаченный результат.

`generate_image_preview.py` разделяет идентификаторы: обязательный
`image_request_id`, опциональный `source_editorial_request_id` и provider
`openai_request_id` (`x-request-id`, если он есть). Отсутствующий editorial ID у
recovery-артефакта является допустимым provenance gap, а не image-preflight
ошибкой. Настоящие сбои классифицируются как `image_preflight`,
`image_api_transport`, `image_api_http` или `image_api_response`. Один запуск
обложки делает максимум один Images API POST и не имеет внутреннего retry-loop.
