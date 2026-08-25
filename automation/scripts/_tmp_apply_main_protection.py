from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}: {old[:120]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_section(path: str, start: str, end: str, replacement: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    i = text.find(start)
    j = text.find(end, i + len(start))
    if i < 0 or j < 0:
        raise SystemExit(f"{path}: section markers not found: {start!r} -> {end!r}")
    file.write_text(text[:i] + replacement + text[j:], encoding="utf-8")


def patch_writers() -> None:
    secret_expr = "$" + "{{ secrets.MAIN_PUSH_DEPLOY_KEY }}"

    daily = Path(".github/workflows/daily-production.yml")
    text = daily.read_text(encoding="utf-8")
    anchor = "      - name: Commit production release\n"
    start = text.find(anchor)
    if start < 0:
        raise SystemExit("daily-production.yml: commit step anchor not found")
    marker = "        shell: bash\n        run: |\n"
    pos = text.find(marker, start)
    if pos < 0:
        raise SystemExit("daily-production.yml: commit step shell/run marker not found")
    replacement = (
        "        shell: bash\n"
        "        env:\n"
        f"          MAIN_PUSH_DEPLOY_KEY: {secret_expr}\n"
        "        run: |\n"
    )
    text = text[:pos] + replacement + text[pos + len(marker) :]
    push = "          git push origin HEAD:main\n"
    push_pos = text.find(push, start)
    if push_pos < 0:
        raise SystemExit("daily-production.yml: direct main push not found")
    text = (
        text[:push_pos]
        + "          bash automation/scripts/push_protected_main.sh HEAD:main\n"
        + text[push_pos + len(push) :]
    )
    daily.write_text(text, encoding="utf-8")

    cleanup = Path(".github/workflows/repository-cleanup.yml")
    text = cleanup.read_text(encoding="utf-8")
    anchor = "      - name: Commit applied cleanup\n"
    start = text.find(anchor)
    if start < 0:
        raise SystemExit("repository-cleanup.yml: commit step anchor not found")
    env_pos = text.find("        env:\n", start)
    run_pos = text.find("        run: |\n", start)
    if env_pos < 0 or run_pos < 0 or env_pos > run_pos:
        raise SystemExit("repository-cleanup.yml: commit env/run markers not found")
    retention_pos = text.find("          RETENTION_DAYS:", env_pos, run_pos)
    if retention_pos < 0:
        raise SystemExit("repository-cleanup.yml: RETENTION_DAYS env line not found")
    retention_end = text.find("\n", retention_pos)
    if retention_end < 0:
        raise SystemExit("repository-cleanup.yml: RETENTION_DAYS line terminator not found")
    text = (
        text[: retention_end + 1]
        + f"          MAIN_PUSH_DEPLOY_KEY: {secret_expr}\n"
        + text[retention_end + 1 :]
    )
    push = "          git push origin HEAD:main\n"
    push_pos = text.find(push, start)
    if push_pos < 0:
        raise SystemExit("repository-cleanup.yml: direct main push not found")
    text = (
        text[:push_pos]
        + "          bash automation/scripts/push_protected_main.sh HEAD:main\n"
        + text[push_pos + len(push) :]
    )
    cleanup.write_text(text, encoding="utf-8")


def patch_docs() -> None:
    replace_once(
        "README.md",
        "| `.github/workflows/` | Production, deploy, cleanup/hygiene и два раздельных CI-контура. |",
        "| `.github/workflows/` | Always-on PR Gate, два раздельных CI-домена, production, deploy и cleanup/hygiene. |",
    )
    old_root_ci = """В репозитории шесть постоянных GitHub Actions workflow:

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
[`automation/ARCHITECTURE.md`](automation/ARCHITECTURE.md#4-github-actions).
"""
    new_root_ci = """В репозитории семь постоянных GitHub Actions workflow:

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
"""
    replace_once("README.md", old_root_ci, new_root_ci)

    old_auto = """## Workflows

Основной production-код обслуживается `Main CI`, а локальный video-подпроект
имеет отдельный `Video CI`. Полный workflow inventory и границы ответственности
см. в [`ARCHITECTURE.md`](ARCHITECTURE.md).

Video-only изменения под `notebooklm-video/**` не являются изменениями nightly
production и не должны запускать Main CI. В обратную сторону production
workflows не должны читать или изменять video runtime.
"""
    new_auto = """## Workflows

Каждый pull request в `main` сначала проходит через always-on `PR Gate`. Он
классифицирует changed paths и вызывает reusable `Main CI`, `Video CI` или оба
домена. Финальный job `Required PR Gate` является единственным стабильным
required status для защиты `main`.

Video-only изменения под `notebooklm-video/**` не являются изменениями nightly
production и не запускают Main CI; их через PR Gate проверяет только Video CI.
В обратную сторону production workflows не должны читать или изменять video
runtime. Полный workflow inventory, ruleset и automated-writer boundary описаны
в [`ARCHITECTURE.md`](ARCHITECTURE.md).
"""
    replace_once("automation/README.md", old_auto, new_auto)

    agents_section = """## GitHub change workflow

Do not commit project changes directly to `main`. Use a dedicated branch and a
pull request, run CI, and inspect the resulting diff before merge.

A pull request must not be merged merely because checks are green or because a
previous message asked to continue. Merge only after the project owner gives a
separate explicit merge command for that prepared PR. Production recovery or
publication that depends on the change must wait for that merge command.

`main` is protected by the canonical repository ruleset described in
`automation/config/main-branch-ruleset.json`. `Required PR Gate` is the only
required status check. Do not make path-filtered Main CI or Video CI directly
required, because a skipped required workflow remains pending.

The only allowed direct pushes to protected `main` are the validated publication
commit in `daily-production.yml` and validated retention commit in
`repository-cleanup.yml`. They must use `automation/scripts/push_protected_main.sh`
with the dedicated `MAIN_PUSH_DEPLOY_KEY` secret. Do not expose that secret to any
other workflow or job, and do not grant broad GitHub Actions/admin bypass instead.

## CI ownership boundary

`PR Gate` (`.github/workflows/pr-gate.yml`) is the always-on pull-request
orchestrator. It classifies changed paths, calls the relevant reusable domain CI,
and emits `Required PR Gate`. A change to the gate itself must exercise both CI
domains.

`Main CI` (`.github/workflows/ci.yml`) owns the main production repository checks.
It remains reusable for PR Gate and keeps push/manual execution. Its push path
filter must exclude video-only changes under `automation/notebooklm-video/**` and
the dedicated `.github/workflows/video-ci.yml` file.

`Video CI` (`.github/workflows/video-ci.yml`) exclusively owns repository-level
offline checks for the local NotebookLM video subproject. It remains reusable for
PR Gate and dependency-free. Video-only source or test changes must not require
Main CI. Cross-cutting changes can route to both domains.

Do not add `automation/notebooklm-video/` as an input, dependency, generated
artifact, cleanup target or deploy source of `daily-production.yml`,
`deploy-posts.yml`, `repository-cleanup.yml` or `repository-hygiene.yml` unless
the project owner explicitly changes the architecture boundary.

These boundaries are enforced by `automation/tests/test_video_ci_boundary.py`,
`automation/tests/test_pr_gate_and_main_protection.py`, and the video subproject's
own dependency-free smoke tests. A future workflow change that re-couples the two
CI domains or broadens protected-main bypass must update the architecture
intentionally rather than bypassing those tests.

"""
    replace_section(
        "AGENTS.md",
        "## GitHub change workflow\n",
        "## NotebookLM video subproject boundary\n",
        agents_section,
    )

    architecture_section = """## 4. GitHub Actions

Постоянный workflow inventory состоит из семи файлов.

| Workflow | Ответственность | Может менять production state |
|---|---|---|
| `pr-gate.yml` | Always-on PR routing и единый required gate | Нет |
| `ci.yml` | Main CI, offline проверки основного production-кода | Нет |
| `video-ci.yml` | Video CI, dependency-free offline проверки video-подпроекта | Нет |
| `daily-production.yml` | Ежедневный retrieval/editorial/build/publish pipeline | Да, по production contract |
| `deploy-posts.yml` | FTP-синхронизация точного `posts/` выбранного commit | Да, только public deploy |
| `repository-cleanup.yml` | 32-day content/public cleanup с validation | Да, только documented retention scope |
| `repository-hygiene.yml` | Уборка безопасно классифицированных GitHub objects | Да, только GitHub-object policy scope |

### 4.1. PR Gate

`pr-gate.yml` запускается для каждого pull request в `main` без `paths` filter.
Он сравнивает base/head commit, классифицирует changed paths и вызывает reusable
domain workflows:

- Main CI для production/shared paths;
- Video CI для `automation/notebooklm-video/**` и `video-ci.yml`;
- оба домена для изменения самого `pr-gate.yml` и mixed PR.

Финальный job всегда называется `Required PR Gate`. Именно он является
стабильным required status ruleset. Path-dependent Main CI и Video CI нельзя
делать required напрямую: когда workflow пропущен по path routing, required
status не появляется как успешный check и merge может зависнуть.

### 4.2. Main CI

Main CI является reusable workflow для PR Gate и сохраняет `workflow_dispatch`
и push-to-main проверку. Его push path filter исключает:

- `automation/notebooklm-video/**`;
- `.github/workflows/video-ci.yml`.

Video-only PR не становится зависимым от Python production CI. Изменения общей
архитектуры, production workflow/tests и других main-domain paths маршрутизируются
PR Gate в Main CI.

Main CI выполняет compileall, Python unit regressions и ключевые validators
editorial/archive/production/RSS/sitemap/structured-data contracts.

### 4.3. Video CI

Video CI является reusable workflow для PR Gate и сохраняет manual/push режимы.
На PR он вызывается только для video-domain changes. Текущий CI намеренно
dependency-free: он не выполняет `npm install` или `npm ci`, не запускает
браузер, NotebookLM, FTP или Windows DPAPI. Он использует Node.js для syntax
checks и offline contract smoke tests, которые работают только со встроенными
Node modules и committed files.

Полное npm-дерево video runtime при этом воспроизводимо: `package.json` и
committed `package-lock.json` являются одной версионируемой единицей, а локальные
setup/dependency entrypoints устанавливают зависимости через `npm ci`. Изменение
npm-зависимостей должно обновлять lockfile в том же PR и отдельно доказывать
чистую `npm ci` установку; обычный Video CI от npm registry по-прежнему не зависит.

### 4.4. Enforcement CI boundary

`automation/tests/test_video_ci_boundary.py` проверяет разделение production/video,
а `automation/tests/test_pr_gate_and_main_protection.py` проверяет always-on gate,
reusable domain CI, узкий automated-writer secret scope и canonical ruleset.

`automation/notebooklm-video/tests/video-boundary-smoke.js` проверяет hard FTP
boundary и ignore rules. `lockfile-contract-smoke.js` проверяет синхронизацию
`package.json`/`package-lock.json` и локальный `npm ci` contract.

### 4.5. Защита `main` и automated writers

Канонический desired ruleset хранится в
`automation/config/main-branch-ruleset.json`. Он нацелен только на default branch
и требует:

- pull request для обычных изменений;
- успешный `Required PR Gate` на актуальном base;
- linear history с merge через squash/rebase;
- resolved review threads;
- запрет удаления `main` и force-push.

Число обязательных approvals равно 0: репозиторий персональный, поэтому правило
не должно требовать невозможного self-approval. Bypass actor только `DeployKey`.
Нельзя заменять его repository-admin role или всем GitHub Actions App: это
расширило бы прямой write bypass на несвязанные workflows.

Два легитимных automated writer контура остаются direct-push по архитектурной
необходимости: `daily-production.yml` публикует validated release, а
`repository-cleanup.yml` фиксирует validated retention cleanup. Только их финальные
commit steps получают secret `MAIN_PUSH_DEPLOY_KEY` и вызывают
`automation/scripts/push_protected_main.sh HEAD:main`. Helper отвергает другой
refspec, использует отдельный SSH key только на время push и pin'ит официальный
GitHub Ed25519 host key.

Пока deploy-key secret не установлен и ruleset ещё не активирован, helper может
использовать существующий authenticated `origin` как переходный fallback. Перед
активацией ruleset write deploy key и repository secret обязаны быть установлены;
после активации fallback больше не является рабочим путём. Repository hygiene,
Video CI, Main CI, PR Gate и deploy-posts этот secret не получают.

"""
    replace_section(
        "automation/ARCHITECTURE.md",
        "## 4. GitHub Actions\n",
        "## 5. Nightly production и временная непрерывность\n",
        architecture_section,
    )

    replace_once(
        "automation/notebooklm-video/README.md",
        "Video CI выполняет только переносимые dependency-free проверки:\n",
        "На pull request always-on `PR Gate` вызывает Video CI только когда затронут video-домен; Main CI для video-only изменений не запускается. Сам Video CI выполняет только переносимые dependency-free проверки:\n",
    )
    replace_once(
        "automation/notebooklm-video/AGENTS.md",
        "- Repository checks for this directory belong to the dedicated **Video CI** in `.github/workflows/video-ci.yml`; **Main CI** must exclude video-only changes.\n",
        "- Pull requests are routed by the always-on **PR Gate**; video-domain changes call the dedicated **Video CI** in `.github/workflows/video-ci.yml`, while **Main CI** must remain unnecessary for video-only changes.\n",
    )


def main() -> None:
    patch_writers()
    patch_docs()


if __name__ == "__main__":
    main()
