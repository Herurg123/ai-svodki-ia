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
  entrypoint;
- `scripts/agency_discovery_rescue.py` — conditional missing-event rescue;
- `scripts/source_pulse_shadow.py` — production-shadow Source Pulse перед Hybrid;
- `scripts/hybrid_search_completeness.py` — bounded Hybrid completeness;
- `scripts/ensure_story_coverage.py` — fallback Coverage public entrypoint;
- `scripts/recover_digest_artifact.py` — paid-stage recovery entrypoint;
- `scripts/source_freshness.py` — deterministic source publication-date proof;
- `scripts/build_site.py` / validators — site/RSS/publication contracts;
- `scripts/cleanup_repository_content.py` и `cleanup_public_posts.py` — 32-day
  content cleanup;
- `scripts/repository_hygiene.py` — GitHub object hygiene.

Versioned implementation files such as `*_v1.py`, `*_v2.py` and `*_v8.py` are
preserved compatibility/recovery layers, not arbitrary duplicates. Their
lifecycle and refactor rules are described in
[`ARCHITECTURE.md`](ARCHITECTURE.md#совместимость-и-versioned-реализации).

## Workflows

Основной production-код обслуживается `Main CI`, а локальный video-подпроект
имеет отдельный `Video CI`. Полный workflow inventory и границы ответственности
см. в [`ARCHITECTURE.md`](ARCHITECTURE.md#github-actions).

Video-only изменения под `notebooklm-video/**` не являются изменениями nightly
production и не должны запускать Main CI. В обратную сторону production
workflows не должны читать или изменять video runtime.

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
