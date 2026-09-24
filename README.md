# ИИ-Сводки

Production-репозиторий ежедневных аналитических выпусков об искусственном
интеллекте. GitHub хранит код конвейера, редакционный архив и публикуемый
статический сайт; успешный выпуск собирается, проверяется, фиксируется в `main`
и только затем синхронизируется на FTP.

Публичные адреса:

- [Дзен](https://dzen.ru/rybv)
- [сайт выпусков](https://rybalka.one/posts/)
- [RSS](https://rybalka.one/posts/rss.xml)
- [sitemap](https://rybalka.one/posts/sitemap.xml)

## Где читать устройство проекта

- [`automation/ARCHITECTURE.md`](automation/ARCHITECTURE.md) — каноническая
  подробная архитектура: data flow, retrieval, freshness, editorial, recovery,
  publication, cleanup/hygiene, CI и video boundary.
- [`automation/README.md`](automation/README.md) — рабочая карта `automation/`,
  active entrypoints, ключевые production-инварианты и команды проверки.
- [`AGENTS.md`](AGENTS.md) — обязательные правила изменения репозитория.
- [`automation/notebooklm-video/README.md`](automation/notebooklm-video/README.md)
  — локальный Windows downstream NotebookLM/Dzen.

README намеренно остаётся обзорным. Детальные implementation/recovery contracts
не дублируются здесь, если для них уже есть канонический architecture/spec
документ.

## Основные части

| Часть | Назначение |
|---|---|
| `automation/` | Production-конвейер: retrieval, freshness, editorial, recovery, validators, archive, audits и configuration. |
| `posts/` | Публичный статический сайт, article/image RSS, sitemap и постоянные assets. |
| `automation/notebooklm-video/` | Независимый локальный Windows downstream после публикации выпуска: NotebookLM → MP4/PNG → optional FTP → native Dzen → collections → video-in-article. |
| `automation/archive/video-rss-enrichment-2026-08/` | Inert reference-only архив закрытого Video → RSS эксперимента. |
| `.github/workflows/` | PR Gate, Main CI, Video CI, production, deploy и maintenance workflows. |

## CI и production

В репозитории семь постоянных GitHub Actions workflow:

- `pr-gate.yml` — always-on PR Gate и единый `Required PR Gate`;
- `ci.yml` — Main CI для основного production-кода;
- `video-ci.yml` — отдельный Video CI для NotebookLM-video;
- `daily-production.yml` — ежедневный выпуск;
- `deploy-posts.yml` — синхронизация выбранного `posts/` commit на FTP;
- `repository-cleanup.yml` — 32-дневная очистка tracked/public content и
  отдельная FTP-video retention стадия;
- `repository-hygiene.yml` — безопасная уборка классифицированных GitHub
  objects.

Video-only PR не должен тянуть Main CI; mixed/cross-cutting изменение проходит
оба домена. Подробная ownership boundary находится в
[`automation/ARCHITECTURE.md`](automation/ARCHITECTURE.md#4-github-actions).

Все управляемые проектом сообщения для оператора в GitHub Actions выводятся по-русски:
manual-input descriptions, Summary, annotations, явные ошибки/предупреждения и
recovery guidance. Английскими могут оставаться названия workflow/jobs/steps,
технические идентификаторы и сырые сообщения GitHub или сторонних actions.

Обычные изменения проекта идут через отдельную ветку, pull request, CI и review
diff. Техническая возможность direct push в `main` сама по себе не является
дефектом проекта. Nightly production и retention cleanup имеют отдельную
документированную automated-writer boundary; GitHub-side hardening описан в
[`automation/MAIN_PROTECTION.md`](automation/MAIN_PROTECTION.md).

## Production-контракт в одном экране

Подробные числа, состояния и compatibility layers поддерживаются в
`automation/ARCHITECTURE.md`; здесь остаются только границы, полезные при
навигации:

- fresh Primary имеет 12 Web Search operations, Coverage — до 7 Coverage search
  operations;
- Hybrid обычно ограничен четырьмя search operations; ровно один conditional
  fifth search разрешён только при одновременных Search-derived gaps Russia +
  China/Asia;
- обычный whole-pipeline потолок — 24 search operations, double-gap потолок — 25;
- Event Freshness и Source Freshness являются разными gates; доказанно старое
  событие не омолаживается свежей перепечаткой;
- Source Pulse и deterministic viability/health diagnostics не добавляют
  OpenAI/Web Search вызовы и не отменяют обязательный Search-derived recovery;
- recovery переиспользует наиболее полный пригодный same-day final artifact
  или durable stage checkpoint и не повторяет уже завершённые paid stages;
- `posts/rss.xml` остаётся article/image surface и не используется для доставки
  локального видео;
- production/API spend не используется для обычных refactor/regression работ без
  отдельного разрешения.

Точный operational contract, включая schedule, search budget, recovery states,
freshness и publication gates, находится в
[`automation/README.md`](automation/README.md) и
[`automation/ARCHITECTURE.md`](automation/ARCHITECTURE.md).

## Видео и RSS: закрытая ветвь

Video → RSS enrichment признан нерабочим способом получения нативной Dzen-video
публикации и удалён из active production. `posts/rss.xml` не должен содержать
локальные video payloads, `/posts/video/`, `medium="video"` или
`type="video/*"`.

Историческая реализация сохранена только под
[`automation/archive/video-rss-enrichment-2026-08/`](automation/archive/video-rss-enrichment-2026-08/)
как reference-only evidence. Возврат к этому пути требует нового изолированного
эксперимента и отдельного архитектурного изменения.

Рабочий NotebookLM-video downstream независим от nightly production и публикует
video через локальный browser path. Его детали находятся в
[`automation/notebooklm-video/README.md`](automation/notebooklm-video/README.md).

## 32-дневная очистка

`repository-cleanup.yml` компактирует старые `automation/content/YYYY-MM-DD/`,
удаляет истёкшие public dated pages/images после validation и затем отдельно
чистит FTP `video/` от exact-pattern `ai-svodka-YYYY-MM-DD.mp4/.png`, если их
дата строго раньше общего cutoff.

FTP-video cleanup не выводит inventory из RSS, не требует пары MP4/PNG и не
трогает другие remote names/directories. Manual cleanup по умолчанию dry-run;
scheduled cleanup применяет validated deletion автоматически. Полный contract —
в `automation/ARCHITECTURE.md`.

## Правила инженерной уборки GitHub

`repository-hygiene.yml` не чистит tracked source или опубликованный content.
Он работает только с GitHub objects, которые policy доказуемо классифицировала
как безопасные для mutation. Перед destructive operation состояние и SHA
проверяются повторно.

Операторский результат: `Actions → Repository hygiene → последний запуск →
Summary`. Диагностические JSON artifacts имеют `retention: 2 дня`.

Классификация, protected objects и retry/delete boundaries описаны в
[`automation/ARCHITECTURE.md`](automation/ARCHITECTURE.md) и
[`AGENTS.md`](AGENTS.md).

## Локальный NotebookLM-video

Подпроект стартует после уже опубликованного выпуска и живёт на Windows-машине
оператора. Один scheduled entrypoint ведёт NotebookLM/MP4/PNG/optional FTP,
native Dzen publication, две Dzen collections и insertion опубликованного видео
в same-day статью. На article-video этапе пользовательский Windows clipboard не
сохраняется и не восстанавливается: он используется только как рабочий канал для
проверенного video URL перед Ctrl+V.

Его state, browser profile, реальные configs, FTP credentials, logs и downloaded
media не коммитятся. Точные state machines, manual entrypoints, deployment и
browser safety описаны в:

- [README подпроекта](automation/notebooklm-video/README.md)
- [DEPLOYMENT.md](automation/notebooklm-video/DEPLOYMENT.md)
- [локальных правилах](automation/notebooklm-video/AGENTS.md)

## Разработка и изменения

Изменения поведения или структуры должны обновлять
`automation/ARCHITECTURE.md` и затронутые entry-point README/AGENTS в том же PR.
Retrieval/search изменения дополнительно проходят независимую validation matrix и
не используют пользовательский production API budget без отдельного разрешения.

Исторические audits/fixtures сохраняются как evidence и regression assets; их не
следует переписывать только ради сокращения живой документации.
