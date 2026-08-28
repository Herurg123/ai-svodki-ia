# Развёртывание NotebookLM video worker

Эта инструкция предназначена для переноса локального video-worker на другую
Windows-машину или в новый рабочий каталог. Она не заменяет основной GitHub
production ИИ-Сводок и не требует изменения ночных GitHub Actions.

## 1. Предварительные требования

Нужны:

- Windows;
- Node.js;
- установленный Яндекс.Браузер;
- доступ к RSS выпуска;
- отдельный рабочий профиль Яндекс.Браузера с действующей Google/NotebookLM
  сессией, ZeroOmega и необходимым прокси;
- разрешённый внешний IP для браузерной проверки;
- при использовании FTP — отдельная FTP-учётка.

Защищённый профиль браузера является локальным runtime-активом. Он не хранится
в Git и не создаётся `setup-local.ps1`.

### Обязательное исключение антивируса до установки

Рабочую папку локального образа NotebookLMBot необходимо **сразу после её
создания и до копирования, восстановления, `npm ci` или первого запуска**
добавить в исключения активной антивирусной программы.

Для текущего рабочего развёртывания:

```text
C:\TRASH\NotebookLMBot
```

Если используется другой `TargetDir`, исключение должно указывать только на этот
фактический рабочий каталог. Поведенческие эвристики антивирусов могут помещать
в карантин или удалять `worker.js`, npm runtime-файлы, исполняемые зависимости
вроде `ffmpeg.exe` и другие части локального образа, после чего установка может
выглядеть частично рабочей, но ломаться на отдельном этапе.

Не отключать антивирус целиком и не исключать весь диск, весь пользовательский
профиль или `C:\Program Files`. Требуется узкое исключение только для рабочей
папки NotebookLMBot. Защищённый профиль Яндекс.Браузера находится отдельно и не
добавляется в это исключение автоматически.

Если антивирус уже вмешивался в папку, сначала добавить рабочий каталог в
исключения, затем восстановить канонические файлы и зависимости и только после
этого выполнять проверочный запуск.

Это требование также вынесено в `НАСТРОЙКИ.txt`, который должен находиться рядом
с локальными runtime-файлами.

## 2. Получение исходников

Клонировать основной репозиторий и перейти в:

```text
automation/notebooklm-video/
```

В каталоге должны присутствовать одновременно `package.json` и
`package-lock.json`. Lockfile является частью канонического переносимого
комплекта и фиксирует полное npm-дерево зависимостей.

Не копировать из Git никакие реальные секреты: их там быть не должно.

## 3. Автоматическая подготовка рабочего каталога

Пример:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup-local.ps1 `
  -TargetDir "C:\TRASH\NotebookLMBot" `
  -BrowserProfile "C:\Users\<USER>\NotebookLMBot-test\yandex-profile" `
  -ConfigureFtp
```

Перед выполнением этой команды целевой `TargetDir` уже должен быть добавлен в
исключения активного антивируса.

Скрипт:

1. копирует переносимые runtime-файлы, включая `worker.js`, `scheduled-worker.js`,
   Dzen browser-upload runtime, `package.json`, `package-lock.json` и `НАСТРОЙКИ.txt`;
2. создаёт `config.json` из `config.example.json`;
3. подставляет локальные каталоги;
4. запрашивает разрешённый внешний IP, если он не передан параметром;
5. выполняет `npm ci --no-audit --no-fund` строго по committed lockfile;
6. выполняет `node --check worker.js`;
7. при необходимости запускает интерактивное создание `ftp-access.json`.

`npm ci` намеренно не обновляет dependency tree. Если `package.json` и
`package-lock.json` расходятся, установка завершается ошибкой. При успешном
запуске существующий `node_modules` заменяется содержимым, соответствующим
lockfile.

После этого вручную проверить параметры `config.json`, особенно:

- `browserExecutable`;
- `browserProfile`;
- `allowedIp`;
- `minimizeBrowserWindow`;
- `ftpUpload.enabled`;
- `ftpUpload.publicBaseUrl`;
- `dzenUpload.automaticEnabled`;
- `dzenUpload.channelName`;
- `dzenUpload.verificationTimeoutMs`.

## 4. Локальный FTP-доступ

Использовать:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  C:\TRASH\NotebookLMBot\configure-ftp-access.ps1
```

Скрипт создаёт локальный файл с `protocol=0`. На ближайшем запуске worker при
включённой FTP-доставке переведёт его в `protocol=1` средствами Windows DPAPI
`CurrentUser`, даже если текущий выпуск уже полностью доставлен.

Защищённое значение нельзя переносить как рабочее между разными Windows-
пользователями. При смене машины/профиля создать локальный файл заново.

## 5. Защищённый профиль Яндекс.Браузера

Профиль должен содержать действующие:

- Google session;
- NotebookLM session;
- cookies/local data;
- ZeroOmega;
- proxy configuration.

Его нельзя автоматически заменять обычным профилем Яндекс.Браузера. При переносе
проверить вручную, что профиль запускается и NotebookLM открывается без повторного
ввода учётных данных.

## 6. Ручная проверка до Планировщика

Если исходники только что получены или зависимости были обновлены, сначала
выполнить в каталоге подпроекта:

```powershell
npm ci --no-audit --no-fund
node --check .\worker.js
node --check .\scheduled-worker.js
npm test
```

Для наблюдения за полным scheduled flow временно установить
`minimizeBrowserWindow=false`, затем запустить именно production-entrypoint:

```cmd
cd /d C:\TRASH\NotebookLMBot
run-worker.cmd
```

`node worker.js` допустим только как NotebookLM-only диагностика и сам Dzen-фазу
не запускает.

Проверить: browser стартует с нужным защищённым профилем; IP совпадает; RSS и
NotebookLM доступны; после готового MP4/PNG и optional FTP первый browser закрыт;
затем Dzen duplicate guard подтверждает вкладку `Видео`. Для уже опубликованного
выпуска он обязан завершиться без upload. Fresh publish следует проверять на
реальном новом выпуске уже после отдельного решения о live rollout.

После проверки вернуть `minimizeBrowserWindow=true`, если нужен фоновый режим.

## 7. Планировщик Windows

Рабочая цепочка:

```text
Task Scheduler -> wscript.exe -> run-worker-hidden.vbs
               -> run-worker.cmd -> scheduled-worker.js
               -> worker.js -> NotebookLM -> MP4/PNG -> optional FTP
               -> Dzen duplicate guard -> optional fresh publish -> verification
```

Рекомендуемый production-контракт текущего развёртывания сохраняется: ежедневно,
каждые 10 минут примерно с 06:30 до 11:00 Europe/Moscow, только при входе
пользователя, без видимого console window, с запрещёнными параллельными
экземплярами и выполнением пропущенного запуска после входа. Компьютер
автоматически не пробуждается.

Дополнительно `scheduled-worker.lock` защищает всю двухфазную цепочку, поэтому
новый 10-минутный trigger не может войти в Dzen, пока предыдущий full run ещё
работает.

После создания задачи выполнить один ручной запуск из Task Scheduler и проверить
`worker.log` и `state.json`.

## 8. Что переносить со старой машины

По необходимости переносить отдельно от Git:

- защищённый профиль Яндекс.Браузера;
- рабочий `config.json` только как справочник, затем проверить пути;
- `state.json`, если нужно продолжить незавершённую генерацию;
- `downloads/_СКАЧАННЫЕ_ВИДЕО.json`, если нужно сохранить историю уже скачанных
  выпусков;
- локальные MP4/PNG только если они нужны для недовыполненной FTP-доставки.

`node_modules` переносить между машинами не требуется и не рекомендуется: на
целевой машине зависимости восстанавливаются через `npm ci` из committed
`package-lock.json`.

Не следует просто переносить `protocol=1` как универсальный секрет между
Windows-пользователями. На новом профиле локальный доступ создаётся заново.

## 9. Проверка после переноса

```powershell
npm ci --prefix C:\TRASH\NotebookLMBot --no-audit --no-fund
node --check C:\TRASH\NotebookLMBot\worker.js
node --check C:\TRASH\NotebookLMBot\scheduled-worker.js
Get-Content -Raw C:\TRASH\NotebookLMBot\config.json | ConvertFrom-Json | Out-Null
```

Затем проверить фактические результаты, а не только exit code:

- `worker.log`;
- `state.json`;
- реестр скачиваний;
- локальный MP4/PNG;
- FTP `video/`;
- отсутствие повторной обработки NotebookLM `DONE`;
- `job.dzenAutomation.status` и отсутствие второго upload/click после `PUBLISH_ARMED`;
- подтверждение `PUBLISHED` через Studio `Видео` после успешного live publish.

## 10. Обновление npm-зависимостей

Если меняется любая запись `dependencies` в `package.json`, в том же pull request
обязательно обновляется `package-lock.json` штатным npm. После обновления нужно
проверить чистую установку `npm ci` и dependency-free `npm test`.

Обычное развёртывание и helper `install-ftp-support.cmd` не должны выполнять
`npm install`: они используют только `npm ci` и не переписывают lockfile.

## 11. Откат

Перед заменой рабочего `worker.js` всегда сохранять резервную копию. Git хранит
канонический исходник подпроекта, включая manifest и lockfile, но локальный
runtime может иметь ещё не перенесённые настройки. При откате менять только
код/шаблоны и не удалять профиль браузера, state, реестр или скачанные медиа.
