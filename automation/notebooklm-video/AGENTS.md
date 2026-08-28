# NotebookLM video subproject instructions

This directory is an independently maintained local Windows downstream subproject inside the wider AI-Svodki repository.

The repository-level relationship and CI boundary are canonical in [`../ARCHITECTURE.md`](../ARCHITECTURE.md). This file contains the prescriptive local rules.

- Its scope is the local NotebookLM video workflow: RSS detection, Yandex Browser/Playwright automation, NotebookLM generation, MP4 download, PNG first-frame preview, local state/logging, restricted FTP delivery to `video`, and isolated Dzen native-video publication experiments.
- It is not part of the main nightly retrieval/editorial GitHub Actions production.
- Pull requests are routed by the always-on **PR Gate**; video-domain changes call the dedicated **Video CI** in `.github/workflows/video-ci.yml`, while **Main CI** must remain unnecessary for video-only changes.
- Do not re-couple Video CI and Main CI without an explicit architecture change plus matching documentation and contract-test updates.
- Video CI stays offline with respect to NotebookLM, FTP, Dzen, production APIs, Windows DPAPI, and npm dependency installation. Platform-specific behavior is verified on the target Windows machine.
- Keep `package.json` and committed `package-lock.json` synchronized. Any npm dependency change must update the lockfile in the same pull request and prove a clean `npm ci`; normal setup/deployment entrypoints must use `npm ci`, not `npm install`.
- Do not modify files in this directory as a side effect of tasks about retrieval, editorial policy, RSS/site generation, the main FTP deploy, cleanup, audits, or repository hygiene unless the task explicitly targets that subproject.
- Conversely, a video-subproject task does not authorize changes to unrelated production architecture.
- Keep `README.md` and `DEPLOYMENT.md` current whenever production behavior, configuration, dependencies, deployment, recovery, or operator actions change. An isolated manual experiment that is not wired into `worker.js`, setup or Task Scheduler may instead be documented in its dedicated experiment document until promotion.
- Keep practical Dzen publication experiments and negative results in [`DZEN_VIDEO_EXPERIMENTS.md`](DZEN_VIDEO_EXPERIMENTS.md); do not silently discard failed hypotheses and later re-present them as established solutions.
- The 2026-08-27 controlled tests established that RSS-based delivery did not produce a native Dzen video publication in this project. Treat the RSS route for native Dzen video publication as unsuccessful and closed unless materially new evidence justifies reopening it.
- Do not add production RSS mutations in an attempt to publish native Dzen video without a new, isolated experiment and explicit approval.
- The 2026-08-27 manual Dzen Studio test and the 2026-08-28 automated fresh-upload MVP test confirmed that native browser upload works on the target Windows machine and lands in the Dzen video flow.
- The 2026-08-28 duplicate-guard live test confirmed that Studio `Публикации` -> `Видео` can safely prevent a repeated upload by matching the visible title prefix before ` | `.
- The native Dzen browser-upload experiment may perform the final publish click only through the explicit operator live-publish entrypoint. It is not wired into `worker.js`, `run-worker.cmd`, `run-worker-hidden.vbs` or Task Scheduler.
- `run-dzen-publish.cmd` and `run-dzen-dry-run.cmd` are the canonical Dzen operator entrypoints. They start the robotized Yandex Browser automatically through `dzen-browser-runner.js` / `browser-session.js`, using the protected persistent browser profile and CDP lifecycle.
- The Dzen browser bootstrap must never delete or recreate the protected browser profile, cookies, Google session, Dzen session, or profile session files.
- The canonical live-publish baseline starts with a **pre-upload duplicate guard**. Before any live child/upload, open `https://dzen.ru/profile/editor/rybv/publications`, activate the real `input[type="radio"][aria-label="Видео"]` control, confirm `checked=true`, and search the visible list for the expected title prefix before ` | `. Do not click the visual text `<div>Видео</div>` because the radio input intercepts pointer events and causes Playwright click/scroll retries.
- If the duplicate guard finds `ИИ-Сводка на <дата>` in the visible Video list, log `ВИДЕО УЖЕ ЕСТЬ`, do not start the live child, do not create a draft, do not upload MP4, and do not click publish. If the guard cannot reliably open/confirm the Video filter, fail closed before upload.
- If no duplicate is found, the validated live-publish baseline remains a **fresh-upload, single-child, single-page MVP**: open Studio, create a new video upload, transfer the MP4, fill title/description once, set cover once, confirm exactly five tag chips, stop touching metadata/cover/tags, wait for the final processed/ready status, set comments to `Все пользователи`, click `Опубликовать`/`Отправить` once, log the click, then let the runner close the browser.
- A normal live run must not reopen or resume a saved `videoEditorPublicationId`, must not reopen old drafts, and must not refill already prepared metadata. If a run fails before the publish click, the next explicit operator run starts from the duplicate guard and, only when no existing video is found, creates a new upload. Remote drafts are not auto-deleted.
- `videoEditorPublicationId` may be logged for diagnostics but is not a reliable persistent permalink for reopening the populated editor. The observed redirect to the channel page closed the inter-run resume hypothesis.
- A Playwright file-upload timeout is not by itself proof that the Dzen MP4 upload failed; the same child may continue waiting for `videoEditorPublicationId` before deciding that upload failed.
- Dzen metadata is written once. Whitespace-only changes introduced by Dzen must not trigger another write; non-whitespace content changes remain errors.
- Video-description links after `Этот выпуск:` are separate bullet lines, each prefixed by `- `.
- Dzen tags are mandatory: exactly five configured tags must become five separate visible tag chips. The tag input may disappear/re-render after Enter, especially after the fifth tag; reacquire the input when needed and validate completion from the visible chips.
- Readiness is status-driven. Early `Уже можно публиковать` is not final readiness. Wait for `Загрузили и обработали видео` + `Готово: можно публиковать и смотреть` + an enabled exact publish button before the final click.
- `Кто может комментировать = Все пользователи` is set after final readiness and before the one publish click in the validated MVP.
- The validated MVP intentionally has no post-click verification and no automatic second click. The pre-upload duplicate guard is the protection against repeating an already visible published video on a later explicit run.
- The isolated native-upload implementation and operator procedure are documented in [`DZEN_NATIVE_UPLOAD.md`](DZEN_NATIVE_UPLOAD.md). Do not wire the live path into `worker.js`, `run-worker.cmd` or Task Scheduler without a separate promotion change.
- Any Dzen video-delivery experiment must be isolated, documented before it is promoted to production behavior, and recorded in `DZEN_VIDEO_EXPERIMENTS.md` with observed results.
- Commit only portable source, safe templates, tests, dependency lockfiles, and documentation. Never commit real runtime configuration, access data, state, logs, downloaded media, browser profiles, or machine-local runtime state.
- Use the committed example configuration files and setup scripts for portable deployment; machine-local files remain outside Git.
- FTP access is hard-confined to remote directory `video`. Changing that boundary requires an explicit architecture decision, not a configuration-only edit.
- All repository changes still follow branch -> pull request -> CI -> diff review -> separate explicit merge approval.
