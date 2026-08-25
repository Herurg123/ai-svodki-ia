# Архитектура проекта ИИ-Сводки

Этот файл является каноническим подробным описанием текущей архитектуры
репозитория `Herurg123/ai-svodki-ia`. README-файлы дают короткую навигацию, а
`AGENTS.md` задаёт обязательные правила изменений. Если подробное описание
системы расходится с README, исправляется эта архитектура и затем entry-point
README; если изменение затрагивает обязательный запрет или safety invariant,
одновременно обновляется соответствующий `AGENTS.md`.

## 1. Границы системы

Проект состоит из двух связанных, но технически независимых контуров.

### 1.1. Основной GitHub production

Основной контур формирует ежедневную ИИ-Сводку:

```text
scheduled/manual trigger
  -> previous-release / recovery gate
  -> Primary Recall
  -> conditional agency discovery rescue
  -> Source Freshness Proof for rescue additions
  -> Source Pulse v1 shadow snapshot
  -> Hybrid completeness
  -> fallback Coverage when required
  -> Source Freshness Proof
  -> editorial
  -> cover
  -> site/RSS/sitemap
  -> validators
  -> commit to main
  -> FTP deploy of posts/
```

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

Документация должна описывать реализованный код, а не предполагаемую будущую
схему.

## 3. Репозиторная структура

### 3.1. `automation/`

- `content/YYYY-MM-DD/` хранит структурированные материалы выпусков;
- `archive/index.json` хранит редакционную память, dedupe и material-update
  context;
- `archive/search-baselines/` хранит manifests постоянных search baselines;
- `audits/` хранит независимые проверки и controlled experiments;
- `config/` содержит production/editorial/site/image/Source Pulse config;
- `prompts/` содержит active и исторические prompts;
- `fixtures/recall/` содержит machine-readable retrieval regressions;
- `fixtures/research/.runtime/` является ignored trusted ingress для внутреннего
  fresh research;
- `scripts/` содержит orchestration, retrieval, recovery, publication, cleanup и
  validators;
- `tests/` содержит основной Python offline regression suite;
- `notebooklm-video/` является отдельным локальным downstream-подпроектом;
- `preview/` и `recovery/` являются временными ignored runtime directories.

### 3.2. `posts/`

`posts/` является deployable public tree. Он включает страницы выпусков, RSS,
sitemap, изображения и постоянные assets. `posts/_footer-scr.png` является
постоянным production asset и не относится к dated retention cleanup.

### 3.3. `.github/workflows/`

Содержит только постоянные production/maintenance/CI workflow. One-shot,
emergency и patch workflow после выполнения задачи в постоянном inventory не
остаются.

## 4. GitHub Actions

Постоянный workflow inventory состоит из семи файлов.

| Workflow | Ответственность | Может менять production state |
|---|---|---|
| `pr-gate.yml` | Always-on PR routing и единый required gate | Нет |
| `ci.yml` | Main CI, offline проверки основного production-кода | Нет |
| `video-ci.yml` | Video CI, dependency-free offline проверки video-подпроекта | Нет |
| `daily-production.yml` | Ежедневный retrieval/editorial/build/publish pipeline | Да, по production contract |
| `deploy-posts.yml` | FTP-синхронизация точного `posts/` выбранного commit | Да, только public deploy |
| `repository-cleanup.yml` | 32-day content/public cleanup с validation | Да, только documented retention scope |
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
архитектуры, production workflow/tests и других main-domain paths маршрутизируются
PR Gate в Main CI.

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
а `automation/tests/test_pr_gate_and_main_protection.py` проверяет always-on gate,
reusable domain CI, узкий automated-writer secret scope и canonical ruleset.

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

Два легитимных automated writer контура остаются direct-push по архитектурной
необходимости: `daily-production.yml` публикует validated release, а
`repository-cleanup.yml` фиксирует validated retention cleanup. Только их финальные
commit steps получают secret `MAIN_PUSH_DEPLOY_KEY` и вызывают
`automation/scripts/push_protected_main.sh HEAD:main`. Helper отвергает другой
refspec, использует отдельный SSH key только на время push и pin'ит официальный
GitHub Ed25519 host key.

Пока deploy-key secret не установлен и ruleset ещё не активирован, helper может
использовать существующий authenticated `origin` как переходный fallback. Перед
активацией ruleset write deploy key и repository secret обязаны быть установлены;
после активации fallback больше не является рабочим путём. Repository hygiene,
Video CI, Main CI, PR Gate и deploy-posts этот secret не получают.

## 5. Nightly production и временная непрерывность

Canonical continuity anchor равен `search_cutoff_at` последнего успешно
опубликованного выпуска и никогда не двигается назад.

Fresh discovery может использовать bounded healing overlap до 24 часов перед
anchor, чтобы восстанавливать важные события, пропущенные предыдущим выпуском.
Exact source URL уже опубликованного события отсекается до merge, а downstream
semantic archive dedupe остаётся обязательным.

Exact `search_window.end_at` является authoritative current-time boundary для
Primary, conditional agency rescue, Hybrid, Coverage и sentinel. Model/system
calendar date не может переопределить эту временную границу.

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

### 6.2. Conditional agency discovery rescue

После Primary и до Hybrid может выполняться bounded missing-event rescue.
Trigger зависит от технически завершённого `major_agencies` с `raw_count == 0`
или `accepted_count == 0`, а не от общего количества candidates/stories.

Разрешена максимум одна дополнительная Web Search operation. Текущий provider
route Reuters-only и acceptance требует прямого `reuters.com` primary URL.
Syndication/aggregator URL не заменяет прямой источник. Rescue не повышает
significance и не гарантирует публикацию.

State сохраняется до и после paid call. `search_started` автоматически не
ретраится, потому что consumption единственного search может быть неизвестен.
`search_completed`/`merge_failed` могут продолжить merge из сохранённого response
без второго search.

### 6.3. Source Pulse v1 shadow

`source_pulse_shadow.py` работает после conditional rescue/freshness и до Hybrid.
Текущий режим production-shadow:

- `candidate_influence=false`;
- zero OpenAI calls;
- zero Web Search operations;
- source/network/parser failure fail-open;
- сохранённый snapshot не repoll'ится молча при same-artifact recovery.

Pulse даёт diagnostics `pulse_only / both / search_only` и source-health, но не
добавляет, не удаляет и не ранжирует candidates.

### 6.4. Hybrid completeness

Stable public entrypoint: `hybrid_search_completeness.py`.

Hybrid выполняет три fixed one-search passes и может использовать один optional
adaptive/regional health slot. Hard ceiling равен 4 search operations. API domain
filter отсутствует. Russia/Asia health check не является publication quota.

Новые candidates проходят обычную validation/dedupe chain. Editorial rerun
происходит только после реально принятого нового candidate. Hybrid failure не
должен уничтожать уже пригодный Primary/rescue artifact.

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

Navigation hosted calls не повышают этот search-operation ceiling. Изменение
ceiling требует отдельного controlled experiment и architecture-wide review.

## 7. Source freshness и editorial

Trusted internal research перед публикацией проходит deterministic Source
Freshness Proof. Verifier открывает только уже процитированные candidate URLs,
извлекает machine-readable publication evidence и сравнивает его с exact saved
window. `dateModified` не заменяет publication date.

Outside-window source исключается как stale/old reprint. Отсутствие проверяемой
date evidence блокирует публикацию. Supporting source может стать primary, если
именно он доказывает freshness.

Editorial применяется после discovery/validation. Короткий выпуск допустим:
нельзя вводить искусственные региональные или тематические quotas только ради
числа сюжетов. Подробные правила находятся в `specs/editorial-policy.md`.

## 8. Recovery

Stable public recovery entrypoint: `recover_digest_artifact.py`.

Основной принцип: уже успешно оплаченная стадия не повторяется автоматически из-
за ошибки более поздней стадии. Recovery выбирает наиболее полный валидный
same-day artifact и продолжает с первого незавершённого этапа.

Known-bad normalization/validation artifacts не переиспользуются. Modern saved
Primary повторно проходит current source-health. Conditional agency rescue
соблюдает собственную at-most-once state machine.

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

## 10. Cleanup и repository hygiene

Это два разных механизма.

### 10.1. Content/public cleanup

32-day cleanup:

- compact'ит старые `automation/content/YYYY-MM-DD/`, сохраняя `meta.json` и
  `stories.json`;
- удаляет expired public dated pages/images согласно validation contract;
- считает `posts/images/` обязательным;
- допускает отсутствие исторического `posts/dzen-test/images/` после исчезновения
  последнего legacy image;
- не использует `.gitkeep` как замену корректной validation semantics.

### 10.2. Repository hygiene

Repository hygiene работает с GitHub objects, а не с tracked production files.
Он может удалять только объекты, которые policy доказуемо классифицировал как
safe: stale merged/closed refs, safe artifacts и отдельные orphan workflow
objects/runs.

Retry разрешён только для idempotent read-only GET после documented transient
transport failures/HTTP `500/502/503/504`. Destructive DELETE/PUT автоматически
не повторяются.

Permanent archive branches, `main`, releases, tags и published/editorial content
не входят в scope автоматической hygiene mutation.

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
state пользователя.

## 14. Правило изменений архитектуры

Любая material architecture change должна отвечать на четыре вопроса:

1. Какие компоненты и saved artifacts зависят от изменяемой границы?
2. Какие offline regressions доказывают отсутствие побочного изменения?
3. Требуется ли controlled external/retrieval experiment и каким ресурсом он
   выполняется?
4. Какие `ARCHITECTURE.md`, README, AGENTS и contract tests должны измениться в
   том же PR?

Search/retrieval изменения сначала проверяются на assistant-owned resources.
Production API пользователя не расходуется без явного разрешения.
