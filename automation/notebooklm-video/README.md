# NotebookLM video worker

`automation/notebooklm-video/` — отдельный локальный downstream-подпроект внутри
общего проекта ИИ-Сводок. Он не участвует в ночном GitHub Actions production и
не формирует новости. Его работа начинается после публикации ежедневной
ИИ-Сводки: найти сегодняшний выпуск в RSS, создать видеоповествование в
NotebookLM, скачать MP4, создать PNG-превью первого кадра и при включённой
настройке доставить оба файла в строго ограниченный FTP-каталог `video`.

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
  -> если видео уже есть: DONE
  -> иначе один fresh-upload child -> один publish click
  -> post-click проверка через вкладку Видео
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
- принудительное сворачивание Яндекс.Браузера управляется конфигурацией.

## Автоматическая публикация видео в Дзен

`run-worker.cmd` теперь является единым production-entrypoint локального downstream.
Он запускает `scheduled-worker.js`, а тот последовательно выполняет две фазы:
сначала существующий `worker.js` (RSS -> NotebookLM -> MP4/PNG -> optional FTP),
затем Dzen после выбора самого свежего локального `DONE` job с датой не позже текущей.
Отдельная задача Планировщика Windows для Дзена не нужна.

После успешного `worker.js` выбирается самый свежий `DONE` job с датой не позже
текущей локальной даты. Поэтому delayed/catch-up выпуск предыдущего дня не
теряется, а future-dated state никогда не запускает публикацию.

Dzen использует тот же защищённый профиль Яндекс.Браузера и тот же CDP-порт, но
не одновременно с NotebookLM. `worker.js` сначала штатно закрывает свой browser;
только после выхода child оркестратор запускает новый Dzen browser session.

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

- `worker.js` и `scheduled-worker.js`;
- Dzen runtime (`browser-session.js`, duplicate guard, runner и publishers);
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
`package-lock.json`, выполняет `npm ci --no-audit --no-fund` и проверяет
`worker.js`. Реальный FTP-доступ создаётся только при явном `-ConfigureFtp`; без
него используется отдельная команда `configure-ftp-access.ps1`.

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

На pull request always-on `PR Gate` вызывает Video CI только когда затронут
video-домен; Main CI для video-only изменений не запускается. Video CI выполняет
переносимые dependency-free проверки:

```text
node --check worker.js
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
node --check .\scheduled-worker.js
npm test
```

Windows DPAPI и реальный browser/NotebookLM/Dzen flow проверяются на целевой
Windows-машине. Полный перенос на новую машину описан в [DEPLOYMENT.md](DEPLOYMENT.md).
