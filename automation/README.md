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
- `audits/independent-audit-journal.md` — канонический журнал независимых
  Freshness/Completeness аудитов;
- `audits/experiments/` — сохранённые controlled architecture/retrieval
  эксперименты;
- `config/` — production, editorial, site, image и Source Pulse configuration;
- `prompts/` — active prompts и сохранённые legacy prompts;
- `fixtures/recall/` — machine-readable retrieval regressions;
- `fixtures/research/.runtime/` — ignored trusted runtime ingress для fresh
  research;
- `specs/` — редакционные и технические спецификации;
- `scripts/` — production, retrieval, recovery, cleanup, site generation и
  validators;
- `tests/` — основной Python offline regression suite;
- `notebooklm-video/` — отдельный локальный Windows downstream-подпроект;
- `preview/` и `recovery/` — временные ignored runtime/diagnostic каталоги.

## Основные entrypoints

- `scripts/run_digest_preview.py` — orchestration fresh/recovery research и
  editorial flow;
- `scripts/primary_recall_search.py` — стабильный public Primary Recall
  entrypoint; после fresh Primary запускает zero-paid Source Pulse v1.1 supplement
  до первого editorial;
- `scripts/agency_discovery_rescue.py` — conditional missing-event rescue;
- `scripts/source_pulse_supplement.py` — bounded Tier-A official supplemental
  discovery: обычный HTTPS, deterministic date/relevance gate, `consider` only,
  без OpenAI/Web Search;
- `scripts/source_pulse_shadow.py` — сохранённый snapshot/fusion diagnostics перед
  и после Hybrid без повторного polling;
- `scripts/hybrid_search_completeness.py` — bounded Hybrid completeness;
- `scripts/ensure_story_coverage.py` — fallback Coverage public entrypoint;
- `scripts/recover_digest_artifact.py` — paid-stage recovery entrypoint;
- `scripts/source_freshness.py` — deterministic source publication-date proof;
- `scripts/build_site.py` / validators — site/RSS/publication contracts;
- `scripts/video_rss_enrichment.py` — controlled post-publication bridge: проверяет
  публичные MP4+PNG и идемпотентно добавляет Media RSS video group в существующий
  item, не меняя публикационные поля и `content:encoded`;
- `scripts/cleanup_repository_content.py` и `cleanup_public_posts.py` — 32-day
  tracked content/public cleanup;
- `scripts/cleanup_video_ftp.py` — независимая от RSS 32-day очистка уже
  опубликованных MP4/PNG в hard-confined FTP-каталоге `video`;
- `scripts/repository_hygiene.py` — общая GitHub object hygiene;
- `scripts/repository_hygiene_video_rss_runs.py` — узкая retention-политика для
  Actions runs канонического `video-rss-enrichment.yml`, вызываемая только из
  ежедневного Repository hygiene.

Versioned implementation files such as `*_v1.py`, `*_v2.py` and `*_v8.py` are
preserved compatibility/recovery layers, not arbitrary duplicates. Their
lifecycle and refactor rules are described in [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Source Pulse v1.1

Fresh production сначала завершает Primary Recall, затем Source Pulse v1.1
опрашивает фиксированный registry обычным HTTPS. Только `pulse_only` Tier-A
official leads могут попасть в trusted research, причём только как
`recommendation=consider`. Tier B остаётся diagnostic-only. Для каждого
продвигаемого lead повторно открывается уже найденный официальный URL,
детерминированно проверяется publication date против exact saved window и
применяется AI-relevance gate. После merge штатный Source Freshness Proof всё
равно повторно проверяет trusted research перед первым editorial.

Pulse не вызывает OpenAI и Web Search. Search-derived `regional_health` для
Russia/China после Pulse не пересчитывается, поэтому второй discovery-plane не
может скрыть деградацию Primary и подавить существующий Hybrid health check.
Общий потолок остаётся 24 Web Search operations. Runtime report
`preview/production-daily/source-pulse-<DATE>.json` сохраняет source/parser health,
fusion, каждую причину promotion/rejection, promoted URLs и snapshot reuse; весь
`production-daily/` уже входит в стандартный Actions artifact.

## Workflows

Каждый pull request в `main` сначала проходит через always-on `PR Gate`. Он
классифицирует changed paths и вызывает reusable `Main CI`, `Video CI` или оба
домена. Финальный job `Required PR Gate` является единственным стабильным
required status для защиты `main`.

Video-only изменения под `notebooklm-video/**` не являются изменениями nightly
production и не запускают Main CI; их через PR Gate проверяет только Video CI.
В обратную сторону nightly production workflows не должны читать или изменять
video runtime.

На период controlled test отдельный `video-rss-enrichment.yml` образует только
односторонний post-publication мост: он не читает локальное состояние
`notebooklm-video`, а каждые пять минут проверяет уже публичные
`/posts/video/ai-svodka-2026-08-27.mp4` и `.png`. Пока пара не готова, запуск
успешно ничего не делает. После готовности он валидирует preview, добавляет
`media:group` только в RSS item выпуска 2026-08-27, повторно проверяет RSS,
фиксирует только `posts/rss.xml` и вызывает обычный FTP deploy. Ошибка или
отсутствие video assets не может блокировать ежедневную публикацию ИИ-Сводки.

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
32-дневную очистку контента и FTP-video assets. В его Actions-job дополнительно
работает только одна canonical-run retention policy: для
`video-rss-enrichment.yml` success старше трёх дней можно удалить после
безусловного сохранения последних 14 успешных runs; `failure`/`cancelled`
сохраняются 14 дней, а active/неизвестные состояния автоматически не удаляются.
Перед destructive phase заново проверяются `main`, workflow identity, отсутствие
активной Daily production и отсутствие активного Video RSS run. Полная история
этого workflow читается с пагинацией, поэтому policy не ограничена первыми 100
runs. Остальные canonical workflows этой специальной политикой не затрагиваются.

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
