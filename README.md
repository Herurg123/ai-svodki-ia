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
| `automation/` | Основной production-конвейер: retrieval, event/source freshness, editorial, recovery, validators, archive, audits и configuration. |
| `posts/` | Сформированный публичный сайт, article/image RSS, sitemap и постоянные публичные assets. |
| `automation/notebooklm-video/` | Отдельный локальный Windows downstream-подпроект: после публикации выпуска создаёт NotebookLM-видео, MP4/PNG, при необходимости доставляет их в FTP `video`, автоматически публикует нативное видео в Дзен, а затем назначает видео и ежедневную сводку текущего дня в две фиксированные Дзен-подборки с persistent per-target state. |
| `automation/archive/video-rss-enrichment-2026-08/` | Reference-only архив закрытого Video → RSS эксперимента. Не является runtime/workflow path. |
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
- `repository-cleanup.yml` — единая 32-дневная maintenance-цепочка: компактирует
  repository content, удаляет просроченные public posts и после безопасного
  public deploy отдельно удаляет просроченные MP4/PNG из FTP-каталога `video`;
- `repository-hygiene.yml` — отдельная уборка безопасно классифицированных
  GitHub-объектов.

Video-only изменения по-прежнему не запускают Main CI: PR Gate вызывает только
Video CI. Для mixed/cross-cutting PR он требует оба домена. В ruleset обязательным
является только всегда существующий `Required PR Gate`, а не path-dependent Main
CI/Video CI. Подробности описаны в
[`automation/ARCHITECTURE.md`](automation/ARCHITECTURE.md#4-github-actions).

Для `main` подготовлен repository ruleset: обычные изменения должны проходить
через pull request, force-push и удаление запрещаются, а direct-push bypass
предназначен только для двух узких validated writers: nightly production и
retention cleanup. Они используют один выделенный write deploy key только в своих
финальных commit steps. Наличие ruleset JSON в Git само по себе не включает
GitHub setting; порядок активации описан в
[`automation/MAIN_PROTECTION.md`](automation/MAIN_PROTECTION.md).

## Краткие production-инварианты

Этот раздел намеренно сохраняет операторские и тестируемые маркеры текущего
production-контракта, а подробное объяснение находится в `automation/ARCHITECTURE.md`.

У `daily-production.yml` намеренно ровно один нативный GitHub `schedule`:
`23:17 UTC`, то есть `02:17 Europe/Moscow` даты выпуска. Внутрисуточных повторных
GitHub cron нет. Внешняя страховка обслуживается через cron-job.org и вызывает
workflow через `workflow_dispatch`, поэтому такой запуск в Actions отображается
как manual/dispatch, а не как scheduled run. Время выпуска нормализуется к
06:00 МСК. Recovery выбирает наиболее полный пригодный artifact той же даты.

Fresh Primary выполняет ровно 12 Web Search search operations. Coverage выполняет
до 7 Coverage search operations. Hybrid сохраняет базовый потолок 4 search
operations; только когда Search-derived health одновременно показывает нулевой
recall для Russia и China/Asia, разрешён один дополнительный пятый Hybrid search,
чтобы сохранить все три широких Hybrid-прохода и выполнить два отдельных
региональных health-check. Поэтому обычный архитектурный потолок остаётся 24
search operations, а условный double-gap потолок равен 25. Пятый Hybrid search не
разрешён при одном или отсутствии региональных gaps.

Каноническая continuity-точка остается `search_cutoff_at` последнего успешно
опубликованного выпуска. После единственного search один Primary-pass может
использовать `open_page` и `find_in_page` как навигацию, не увеличивая
search-operation budget.

Event-age freshness теперь проверяется отдельно от source-page freshness.
Надёжно доказанное событие вне exact saved window отклоняется deterministic gate
с кодом `event_freshness_stale` до editorial. Неизвестный или неоднозначный
origin не является автоматической причиной исключения и остаётся `unknown`, но
это не обход freshness: цитируемая страница затем обязана пройти прежний
fail-closed Source Freshness Proof. P1 не добавляет новый LLM/Web Search pass и не
увеличивает paid search ceiling.

После fresh Primary Source Pulse v1.3 выполняет второй discovery-plane без
дополнительного платного retrieval: обычный HTTPS к фиксированному registry,
**0 OpenAI calls и 0 Web Search operations**. В candidate pool могут попасть
только свежие `pulse_only` Tier-A `official` или `trusted_news` leads, и только
как `consider` после детерминированной проверки страницы/даты, host allowlist и
AI relevance. Yandex IR/company-news имеет узкий P2 fallback: только совпадение
dated first-party URL/id и видимой даты может дополнить отсутствующую generic
machine-readable publication date; сам общий Source Freshness parser body text не
сканирует. ТАСС включён в российский Tier-A `trusted_news` registry через AI-tag
surface; Yandex IR/MWS/VK остаются official, CNews остаётся Tier-B lead-only.
Tier B не влияет на publication. Search-derived China/Asia и Russia gaps после
Pulse не пересчитываются, поэтому механизм не может подавить Hybrid health-check.
Полная диагностика сохраняется в daily Actions artifact.

Обязательные Coverage-направления сохраняют ids `security_world`,
`security_russia`, `security_asia`, `legal_copyright_scraping`, `curiosity` и
`general_coverage_gaps`; последний является авторитетный last-mile sweep
оставшихся пробелов. Дополнительные региональные Coverage searches только из-за
красного regional health сейчас не включены. `partial`, `budget_exhausted` и
`error` блокируют Image API, commit и deploy. Один evidence-rich source-neutral
Retrieval Quality resolution может завершиться `complete_with_gaps`, если
минимум три разных source hosts подтверждают наличие того же high-signal
сообщения, но ни один не даёт verified evidence; такой сюжет остаётся
исключённым, а thin/ambiguous evidence остаётся fail-closed. Для короткого
выпуска сохраняется пометка «Новостей сегодня меньше, чем обычно».

Ручной production dispatch имеет `publish=false` по умолчанию и отдельный
`recovery_run_id`. Текущие production defaults: `gpt-5.6-terra` для text/search и
`gpt-image-2` для cover generation.

Полностью завершённый нулевой candidate pool является normal successful `no-publish`, а не production failure. Technical partial/error audits remain fail-closed. Нулевая остановка требует актуальный `high_signal_recall_sentinel` версии 8 и завершённые обязательные quality/search стадии.

## Видео и RSS: закрытая ветвь

Video → RSS enrichment признан тупиковым способом получения нативной публикации
видео в Дзене и удалён из production. Active workflow больше не проверяет MP4/PNG
для последующего изменения `posts/rss.xml`, а RSS не должен содержать локальные
video payloads `/posts/video/`, `medium="video"` или `type="video/*"`.

Исходная реализация не уничтожена. Workflow, script, его regression test и
специальная retention-политика Actions runs сохранены в
[`automation/archive/video-rss-enrichment-2026-08/`](automation/archive/video-rss-enrichment-2026-08/)
как inert reference-only archive. Архив не импортируется, не планируется по cron и
не входит в active test discovery. Возврат к этому подходу требует нового
изолированного эксперимента и отдельного PR.

Рабочая video-ветка остаётся независимой: локальный NotebookLM-video может
создавать и хранить MP4/PNG и публиковать видео через отдельный browser path, но
не модифицирует RSS ради видео или назначения Дзен-подборок.

## 32-дневная очистка видео на FTP

Очистка старых MP4 и PNG не зависит от того, присутствует ли видео в RSS или в
каком-либо content item. После успешной основной ночной cleanup-цепочки отдельный
job читает только FTP-каталог `video/` и управляет только файлами с точными
именами `ai-svodka-YYYY-MM-DD.mp4` и `ai-svodka-YYYY-MM-DD.png`.

Используется та же календарная граница, что и для public cleanup: при
`cutoff_date = reference_date - 32 days` удаляются только файлы с датой **раньше**
`cutoff_date`; файл ровно на границе сохраняется. Старые orphan MP4/PNG удаляются
независимо, наличие пары не требуется. Любые другие имена и каталоги остаются без
изменений. Перед первым DELETE валидируется весь управляемый inventory, а после
удаления выполняется повторный listing для подтверждения результата.

Manual cleanup по умолчанию остаётся dry-run. Scheduled cleanup применяет
удаление автоматически. Если основной public FTP deploy завершился ошибкой,
video cleanup не запускается, чтобы не добавлять вторую удалённую mutation к уже
неуспешной maintenance-цепочке.

## Правила инженерной уборки GitHub

`repository-hygiene.yml` работает отдельно от 32-дневной очистки выпусков. Он
может изменять только безопасно классифицированные GitHub-объекты и не является
механизмом очистки tracked source или опубликованного контента.

Специальная retention-политика только для runs бывшего
`video-rss-enrichment.yml` больше не входит в active Repository hygiene, поскольку
сам workflow закрыт. Её код сохранён в том же reference-only архиве для истории и
возможного будущего исследования.

Операторский отчёт доступен через `Actions → Repository hygiene → последний
запуск → Summary`. Диагностический JSON каждого этапа прикладывается как Actions
artifact с `retention: 2 дня`. Полные правила классификации и destructive safety
описаны в [`automation/ARCHITECTURE.md`](automation/ARCHITECTURE.md) и `AGENTS.md`.

## Локальный NotebookLM-video

Подпроект начинает работу только после появления уже опубликованного выпуска в
RSS. Его runtime находится на Windows-машине пользователя и не является
GitHub-production стадией. `run-worker.cmd` запускает единый scheduled flow через
`full-worker.js`: NotebookLM/MP4/PNG/FTP, затем Dzen duplicate guard и один fresh
publish при необходимости с verification-only защитой от повторного клика, затем
отдельный этап назначения same-day видео и ежедневной сводки в две фиксированные
Дзен-подборки.

Факт назначения хранится раздельно как `job.dzenCollections.video.status` и
`job.dzenCollections.digest.status`. После двух `ADDED` агрегат становится
`COMPLETE`, и следующие scheduled runs не открывают браузер для этапа подборок.
При `PARTIAL` повторяется только недостающая цель.

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