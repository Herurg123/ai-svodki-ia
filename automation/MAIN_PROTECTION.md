# Активация защиты `main`

Этот документ описывает операторскую часть защиты `main`. Каноническая
архитектура находится в [`ARCHITECTURE.md`](ARCHITECTURE.md), а machine-readable
ruleset — в [`config/main-branch-ruleset.json`](config/main-branch-ruleset.json).

Наличие JSON-файла в Git **не активирует** GitHub ruleset автоматически. Ruleset
включается только после подготовки отдельного write deploy key, иначе ночной
production и 32-дневный cleanup потеряют право на свои валидированные direct
push в `main`.

## 1. Что должно быть в `main` до активации

До включения ruleset должны быть смержены:

- always-on `.github/workflows/pr-gate.yml`;
- reusable `ci.yml` и `video-ci.yml`;
- `automation/scripts/push_protected_main.sh`;
- передача `MAIN_PUSH_DEPLOY_KEY` только в финальные commit/push steps
  `daily-production.yml` и `repository-cleanup.yml`;
- contract tests защиты `main`.

`Required PR Gate` должен хотя бы один раз успешно завершиться на реальном pull
request. Main CI и Video CI не назначаются required checks напрямую.

## 2. Создать отдельный deploy key

Ключ создаётся локально администратором репозитория. Приватный ключ не нужно
передавать в чат, коммитить, класть в artifacts или сохранять рядом с runtime
конфигами проекта.

Пример команды:

```bash
ssh-keygen -t ed25519 -C "ai-svodki-main-writer" -f ai-svodki-main-writer -N ""
```

Получаются два файла:

- `ai-svodki-main-writer.pub` — публичная часть;
- `ai-svodki-main-writer` — приватная часть.

## 3. Добавить write deploy key в GitHub

В репозитории открыть:

`Settings → Deploy keys → Add deploy key`

Добавить **публичную** часть `ai-svodki-main-writer.pub`, задать понятное имя,
например `AI Svodki protected-main writer`, и включить **Allow write access**.

Этот ключ предназначен только для двух автоматических writer-контуров проекта.
Не использовать его как обычный пользовательский SSH-ключ.

## 4. Добавить Actions secret

Открыть:

`Settings → Secrets and variables → Actions → New repository secret`

Имя секрета:

```text
MAIN_PUSH_DEPLOY_KEY
```

Значение — полное содержимое **приватного** файла `ai-svodki-main-writer`,
включая строки `BEGIN/END OPENSSH PRIVATE KEY`.

После сохранения локальный приватный файл следует удалить либо хранить в
подходящем защищённом хранилище. Публичный `.pub` секретом не является.

## 5. Активировать repository ruleset

Открыть:

`Settings → Rules → Rulesets`

Создать branch ruleset по содержимому
[`config/main-branch-ruleset.json`](config/main-branch-ruleset.json). Целевой ref —
default branch (`main`). Требования канонического ruleset:

- обычные изменения только через pull request;
- required status `Required PR Gate`;
- strict/up-to-date required checks;
- linear history;
- разрешённые merge methods: squash и rebase;
- resolved review threads;
- 0 обязательных approvals;
- запрет удаления ветки;
- запрет force-push;
- единственный bypass actor: `DeployKey`, режим `always`.

Не добавлять в bypass владельца репозитория, repository-admin role или весь
GitHub Actions App. Иначе защита direct push становится существенно шире, чем
нужно production/cleanup.

## 6. Проверка после активации

Проверить три свойства:

1. обычный пользовательский direct push в `main` блокируется ruleset;
2. новый PR не может быть смержен до успешного `Required PR Gate`;
3. очередной реальный publish/cleanup commit, когда он действительно нужен,
   проходит через dedicated deploy key и не получает ruleset rejection.

`push_protected_main.sh` pin'ит официальный GitHub Ed25519 host key и допускает
только refspec `HEAD:main`. При наличии `MAIN_PUSH_DEPLOY_KEY` обычный HTTPS
`origin` для writer push не используется.

## 7. Безопасный откат

Если automated writer после активации получает SSH/ruleset rejection:

1. не расширять bypass на администраторов или весь GitHub Actions;
2. временно перевести ruleset в disabled, если публикацию/cleanup необходимо
   срочно восстановить;
3. проверить deploy key, его write access и repository secret;
4. после исправления снова активировать тот же канонический ruleset.

Удалять `Required PR Gate` или возвращать Main CI/Video CI в required checks как
аварийный обход не следует: это возвращает исходную проблему path-filtered
pending checks.
