# Архитектура проекта ИИ-Сводки

Этот файл является каноническим подробным описанием текущей архитектуры
репозитория `Herurg123/ai-svodki-ia`. README-файлы дают короткую навигацию, а
`AGENTS.md` задаёт обязательные правила изменений. Если подробное описание
системы расходится с README, исправляется эта архитектура и затем entry-point
README; если изменение затрагивает обязательный запрет или safety invariant,
одновременно обновляется соответствующий `AGENTS.md`.

## 1. Границы системы

Проект состоит из двух связанных, но технически независимых контуров и отдельной
maintenance-операции над уже опубликованным FTP `video/`. Ранее существовавший
Video → RSS post-publication bridge закрыт и сохранён только как inert archive.

### 1.1. Основной GitHub production

Основной контур формирует ежедневную ИИ-Сводку:

```text
scheduled/manual trigger
  -> previous-release / recovery gate
  -> Primary Recall
  -> Source Pulse v1.1 fixed-source supplemental discovery
  -> deterministic Source Freshness Proof for trusted Primary + Pulse research
  -> first editorial
  -> conditional agency discovery rescue
  -> Source Freshness Proof for rescue additions
  -> saved Source Pulse snapshot/fusion reuse
  -> Hybrid completeness
  -> editorial rerun when rescue/Hybrid adds a candidate
  -> fallback Coverage when required
  -> Source Freshness Proof for merged trusted research
  -> final editorial when Coverage adds a candidate
  -> cover
  -> site/RSS/sitemap
  -> validators
  -> commit to main
  -> FTP deploy of posts/
```

Source Pulse v1.1 intentionally supplements fresh Primary **before the first
editorial call**. This placement allows the second discovery plane to influence
the normal editorial selection without introducing a dedicated extra model call.
The later Hybrid stage reuses the saved Pulse snapshot only for fusion diagnostics
and never silently repolls the mutable source set.

Production работает из GitHub Actions, хранит результаты в репозитории и
использует `posts/` как публичный deploy tree.

### 1.2. Локальный NotebookLM-video downstream

`automation/notebooklm-video/` находится в том же репозитории только для общей
версии исходников, документации и понимания связей. Он:

- запускается на Windows-машине пользователя, а не в nightly production;
- читает уже опубликованный выпуск через RSS;
- автоматизирует NotebookLM через отдельный Яндекс.Браузер/Playwright профиль;
- скачивает MP4;
- создаёт PNG первого кадра;
- при включённой настройке доставляет media только в FTP-каталог `video`.

Video runtime не является prerequisite, stage, fallback или recovery-компонентом
основного production. Ошибка video worker не должна менять статус ежедневной
ИИ-Сводки и не должна блокировать её публикацию.

### 1.3. RSS boundary и архив Video → RSS

`posts/rss.xml` является article/image publication surface. Активные production
workflow и scripts не должны использовать RSS как канал доставки локальных видео
и не должны добавлять туда локальные video payloads или ссылки, включая:

```text
/posts/video/
medium="video"
type="video/*"
```

Контролируемый эксперимент выпуска `2026-08-27`, который добавлял Media RSS
`media:group` после появления публичной пары MP4+PNG, закрыт. Эксперимент не дал
нужной нативной публикации видео в Дзене, поэтому его production workflow,
script, tests и специальная retention-политика Actions runs удалены из active
paths.

Для сохранения наработки точные исходники перенесены в
`automation/archive/video-rss-enrichment-2026-08/`. Этот каталог reference-only:
он не находится в `.github/workflows/`, `automation/scripts/` или
`automation/tests/`, не импортируется active runtime и не участвует в cron/test
discovery. Повторное использование требует нового изолированного эксперимента,
актуальной проверки платформы, architecture review и отдельного PR.

### 1.4. FTP video retention maintenance

Удаление старых MP4/PNG не является частью RSS semantics и не зависит от наличия
video metadata в content или RSS. В `repository-cleanup.yml` существует отдельный
downstream job, который после успешной основной cleanup-цепочки работает только с
уже опубликованным FTP-каталогом `video`.

Канонический entrypoint — `automation/scripts/cleanup_video_ftp.py`. Он получает
тот же `reference_date` и `retention_days`, которые использовала public cleanup,
входит только в hard-coded remote directory `video` и управляет только basename,
строго совпадающими с:

```text
ai-svodka-YYYY-MM-DD.mp4
ai-svodka-YYYY-MM-DD.png
```

При `cutoff_date = reference_date - retention_days` удаляется только media с
`publication_date < cutoff_date`; сама граничная дата сохраняется. Пара MP4+PNG
не является prerequisite: просроченный orphan одного из двух типов удаляется
независимо. Неизвестные файлы, расширения и каталоги игнорируются. Весь managed
inventory валидируется до первого DELETE; после apply выполняется повторный
listing и проверяется отсутствие всех удалённых targets.

## 2. Источники истины

| Область | Канонический источник |
|---|---|
| Подробная архитектура | `automation/ARCHITECTURE.md` |
| Репозиторные правила изменений | `/AGENTS.md` |
| Правила video-подпроекта | `automation/notebooklm-video/AGENTS.md` |
| Пользовательская карта проекта | `/README.md` |
| Карта production automation | `automation/README.md` |
| Editorial policy | `automation/specs/editorial-policy.md` и соответствующие validators |
| Production configuration | `automation/config/production-daily.json` и связанные config files |
| Независимые аудиты | `automation/audits/independent-audit-journal.md` |
| Controlled experiments | `automation/audits/experiments/` |
| Retrieval regression contracts | `automation/fixtures/recall/` |
| Video runtime/deployment | `automation/notebooklm-video/README.md` и `DEPLOYMENT.md` |
| RSS no-video boundary | `automation/tests/test_rss_video_boundary.py` |
| Retired Video → RSS reference | `automation/archive/video-rss-enrichment-2026-08/` |
| FTP video retention | `.github/workflows/repository-cleanup.yml` и `automation/scripts/cleanup_video_ftp.py` |

Документация должна описывать реализованный код, а не предполагаемую будущую
схему.

## 3. Репозиторная структура

### 3.1. `automation/`

- `content/YYYY-MM-DD/` хранит структурированные материалы выпусков;
- `archive/index.json` хранит редакционную память, dedupe и material-update
  context;
- `archive/search-baselines/` хранит manifests постоянных search baselines;
- `archive/video-rss-enrichment-2026-08/` хранит inert reference-only snapshot
  закрытого Video → RSS эксперимента;
- `audits/` хранит независимые проверки и controlled experiments;
- `config/` содержит production/editorial/site/image/Source Pulse config;
- `prompts/` содержит active и исторические prompts;
- `fixtures/recall/` содержит machine-readable retrieval regressions;
- `fixtures/research/.runtime/` является ignored trusted ingress для внутреннего
  fresh research;
- `scripts/` содержит orchestration, retrieval, recovery, publication, cleanup и
  validators, включая `source_pulse_supplement.py`, сохранённый
  `source_pulse_shadow.py` и FTP-retention `cleanup_video_ftp.py`;
- `tests/` содержит основной Python offline regression suite, включая no-video RSS
  boundary;
- `notebooklm-video/` является отдельным локальным downstream-подпроектом;
- `preview/` и `recovery/` являются временными ignored runtime directories.

### 3.2. `posts/`

`posts/` является deployable public tree. Он включает страницы выпусков, RSS,
sitemap, изображения и постоянные assets. `posts/_footer-scr.png` является
постоянным production asset и не относится к dated retention cleanup.

Публичный FTP-каталог `video` не является tracked subtree `posts/` репозитория:
его MP4/PNG создаёт локальный downstream. RSS не используется для доставки этих
video assets и не должен ссылаться на локальный `/posts/video/` payload. Отдельный
retention job может удалять из `video` только строго классифицированные
просроченные MP4/PNG по контракту раздела 1.4; никакой другой FTP path в его
mutation scope не входит.

### 3.3. `.github/workflows/`

Содержит только постоянные production/maintenance/CI workflow. Закрытый
`video-rss-enrichment.yml` не входит в active inventory и хранится только под
`automation/archive/`. One-shot, emergency и patch workflow после выполнения
задачи в постоянном inventory не остаются.

## 4. GitHub Actions

Постоянный workflow inventory состоит из семи файлов.

| Workflow | Ответственность | Может менять production state |
|---|---|---|
| `pr-gate.yml` | Always-on PR routing и единый required gate | Нет |
| `ci.yml` | Main CI, offline проверки основного production-кода | Нет |
| `video-ci.yml` | Video CI, dependency-free offline проверки video-подпроекта | Нет |
| `daily-production.yml` | Ежедневный retrieval/editorial/build/publish pipeline | Да, по production contract |
| `deploy-posts.yml` | FTP-синхронизация точного `posts/` выбранного commit | Да, только public deploy |
| `repository-cleanup.yml` | 32-day repository/public cleanup и отдельная FTP-video retention стадия | Да, только documented retention scope |
| `repository-hygiene.yml` | Уборка безопасно классифицированных GitHub objects | Да, только GitHub-object policy scope |

### 4.1. PR Gate

`pr-gate.yml` запускается для каждого pull request в `main` без `paths` filter.
Он сравнивает base/head commit, классифицирует changed paths и вызывает reusable
domain workflows:

- Main CI для production/shared paths;
- Video CI для `automation/notebooklm-video/**` и `video-ci.yml`;
- оба домена для изменения самого `pr-gate.yml` и mixed PR.

Финальный job всегда называется `Required PR Gate`. Именно он является
стабильным required status ruleset. Path-dependent Main CI и Video CI нельзя
делать required напрямую: когда workflow пропущен по path routing, required
status не появляется как успешный check и merge может зависнуть.

### 4.2. Main CI

Main CI является reusable workflow для PR Gate и сохраняет `workflow_dispatch`
и push-to-main проверку. Его push path filter исключает:

- `automation/notebooklm-video/**`;
- `.github/workflows/video-ci.yml`.

Video-only PR не становится зависимым от Python production CI. Изменения общей
архитектуры, production workflow/tests и других main-domain paths, включая RSS
boundary и FTP-video retention, маршрутизируются PR Gate в Main CI.

Main CI выполняет compileall, Python unit regressions и ключевые validators
editorial/archive/production/RSS/sitemap/structured-data contracts.

### 4.3. Video CI

Video CI является reusable workflow для PR Gate и сохраняет manual/push режимы.
На PR он вызывается только для video-domain changes. Текущий CI намеренно
dependency-free: он не выполняет `npm install` или `npm ci`, не запускает
браузер, NotebookLM, FTP или Windows DPAPI. Он использует Node.js для syntax
checks и offline contract smoke tests, которые работают только со встроенными
Node modules и committed files.

Полное npm-дерево video runtime при этом воспроизводимо: `package.json` и
committed `package-lock.json` являются одной версионируемой единицей, а локальные
setup/dependency entrypoints устанавливают зависимости через `npm ci`. Изменение
npm-зависимостей должно обновлять lockfile в том же PR и отдельно доказывать
чистую `npm ci` установку; обычный Video CI от npm registry по-прежнему не зависит.

### 4.4. Enforcement CI boundary

`automation/tests/test_video_ci_boundary.py` проверяет разделение production/video,
`automation/tests/test_rss_video_boundary.py` запрещает video payload в committed
RSS и повторное подключение закрытого Video → RSS production path, а
`automation/tests/test_pr_gate_and_main_protection.py` проверяет always-on gate,
reusable domain CI, узкий automated-writer secret scope и canonical ruleset.
`automation/tests/test_video_ftp_cleanup.py` проверяет strict 32-day cutoff,
dry-run/apply, orphan semantics, MLSD/NLST listing, pre-delete validation,
post-delete verification и hard `video` boundary без RSS/local-runtime dependency.

`automation/notebooklm-video/tests/video-boundary-smoke.js` проверяет hard FTP
boundary и ignore rules. `lockfile-contract-smoke.js` проверяет синхронизацию
`package.json`/`package-lock.json` и локальный `npm ci` contract.

### 4.5. Защита `main` и automated writers

Канонический desired ruleset хранится в
`automation/config/main-branch-ruleset.json`. Он нацелен только на default branch
и требует:

- pull request для обычных изменений;
- успешный `Required PR Gate` на актуальном base;
- linear history с merge через squash/rebase;
- resolved review threads;
- запрет удаления `main` и force-push.

Число обязательных approvals равно 0: репозиторий персональный, поэтому правило
не должно требовать невозможного self-approval. Bypass actor только `DeployKey`.
Нельзя заменять его repository-admin role или всем GitHub Actions App: это
расширило бы прямой write bypass на несвязанные workflows.

Два легитимных automated writer контура имеют direct-push по архитектурной
необходимости:

- `daily-production.yml` публикует validated release;
- `repository-cleanup.yml` фиксирует validated retention cleanup.

Только их финальные commit steps получают secret `MAIN_PUSH_DEPLOY_KEY` и
вызывают `automation/scripts/push_protected_main.sh HEAD:main`. Helper отвергает
другой refspec, использует отдельный SSH key только на время push и pin'ит
официальный GitHub Ed25519 host key.

FTP-video retention не является ещё одним Git writer: его job получает только
`contents: read`, использует существующие FTP credentials непосредственно в
cleanup step и не получает `MAIN_PUSH_DEPLOY_KEY`.

Пока deploy-key secret не установлен и ruleset ещё не активирован, helper может
использовать существующий authenticated `origin` как переходный fallback. Перед
активацией ruleset write deploy key и repository secret обязаны быть установлены;
после активации fallback больше не является рабочим путём. Repository hygiene,
Video CI, Main CI, PR Gate и deploy-posts этот secret не получают.

### 4.6. RSS no-video safety

Удаление Video → RSS bridge является production boundary, а не временным
отключением schedule. Ни один active workflow не должен:

- запускать archived `video_rss_enrichment.py`;
- проверять `/posts/video/` ради последующей мутации RSS;
- коммитить video metadata в `posts/rss.xml`;
- получать `MAIN_PUSH_DEPLOY_KEY` ради RSS-only video enrichment.

Committed RSS проверяется offline regression test на отсутствие local video URLs,
`medium="video"` и MIME `video/*`. Архив может содержать эти строки, потому что
он сознательно хранит историческую реализацию, но archive path не входит в active
workflow/runtime/test discovery.

### 4.7. FTP video cleanup ordering и safety

`repository-cleanup.yml` сначала выполняет обычный repository/public cleanup и,
если public tree изменился, его deploy. Job `video_ftp_cleanup` запускается только
когда `cleanup` успешен и `deploy` либо успешен, либо закономерно skipped из-за
отсутствия public изменений. Если public deploy упал, дополнительная удалённая
mutation в `video/` не выполняется.

Manual `workflow_dispatch` сохраняет общий `apply=false` default: FTP-video job в
этом режиме только строит remote plan. Scheduled cleanup и manual `apply=true`
передают `--apply`. Cleanup получает exact `reference_date` из результата public
cleanup и тот же `retention_days`, поэтому tracked content, public pages и FTP
media не имеют независимых календарных cutoffs.

Remote safety contract:

- FTP directory hard-coded как `video`; пользовательский remote path не принимается;
- MLSD предпочтителен, NLST используется как совместимый fallback;
- DELETE получает только безопасный basename, никогда полный/относительный path;
- managed filename contract ровно `ai-svodka-YYYY-MM-DD.(mp4|png)`;
- невозможная календарная дата в managed-shaped имени блокирует весь apply до
  первого DELETE;
- unknown names, extensions и directories игнорируются;
- после DELETE выполняется повторный listing и presence verification;
- partial remote failure безопасно повторяем: следующий run планирует только
  оставшиеся старые assets;
- скрипт не читает RSS, local worker state или OpenAI API.

## 5. Nightly production и временная непрерывность

Canonical continuity anchor равен `search_cutoff_at` последнего успешно
опубликованного выпуска и никогда не двигается назад.

Fresh discovery может использовать bounded healing overlap до 24 часов перед
anchor, чтобы восстанавливать важные события, пропущенные предыдущим выпуском.
Exact source URL уже опубликованного события отсекается до merge, а downstream
semantic archive dedupe остаётся обязательным.

Exact `search_window.end_at` является authoritative current-time boundary для
Primary, Source Pulse, conditional agency rescue, Hybrid, Coverage и sentinel.
Model/system calendar date не может переопределить эту временную границу.

Retrieval queries используют короткую date-free relative-freshness формулировку.
Exact timestamp window применяется после retrieval как eligibility boundary.

## 6. Retrieval pipeline

### 6.1. Primary Recall

Stable public entrypoint: `automation/scripts/primary_recall_search.py`.
Preserved implementation currently sits behind it as a versioned engine.

Fresh production выполняет ровно 12 mandatory search operations:

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

Каждый mandatory pass выполняет ровно одну `action.type=search` operation и один
logical query. Navigation calls после поиска не считаются дополнительными search
operations. Primary candidate cap применяется после завершения всей матрицы, а
не инкрементально.

`major_agencies` является отдельным Reuters/AP/Bloomberg/FT high-signal route.
Broad catch-all routes остаются source-neutral. China/Asia model и
integration/business routes не схлопываются; Russia остаётся отдельным mandatory
slot.

После того как versioned Primary engine вернул trusted runtime research, public
wrapper запускает Source Pulse v1.1 supplement на том же exact saved window и
только затем возвращает research в `run_digest_preview.py` для Source Freshness
Proof и первого editorial. Search-derived `regional_health` при этом намеренно не
пересчитывается после Pulse promotion.

### 6.2. Conditional agency discovery rescue

После первого editorial и перед Hybrid может выполняться bounded missing-event
rescue. Trigger зависит от технически завершённого `major_agencies` с
`raw_count == 0` или `accepted_count == 0`, а не от общего количества
candidates/stories.

Разрешена максимум одна дополнительная Web Search operation. Текущий provider
route Reuters-only и acceptance требует прямого `reuters.com` primary URL.
Syndication/aggregator URL не заменяет прямой источник. Rescue не повышает
significance и не гарантирует публикацию.

State сохраняется до и после paid call. `search_started` автоматически не
ретраится, потому что consumption единственного search может быть неизвестен.
`search_completed`/`merge_failed` могут продолжить merge из сохранённого response
без второго search.

### 6.3. Source Pulse v1.1 supplemental discovery и shadow fusion

Source Pulse состоит из двух связанных режимов над одним сохранённым snapshot.

**Pre-editorial supplement.** После fresh Primary public wrapper вызывает
`source_pulse_supplement.py`. Он использует тот же фиксированный registry, обычный
bounded HTTPS polling и **0 OpenAI / 0 Web Search operations**. V1.1 сохраняет
hardening исходного collector и добавляет bounded видимую date-association для
реальных article-like HTML containers. JSON-LD, RSS/Atom и `<time datetime>`
семантика v1 сохраняется.

Candidate influence разрешён только по узкому контракту:

- lead обязан иметь fusion disposition `pulse_only`;
- только Tier A с `role=official`;
- Tier B остаётся `lead_only` и никогда не мутирует candidate pool;
- официальный lead URL повторно открывается обычным HTTPS;
- publication evidence обязан детерминированно попадать в exact saved window;
- title/page summary обязан пройти deterministic AI relevance gate;
- candidate входит только как `recommendation=consider`;
- Source Pulse не назначает `include`, legal/curiosity privilege или высокий
  significance; текущий supplemental score консервативно равен 3;
- обычный `story_coverage.merge_candidates` применяет schema/window/exact-URL
  validation и общий candidate cap.

После supplement штатный trusted-runtime Source Freshness Proof **ещё раз**
проверяет уже merged Primary+Pulse research до первого editorial. Следовательно,
внутренний Pulse parser не является публикационным authority и не обходит
существующий freshness fail-closed boundary.

**Поздний shadow/fusion.** Hybrid продолжает вызывать
`source_pulse_shadow.py`, но normal fresh run находит уже сохранённый
`source-pulse-<DATE>.json` и переиспользует snapshot без второго polling. Этот
этап не добавляет новых Pulse candidates. После Hybrid тот же snapshot снова
сравнивается с merged research для `fusion_post_hybrid`.

Search-derived regional gaps сохраняются из Primary и не пересчитываются после
Pulse. Поэтому найденная Pulse новость не может скрыть `asia/russia` Primary gap
и не может подавить существующий fourth-slot Hybrid health check.

Runtime diagnostics в `preview/production-daily/source-pulse-<DATE>.json`
содержат source transport/parser health, v1.1 counters
`parsed_items_before_v11 / parsed_items_after_v11 / dated_items_after_v11 /
undated_items_after_v11 / visible_dates_recovered`, pre-promotion fusion,
per-lead promotion/rejection disposition, page freshness evidence, promoted URLs,
merge rejections, post-promotion fusion, reuse flag и позже post-Hybrid fusion.
Весь `production-daily/` уже входит в обычный Actions artifact.

Source/network/parser/promotion error fail-open только для уже валидного Primary:
ошибка Pulse не должна превращать успешные обязательные Search passes в
production failure. Она обязана остаться в diagnostics. Same-day recovery не
repoll'ит mutable Pulse sources.

### 6.4. Hybrid completeness

Stable public entrypoint: `hybrid_search_completeness.py`.

Hybrid выполняет три fixed one-search passes и может использовать один optional
adaptive/regional health slot. Hard ceiling равен 4 search operations. API domain
filter отсутствует. Russia/Asia health check не является publication quota.

Новые candidates проходят обычную validation/dedupe chain. Editorial rerun
происходит только после реально принятого rescue/Hybrid candidate. Pulse не
требует отдельного rerun, потому что его bounded promotion происходит до первого
editorial. Hybrid failure не должен уничтожать уже пригодный Primary/Pulse/rescue
artifact.

### 6.5. Fallback Coverage

Stable public entrypoint: `ensure_story_coverage.py`.

Coverage содержит шесть mandatory directions и максимум семь search operations.
Седьмой slot является bounded adaptive slot и не превращается в дополнительный
неограниченный поиск. Technical partial/error audit fail-closed. Полностью
завершённый search с пустым publishable pool может завершиться успешным
`editorial_stop` без искусственного наполнения выпуска.

### 6.6. Search ceiling

Текущий theoretical maximum:

```text
12 Primary
+ up to 1 conditional agency discovery
+ up to 4 Hybrid
+ up to 7 Coverage
= 24 Web Search operations
```

Source Pulse не входит в search-operation budget: его collector и page/freshness
verification используют только обычный HTTPS и не вызывают OpenAI/Web Search.
Navigation hosted calls не повышают этот search-operation ceiling. Изменение
ceiling требует отдельного controlled experiment и architecture-wide review.

## 7. Source freshness и editorial

Trusted internal research перед публикацией проходит deterministic Source
Freshness Proof. Для fresh run первый такой gate выполняется после
Primary+Source-Pulse supplement и до первого editorial. Rescue/Hybrid/Coverage
merged inputs проходят тот же proof по существующему rerun contract. Verifier
открывает только уже процитированные candidate URLs, извлекает machine-readable
publication evidence и сравнивает его с exact saved window. `dateModified` не
заменяет publication date.

Outside-window source исключается как stale/old reprint. Отсутствие проверяемой
date evidence блокирует публикацию. Supporting source может стать primary, если
именно он доказывает freshness.

Editorial применяется после discovery/validation. Короткий выпуск допустим:
нельзя вводить искусственные региональные или тематические quotas только ради
числа сюжетов. Source Pulse не имеет отдельной publication quota и не может
обязать editorial выбрать promoted `consider`. Подробные правила находятся в
`specs/editorial-policy.md`.

## 8. Recovery

Stable public recovery entrypoint: `recover_digest_artifact.py`.

Основной принцип: уже успешно оплаченная стадия не повторяется автоматически из-
за ошибки более поздней стадии. Recovery выбирает наиболее полный валидный
same-day artifact и продолжает с первого незавершённого этапа.

Known-bad normalization/validation artifacts не переиспользуются. Modern saved
Primary повторно проходит current source-health. Conditional agency rescue
соблюдает собственную at-most-once state machine. Сохранённый Source Pulse
snapshot считается mutable-source evidence того же artifact и не repoll'ится при
обычном same-day recovery; later fusion использует сохранённый snapshot.

Manual `force_fresh_research=true` является отдельным operator override после
retrieval hotfix. Он не эквивалентен обычному rerun и не является разрешением на
production API spend без явного решения владельца.

## 9. Publication и public deploy

После успешного text/image/site validation формируется `posts/`. Публикуемый
commit является источником для FTP sync; deploy не должен собирать произвольное
локальное состояние поверх другого commit.

`posts/_footer-scr.png` является постоянным asset. Deploy проверяет его remote
presence и при необходимости восстанавливает. Dated cleanup не удаляет этот
файл.

RSS публикует article/image данные основного выпуска. Video assets и их нативная
публикация являются отдельным downstream и не должны изменять RSS. Любое active
production изменение, которое снова добавляет local video payload в
`posts/rss.xml`, считается архитектурным изменением и должно быть заблокировано
current no-video regression contract.

FTP-video cleanup не является publish path: он ничего не создаёт и не меняет в
RSS/content. Это maintenance над уже опубликованными remote media после истечения
retention window.

## 10. Cleanup и repository hygiene

Это два разных механизма.

### 10.1. Content/public/video retention cleanup

32-day cleanup:

- compact'ит старые `automation/content/YYYY-MM-DD/`, сохраняя `meta.json` и
  `stories.json`;
- удаляет expired public dated pages/images согласно validation contract;
- считает `posts/images/` обязательным;
- допускает отсутствие исторического `posts/dzen-test/images/` после исчезновения
  последнего legacy image;
- не использует `.gitkeep` как замену корректной validation semantics;
- после успешной основной cleanup/deploy цепочки независимо чистит FTP `video/`
  от exact-pattern MP4/PNG, дата которых строго раньше общего cutoff.

FTP media не выводятся из RSS и не требуют presence соответствующего RSS item.
Это намеренно делает storage retention независимым от placement semantics.
Scheduled mode применяет удаление автоматически; manual mode по умолчанию dry-run.
Если public deploy нужен и завершился ошибкой, FTP-video cleanup не запускается.

### 10.2. Repository hygiene

Repository hygiene работает с GitHub objects, а не с tracked production files.
Он может удалять только объекты, которые policy доказуемо классифицировал как
safe: stale merged/closed refs, safe artifacts и отдельные orphan workflow
objects/runs.

Специальная retention-политика для runs бывшего `video-rss-enrichment.yml`
удалена из active `repository-hygiene.yml` вместе с закрытием workflow. Её
реализация сохранена только в reference-only архиве и не вызывается ежедневной
hygiene.

Перед destructive phase заново проверяются SHA `main`, актуальная policy и
отсутствие активного Daily production run. Retry разрешён только для idempotent
read-only GET после documented transient transport failures/HTTP
`500/502/503/504`. Destructive DELETE/PUT автоматически не повторяются.

Tracked files, RSS, FTP media, локальный NotebookLM runtime и production API в
mutation scope repository hygiene не входят. Permanent archive branches, `main`,
releases, tags и published/editorial content также не входят в scope
автоматической hygiene mutation.

## 11. Permanent search baseline и audits

Состояние непосредственно до hybrid completeness сохранено навсегда:

- branch `archive/search-baseline-pre-hybrid-2026-08-09`;
- commit `d926a3abf8b9443f58f303d984ef79fdc289fc3e`;
- manifest `automation/archive/search-baselines/2026-08-09-pre-hybrid.md`.

Этот ref нельзя перемещать, repurpose или удалять.

Независимые production-quality наблюдения ведутся в
`audits/independent-audit-journal.md`. Controlled retrieval experiments хранятся
в `audits/experiments/`, regression windows в `fixtures/recall/`.

Один retrieval miss является evidence, но не автоматическим разрешением менять
архитектуру. Сначала формируется независимый reference set, затем bounded
experiment, dependency audit и regression proof.

## 12. Совместимость и versioned реализации

Некоторые stable public files являются wrappers над сохранёнными versioned
implementations, например:

- `primary_recall_search.py` над `primary_recall_search_v2.py`;
- `hybrid_search_completeness.py` над preserved Hybrid implementation;
- `ensure_story_coverage.py` над preserved Coverage implementation;
- `recover_digest_artifact.py` над preserved recovery implementation.

Это не случайные дубликаты. Причины сохранения:

- stable imports для production/tests;
- historical monkeypatch surfaces;
- saved-artifact recovery compatibility;
- source-inspection contract tests, которые защищают search/output budgets;
- возможность semantic overlay без переписывания proven engine в том же change.

Source Pulse v1.1 следует этому же принципу: production semantics добавлены новым
supplement wrapper над hardening v1 collector, а исходный collector/shadow
surface остаётся совместимым для replay, saved snapshots и regression hooks.

Удаление или схлопывание versioned files требует отдельного semantic-neutral
refactor с полным offline regression доказательством. Нельзя одновременно
менять retrieval semantics и compatibility topology, иначе невозможно отделить
регрессию алгоритма от регрессии загрузки/recovery.

## 13. NotebookLM-video подробнее

Video worker использует:

```text
RSS
 -> Windows Task Scheduler
 -> run-worker-hidden.vbs / run-worker.cmd
 -> Node.js worker.js
 -> Yandex Browser + dedicated profile
 -> Playwright CDP
 -> NotebookLM
 -> local MP4
 -> PNG preview via ffmpeg-static
 -> optional FTP video/
```

Runtime state, real config, FTP access, logs, media и browser profile не хранятся
в Git. Локальный `.gitignore` является частью safety contract.

Переносимые npm dependencies являются частью versioned runtime contract:

- `package.json` фиксирует direct dependency versions;
- `package-lock.json` фиксирует полное транзитивное дерево;
- `setup-local.ps1` и `install-ftp-support.cmd` используют `npm ci`, а не
  `npm install`;
- dependency change обязан обновлять manifest и lockfile одним PR и проходить
  clean-install proof;
- обычный Video CI проверяет lockfile contract офлайн и не устанавливает npm
  dependencies.

FTP boundary реализован defense-in-depth:

- example/default `remoteDir` равен `video`;
- worker отвергает другое configured значение;
- FTP runtime явно создаёт/использует `video`;
- worker не должен удалять или модифицировать другие remote paths.

Ошибка локального video worker не должна инициировать recovery основного
production, а repository cleanup/hygiene не должны управлять локальным runtime
state пользователя. Video downstream читает RSS только как источник уже
опубликованного выпуска, но не пишет video metadata обратно в RSS. FTP retention
также не читает локальный runtime: он видит только remote listing `video/` и
удаляет уже опубликованные exact-pattern assets после общего 32-day cutoff.

## 14. Правило изменений архитектуры

Любая material architecture change должна отвечать на четыре вопроса:

1. Какие компоненты и saved artifacts зависят от изменяемой границы?
2. Какие offline regressions доказывают отсутствие побочного изменения?
3. Требуется ли controlled external/retrieval experiment и каким ресурсом он
   выполняется?
4. Какие `ARCHITECTURE.md`, README, AGENTS и contract tests должны измениться в
   том же PR?

Для закрытия Video → RSS dependency audit затрагивает workflow inventory,
protected-main writer scope, committed RSS, Repository hygiene и historical
implementation. Active bridge и его special-run retention удалены, RSS возвращён
к article/image состоянию, а исходники сохранены как inert archive. No-video RSS
regression запрещает обратное подключение без отдельного архитектурного решения.
Nightly retrieval/editorial, search budgets, recovery, FTP-video retention и
локальная native-browser публикация не меняются.

Для FTP-video retention dependency audit показал только maintenance boundary:
`repository-cleanup.yml`, существующие FTP credentials, remote `video/` и общий
32-day cutoff. Workflow inventory, protected-main writer set, RSS/content model,
retrieval/editorial, local video worker и deploy-posts payload не меняются.
Offline fake-FTP regressions проверяют deletion scope и failure semantics; реальный
FTP при разработке не используется.

Для Source Pulse v1.1 dependency audit затрагивает fresh Primary wrapper,
фиксированный source registry, trusted runtime research, Source Freshness Proof,
первый editorial, сохранённый Pulse snapshot и позднюю Hybrid fusion. Paid
Primary/agency/Hybrid/Coverage budgets не меняются. Региональные Search gaps
сохраняются до Pulse, Tier B не получает candidate influence, а normal recovery
переиспользует snapshot. Controlled experiment и regressions сохранены в
`audits/experiments/2026-08-27-source-pulse-v11-supplement.md` и
`tests/test_source_pulse_supplement.py`.

Search/retrieval изменения сначала проверяются на assistant-owned resources.
Production API пользователя не расходуется без явного разрешения.
