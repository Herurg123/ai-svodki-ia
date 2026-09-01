# Автоматизация ИИ-Сводок

`automation/` содержит основной production-конвейер ежедневной ИИ-Сводки,
редакционный архив, offline regressions, recovery и эксплуатационные инструменты.

Подробная и каноническая архитектура вынесена в
[`ARCHITECTURE.md`](ARCHITECTURE.md). Этот README остаётся короткой навигационной
картой и не должен повторять подробные retrieval/recovery контракты.

## Карта каталога

- `content/YYYY-MM-DD/` — структурированные материалы выпусков;
- `archive/index.json` — редакционная память и dedupe/material-update context;
- `archive/search-baselines/` — manifests постоянных retrieval baselines;
- `archive/video-rss-enrichment-2026-08/` — inert reference-only архив закрытого
  Video → RSS эксперимента, не входящий в active workflow/scripts/tests paths;
- `audits/independent-audit-journal.md` — канонический журнал независимых
  Freshness/Completeness аудитов;
- `audits/experiments/` — сохранённые controlled architecture/retrieval
  эксперименты;
- `config/` — production, editorial, site, image и Source Pulse configuration;
- `prompts/` — active prompts и сохранённые legacy prompts;
- `fixtures/recall/` — machine-readable retrieval regressions, включая P1
  event-freshness controls, P2 Yandex Source Pulse date controls, P3
  provider/source-routing controls и P4 regional-health viability controls;
- `fixtures/research/.runtime/` — ignored trusted runtime ingress для fresh
  research;
- `specs/` — редакционные и технические спецификации;
- `scripts/` — production, retrieval, event/source freshness, recovery, cleanup,
  site generation и validators;
- `tests/` — основной Python offline regression suite;
- `notebooklm-video/` — отдельный локальный Windows downstream-подпроект с единым scheduled flow NotebookLM → media/FTP → native Dzen publish;
- `preview/` и `recovery/` — временные ignored runtime/diagnostic каталоги.

## Основные entrypoints

- `scripts/run_digest_preview.py` — orchestration fresh/recovery research и
  editorial flow;
- `scripts/primary_recall_search.py` — стабильный public Primary Recall
  entrypoint; после fresh Primary запускает zero-paid Source Pulse v1.3 supplement
  до первого editorial;
- `scripts/agency_discovery_rescue.py` / `agency_discovery_rescue_v4.py` —
  preserved previous rescue implementations для replay/rollback;
  `scripts/agency_discovery_rescue_v5.py` — active conditional Reuters-only
  missing-event rescue: максимум один Web Search, global publisher route без
  regional-gap подмены query и с post-freshness/editorial health trigger;
- `scripts/agency_health_viability.py` — zero-network deterministic bridge перед
  active v5 rescue: по exact Search-derived Primary `major_agencies` provenance
  проверяет, остался ли viable survivor после Primary final cap, freshness и
  первого editorial; ambiguous identity не разрешает search;
- `scripts/retrieval_routing_audit.py` — zero-network P3 classifier/replay для
  provider source-pool miss vs missing source metadata и query-control coverage;
- `scripts/regional_health_viability.py` — zero-network P4 pre-Hybrid viability
  refresh: может только переоткрыть early false-healthy Russia/China-Asia gap по
  exact Primary provenance после freshness/editorial filtering;
- `scripts/source_pulse_supplement_v13.py` — bounded Tier-A official/trusted-news
  supplemental discovery поверх сохранённого v1.2: обычный HTTPS,
  source-aware date parsing, узкий Yandex URL+visible-date repair,
  deterministic date/relevance/host gate, `consider` only, без OpenAI/Web Search;
- `scripts/source_pulse_supplement_v12.py` — сохранённый предыдущий Source Pulse
  implementation для rollback/replay compatibility;
- `scripts/source_pulse_shadow.py` — сохранённый snapshot/fusion diagnostics перед
  и после Hybrid без повторного polling;
- `scripts/hybrid_search_completeness.py` — stable Hybrid v3 entrypoint: baseline
  максимум 4 searches и ровно один conditional fifth search только при
  одновременных Search-derived Russia + China/Asia gaps; P3 сохраняет
  representative query routing/v5 rescue, а P4 перед search детерминированно
  переоткрывает false-healthy gap, если exact Primary regional candidates больше
  не имеют viable post-filter survivor;
- `scripts/ensure_story_coverage.py` — fallback Coverage public entrypoint;
  evidence-rich unverified exhaustion может завершить bounded quality check
  без публикации слуха и без повторного search при same-day recovery; fresh-agency
  source-health rescue использует свободный седьмой slot только когда в текущем
  пуле существует допустимый funding/M&A/investment/infrastructure/chips/partnership
  target, а при реальном source-health gap без такого target фиксируется
  `not_applicable` без дополнительного search и без ложной блокировки выпуска;
- `scripts/recover_digest_artifact.py` — paid-stage recovery entrypoint; текущий
  agency-health contract разрешает повторно оценить только zero-spend saved
  `not_triggered`, но никогда не повторяет started/spent/indeterminate rescue;
- `scripts/event_freshness.py` — zero-network deterministic event-age gate по
  уже сохранённому origin evidence;
- `scripts/source_freshness.py` — stable двухслойный freshness entrypoint:
  Event Freshness перед preserved fail-closed Source Freshness v1;
- `scripts/source_freshness_v1.py` — сохранённая authority для безопасного fetch
  и доказательства publication date цитируемой страницы;
- `scripts/build_site.py` / validators — site/RSS/publication contracts;
- `scripts/cleanup_repository_content.py` и `cleanup_public_posts.py` — 32-day
  tracked content/public cleanup;
- `scripts/cleanup_video_ftp.py` — независимая от RSS 32-day очистка уже
  опубликованных MP4/PNG в hard-confined FTP-каталоге `video`;
- `scripts/repository_hygiene.py` — общая GitHub object hygiene.

Закрытые `video_rss_enrichment.py` и
`repository_hygiene_video_rss_runs.py` сохранены только в
`archive/video-rss-enrichment-2026-08/` как reference material. Они не являются
active entrypoints.

Versioned implementation files such as `*_v1.py`, `*_v2.py`, `*_v3.py` и
`*_v8.py` являются preserved compatibility/recovery layers, а не произвольными
дубликатами. Их lifecycle и refactor rules описаны в
[`ARCHITECTURE.md`](ARCHITECTURE.md).

## Event Freshness P1

Paid retrieval candidates сохраняют два независимых времени. Поля
`published_date`/`published_at`/`time_precision` относятся к цитируемой странице,
а nullable `event_date`/`event_at`/`event_time_precision` вместе с
`event_origin_url`, `event_evidence_kind` и `event_date_evidence` относятся к
самому событию или его первому существенному публичному анонсу.

`event_freshness.py` не открывает сеть и не вызывает OpenAI/Web Search. Надёжный
origin вне exact saved window получает `event_freshness_stale` и отсекается до
editorial. Неизвестный/неоднозначный origin остаётся `unknown` и сохраняет recall,
но после этого candidate всё равно обязан пройти прежний fail-closed Source
Freshness Proof по странице. Поэтому свежая перепечатка не омолаживает старое
доказанное событие, а отсутствие origin evidence не становится самостоятельным
false-negative gate.

Regression fixture находится в
`fixtures/recall/event-freshness-2026-08-29.json`, controlled offline replay — в
`audits/experiments/2026-08-29-event-freshness-p1.md`. P1 не добавляет paid calls
или Web Search operations и сохраняет recovery старых artifacts без `event_*`
полей через `event=unknown`.

## Source Pulse v1.3

Fresh production сначала завершает Primary Recall, затем Source Pulse v1.3
опрашивает фиксированный registry обычным HTTPS. Только `pulse_only` Tier-A
`official` или `trusted_news` leads могут попасть в trusted research, причём
только как `recommendation=consider`. Tier B остаётся diagnostic-only.

Для каждого продвигаемого lead повторно открывается уже найденный URL,
детерминированно проверяется publication date против exact saved window,
проверяется redirect/host allowlist и применяется AI-relevance gate. После merge
штатный Event + Source Freshness Proof всё равно повторно проверяет trusted
research перед первым editorial. Pulse rows без отдельного event-origin evidence
остаются `event=unknown`, но не обходят fail-closed page freshness. ТАСС включён
в российский Tier-A `trusted_news` registry через
`https://tass.ru/tag/iskusstvennyi-intellekt`; Yandex IR, MWS и VK остаются
официальными Tier-A surfaces, CNews остаётся Tier-B lead-only.

P2 добавляет только Yandex-specific publication-date repair. Generic Source
Freshness parser по-прежнему не извлекает случайные даты из body text. Если у
Yandex IR/company-news страницы нет обычной machine-readable publication date,
v1.3 принимает fallback только при согласии двух first-party сигналов: dated
Yandex URL/id и совпадающей видимой даты в верхней части страницы или index item.
Конфликтующая ненулевая parser-date не получает приоритет только потому, что она
уже заполнена. Existing machine-readable publication metadata остаётся
authoritative. Same-day recovery чинит сохранённый Pulse snapshot из уже
сохранённых Yandex URL/title evidence и не repoll'ит mutable indexes.

Regression fixture: `fixtures/recall/source-pulse-yandex-2026-08-29.json`.
Controlled replay/audit: `audits/experiments/2026-08-29-yandex-source-pulse-date-p2.md`.

Pulse не вызывает OpenAI и Web Search. Он никогда не закрывает уже существующий
Search-derived `regional_health` gap и поэтому не может скрыть деградацию Primary.
P4 отдельно, уже после Event/Source Freshness и первого editorial, может только
переоткрыть early healthy регион по exact Primary provenance; Pulse-only candidate
не считается доказательством здоровья Primary. Runtime report
`preview/production-daily/source-pulse-<DATE>.json` сохраняет source/parser health,
fusion, каждую причину promotion/rejection, promoted URLs и snapshot reuse; весь
`production-daily/` входит в стандартный Actions artifact.

## Provider routing P3

P3 не добавляет новый discovery stage. Saved production replay показал, что
Yandex Sim, AI Alliance copyright/training-data и Tencent Hy4 в контрольных
маршрутах терялись до candidate normalization: при доступной source metadata их
control URLs отсутствовали в provider source pool. Отдельно Reuters rescue v4
завершил search с `action.sources=null`; это трактуется как
`source_metadata_unavailable`, а не как доказательство нулевого source pool.

Primary сохраняет те же 12 slots, но `russia`, `china_asia_models` и
`major_agencies` получают короткие representative query contracts, покрывающие
product/policy, Tencent/Hunyuan и model/research surfaces. Это ranking anchors,
не company whitelist. Hybrid сохраняет свои прежние trigger semantics и лишь
расширяет текст уже существующих regional health queries.

Agency rescue v5 сохраняет один Reuters-only high-context search и его global
publisher-route роль: Search-derived regional gaps записываются в диагностику, но
не подменяют query словом Russia/Asia. Теперь перед этим слотом отдельный
zero-paid agency-health bridge проверяет post-filter survival exact Primary
`major_agencies`; он меняет только trigger semantics, а не query/provider route
или число slots. Same-day recovery использует тот же v5 entrypoint. Versioned v4
остаётся preserved replay/rollback asset.

Offline fixture: `fixtures/recall/provider-routing-2026-08-29.json`.
Classifier: `scripts/retrieval_routing_audit.py`. Controlled audit:
`audits/experiments/2026-08-29-provider-routing-p3.md`. P3 добавляет 0 search
operations; ordinary ceiling остаётся 24, conditional double-gap ceiling — 25.

## Regional health viability P4

Primary `regional_health` изначально строится по раннему accepted count в
`china_asia_models` + `china_asia_integrations` и `russia`. Production replay 29
августа показал ложный healthy-case: Asia получила два Primary candidates, но
после freshness/editorial viability пригодных Asia candidates осталось 0, а
Hybrid продолжал видеть старое `health_check_needed=false`.

P4 не пересчитывает регион по словам в title и не вводит квоту. Перед fresh Hybrid
`regional_health_viability.py` берёт exact provenance из `primary-recall.json`,
учитывает Primary final cap и сопоставляет эти же региональные Primary candidates
с post-freshness/editorial `candidates.json`. Если все доказуемо сопоставлены и ни
один не остался `include|consider` без explicit stale/old-reprint статуса, gap
переоткрывается `false → true`. Уже открытый Search-gap нельзя закрыть; при
неполной provenance/identity старое состояние сохраняется.

Fixture: `fixtures/recall/regional-health-viability-2026-08-29.json`.
Controlled replay + architecture audit:
`audits/experiments/2026-08-29-regional-health-viability-p4.md`. P4 делает 0
OpenAI/Web Search calls и не добавляет query slot. Он лишь позволяет существующему
Hybrid v3 regional recovery сработать после поздней потери ранних candidates.

## Agency health viability

`agency_health_viability.py` решает аналогичный lifecycle-state defect для
`major_agencies`. Early Primary `raw=0`/`accepted=0` по-прежнему немедленно
открывает rescue. Если же early accepted count был положительным, bridge сначала
пересекает raw agency candidates с Primary `final_candidates`, а затем ищет эти же
provenance в текущем post-freshness/editorial pool. Shared source URL является
authoritative identity; title fallback используется только когда у одной стороны
нет source identity.

Если все exact Primary agency rows доказуемо сопоставлены и viable survivor нет,
trigger получает reason `major_agencies_no_viable_survivor_after_filtering` и
может использовать существующий единственный Reuters slot. Pulse-only или
unrelated later candidate с тем же заголовком не считается доказательством
здоровья Primary. Любая unmatched/ambiguous identity сохраняет no-search state.
Bridge сам выполняет 0 OpenAI/Web Search operations.

Recovery переоценивает только saved `not_triggered`, который доказуемо не
резервировал и не выполнил search. Если health после filtering теперь красный,
full recovery понижается до `partial_editorial`, чтобы text runtime мог выполнить
первую и единственную попытку существующего slot. `search_started`, completed,
failed и indeterminate состояния не получают второй search. Controlled A/B audit:
`audits/experiments/2026-09-01-post-freshness-agency-rescue-ab.md`.

## Hybrid v3 и search budget

Обычный Hybrid contract не подорожал: три fixed passes и максимум один
adaptive/regional slot, то есть не более 4 Web Search operations. Если effective
Search-derived health после P4 одновременно помечает **оба** regional gaps,
Russia и China/Asia, Hybrid v3 не отнимает общий broad slot: он выполняет три
broad passes и два отдельных regional health-check, итого максимум 5 Hybrid
searches.

Пятый search является единственным одобренным платным расширением и включается
только при double-gap. При одном regional gap остаётся 3+1, без regional gap —
штатная baseline логика. P4 может сделать существующий fifth slot достижимым в
false-healthy случае, но не создаёт шестой или новый постоянный search. Переданный
завышенный `maximum_search_calls` не может создать шестой вызов; пониженный
baseline не активирует conditional extension.

Whole-pipeline theoretical ceiling:

```text
обычно:      12 Primary + 1 agency rescue + 4 Hybrid + 7 Coverage = 24
оба gaps:    12 Primary + 1 agency rescue + 5 Hybrid + 7 Coverage = 25
```

Source Pulse, Event Freshness, P4 regional viability и agency-health viability в
эти числа не входят: у них 0 OpenAI calls и 0 Web Search. Дополнительные
региональные Coverage searches и отдельный LLM semantic-event matcher сейчас не
включены; они остаются deferred options для будущих аудитов.

## Workflows

Каждый pull request в `main` сначала проходит через always-on `PR Gate`. Он
классифицирует changed paths и вызывает reusable `Main CI`, `Video CI` или оба
домена. Финальный job `Required PR Gate` является единственным стабильным
required status для защиты `main`.

`daily-production.yml` имеет ровно один нативный GitHub schedule:
`17 23 * * *`, то есть `02:17 Europe/Moscow`. Внутрисуточные повторные cron в
GitHub не используются. Резервный запуск выполняет cron-job.org через
`workflow_dispatch`; поэтому такой внешний вызов отображается как manual/dispatch
и не является scheduled run.

Video-only изменения под `notebooklm-video/**` не являются изменениями nightly
production и не запускают Main CI; их через PR Gate проверяет только Video CI.
В обратную сторону nightly production workflows не должны читать или изменять
video runtime. Локальный Task Scheduler через `scheduled-worker.js` запускает
существующий `worker.js`, а после его успешного выхода выбирает самый свежий
`DONE` job с датой не позже текущей и выполняет Dzen duplicate guard, максимум
один fresh publish click и verification-only подтверждение.

Video → RSS integration закрыта. Active workflows не должны добавлять локальные
MP4/PNG в `posts/rss.xml`, а сам RSS не должен содержать `/posts/video/`,
`medium="video"` или `type="video/*"`. Историческая реализация сохранена в
`archive/video-rss-enrichment-2026-08/`, но архив не исполняется и не входит в
production inventory. Возврат к этому пути требует нового изолированного
эксперимента и отдельного PR.

`repository-cleanup.yml` сохраняет единый retention-контур, но FTP-video cleanup
внутри него является отдельным job и не использует RSS как источник списка
media. После успешной основной cleanup-цепочки он применяет тот же
`reference_date`/`retention_days`, входит только в FTP `video/`, управляет лишь
точными `ai-svodka-YYYY-MM-DD.mp4/.png` и подтверждает отсутствие удалённых
файлов повторным listing. Manual dry-run только планирует; scheduled apply удаляет
просроченные assets.

Полный workflow inventory, ruleset и automated-writer boundary описаны в
[`ARCHITECTURE.md`](ARCHITECTURE.md).

Операторская установка write deploy key, repository secret и самого GitHub
ruleset описана в [`MAIN_PROTECTION.md`](MAIN_PROTECTION.md). Ruleset JSON в
`config/` является каноническим desired state, но не активирует настройку GitHub
сам по себе.

## Repository hygiene

`repository-hygiene.yml` является отдельным operational workflow и не заменяет
32-дневную очистку контента и FTP-video assets. Он управляет только безопасно
классифицированными GitHub objects по общей policy. Специальная retention-политика
для runs закрытого `video-rss-enrichment.yml` удалена из active workflow вместе с
самим Video → RSS механизмом и сохранена лишь в reference-only архиве.

Policy, безопасные mutation boundaries, retention и operator diagnostics описаны
в [`ARCHITECTURE.md`](ARCHITECTURE.md) и в root `AGENTS.md`.

## Бесплатная локальная проверка основного проекта

```bash
python -m compileall automation/scripts automation/tests
python -m unittest discover -s automation/tests -v
python automation/scripts/validate_editorial_contract.py
python automation/scripts/validate_archive.py
```

Точный CI-набор остаётся задан в `.github/workflows/ci.yml`.

Для video-подпроекта используются отдельные команды из
[`notebooklm-video/README.md`](notebooklm-video/README.md) и dedicated
`.github/workflows/video-ci.yml`.

## Изменение архитектуры

При изменении стадий, бюджетов, recovery, workflow boundaries, cleanup/hygiene
или video integration сначала обновляется `ARCHITECTURE.md`, затем affected
README/AGENTS и regression tests. Retrieval experiments выполняются отдельно от
production API и фиксируются в `audits/experiments/`.
