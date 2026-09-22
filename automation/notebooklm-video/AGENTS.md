# NotebookLM video subproject instructions

This directory is an independently maintained local Windows downstream subproject.
The repository-level relationship and CI boundary are canonical in
[`../ARCHITECTURE.md`](../ARCHITECTURE.md). This file contains prescriptive
local rules; operator/runtime explanation belongs in `README.md`,
`DEPLOYMENT.md` and the dedicated DZEN documents.

## Scope and CI

- Scope is RSS detection, protected Yandex Browser/Playwright automation,
  NotebookLM generation, MP4/PNG handling, local state/logging, restricted FTP
  delivery to `video`, scheduled native Dzen publication, Dzen collections and
  same-day article video insertion.
- It is not part of nightly retrieval/editorial GitHub production.
- PR Gate routes video-domain changes to dedicated **Video CI**. **Main CI** must
  remain unnecessary for video-only changes; cross-cutting architecture changes
  may require both.
- Video CI stays offline with respect to NotebookLM, FTP, Dzen, production APIs,
  Windows DPAPI and npm dependency installation.
- Keep `package.json` and `package-lock.json` synchronized. Dependency changes
  must prove clean `npm ci`; setup/deployment uses `npm ci`, not
  `npm install`.
- Do not modify this directory as a side effect of unrelated retrieval,
  editorial, RSS/site, main deploy, cleanup, audit or hygiene tasks. Conversely,
  video work does not authorize unrelated production changes.

## Documentation ownership

- Keep operator/runtime overview in `README.md`.
- Keep Windows installation/migration in `DEPLOYMENT.md`.
- Keep native upload details in `DZEN_NATIVE_UPLOAD.md`.
- Keep article-video details in `DZEN_ARTICLE_VIDEO.md`.
- Keep experiment chronology and negative results in
  `DZEN_VIDEO_EXPERIMENTS.md`.
- Keep this file prescriptive. Do not duplicate exact selectors, dated live-test
  narratives or long implementation walkthroughs here when the dedicated
  document already owns them.
- Historical experiment evidence must not be silently discarded or later
  re-presented as an established solution.

## Repository and runtime data

Commit only portable source, safe templates, tests, dependency lockfiles and
documentation. Never commit real configuration, access data, state, logs,
downloaded media, screenshots, browser profiles or other machine-local state.

Use committed example configs and setup scripts for portable deployment. Real FTP
access remains protected by Windows DPAPI `CurrentUser`.

`tempDir` and `tracesDir` are not active runtime surfaces. Do not precreate
empty `temp/` or `traces/` directories or restore them to fresh config unless
a real producer/consumer is added with tests and documentation.

## Browser/session safety

All NotebookLM and Dzen browser automation reuses the protected persistent Yandex
Browser profile and the project CDP lifecycle. Never delete/recreate the profile,
cookies, Google session, Dzen session or profile session files.

NotebookLM and Dzen must not operate concurrently through competing browser
sessions. The scheduled orchestration closes the NotebookLM browser before the
Dzen phase.

Human verification challenges are manual-only. Automation must not click or
attempt to bypass a Dzen/Google captcha or `Я не робот` challenge.

## Locks, logging and retained state

`full-worker.lock` covers the complete scheduled sequence. The inner
`scheduled-worker.lock` remains the guard for NotebookLM/FTP + native Dzen
publication and must not be bypassed by the normal scheduled entrypoint.

Shared text logging uses `log-utils.js` rotation before append. Day-boundary
detection comes from timestamps already in the active log, not mtime or mutable
sidecar state. Repeated same-day runs must remain in the same active log.

`dzen-browser-runner.js` intentionally remains a direct-writer exception. Do
not modify it merely to normalize logging. If it writes the first current-day
entry into an older log, shared rotation must archive only the older prefix and
preserve the current-day suffix.

Active JSON history is bounded by `history-utils.js`:

- keep 14 calendar days active in `state.json` and
  `_СКАЧАННЫЕ_ВИДЕО.json`;
- move older safe terminal rows/jobs to monthly JSON files under local
  `archive/`;
- never auto-delete that JSON archive;
- keep unresolved/error/verification-only jobs active regardless of age;
- keep archived registry rows in duplicate/idempotency lookup;
- explicit old-date operator commands must safely rehydrate archived state.

Rotated text logs share local `archive/` but have independent 7/30-day
retention. Text-log cleanup must match only `worker-*.log` /
`error-*.log` and must never delete JSON history. A legacy `logs/` directory
may migrate only known rotated log names plus obsolete rotation sidecar state,
preserving unknown files.

## Native Dzen publication safety

The historical Video → RSS route is closed. Do not mutate production RSS to
obtain native Dzen video without a new isolated experiment, architecture review
and explicit approval.

Scheduled native publication begins with a pre-upload duplicate guard. It must
reliably confirm the Studio Video view and expected same-day title prefix before
upload. If an existing video is confirmed, stop without child/upload/draft/click.
If the guard cannot prove the Video surface, fail closed before upload.

If no duplicate exists, the canonical live path is a fresh-upload flow. It may
start one live child and perform at most one publish action. Metadata/cover/tags
must not be repeatedly rewritten after the validated values are set.

The scheduled orchestrator persists `PUBLISH_ARMED` before the live child and
uses `CLICKED_UNVERIFIED` / `BLOCKED_AMBIGUOUS` for uncertain outcomes.
These states are verification-only. A later run must never start a second upload
or second publish click from them.

A fresh retry is allowed only after explicit evidence that
`publishClicked=false`. Remote drafts are not auto-deleted. A saved
`videoEditorPublicationId` is diagnostic and must not be treated as a reliable
inter-run resume permalink.

Readiness is status-driven; do not treat an early partial-ready message as final
readiness. Dzen tags remain mandatory and must resolve to the configured visible
tag chips before publish.

Normal scheduled publication is owned by `scheduled-worker.js`.
`run-dzen-publish.cmd` and `run-dzen-dry-run.cmd` remain explicit
operator/diagnostic entrypoints.

Deep selector, tag, readiness and live evidence contracts are in
[`DZEN_NATIVE_UPLOAD.md`](DZEN_NATIVE_UPLOAD.md) and
[`DZEN_VIDEO_EXPERIMENTS.md`](DZEN_VIDEO_EXPERIMENTS.md).

## Dzen collections safety

The collections stage operates only on two exact targets for the selected job
date: video → `Видеосводки по ИИ` and digest → `Сводки по ИИ`.
Zero or one visible target is valid; never substitute an unrelated publication.

Completion is persisted independently under `job.dzenCollections.video` and
`job.dzenCollections.digest`. A target becomes `ADDED` only after a
confirmed one-click UI success or a confirmed existing/already-added state.
Aggregate state is `PENDING`, `PARTIAL` or `COMPLETE`.

If both targets are `ADDED`, future scheduled runs skip collections before
browser launch. If only one target is complete, only the unresolved target may be
retried.

A collection apply may perform at most one physical click on the confirmed exact
target tile. Page-wide success text alone is not proof. Target-local
selected/already-added confirmation is required; ambiguous outcome must not cause
a second automatic click.

Any blocking error must be logged, capture a diagnostic screenshot when possible,
close the browser and leave only unresolved work retryable.

`run-dzen-collections-debug.cmd` and `run-dzen-collections-apply.cmd` remain
manual diagnostic/operator entrypoints with intentionally stable filenames.
Canonical implementation is `dzen-collections.js`.

## Article-video safety

The article-video stage may run only after native video publication is confirmed
and aggregate collections state is `COMPLETE`. It is date-generic and must
resolve the exact same-day article and video; never hard-code a calendar date or
publication URL.

Before editing, the resolved Dzen article URL may replace only the exact second
placeholder in `downloads/_ИИ-Сводка.txt`. If the placeholder is absent, treat
the file as operator-edited and do not rewrite it. If present, the first link must
still match the selected job's publication URL or the stage fails closed.

Insertion must create exactly one `Видеосводка` H2 and one confirmed Dzen video
embed immediately before exact H2 `Мировые лидеры ИИ`. Preserve/restore the
operator's Windows text clipboard.

Publishing is at-most-once. Persist armed states before the corresponding
publish/save actions. `PUBLISH_ARMED`, `CONFIRMATION_ARMED` and
`CLICKED_UNVERIFIED` are verification-only: later runs must not reopen the
editor or repeat mutation/publish/save actions.

Exact pre-existing H2 `Видеосводка` is terminal `SKIPPED_EXISTING` with no
mutation.

`dzenArticleVideo.status=ERROR` is terminal by default. Only two narrow
one-shot scheduled recovery classes are permitted:

1. proven pre-edit link-resolution failure with no resolved URLs/editor/publish
   markers;
2. pre-publish clipboard-related failure with resolved article/video URLs but no
   publish/terminal markers, after inspecting the live draft before any new
   mutation.

The second class may resume an existing plain heading + confirmed embed only from
H2 formatting and must never insert a second embed. Each recovery class is
at-most-once. Any publish/click uncertainty remains manual-only.

Stable manual entrypoints are
`run-dzen-article-video-dry-run.cmd` and
`run-dzen-article-video-apply.cmd`.
Full details are in [`DZEN_ARTICLE_VIDEO.md`](DZEN_ARTICLE_VIDEO.md).

## FTP boundary

FTP access is hard-confined to remote directory `video`. The worker may manage
only the documented current dated MP4/PNG names. It must not delete, rename or
overwrite unrelated remote paths.

Existing managed file with the expected size is already delivered. Size conflict
fails instead of destructive overwrite.

Broadening this boundary requires an explicit architecture decision, not a
configuration-only change.

## Experiments and promotion

Any Dzen delivery experiment must be isolated and documented before promotion to
production behavior. Record observed results, including failures, in
`DZEN_VIDEO_EXPERIMENTS.md`.

Do not promote incident-only reset/retest scripts or one-off local artifacts as
production assets.

All repository changes still follow the root repository workflow and safety
rules. A video-local task does not override root `AGENTS.md`.
