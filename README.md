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
| `.github/workflows/` | Always-on PR Gate, два раздельных CI-домена, production, deploy и cleanup/hygiene. |

## CI и production

В репозитории семь постоянных GitHub Actions workflow:

- `pr-gate.yml` — **PR Gate**, всегда запускается для pull request в `main`,
  определяет затронутые CI-домены и завершает единым `Required PR Gate`;
- `ci.yml` — **Main CI**, бесплатные офлайн-проверки основного production-кода;
- `video-ci.yml` — **Video CI**, отдельные dependency-free проверки только
  NotebookLM-video подпроекта;
- `daily-production.yml` — ежедневное формирование ИИ-Сводки;
- `deploy-posts.yml` — синхронизация `posts/` выбранного commit на FTP;
- `repository-cleanup.yml` — 32-дневная очистка/компактация content и public
  posts;
- `repository-hygiene.yml` — отдельная уборка безопасно классифицированных
  GitHub-объектов.

Video-only изменения по-прежнему не запускают Main CI: PR Gate вызывает только
Video CI. Для mixed/cross-cutting PR он требует оба домена. В ruleset обязательным
является только всегда существующий `Required PR Gate`, а не path-dependent Main
CI/Video CI. Подробности описаны в
[`automation/ARCHITECTURE.md`](automation/ARCHITECTURE.md#4-github-actions).

`main` защищается repository ruleset: обычные изменения должны проходить через
pull request, force-push и удаление запрещены. Единственный direct-push bypass
предназначен для отдельного write deploy key ночного production/cleanup; ключ не
используется retrieval, video, deploy-posts или repository-hygiene jobs.

## Краткие production-инварианты

Этот раздел намеренно сохраняет операторские и тестируемые маркеры текущего
production-контракта, а подробное объяснение находится в `automation/ARCHITECTURE.md`.

Основной cron запускается в `23:17 UTC`, то есть около `02:17 Europe/Moscow` даты
выпуска; внешний резервный запуск обслуживается через cron-job.org. Время выпуска
нормализуется к 06:00 МСК. Recovery выбирает наиболее полный пригодный artifact
той же даты.

Fresh Primary выполняет ровно 12 Web Search search operations. Coverage выполняет
до 7 Coverage search operations, поэтому общий архитектурный потолок с conditional
agency rescue и Hybrid равен 24 search operations. Каноническая continuity-точка
остается `search_cutoff_at` последнего успешно опубликованного выпуска. После
единственного search один Primary-pass может использовать `open_page` и
`find_in_page` как навигацию, не увеличивая search-operation budget.

Обязательные Coverage-направления сохраняют ids `security_world`,
`security_russia`, `security_asia`, `legal_copyright_scraping`, `curiosity` и
`general_coverage_gaps`; последний является авторитетный last-mile sweep
оставшихся пробелов. `partial`, `budget_exhausted` и `error` блокируют Image API,
commit и deploy. Для короткого выпуска сохраняется пометка «Новостей сегодня
меньше, чем обычно».

Ручной production dispatch имеет `publish=false` по умолчанию и отдельный
`recovery_run_id`. Текущие production defaults: `gpt-5.6-terra` для text/search и
`gpt-image-2` для cover generation.

Полностью завершённый нулевой candidate pool является normal successful `no-publish`, а не production failure. Technical partial/error audits remain fail-closed. Нулевая остановка требует актуальный `high_signal_recall_sentinel` версии 8 и завершённые обязательные quality/search стадии.

## Правила инженерной уборки GitHub

`repository-hygiene.yml` работает отдельно от 32-дневной очистки выпусков. Он
может изменять только безопасно классифицированные GitHub-объекты и не является
механизмом очистки tracked source или опубликованного контента.

Операторский отчёт доступен через `Actions → Repository hygiene → последний
запуск → Summary`. Диагностический JSON каждого этапа прикладывается как Actions
artifact с `retention: 2 дня`. Полные правила классификации и destructive safety
описаны в [`automation/ARCHITECTURE.md`](automation/ARCHITECTURE.md) и `AGENTS.md`.

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
