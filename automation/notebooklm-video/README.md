# NotebookLM video worker

`automation/notebooklm-video/` — отдельный локальный downstream-подпроект внутри
общего проекта ИИ-Сводок. Он не участвует в ночном GitHub Actions production и
не формирует новости. Его работа начинается после публикации ежедневной
ИИ-Сводки: найти сегодняшний выпуск в RSS, создать видеоповествование в
NotebookLM, скачать MP4, создать PNG-превью первого кадра, при включённой
настройке доставить оба файла в строго ограниченный FTP-каталог `video`,
опубликовать нативное видео в Дзен и затем добавить обе публикации текущего дня в
свои Дзен-подборки.

Общая граница подпроекта относительно production и CI описана в
[`../ARCHITECTURE.md`](../ARCHITECTURE.md). Локальные правила изменений находятся
в [`AGENTS.md`](AGENTS.md), перенос на Windows-машину — в
[`DEPLOYMENT.md`](DEPLOYMENT.md).

## Изоляция от основного production

Подпроект хранится в общем репозитории, потому что использует тот же выпуск,
дату и URL публикации. При этом runtime и жизненный цикл изолированы:

- video worker выполняется на Windows-машине пользователя;
- основной nightly production не читает video state и не ждёт video result;
- video-only изменения проверяет отдельный **Video CI**;
- **Main CI** намеренно исключает video-only paths;
- `daily-production`, основной FTP deploy, repository cleanup и repository
  hygiene не должны зависеть от этого каталога.

Эта граница закреплена offline contract tests, чтобы локальный worker не стал
скрытой production-зависимостью.

## Рабочая схема

```text
RSS rybalka.one
  -> Windows Task Scheduler
  -> run-worker-hidden.vbs / run-worker.cmd
  -> full-worker.js
  -> scheduled-worker.js
  -> worker.js
  -> отдельный Яндекс.Браузер + защищённый профиль
  -> Playwright connectOverCDP(127.0.0.1:9222)
  -> NotebookLM
  -> локальный MP4
  -> PNG первого кадра через ffmpeg-static
  -> FTP: только каталог video
  -> закрыть NotebookLM browser/CDP
  -> Dzen duplicate guard: Публикации -> Видео
  -> если видео уже есть: PUBLISHED
  -> иначе один fresh-upload child -> один publish click
  -> при редком post-click «Я не робот»: только ручное подтверждение, без auto-click
  -> post-click проверка через вкладку Видео -> PUBLISHED
  -> dzen-collections.js
  -> видео дня -> «Видеосводки по ИИ»
  -> ежедневная сводка -> «Сводки по ИИ»
  -> сохранить отдельные статусы video/digest
```

Ключевые свойства текущей реализации:

- комплектный Chromium Playwright не используется;
- Google/NotebookLM работают через отдельный Яндекс-профиль;
- внешний IP проверяется внутри браузера до открытия Google;
- существующий блокнот открывается через href карточки;
- импорт источника ждёт стабилизации интерфейса;
- текущий блокнот безусловно переименовывается в `ИИ-YYYY-MM-DD`;
- готовое видео скачивается только один раз и фиксируется в постоянном реестре;
- `_ИИ-Сводка.txt` после ручного заполнения второй полной ссылки для текущего
  выпуска больше не перезаписывается;
- FTP-доставка идемпотентна и не запускает повторную генерацию/скачивание;
- worker работает на FTP только внутри `video` и не изменяет остальные файлы;
- обычный лог ротируется за 7 дней, error-log — за 30 дней;
- принудительное сворачивание Яндекс.Браузера управляется конфигурацией;
- завершённые Dzen-подборки фиксируются в `state.json`, поэтому browser для этого
  этапа не открывается снова после полного подтверждения.

## Автоматическая публикация видео в Дзен

`run-worker.cmd` является единым production-entrypoint локального downstream. Он
запускает внешний `full-worker.js`. Тот держит lock всего scheduled flow и сначала
вызывает существующий `scheduled-worker.js`, который последовательно выполняет
две уже проверенные фазы: `worker.js` (RSS -> NotebookLM -> MP4/PNG -> optional
FTP), затем Dzen publish после выбора самого свежего локального `DONE` job с датой
не позже текущей. После подтверждённого `PUBLISHED` внешний worker может выполнить
третью фазу подборок. Отдельные задачи Планировщика Windows для Дзена или подборок
не нужны.

После успешного `worker.js` выбирается самый свежий `DONE` job с датой не позже
текущей локальной даты. Поэтому delayed/catch-up выпуск предыдущего дня не
теряется, а future-dated state никогда не запускает публикацию.

Dzen использует тот же защищённый профиль Яндекс.Браузера и тот же CDP-порт, но
не одновременно с NotebookLM. `worker.js` сначала штатно закрывает свой browser;
только после выхода child оркестратор запускает новую Dzen browser session.

Перед любым upload выполняется live-проверенный duplicate guard:

```text
Studio -> Публикации -> Видео
  -> radio input[type="radio"][aria-label="Видео"]
  -> checked=true
  -> искать title prefix до " | "
```

Если ожидаемое видео уже видно, оркестратор записывает Dzen как `PUBLISHED` и
ничего не загружает. Если совпадения нет, разрешается ровно один fresh-upload
child `dzen-publish-direct.js`: MP4, metadata один раз, PNG cover, ровно пять
tag-chip, финальная готовность, comments=`Все пользователи`, один publish click.

После единственного publish click `dzen-browser-runner.js` в течение 4 секунд
проверяет, не появилось ли редкое окно `Подтвердите, что вы не робот` / `Я не
робот`. Это human-only challenge: автоматизация **никогда не нажимает checkbox и
не пытается обходить проверку**. Если окно появилось, runner восстанавливает
свёрнутое окно Яндекс.Браузера, выводит страницу на передний план и до 120 секунд
только ждёт ручного подтверждения. Пока challenge видим, других UI-click нет.
После его исчезновения выполняется обычная post-click verification. Если окно не
исчезло за лимит, исход считается post-click неопределённостью: новый upload и
второй publish click остаются запрещены, дальнейшие scheduled runs работают
только в verification-only режиме.

Для автоматического режима поверх проверенного direct child добавлена fail-closed
state machine в существующем `state.json`:

```text
PENDING / RETRYABLE_PRE_CLICK
  -> duplicate guard
  -> PUBLISH_ARMED (сохраняется ДО live child)
  -> один live child
  -> CLICKED_UNVERIFIED
  -> verification через Публикации -> Видео
  -> PUBLISHED

PUBLISH_ARMED / CLICKED_UNVERIFIED / BLOCKED_AMBIGUOUS
  -> только verification
  -> НИКОГДА новый upload
  -> НИКОГДА второй publish click
```

Повтор fresh upload допустим только когда предыдущий child явно успел сообщить
`publishClicked=false`. Если процесс оборвался неоднозначно после `PUBLISH_ARMED`,
следующие scheduled runs лишь проверяют список `Видео`.

По умолчанию `dzenUpload.automaticEnabled=true`. Для аварийного отключения только
автоматической Dzen-фазы установить:

```json
"dzenUpload": {
  "automaticEnabled": false
}
```

Отсутствие `automaticEnabled` в старом локальном `config.json` трактуется как
`true`, потому что этот флаг появился именно при promotion в scheduled production.
`verificationTimeoutMs` по умолчанию равен 90000 мс.

Ручные `run-dzen-publish.cmd --date=YYYY-MM-DD` и `run-dzen-dry-run.cmd` сохранены
как операторские/диагностические entrypoints, но штатное расписание их не вызывает.
Подробный browser-upload контракт находится в
[`DZEN_NATIVE_UPLOAD.md`](DZEN_NATIVE_UPLOAD.md).

## Автоматическое добавление в Дзен-подборки

После подтверждённого `job.dzenAutomation.status=PUBLISHED` внешний
`full-worker.js` выполняет отдельную третью фазу `dzen-collections.js`. Она
работает только с публикациями той же даты, что и выбранный локальный job, и знает
ровно две цели:

```text
Видео:
  ИИ-Сводка на <дата> | Подпишись, чтоб получать свежее!
  -> Видеосводки по ИИ
  -> https://dzen.ru/suite/a899d818-52b3-4f87-8e49-4a4bac375244

Ежедневная сводка:
  ИИ-Сводка на <дата>
  -> Сводки по ИИ
  -> https://dzen.ru/suite/7971db4c-2a4e-449f-b8bf-c3907486d6f1
```

Если в конкретный момент видна только одна или ни одной из двух публикаций,
никакая чужая публикация не используется как замена. Отсутствующая цель остаётся
`PENDING` и может быть проверена следующим 10-минутным запуском.

Факт успешного назначения хранится отдельно по каждой цели:

```text
job.dzenCollections.video.status = ADDED
job.dzenCollections.digest.status = ADDED

0 ADDED -> dzenCollections.status = PENDING
1 ADDED -> dzenCollections.status = PARTIAL
2 ADDED -> dzenCollections.status = COMPLETE
```

Если обе цели `ADDED`, следующий scheduled run завершает третью фазу **до запуска
browser child**. Если `ADDED` только одна, `dzen-collections.js` открывает browser
и обрабатывает только вторую цель. Уже завершённая цель не переоткрывается.

Live-тест 29.08.2026 подтвердил необычный Dzen UI contract для уже добавленной
подборки: tile остаётся формально hit-testable и не получает нормальный
`disabled`/ARIA marker, но точное название приглушается до
`rgba(6, 6, 15, 0.6)`. Поэтому alpha `<= 0.70` считается подтверждённым
`already-added`, и повторный клик запрещён.

Для новой цели выполняется один физический клик по подтверждённой плашке
подборки. После клика требуется success-text или переход tile в уже подтверждённое
muted-состояние. При неоднозначности второй автоматический клик не выполняется:
этап пишет ошибку, делает screenshot при возможности, закрывает браузер и оставляет
только эту цель незавершённой.

Ручные команды сохранены под теми же именами, которые использовались во время
отладки, чтобы локальный каталог не обрастал версиями:

```cmd
run-dzen-collections-debug.cmd --date=YYYY-MM-DD
run-dzen-collections-apply.cmd --date=YYYY-MM-DD
```

Первая команда не кликает по подборке, вторая применяет тот же production
алгоритм вручную. Канонический исходник — `dzen-collections.js`.

## Антивирус: обязательное исключение рабочей папки

До первого запуска, восстановления или обновления локального образа необходимо
сразу добавить **точную рабочую папку NotebookLMBot** в исключения активной
антивирусной программы. Для текущего развёртывания это:

```text
C:\TRASH\NotebookLMBot
```

Если `TargetDir` выбран другой, исключение должно указывать именно на него.
Worker запускает Node.js, управляет браузером через Playwright/CDP, использует
PowerShell/DPAPI и `ffmpeg-static`, поэтому поведенческие эвристики антивируса
могут помещать отдельные runtime-файлы в карантин или удалять их.

Не отключать антивирус целиком и не добавлять в исключения весь диск, весь
Windows-профиль пользователя или `C:\Program Files`. Исключение должно быть
узким и относиться только к рабочей папке NotebookLMBot. Защищённый профиль
Яндекс.Браузера является отдельным runtime-активом и этим требованием
автоматически не охватывается.

То же предупреждение продублировано в [`НАСТРОЙКИ.txt`](НАСТРОЙКИ.txt) и в
[`DEPLOYMENT.md`](DEPLOYMENT.md).

## Что хранится в Git

В репозитории находятся только переносимые исходники, шаблоны и инструкции:

- `worker.js`, `scheduled-worker.js` и внешний `full-worker.js`;
- Dzen runtime (`browser-session.js`, duplicate guard, runner, publishers и
  `dzen-collections.js`);
- совместимый `dzen-collections-debug.js` и две ручные команды подборок;
- `package.json` с фиксированными верхнеуровневыми версиями зависимостей;
- `package-lock.json` с зафиксированным полным транзитивным npm-деревом;
- `config.example.json`;
- `ftp-access.example.json`;
- `setup-local.ps1` и `configure-ftp-access.ps1`;
- `install-ftp-support.cmd`;
- portable `run-worker.cmd` и `run-worker-hidden.vbs`;
- `НАСТРОЙКИ.txt` с локальной памяткой;
- документация и безопасные offline smoke tests.

`package.json` и `package-lock.json` являются одной версионируемой единицей.
Изменение npm-зависимостей должно обновлять lockfile в том же pull request.
Локальная установка выполняется через `npm ci`.

Реальные локальные конфиги, доступы, state, журналы, скачанные медиафайлы,
диагностические файлы и профиль браузера в Git не попадают. Правила закреплены
локальным `.gitignore`.

## Конфигурация

Предпочтительный способ первичной настройки — `setup-local.ps1`. Он создаёт
рабочую конфигурацию из безопасного шаблона, подставляет выбранный каталог,
текущий Windows-профиль и локальные пути, копирует `package.json` вместе с
`package-lock.json`, выполняет `npm ci --no-audit --no-fund` и проверяет основные
worker entrypoints. Реальный FTP-доступ создаётся только при явном
`-ConfigureFtp`; без него используется отдельная команда
`configure-ftp-access.ps1`.

`npm ci` намеренно удаляет существующий `node_modules` и восстанавливает его
строго по committed lockfile. Локальный FTP access защищается Windows DPAPI
`CurrentUser` и при переносе под другой Windows-профиль создаётся заново.

## FTP-граница

После подключения worker проверяет каталог `video` и создаёт его при отсутствии.
В него загружаются только текущие:

- `ai-svodka-YYYY-MM-DD.mp4`;
- `ai-svodka-YYYY-MM-DD.png`.

Другие FTP-каталоги и файлы worker не должен удалять, переименовывать или
перезаписывать. Существующий файл правильного размера считается уже доставленным;
конфликт размера завершает FTP-этап ошибкой вместо destructive overwrite.

## Проверка в GitHub

На pull request always-on `PR Gate` вызывает Video CI для video-домена; изменение
общей `automation/ARCHITECTURE.md` также может потребовать Main CI как
cross-cutting documentation contract. Video CI выполняет переносимые
dependency-free проверки:

```text
node --check worker.js
node --check full-worker.js
node --check dzen-collections.js
node --check tests/*.js
npm test
```

Тесты не открывают NotebookLM, не подключаются к FTP/Dzen, не используют
production API и не эмулируют Windows DPAPI. Отдельный lockfile contract smoke
проверяет синхронизацию `package.json`/`package-lock.json` и использование
`npm ci` в install entrypoints.

Локально после получения исходников или изменения зависимостей выполнять:

```powershell
npm ci --no-audit --no-fund
node --check .\worker.js
node --check .\full-worker.js
node --check .\scheduled-worker.js
node --check .\dzen-collections.js
npm test
```

Windows DPAPI и реальный browser/NotebookLM/Dzen flow проверяются на целевой
Windows-машине. Полный перенос на новую машину описан в [DEPLOYMENT.md](DEPLOYMENT.md).
