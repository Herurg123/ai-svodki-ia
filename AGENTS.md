# Repository instructions

The repository-wide architecture contract is maintained in
[`automation/ARCHITECTURE.md`](automation/ARCHITECTURE.md). Read it before any
change that affects workflows, retrieval, editorial behavior, recovery,
publication, cleanup, repository hygiene, or the NotebookLM video subproject.
Do not duplicate detailed architecture in this file: keep prescriptive rules here
and keep the descriptive system map in `automation/ARCHITECTURE.md`.

`README.md` and `automation/README.md` are maintained entry points. Any pull
request that materially changes project behavior or structure must update every
affected README and `automation/ARCHITECTURE.md` in the same pull request. If a
change truly has no documentation impact, state that explicitly in the PR.

Before declaring a material change complete:

1. compare the implementation, workflows, configuration and canonical specs with
   `automation/ARCHITECTURE.md` and affected README files;
2. update documentation-contract tests when boundaries or workflow inventory
   change;
3. run the relevant offline checks;
4. for retrieval/search architecture changes, perform the project-required
   architecture-wide dependency/regression audit and controlled experiment before
   production use.

## GitHub change workflow

Do not commit project changes directly to `main`. Use a dedicated branch and a
pull request, run CI, and inspect the resulting diff before merge.

A pull request must not be merged merely because checks are green or because a
previous message asked to continue. Merge only after the project owner gives a
separate explicit merge command for that prepared PR. Production recovery or
publication that depends on the change must wait for that merge command.

`main` must be protected by the canonical repository ruleset described in
`automation/config/main-branch-ruleset.json`; operator activation is documented
in `automation/MAIN_PROTECTION.md`. Presence of the JSON file alone does not
activate GitHub settings. `Required PR Gate` is the only required status check.
Do not make path-filtered Main CI or Video CI directly required, because a skipped
required workflow remains pending.

The only allowed direct pushes to protected `main` are the validated publication
commit in `daily-production.yml`, validated retention commit in
`repository-cleanup.yml`, and the controlled validated RSS-only commit in
`video-rss-enrichment.yml`. All three must use
`automation/scripts/push_protected_main.sh` with the dedicated
`MAIN_PUSH_DEPLOY_KEY` secret. Do not expose that secret to any other workflow or
job, and do not grant broad GitHub Actions/admin bypass instead. The video RSS
writer may commit only `posts/rss.xml` after proving that the expected public MP4
and PNG are ready and the existing article item remains otherwise unchanged.

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
`deploy-posts.yml`, `repository-cleanup.yml`, `repository-hygiene.yml` or
`video-rss-enrichment.yml`. The explicitly approved video-RSS bridge is one-way
and public-only: it may probe already-published media under `/posts/video/`, but
must not read local video runtime state or make daily production depend on video
success.

These boundaries are enforced by `automation/tests/test_video_ci_boundary.py`,
`automation/tests/test_pr_gate_and_main_protection.py`, and the video subproject's
own dependency-free smoke tests. A future workflow change that re-couples the two
CI domains or broadens protected-main bypass must update the architecture
intentionally rather than bypassing those tests.

## NotebookLM video subproject boundary

`automation/notebooklm-video/` is an independently maintained local Windows
downstream subproject. It consumes an already-published digest and produces
NotebookLM video assets; it is not a stage of the nightly retrieval/editorial
GitHub Actions production.

Do not modify video files as a side effect of retrieval, editorial, RSS/site,
main FTP deploy, cleanup, audit or repository-hygiene work unless the task
explicitly targets video. Conversely, a video task does not authorize unrelated
production changes. Its own `AGENTS.md`, `README.md` and `DEPLOYMENT.md` are
authoritative for local runtime behavior; the repository relationship is defined
in `automation/ARCHITECTURE.md`.

The controlled `video-rss-enrichment.yml` test is a narrow exception only for
post-publication RSS metadata. It may observe the public MP4/PNG pair and attach a
Media RSS group to the matching existing article item. It must preserve that
item's `title`, `link`, `guid`, `pubDate` and `content:encoded`; missing media is a
successful no-op and video failure must never change the digest publication
status.

The 32-day FTP video retention step in `repository-cleanup.yml` is a separate
narrow exception that manages only already-published remote media. It may enter
only the hard-coded FTP directory `video` and may delete only basenames that
exactly match `ai-svodka-YYYY-MM-DD.mp4` or `ai-svodka-YYYY-MM-DD.png` and whose
embedded date is strictly older than the shared cleanup cutoff. It must ignore
all other remote names and directories, validate the complete managed inventory
before the first delete, and must not read RSS or local NotebookLM runtime state.
A preview/video pair is not required for deletion: an expired orphan matching the
managed filename contract is independently eligible.

Real `config.json`, `ftp-access.json`, state, logs, downloaded media and browser
profiles must never be committed. FTP behavior must remain hard-confined to the
remote directory `video` unless an explicit architecture change is approved.

## Retrieval compatibility boundary

The public retrieval entrypoints such as `primary_recall_search.py`,
`hybrid_search_completeness.py`, `ensure_story_coverage.py` and
`recover_digest_artifact.py` intentionally sit over preserved versioned
implementations. Those preserved modules are compatibility and recovery assets,
not disposable duplicate files.

Do not delete, inline, rename or collapse a preserved `*_vN.py` implementation
merely as cleanup. Such a refactor requires proof that public imports,
monkeypatch/test hooks, saved-artifact recovery and source-inspection contract
tests remain compatible. A semantic retrieval change must not be mixed into a
compatibility cleanup.

The current search-operation ceilings and layer order are architectural
invariants documented in `automation/ARCHITECTURE.md`; do not silently change
them during refactoring.

## Permanent and safety invariants

- The permanent pre-hybrid baseline is commit
  `d926a3abf8b9443f58f303d984ef79fdc289fc3e` and branch
  `archive/search-baseline-pre-hybrid-2026-08-09`. Do not move, rewrite,
  repurpose or delete it.
- `posts/_footer-scr.png` is a permanent production asset and must not be removed
  by dated-content cleanup.
- Repository hygiene may mutate only explicitly classified ephemeral GitHub objects
  that are safe under its policy. It must not edit tracked project files, `main`,
  releases, tags, permanent archive branches or published/editorial content.
- The 32-day repository/public-content cleanup is separate from repository
  hygiene. `posts/images/` remains mandatory; absent historical
  `posts/dzen-test/images/` is valid after the last legacy image expires. Its FTP
  video step is independently hard-confined to `video/` and the exact dated
  MP4/PNG filename contract above.
- Repository hygiene retries only idempotent GitHub API GET requests after the
  documented transient failures. Do not automatically retry destructive
  DELETE/PUT operations.
- Exact saved research time boundaries, source freshness proof, archive dedupe,
  fail-closed mandatory search stages and recovery at-most-once semantics must
  not be weakened as incidental cleanup.
- Production API spend is never authorized merely by a code-fix request.

## Independent audits and experiments

The canonical independent audit journal is
`automation/audits/independent-audit-journal.md`; controlled architecture and
retrieval experiments belong under `automation/audits/experiments/`, and
machine-readable regression contracts belong under `automation/fixtures/recall/`.

Retrieval/search experiments use assistant-owned resources. When the project
requires Terra, use assistant-side Terra when actually available and state the
limitation if it is not exposed. Never spend the user's production API budget to
fill that tooling gap without explicit permission.
