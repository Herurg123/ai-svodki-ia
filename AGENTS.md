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
commit in `daily-production.yml` and the validated retention commit in
`repository-cleanup.yml`. Both must use
`automation/scripts/push_protected_main.sh` with the dedicated
`MAIN_PUSH_DEPLOY_KEY` secret. Do not expose that secret to any other workflow or
job, and do not grant broad GitHub Actions/admin bypass instead.

## Incident/fix verification gate

Production incident fixes require evidence beyond a plausible diff or green CI.
Before merge, the agent must inspect the exact failing run/job and saved artifact;
reproduce the failure offline from that artifact when possible; define and test
neighboring success/failure/recovery cases; verify architecture, search-budget,
source-freshness, publication and at-most-once recovery invariants; inspect the
final PR diff and CI on the exact head SHA; and verify the resulting `main` after
merge. A required check that remains `not verified` blocks a claim of full
verification and blocks merge.

For paid production pipelines, independent regression work must use assistant-owned
or saved artifacts and must not spend the owner's production API budget without
separate explicit permission. Recovery after a late-stage failure must prefer the
already-paid same-day artifact and prove that completed paid stages will not be
repeated. Merge must use the exact reviewed head SHA (`expected_head_sha` or an
equivalent race-safe guard). Green CI by itself is never sufficient evidence.

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

`daily-production.yml` must keep exactly one native GitHub schedule,
`17 23 * * *` (`02:17 Europe/Moscow`). Do not add intra-day retry crons. The
availability backup is external and must enter through `workflow_dispatch`
(currently cron-job.org), so backup/manual runs remain operationally
distinguishable from the native scheduled run.

Do not add `automation/notebooklm-video/` as an input, dependency, generated
artifact, cleanup target or deploy source of `daily-production.yml`,
`deploy-posts.yml`, `repository-cleanup.yml` or `repository-hygiene.yml`.
The local video downstream may consume an already-published digest but must not
make nightly production depend on video success.

`posts/rss.xml` is an article/image publication surface, not a video delivery
channel. Active production code and workflows must not inject local video payloads
or references into RSS, including `/posts/video/`, `medium="video"` or
`type="video/*"`. The retired Video → RSS implementation is preserved only under
`automation/archive/video-rss-enrichment-2026-08/` and must remain inert. Reusing
it requires a new isolated experiment, architecture review and pull request.

These boundaries are enforced by `automation/tests/test_video_ci_boundary.py`,
`automation/tests/test_rss_video_boundary.py`,
`automation/tests/test_pr_gate_and_main_protection.py`, and the video subproject's
own dependency-free smoke tests. A future workflow change that re-couples the two
CI domains, reintroduces Video → RSS mutation or broadens protected-main bypass
must update the architecture intentionally rather than bypassing those tests.

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

The former controlled `video-rss-enrichment.yml` route is closed and archived.
It is not an exception to the video boundary anymore. Video assets may be stored
and retained independently, and native video publication may use the separate
operator-controlled browser path, but video work must not mutate RSS in order to
publish video.

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

The normal Hybrid ceiling is four Web Search operations. One conditional fifth
Hybrid operation is permitted **only** when Search-derived `regional_health`
simultaneously marks both Russia and China/Asia as gaps. That double-gap path must
preserve all three broad Hybrid passes and add exactly two dedicated regional
checks, for an effective Hybrid maximum of five. A single regional gap remains
3 broad + 1 regional; no regional gap does not authorize the fifth call.

The ordinary whole-pipeline ceiling is 24 Web Search operations
(12 Primary + 1 agency rescue + 4 Hybrid + 7 Coverage). The sole approved
conditional extension raises the theoretical ceiling to 25 only on the double-gap
path. A caller-provided oversized Hybrid limit must never create a sixth search;
a lowered baseline must not silently enable the conditional extension.

Additional regional Coverage searches and an LLM semantic-event matcher are not
part of the active contract. They remain deferred options and require a future
audit plus explicit approval before any implementation or spend.

## Source Pulse supplemental boundary

Source Pulse v1.2 may supplement a fresh Primary research artifact only through
the bounded pre-editorial path documented in `automation/ARCHITECTURE.md`.
It must use **zero OpenAI calls and zero Web Search operations** and must not
reduce or suppress any mandatory Primary, agency-rescue, Hybrid or Coverage
search obligation.

Candidate influence is limited to `pulse_only` Tier-A sources whose role is
`official` or `trusted_news` and that pass deterministic source-page freshness,
host/redirect safety and deterministic AI relevance. Such rows enter only as
`recommendation=consider` with conservative significance. `trusted_news` does not
become an official company source and does not gain automatic `include` status.
ТАСС is an approved Russian Tier-A `trusted_news` source; Yandex IR/MWS/VK are
official Tier-A sources; CNews and other Tier B entries remain lead-only and must
never influence publication.

Search-derived China/Asia and Russia `regional_health` gaps must not be recomputed
after Pulse promotion, because the second plane must not hide a degraded Primary
Search route. Same-day recovery must reuse the saved Pulse snapshot and must not
silently repoll mutable sources. Source/network/parser errors, including HTTP
anti-bot responses, must remain visible as degraded diagnostics rather than being
reported as healthy success.

## Permanent and safety invariants

- The permanent pre-hybrid baseline is commit
  `d926a3abf8b9443f58f303d984ef79fdc289fc3e` and branch
  `archive/search-baseline-pre-hybrid-2026-08-09`. Do not move, rewrite,
  repurpose or delete it.
- `posts/_footer-scr.png` is a permanent production asset and must not be removed
  by dated-content cleanup.
- `posts/rss.xml` must remain free of local video payloads and local video URLs;
  the archived Video → RSS experiment is not an active production dependency.
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
- Production API spend is never authorized merely by a generic code-fix request.
  The conditional fifth Hybrid search described above is separately authorized
  as an explicit architecture contract; any other new paid retrieval requires
  separate approval.

## Independent audits and experiments

The canonical independent audit journal is
`automation/audits/independent-audit-journal.md`; controlled architecture and
retrieval experiments belong under `automation/audits/experiments/`, and
machine-readable regression contracts belong under `automation/fixtures/recall/`.

Retrieval/search experiments use assistant-owned resources. When the project
requires Terra, use assistant-side Terra when actually available and state the
limitation if it is not exposed. Never spend the user's production API budget to
fill that tooling gap without explicit permission.