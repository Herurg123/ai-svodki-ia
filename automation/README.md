# Автоматизация ИИ-Сводок

`automation/` содержит основной production-конвейер ежедневной ИИ-Сводки,
редакционный archive/dedupe context, recovery, offline regressions и
эксплуатационные инструменты.

Каноническая подробная архитектура находится в
[`ARCHITECTURE.md`](ARCHITECTURE.md). Этот README является operational map:
он показывает каталоги, active entrypoints, ключевые production-инварианты и
команды проверки, но не повторяет implementation history каждого retrieval
слоя.

Активный P0 durable Coverage editorial-repair recovery отдельно специфицирован в
[`P0_EDITORIAL_REPAIR_ARCHITECTURE.md`](P0_EDITORIAL_REPAIR_ARCHITECTURE.md).

## Карта каталога

- `content/YYYY-MM-DD/` — структурированные материалы текущего retention window;
- `archive/index.json` — active редакционная память и dedupe/material-update context;
- `archive/search-baselines/` — permanent retrieval baseline manifests;
- `archive/video-rss-enrichment-2026-08/` — inert reference-only архив закрытого Video → RSS эксперимента;
- `archive/documentation-snapshots/` — inert snapshots живой документации перед явно выполненными consolidation/refactor работами; не являются current contract;
- `audits/independent-audit-journal.md` — канонический независимый audit journal;
- `audits/experiments/` — controlled experiments, incident/remediation evidence;
- `config/` — production/editorial/site/image/Source Pulse configuration;
- `prompts/` — active и preserved legacy prompts;
- `fixtures/recall/` — machine-readable retrieval/recovery regression fixtures;
- `specs/` — редакционные и технические спецификации и validation matrices;
- `scripts/` — orchestration, retrieval, freshness, recovery, publication, cleanup и validators;
- `tests/` — основной offline regression suite;
- `notebooklm-video/` — отдельный local Windows downstream;
- `preview/` и `recovery/` — ignored runtime/diagnostic directories.

## Основные entrypoints

| Контур | Active entrypoint | Назначение |
|---|---|---|
| Оркестрация | `scripts/run_digest_preview.py` | fresh/recovery research → editorial → publication preparation |
| Primary | `scripts/primary_recall_search.py` | stable Primary Recall, затем zero-paid Source Pulse supplement |
| Agency rescue | `scripts/agency_discovery_rescue_v6.py` через stable compatibility surface | максимум один Reuters-only rescue slot + observability |
| Agency viability | `scripts/agency_health_viability.py` | zero-network post-filter viability перед rescue |
| Event Freshness | `scripts/event_freshness.py` | deterministic event-age gate по сохранённому evidence |
| Source Freshness | `scripts/source_freshness.py` | active v3 page/source proof с preserved compatibility layers |
| Source Pulse | `scripts/source_pulse_supplement_v14.py` | bounded Tier-A supplemental discovery без OpenAI/Web Search |
| Regional viability | `scripts/regional_health_viability.py` | zero-paid one-way re-open раннего false-healthy regional state |
| Hybrid | `scripts/hybrid_search_completeness.py` | stable Hybrid v3 и conditional double-gap fifth search |
| Coverage | `scripts/ensure_story_coverage.py` | mandatory directions + bounded optional seventh-slot recovery |
| Recovery | `scripts/recover_digest_artifact.py` | reuse exact same-day saved bundle без повторения completed paid stages |
| Discovery health | `scripts/discovery_health.py` | zero-network diagnostics пяти discovery lanes |
| Production summary | `scripts/summarize_production_status.py` | pipeline status + Discovery Health в Actions Summary |
| Site | `scripts/build_site.py` + validators | canonical article/image site и RSS |
| Content cleanup | `scripts/cleanup_repository_content.py`, `cleanup_public_posts.py` | 32-day tracked/public retention |
| FTP video cleanup | `scripts/cleanup_video_ftp.py` | strict remote `video/` exact-pattern retention |
| GitHub hygiene | `scripts/repository_hygiene.py` | policy-based cleanup только GitHub objects |

Preserved `*_vN.py`, `*_base.py`, `*_pre_p0.py` и related wrappers являются
compatibility/recovery/replay assets, а не произвольными дубликатами. Условия их
refactor/removal заданы в `ARCHITECTURE.md` и root `AGENTS.md`.

Закрытые `video_rss_enrichment.py` и
`repository_hygiene_video_rss_runs.py` существуют только внутри
`archive/video-rss-enrichment-2026-08/` как reference material.

## Production contract summary

Этот раздел сохраняет компактные маркеры, которые нужны оператору и
documentation-contract tests. Полная логика находится в `ARCHITECTURE.md`.

### Schedule и continuity

`daily-production.yml` имеет ровно один native schedule: `23:17 UTC`
(`02:17 Europe/Moscow`). Внутрисуточных GitHub retry cron нет. Резервный
cron-job.org вызывает `workflow_dispatch`, поэтому backup run остаётся
отличимым от scheduled run.

Publication time нормализуется к 06:00 МСК. Continuity anchor —
`search_cutoff_at` последнего успешно опубликованного выпуска. Внутри уже
выполненного Primary pass `open_page` и `find_in_page` являются навигацией, а
не новыми search operations.

Recovery выбирает наиболее полный пригодный exact same-day artifact и сохраняет
bundle identity через compatibility wrappers. Completed paid stages не
повторяются только ради восстановления или regression.

### Search budget

- fresh Primary: 12 Web Search operations;
- Agency Rescue: максимум 1 existing Reuters-only slot;
- Hybrid: baseline максимум 4, conditional maximum 5 только при одновременных Search-derived Russia + China/Asia gaps;
- Coverage: до 7 Coverage search operations;
- ordinary whole-pipeline ceiling: 24 search operations;
- единственный approved double-gap extension: 25 search operations.

Source Pulse, Event Freshness, regional/agency viability, Discovery Health и
диагностические reducers не добавляют Web Search/OpenAI calls. P3b может занять
только существующий optional seventh Coverage slot; восьмой Coverage search не
разрешён.

### Coverage и publication gates

Обязательные Coverage ids:

- `security_world`
- `security_russia`
- `security_asia`
- `legal_copyright_scraping`
- `curiosity`
- `general_coverage_gaps` — авторитетный last-mile sweep оставшихся gaps.

`partial`, `budget_exhausted` и `error` блокируют Image API, commit и deploy.
Evidence-rich source-neutral resolution может завершиться
`complete_with_gaps` только по documented fail-closed contract; недоказанный
сюжет не становится публикационно пригодным.

Короткий выпуск сохраняет публичную пометку «Новостей сегодня меньше, чем обычно».
Полностью завершённый нулевой candidate pool является normal successful `no-publish`, а не production failure. Technical partial/error audits remain fail-closed. Нулевая остановка требует актуальный `high_signal_recall_sentinel` версии 8 и завершённые обязательные quality/search стадии.

### Freshness и supplemental discovery

Event age и cited-source publication age проверяются независимо. Надёжно
доказанное stale event evidence отклоняется до editorial; unknown event origin
сохраняет recall, но не обходит fail-closed Source Freshness.

Source Pulse v1.4 использует fixed registry и ordinary HTTPS, допускает к
publication influence только bounded Tier-A `official`/`trusted_news`
`pulse_only` leads как `consider` и не закрывает Search-derived regional gaps.
Точные Yandex/trusted-feed adapters, source roles и saved-proof recovery описаны
в `ARCHITECTURE.md`, конфиге registry и соответствующих audits.

### Retrieval quality layers

- P3a сохраняет qualified Primary `weak_source` product/model signal как evidence-only unresolved row без нового search obligation;
- P3b выполняет exact authoritative binding downstream в Coverage и только через свободный существующий optional seventh slot;
- provider labels, fuzzy identity и неподтверждённые lifecycle/version matches не являются proof;
- `request_started` с неизвестным outcome не ретраится;
- saved response/result reuse требует durable request/response/bundle/result provenance;
- P4 regional viability и agency-health viability могут только восстановить достижимость уже существующего recovery slot, но не создают новые slots.

Подробности этих contracts находятся в `ARCHITECTURE.md`, specs и
`audits/experiments/`. Audit README сохраняются как historical evidence, а не
копируются сюда целиком.

### Runtime defaults

Ручной production dispatch имеет `publish=false` по умолчанию и отдельный
`recovery_run_id`. Current production defaults: `gpt-5.6-terra` для
text/search и `gpt-image-2` для cover generation.

Usage accounting остаётся diagnostic-only: `usage_observer.py` и
`usage_ledger.py` объединяют observed current/recovery usage без повторного
счёта копий; unknown/missing evidence не превращается в нулевую стоимость и не
меняет retrieval/publication policy.

## Workflows

`PR Gate` классифицирует changed paths и вызывает reusable Main CI, Video CI
или оба домена. `Required PR Gate` остаётся единым стабильным required status.

`daily-production.yml` не зависит от локального NotebookLM-video runtime.
Video-only изменения под `notebooklm-video/**` не должны запускать Main CI.

Управляемая проектом operator-facing диагностика GitHub Actions русскоязычная:
`workflow_dispatch` descriptions, Actions Summary, annotations, явные ошибки и
recovery guidance. Названия workflow/jobs/steps и машинные/сторонние сообщения
могут оставаться английскими.

Video → RSS integration закрыта. Active workflows не добавляют MP4/PNG в
`posts/rss.xml`; historical implementation сохранена только в
`archive/video-rss-enrichment-2026-08/`.

`repository-cleanup.yml` объединяет tracked/public retention и отдельный
FTP-video job, но последний не использует RSS как media inventory и входит только
в hard-confined remote `video/`.

Полный workflow inventory, automated writers, concurrency и ruleset boundary
описаны в `ARCHITECTURE.md` и `MAIN_PROTECTION.md`.

## Repository hygiene

`repository-hygiene.yml` является отдельным operational workflow и не заменяет
32-day content/public/video retention. Он управляет только GitHub objects, которые
policy классифицирует как safe, с повторной проверкой перед destructive mutation.

Операторская диагностика находится в Actions Summary и JSON artifacts. Специальная
retention policy закрытого Video → RSS workflow удалена из active hygiene и
сохранена только в reference archive.

Подробные classification/retention/mutation boundaries — в
`ARCHITECTURE.md` и root `AGENTS.md`.

## Бесплатная локальная проверка основного проекта

~~~bash
python -m compileall automation/scripts automation/tests
python -m unittest discover -s automation/tests -v
python automation/scripts/validate_editorial_contract.py
python automation/scripts/validate_archive.py
~~~

Точный CI-набор задаётся `.github/workflows/ci.yml`.

Video-подпроект проверяется отдельно командами из
[`notebooklm-video/README.md`](notebooklm-video/README.md) и
`.github/workflows/video-ci.yml`.

## Изменение архитектуры

При изменении стадий, search budgets, freshness, recovery, publication,
workflow boundaries, cleanup/hygiene или video integration сначала обновляется
`ARCHITECTURE.md`, затем affected README/AGENTS/specs и regression tests.

Semantic retrieval/search change требует независимого baseline-vs-proposal
эксперимента по `specs/search-change-validation-matrix.md`. Production API
budget не используется для таких проверок без отдельного разрешения.

Живые README должны оставаться картами и operator entrypoints. Историческая
доказательная информация остаётся в audits/fixtures/archive, а детальный
current-state contract — в `ARCHITECTURE.md`; не следует снова размножать один
и тот же implementation narrative по нескольким README.
