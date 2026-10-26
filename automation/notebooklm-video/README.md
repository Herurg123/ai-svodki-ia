# NotebookLM video worker

`automation/notebooklm-video/` — отдельный локальный Windows downstream
проекта ИИ-Сводок. Он стартует только после появления опубликованного выпуска и
не участвует в nightly retrieval/editorial GitHub production.

Канонические ссылки:

- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — граница подпроекта относительно
  общего production/CI;
- [`AGENTS.md`](AGENTS.md) — локальные prescriptive rules;
- [`DEPLOYMENT.md`](DEPLOYMENT.md) — перенос и установка на Windows;
- [`DZEN_NATIVE_UPLOAD.md`](DZEN_NATIVE_UPLOAD.md) — deep contract native Dzen
  upload;
- [`DZEN_ARTICLE_VIDEO.md`](DZEN_ARTICLE_VIDEO.md) — deep contract video-in-article;
- [`DZEN_VIDEO_EXPERIMENTS.md`](DZEN_VIDEO_EXPERIMENTS.md) — historical live
  experiments и negative evidence.

Этот README является операторской/runtime-картой. Точные selectors, live-test
chronology и incident evidence остаются в subsystem/audit документах, а не
дублируются здесь.

## Изоляция от основного production

- worker выполняется на Windows-машине оператора;
- основной nightly production не читает video state и не ждёт video result;
- video-only изменения проверяет отдельный Video CI;
- Main CI намеренно исключает video-only paths;
- `daily-production`, основной FTP deploy, repository cleanup и repository
  hygiene не должны зависеть от локального video runtime;
- video downstream не модифицирует `posts/rss.xml` ради публикации видео.

## Scheduled flow

~~~text
RSS rybalka.one
  -> Windows Task Scheduler
  -> run-worker-hidden.vbs / run-worker.cmd
  -> full-worker.js
  -> scheduled-worker.js
     -> worker.js
        -> protected Yandex Browser profile / Playwright CDP
        -> NotebookLM
        -> MP4 + PNG first-frame preview
        -> optional FTP video/
     -> Dzen duplicate guard
     -> at most one fresh native-video publish child
     -> post-click verification
  -> dzen-collections.js
     -> video -> «Видеосводки по ИИ»
     -> digest -> «Сводки по ИИ»
  -> dzen-article-video.js
     -> same-day article H2 «Видеосводка»
     -> public verification
  -> dzen-article-link.js (optional, VK enabled, no verified article URL)
     -> published same-day Dzen ARTICLE link (Studio + public verification)
  -> vk-stage.mjs (optional, requires verified MP4/PNG + published article URL)
     -> VK video -> «Сводки по ИИ» playlist
     -> VK wall post with video + published Dzen article link
     -> VK story: separate portrait PNG + post sticker + Dzen article link
~~~

`full-worker.js` owns the outer lock for the whole scheduled sequence.
`scheduled-worker.js` keeps its inner guard for NotebookLM/FTP + native Dzen
publication. Separate Task Scheduler jobs for later Dzen phases are not needed.

The worker selects the newest eligible local `DONE` job whose date is not in the
future, so delayed/catch-up processing remains possible.

## Пятый этап VK

Проверка на живом VK 18.10.2026: видео `456239139`,
плейлист `1`, пост `206`, история `456239131`; отдельный
story-only ретест с неизменённым PNG **визуально подтверждён
пользователем** после обнаружения пустого изображения первой истории.
Подробная история инцидента и безопасная очистка одноразовых
Windows-файлов находятся в `VK_PUBLICATION.md`.



При включении `vkPublish.enabled` и `vkPublish.automaticEnabled`
пятый этап использует **только текущий сегодняшний** полностью готовый job.
MP4/PNG берутся из `downloads`, ссылка Дзена из сохранённого состояния.
Перед загрузкой истории из готового горизонтального PNG формируется
`downloads/ИИ-Сводка YYYY-MM-DD-vk.png` (1080×1920, размытый фон и
резкий полный кадр по центру). Исходный PNG для других этапов не меняется.
Используется имеющийся `ffmpeg-static`, новых зависимостей нет.
Тексты создаются из отдельного `vk-publication-template.txt`, не из
изменяемого `downloads/_ИИ-Сводка.txt`.
Проверенные ранее стадии не перезапускаются при сбоях VK.
После инцидента 19.10.2026 pre-save загрузка оригинального PNG
может быть безопасно повторена максимум три раза на выпуск с сохранением
счётчика в state.json; повтор stories.save после неизвестного результата
по-прежнему запрещён. Видео 456239140, post 208 и восстановленная
story 456239132 подтверждены в логах; автоматическая публикация на
рабочей машине включена оператором 18.10.2026, но безопасный
config.example.json по-прежнему **выключен**.

Настройки, миграция из временного .env в локальный DPAPI файл, статусы,
безопасный incident recovery и ограничение подписи истории описаны
в [VK_PUBLICATION.md](VK_PUBLICATION.md).

## NotebookLM и media

The worker uses a dedicated protected Yandex Browser profile through CDP. It must
not delete/recreate that profile or its Google/NotebookLM/Dzen sessions.

Current NotebookLM home handling supports the current `+ Новый блокнот` /
`Недавние блокноты` UI while preserving compatibility with the previous
`Создать` / `Мои блокноты` surface. Source import waits for a stable
content-ready state before video generation: the worker accepts a substantial
visible central overview, legacy chat text, or a generated notebook title only
alongside a confirmed source count, no loading indicators, and an enabled
video control. After the readiness signals agree, the UI must remain stable
for at least 5 seconds (the source timeout remains configurable, with the
current 300-second operator setting). An untitled notebook is not sufficient
evidence on its own.

The newly created notebook's canonical URL is persisted as `CREATING_VIDEO`
*before* the potentially long source-readiness wait. If that wait times out,
a later scheduled run resumes the same notebook by URL, verifies readiness,
renames it to `ИИ-YYYY-MM-DD`, and only then starts generation, rather than
creating another notebook for the same publication. Existing notebook cards
remain the fallback when a saved URL cannot be opened.

Downloaded video is registered persistently and is not regenerated/redownloaded
when the same publication is already known. PNG preview is generated from the
first frame. FTP delivery is idempotent and does not trigger a second
NotebookLM-generation pass.

`downloads/_ИИ-Сводка.txt` is operator-owned after manual edits. Article-video
may replace only the exact still-empty second-link placeholder under
`Этот выпуск:`; if that placeholder is absent, the file is not rewritten.

## State, logs and history

Shared text writers use `log-utils.js` and rotate before append. Day boundaries
come from timestamps already present in the active log, not mtime/sidecar state,
so repeated same-day runs accumulate in one active file.

- active `worker.log`: 7-day rotated retention;
- error log: 30-day rotated retention;
- size threshold: 25 MB;
- rotated text logs live under local `archive/`.

`dzen-browser-runner.js` remains the documented direct-writer exception. When it
writes the first current-day line into an older active log, the next shared writer
archives only the older prefix and preserves the current-day suffix.

`history-utils.js` keeps a 14-calendar-day active window in `state.json` and
`downloads/_СКАЧАННЫЕ_ВИДЕО.json`. Older safe terminal history moves to monthly
JSON files under local `archive/`. Unresolved/error/verification-only jobs remain
active regardless of age. JSON archive is not auto-deleted and stays available for
duplicate/idempotency lookup and explicit old-date operator actions.

Empty `temp/` and `traces/` are not active runtime surfaces and are not
precreated.

## Native Dzen video publication

Since the 2026-10-25 incident, new native uploads persist the exact Dzen
draft ID as soon as remote creation is observed. After setting metadata/cover/
tags, DRAFT_PROCESSING allows a later scheduled run to reopen that exact
draft, check the unchanged metadata and continue waiting for server-side
processing. The normal "Опубликовать" action is attempted only after final
ready status and active button, once per draft. No "publish after processing"
button or automatic second upload is used. The child reserves the click in
state.json before dispatch. Dzen's processing may take longer than the
single-run wait window; that is NOT permission for a new upload.
Existing CLICKED_UNVERIFIED jobs (including both 2026-10-25 drafts) are not
automatically migrated or re-published.

Normal scheduled publication begins with a fail-closed duplicate guard in Studio
`Публикации → Видео`. It must confirm the real Video filter and match the
expected title prefix before any upload.

If an existing same-day video is confirmed, state becomes `PUBLISHED` and no
new draft/upload/publish click occurs.

If no duplicate exists, the validated production path runs one fresh-upload child
`dzen-publish-direct.js`. Metadata, cover and configured tags are set once,
readiness is status-driven, comments are set to `Все пользователи`, and the
child performs at most one publish action.

Scheduled safety state:

~~~text
PENDING (without draft ID)
  -> published duplicate guard
  -> UPLOAD_ARMED
  -> one fresh upload -> DRAFT_CREATED (draft ID pinned immediately)
  -> metadata/cover/tags confirmed -> DRAFT_PROCESSING
  -> if still processing: stop this pass, resume exact draft on next run
  -> final ready status -> durable CLICKED_UNVERIFIED -> one normal publish click
  -> read-only draft-ID + published-list verification -> PUBLISHED

Legacy RETRYABLE_PRE_CLICK / UPLOAD_ARMED / DRAFT_CREATED /
PUBLISH_ARMED / CLICKED_UNVERIFIED / BLOCKED_AMBIGUOUS
  -> verification or manual intervention only
  -> never a fresh upload
  -> never a second publish click
~~~

A fresh retry is allowed only when the previous child explicitly proved
`publishClicked=false`. Ambiguous post-arm/post-click outcomes remain
verification-only.

The runner has no special handling or waiting for human verification popups.
The user may resolve them manually. The direct publisher polls an extensible
`dzen-safe-notices` allowlist **during** the existing 45-second observation
after the single publish click. Unknown prompts remain untouched and do not
extend the observation window. An unverified click never permits a second
upload or click.

Emergency switch:

~~~json
"dzenUpload": {
  "automaticEnabled": false
}
~~~

Missing `automaticEnabled` in an older local config is treated as `true`.
Default verification timeout is 90000 ms.

Manual operator entrypoints remain:

~~~cmd
run-dzen-publish.cmd --date=YYYY-MM-DD
run-dzen-dry-run.cmd
~~~

Deep selectors, metadata/tag/readiness rules and live evidence are canonical in
[`DZEN_NATIVE_UPLOAD.md`](DZEN_NATIVE_UPLOAD.md) and
[`DZEN_VIDEO_EXPERIMENTS.md`](DZEN_VIDEO_EXPERIMENTS.md).

После единственного клика «Опубликовать» прямой Dzen writer оставляет редактор
открытым на 45 секунд для read-only наблюдения. При неопределённости
сохраняется PNG в `screenshots/`, а `CLICKED_UNVERIFIED` запрещает второй
upload/click. После ручной публикации штатный запуск найдёт готовое видео.

**Независимый VK:** только при готовом проверенном MP4/PNG текущей даты
и опубликованной статье-сводке Дзена. Если dzenArticleVideo не запускался
из-за неопубликованного Dzen-видео, отдельный `dzen-article-link.js`
через Studio «Опубликованные» → «Статьи» находит ровно одну
same-day публикацию и независимо проверяет её публичную страницу. URL
сохраняется в `job.dzenPublishedArticle.url` со статусом `VERIFIED`,
после чего допускается `vk-stage.mjs`. При отсутствии статьи VK не
публикуется; `rybalka.one` и `/video/watch/` не являются fallback.
Ссылка статьи фиксируется в `job.vkPublication.articleUrl` и не меняется
после начала VK-публикации. Статусы Dzen-видео, подборок и вставки видео
в статью VK не блокируют. Общий `full-worker.lock` и последовательная
запись `state.json` предотвращают гонки; старые даты не запускаются
автоматически.

## Dzen collections

After native publication is confirmed, `dzen-collections.js` manages exactly
two same-day targets:

- video → `Видеосводки по ИИ`;
- daily digest → `Сводки по ИИ`.

Zero or one visible target is valid; unrelated publications are never substituted.

Per-target state is independent:

~~~text
job.dzenCollections.video.status = ADDED
job.dzenCollections.digest.status = ADDED

0 ADDED -> PENDING
1 ADDED -> PARTIAL
2 ADDED -> COMPLETE
~~~

A completed target is never clicked again. Once aggregate state is `COMPLETE`,
future scheduled runs skip the collections browser child.

The worker scrolls the exact target tile into a safe visible position and verifies
target-local state before persisting `ADDED`. A page-wide success message alone
is not sufficient. Already-added detection and post-click confirmation are
fail-closed; an ambiguous action never authorizes a second automatic collection
click.

Manual entrypoints:

~~~cmd
run-dzen-collections-debug.cmd --date=YYYY-MM-DD
run-dzen-collections-apply.cmd --date=YYYY-MM-DD
~~~

Their filenames are intentionally stable; canonical implementation is
`dzen-collections.js`.

## Video in the same-day Dzen article

The fourth stage runs only after native video is `PUBLISHED` and collections are
`COMPLETE`. `dzen-article-video.js` resolves exact same-day article/video URLs
through Studio and inserts the video before H2 `Мировые лидеры ИИ` under a new
H2 `Видеосводка`.

The production video paste is dispatched inside the browser page with
`ClipboardEvent` + `DataTransfer(text/plain=<videoUrl>)`, so it does not depend
on the Windows desktop clipboard and can be tested with the workstation locked.
Windows clipboard remains only a last-resort Studio URL fallback. Publish still
requires a real Dzen video preview, stable autosave and the existing two-stage
at-most-once publish/save flow.

Safety states `PUBLISH_ARMED`, `CONFIRMATION_ARMED` and
`CLICKED_UNVERIFIED` are verification-only on later runs. They must never cause
a second editor mutation or publish/save click. Exact pre-existing H2
`Видеосводка` ends as `SKIPPED_EXISTING`.

`ERROR` is terminal by default. Two production one-shot scheduled recovery
classes remain, plus one isolated one-shot browser-paste migration recovery for legacy clipboard-related ERROR:

1. proven pre-edit link-resolution failure with no resolved links/editor/publish
   markers;
2. pre-publish clipboard-related failure with resolved links but no publish
   markers, after mandatory live-draft inspection;
3. one isolated `--recover-browser-paste-migration` attempt for an old
   clipboard-related ERROR. This new attempt is independent of old clipboard
   recovery history, but its own migration marker is at-most-once.

The second and third cases may resume an already confirmed plain heading + video
embed only from H2 formatting, never by inserting another embed.

Manual entrypoints:

~~~bat
run-dzen-article-video-dry-run.cmd --date=YYYY-MM-DD
run-dzen-article-video-apply.cmd --date=YYYY-MM-DD
~~~

Full editor/state/recovery contract and acceptance evidence:
[`DZEN_ARTICLE_VIDEO.md`](DZEN_ARTICLE_VIDEO.md).

## Антивирус

До первого запуска/восстановления/обновления добавьте точную рабочую папку
NotebookLMBot в исключения активного антивируса. Для текущего deployment это
`C:\TRASH\NotebookLMBot`; при другом `TargetDir` исключение должно указывать
именно на него.

Не отключайте антивирус целиком и не исключайте весь диск/Windows profile.
Подробная deployment-процедура и то же safety warning находятся в
[`DEPLOYMENT.md`](DEPLOYMENT.md) и `НАСТРОЙКИ.txt`.

## Что хранится в Git

Коммитятся только portable source, safe templates, dependency manifests,
launchers, documentation и offline tests.

`package.json` и `package-lock.json` являются одной версионируемой единицей.
Dependency change обновляет lockfile в том же PR и должен доказывать clean
`npm ci`.

Не коммитятся:

- real `config.json` / `ftp-access.json`;
- DPAPI access data;
- state/history/logs/screenshots;
- downloaded media;
- protected browser profile;
- machine-local runtime state.

## Настройка

Preferred bootstrap: `setup-local.ps1`. Он создаёт local config из safe
template, подставляет machine paths/profile, копирует dependency manifests,
выполняет `npm ci --no-audit --no-fund` и проверяет основные entrypoints.

FTP credentials создаются только явно через `-ConfigureFtp` или
`configure-ftp-access.ps1`. Local FTP access защищён Windows DPAPI
`CurrentUser` и должен быть пересоздан при смене Windows user profile.

Полная процедура: [`DEPLOYMENT.md`](DEPLOYMENT.md).

## FTP boundary

Worker работает только внутри remote directory `video` и управляет текущими:

- `ai-svodka-YYYY-MM-DD.mp4`;
- `ai-svodka-YYYY-MM-DD.png`.

Он не удаляет/переименовывает/перезаписывает другие remote paths. Existing file
с правильным размером считается уже доставленным; size conflict завершается
ошибкой вместо destructive overwrite.

## Проверка

PR Gate вызывает Video CI для video-domain. Изменение общей
`automation/ARCHITECTURE.md` может сделать PR cross-cutting и потребовать Main
CI.

Video CI остаётся offline относительно NotebookLM, FTP, Dzen, production APIs и
Windows DPAPI. Точный набор задаётся `.github/workflows/video-ci.yml`.

Локальный базовый прогон:

~~~powershell
npm ci --no-audit --no-fund
node --check .\worker.js
node --check .\full-worker.js
node --check .\scheduled-worker.js
node --check .\dzen-collections.js
npm test
~~~

Real browser/NotebookLM/Dzen/DPAPI behavior проверяется только на целевой
Windows-машине.

## Исправление подтверждения видео и уведомления Дзена (26.10.2026)

При сохранённом `dzenAutomation.draftId` публикация теперь подтверждается
по публичной ссылке `dzen.ru/video/watch/<ID>`, найденной непосредственно
в строке опубликованного видео Студии. Повторно открывать редактор через
`state=draft` для доказательства публикации не требуется: такое открытие
после настоящей публикации возвращало `UNKNOWN` и вызывало циклические
проверки. Если ID из строки получить нельзя или он отличается, статус не
подменяется и повторная публикация запрещена.

Только для явного информационного окна `Видео загружено за N сек` разрешена
однократная установка флажка `Больше не показывать такие сообщения`.
Капчи/проверки человека, включая `Я не робот` и `Я не против`, никогда
не подтверждаются автоматически.

### Универсальное наблюдение уведомлений (26.10.2026)

В `dzen-browser-runner.js` нет специфической логики проверки человека,
таймера её ожидания или PowerShell-поднятия окна. Обнаружение известных
информационных уведомлений выполняется через
`dzen-safe-notices.processKnownDzenNotices()` во время прежних 45 секунд
наблюдения после клика публикации; обработка продолжается и если редактор
закрыл вкладку. Поддерживаемые уведомления добавляются только в
`dzen-safe-notices.js`. Неизвестные окна остаются оператору и не вызывают
повторных нажатий публикации.
