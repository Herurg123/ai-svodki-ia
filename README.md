# ИИ-Сводки

Production-репозиторий ежедневных аналитических выпусков об искусственном
интеллекте. GitHub хранит код конвейера, редакционный архив и публикуемый
статический сайт; успешный выпуск собирается, проверяется, фиксируется в `main` и
только затем синхронизируется на FTP.

Публичные адреса:

- [Дзен](https://dzen.ru/rybv)
- [сайт выпусков](https://rybalka.one/posts/)
- [RSS](https://rybalka.one/posts/rss.xml)
- [sitemap](https://rybalka.one/posts/sitemap.xml)

## Где читать устройство проекта

Каноническое подробное описание системы находится в
[`automation/ARCHITECTURE.md`](automation/ARCHITECTURE.md). Там зафиксированы
границы компонентов, nightly data flow, retrieval-бюджеты, recovery, публикация,
cleanup/hygiene, CI и место локального NotebookLM-video подпроекта.

[`automation/README.md`](automation/README.md) является краткой картой каталога
production-автоматизации и операторских проверок. Правила для изменений хранятся
в [`AGENTS.md`](AGENTS.md).

## Основные части

| Часть | Назначение |
|---|---|
| `automation/` | Основной production-конвейер: retrieval, editorial, recovery, validators, archive, audits и configuration. |
| `posts/` | Сформированный публичный сайт, RSS, sitemap и постоянные публичные assets. |
| `automation/notebooklm-video/` | Отдельный локальный Windows downstream-подпроект: после публикации выпуска создаёт NotebookLM-видео, MP4, PNG-превью и при включённой настройке доставляет их только в FTP-каталог `video`. |
| `.github/workflows/` | Production, deploy, cleanup/hygiene и два раздельных CI-контура. |

## CI и production

В репозитории шесть постоянных GitHub Actions workflow:

- `ci.yml` — **Main CI**, бесплатные офлайн-проверки основного production-кода;
- `video-ci.yml` — **Video CI**, отдельные dependency-free проверки только
  NotebookLM-video подпроекта;
- `daily-production.yml` — ежедневное формирование ИИ-Сводки;
- `deploy-posts.yml` — синхронизация `posts/` выбранного commit на FTP;
- `repository-cleanup.yml` — 32-дневная очистка/компактация content и public
  posts;
- `repository-hygiene.yml` — отдельная уборка безопасно классифицированных
  GitHub-объектов.

Video-only изменения намеренно не запускают Main CI и не входят в nightly
retrieval/editorial production. Эта граница закреплена правилами и offline
contract tests; подробности описаны в
[`automation/ARCHITECTURE.md`](automation/ARCHITECTURE.md#ci-и-границы-подпроектов).

## Локальный NotebookLM-video

Подпроект начинает работу только после появления уже опубликованного выпуска в
RSS. Его runtime находится на Windows-машине пользователя и не является
GitHub-production стадией.

Инструкции:

- [README подпроекта](automation/notebooklm-video/README.md)
- [развёртывание](automation/notebooklm-video/DEPLOYMENT.md)
- [локальные правила](automation/notebooklm-video/AGENTS.md)

В Git не попадают реальные локальные конфиги, FTP-доступы, state, логи,
скачанные media и профиль браузера.

## Разработка и изменения

Изменения идут через отдельную ветку и pull request. Детальная архитектура не
дублируется между README: при изменении поведения сначала обновляется
`automation/ARCHITECTURE.md`, затем соответствующие краткие entry-point README и
контрактные тесты.

Production API не используется для обычных refactor/CI/regression-проверок без
явного разрешения.
