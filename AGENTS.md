# Repository instructions

The repository-wide architecture contract is maintained in
[`automation/ARCHITECTURE.md`](automation/ARCHITECTURE.md). Read it before any
change that affects workflows, retrieval, editorial behavior, recovery,
publication, cleanup, repository hygiene, or the NotebookLM video subproject.

This file is prescriptive. Do not copy detailed current-state implementation
narratives here when they already belong in `automation/ARCHITECTURE.md`, a
specification, or a subproject document.

## Documentation ownership

Keep each maintained document in one role:

- root `README.md`: project overview, CI/production overview, navigation;
- `automation/README.md`: operational map, active entrypoints, compact production
  contract and local checks;
- `automation/ARCHITECTURE.md`: canonical detailed current-state architecture;
- root `AGENTS.md`: repository-wide change/safety rules;
- `automation/notebooklm-video/README.md`: video operator/runtime overview;
- `automation/notebooklm-video/AGENTS.md`: video-local prescriptive rules;
- specs/DZEN documents: deep subsystem contracts;
- `audits/experiments/**`: historical evidence and replay records, not living
  overview documentation.

A material behavior or structure change must update `automation/ARCHITECTURE.md`
and every affected README/AGENTS/spec in the same pull request. If a change truly
has no documentation impact, state that explicitly in the PR. Do not add the same
implementation history to multiple README files merely to make each one
self-contained.

Before declaring a material change complete:

1. compare implementation, workflows, configuration and canonical specs with
   `automation/ARCHITECTURE.md` and affected entry-point docs;
2. update documentation-contract tests when their boundaries change;
3. run the relevant offline checks;
4. for retrieval/search changes, perform the required architecture-wide
   dependency/regression audit and compare the current production baseline with
   the proposed version against
   `automation/specs/search-change-validation-matrix.md`.

## GitHub change workflow

For assistant/project changes, use a dedicated branch and pull request, run CI,
and inspect the resulting diff before merge unless the project owner explicitly
instructs otherwise for the current task.

A pull request must not be merged merely because checks are green or because an
earlier message asked to continue. Merge only after a separate explicit owner
merge command for that prepared PR, unless the owner explicitly includes merge
authorization in the current task. Recovery/publication that depends on the
change waits for the authorized merge.

The technical ability to push directly to `main` is an accepted repository
state. Absence of branch protection, an inactive ruleset, `protected: false`, or
mere direct-push capability must not by itself be classified as a defect,
security incident, production risk, technical debt or audit finding.

`automation/config/main-branch-ruleset.json` and
`automation/MAIN_PROTECTION.md` are optional hardening references. If that
ruleset is activated, `Required PR Gate` remains the only required status check;
do not directly require path-filtered Main CI or Video CI.

The validated publication commit in `daily-production.yml` and validated
retention commit in `repository-cleanup.yml` are intentional automated writers.
Both use `automation/scripts/push_protected_main.sh` with the dedicated
`MAIN_PUSH_DEPLOY_KEY` when configured. Do not expose that credential elsewhere.

Those two writers share one non-cancelling Actions concurrency group. Never set
`cancel-in-progress: true` for their shared writer boundary.

## Legacy and compatibility lifecycle

Legacy, compatibility, migration and transitional behavior is temporary technical
debt unless a narrower contract explicitly preserves it for active compatibility,
recovery, replay or reference.

When adding or touching a legacy path:

- prefer the canonical implementation;
- document the active consumer, removal condition and review/removal date when
  practical;
- re-audit the path whenever the same area is changed;
- before removal, trace production, workflow, config, tests, recovery, replay,
  migration, docs and external-consumer dependencies;
- when the last dependency disappears, remove executable legacy code,
  configuration, tests, workflow steps, documentation and static artifacts rather
  than leaving an inert compatibility layer;
- preserve historical fixtures/audit evidence when useful, but keep them inert and
  outside active imports, workflow discovery, deployment and publication paths;
- after retirement, prefer canonical-only fail-closed validation.

A passed review date is a cleanup signal, not permission to extend legacy by
silence. More specific compatibility boundaries below override generic cleanup.

## Incident/fix verification gate

Production incident fixes require more than a plausible diff or green CI.
Before merge:

- inspect the exact failing run/job and saved artifact;
- reproduce the failure offline when possible;
- add neighboring success/failure/recovery controls;
- verify architecture, search budget, freshness, publication and at-most-once
  recovery invariants;
- exercise the real public entrypoint or wrapper path immediately before the
  failed stage on a production-shaped saved artifact/fixture;
- prove the regression fails pre-fix and passes post-fix;
- inspect final diff and CI on the exact head SHA;
- merge with an exact-head guard and verify resulting `main`.

Private helper or monkeypatch-only tests are not sufficient by themselves when
the incident crossed a public entrypoint/recovery seam.

Paid production regression work must use assistant-owned or saved artifacts.
Never spend the owner's production API budget without separate explicit
permission. Late-stage recovery must reuse already-paid same-day work whenever
the contract permits it.

## CI ownership boundary

`PR Gate` (`.github/workflows/pr-gate.yml`) is the always-on pull-request
orchestrator. It routes changes to reusable Main CI, Video CI or both and emits
`Required PR Gate`. A gate change must exercise both domains.

Repository-controlled operator-facing GitHub Actions text must be in Russian.
Workflow/job/step names, technical identifiers, machine-readable values and raw
output from GitHub, third-party actions or external tools may remain in English.
The Russian-language requirement covers `workflow_dispatch` input descriptions,
`GITHUB_STEP_SUMMARY` prose, repository-authored `::error`/`::warning`/`::notice`
annotations, explicit workflow error/warning messages, recovery guidance and
final operator status. Every active workflow must leave a Russian summary for its
own actionable success/failure boundary; do not hide a failure behind only raw
English tool output. Preserve this contract with regression tests when workflows
or their summary renderers change.

`Main CI` owns main production checks and must exclude video-only changes under
`automation/notebooklm-video/**`. `Video CI` exclusively owns repository-level
offline checks for the local video subproject. Video-only source/test changes
must not require Main CI; cross-cutting changes may route to both.

`daily-production.yml` must keep exactly one native GitHub schedule,
`17 23 * * *` (`02:17 Europe/Moscow`). Do not add intra-day retry crons.
Availability backup enters through `workflow_dispatch` (currently cron-job.org).

Do not make `automation/notebooklm-video/` an input, dependency, generated
artifact, cleanup target or deploy source of `daily-production.yml`,
`deploy-posts.yml`, `repository-cleanup.yml` or
`repository-hygiene.yml`.

`posts/rss.xml` is an article/image surface, not a local video channel. Active
production must not inject local video payloads or references including
`/posts/video/`, `medium="video"` or `type="video/*"`. The retired Video → RSS implementation under `automation/archive/video-rss-enrichment-2026-08/`
must remain inert.

## NotebookLM video subproject boundary

`automation/notebooklm-video/` is an independently maintained local Windows
downstream that consumes an already-published digest. It is not a nightly
retrieval/editorial stage.

Do not modify video files as a side effect of unrelated retrieval, editorial,
RSS/site, main FTP deploy, cleanup, audit or hygiene work. Conversely, a video
task does not authorize unrelated production changes. Local behavior is governed
by its `AGENTS.md`, `README.md`, `DEPLOYMENT.md` and DZEN subsystem docs.

The local downstream may publish native Dzen video, manage its two exact
collections and edit only the already-published same-day article under its
at-most-once/verification-only state machines. The article-video runtime must not preserve or restore the operator Windows clipboard. The production browser-paste path must not depend on the Windows desktop clipboard for video insertion; it may still use Windows clipboard only as a last-resort Studio URL fallback. A real Dzen video preview remains mandatory before publish. It must not mutate nightly RSS,
public site generation or GitHub publication state.

The 32-day FTP-video retention job is a separate narrow maintenance exception. It
may enter only remote `video` and delete only exact
`ai-svodka-YYYY-MM-DD.mp4/.png` names strictly older than the shared cutoff
after validating managed inventory. It must ignore other names/directories and
must not derive inventory from RSS or local NotebookLM state.

Real video config/access/state/log/media/browser profiles must never be committed.

## Retrieval compatibility boundary

Public retrieval entrypoints such as `primary_recall_search.py`,
`hybrid_search_completeness.py`, `ensure_story_coverage.py` and
`recover_digest_artifact.py` intentionally sit over preserved versioned
implementations.

Do not delete, inline, rename or collapse preserved `*_vN.py`, `*_base.py` or
compatibility wrappers merely as cleanup. A semantic-neutral consolidation
requires proof for public imports, monkeypatch/test hooks, saved-artifact recovery,
rollback/replay and source-inspection contracts. Do not mix semantic retrieval
changes into compatibility cleanup.

Any semantic search/retrieval/news-collection change must be independently
validated before production use against
`automation/specs/search-change-validation-matrix.md`. The proposed version and
the current production baseline must run against the same controlled
inputs/saved artifacts across all affected dimensions. Cover pairwise intersections and explicit critical three-way combinations for known incident
shapes. A new retrieval incident must enrich the canonical matrix and reusable
fixtures rather than becoming a one-off exception.

The normal Hybrid ceiling is four Web Search operations. One conditional fifth
Hybrid operation is permitted only when Search-derived regional health
simultaneously marks Russia and China/Asia as gaps. It preserves three broad
passes plus two dedicated regional checks. A single gap remains 3 broad + 1
regional.

The ordinary whole-pipeline ceiling is 24 Web Search operations
(12 Primary + 1 agency rescue + 4 Hybrid + 7 Coverage). The sole approved
double-gap extension raises the ceiling to 25. Oversized caller limits must never
create a sixth Hybrid search.

Additional regional Coverage searches and a separate LLM semantic-event matcher
are not active. They require future audit and explicit approval.

## Event/source freshness boundary

Event age and cited-source page age are separate contracts. Paid retrieval may
carry nullable event-origin evidence while `published_date`/`published_at`
remain the cited-page publication time.

Reliable event origin outside the exact saved window is rejected with
`event_freshness_stale`. Missing/ambiguous/untrusted event origin remains
`event_freshness_status=unknown`: it preserves recall but never bypasses Source Freshness.

Do not use a fresh reprint, syndicated copy, tracker/doc update or search-result
publication date as event-origin evidence. Do not add a paid LLM/Web Search pass
just to populate event freshness.

Legacy saved artifacts without event-origin fields remain reusable as
`event=unknown`; completed paid retrieval must not rerun only to backfill those
fields.

## Source Pulse supplemental boundary

Source Pulse may supplement fresh Primary only through the bounded pre-editorial
path documented in `automation/ARCHITECTURE.md`. It must use zero OpenAI calls
and zero Web Search operations and must not reduce/suppress mandatory Primary,
agency-rescue, Hybrid or Coverage obligations.

Publication influence remains limited to approved Tier-A
`official`/`trusted_news` Pulse rows that pass deterministic safety,
freshness and AI-relevance checks, entering conservatively as `consider`.
Registry/configuration is the authority for current source roles; do not duplicate
a mutable source list in AGENTS.

Source Pulse must not close an existing Search-derived China/Asia or Russia gap.
The deterministic pre-Hybrid viability refresh may only **re-open** an early
healthy Primary region when exact Primary provenance no longer has a viable
survivor. It must never turn
`health_check_needed=true` into false, must not use Pulse-only rows as Primary
health proof, and must not create a new search slot.

Saved snapshot/recovery paths may reuse evidence already stored in the snapshot
but must not silently repoll mutable sources.

## Permanent and safety invariants

- Permanent pre-hybrid baseline:
  `d926a3abf8b9443f58f303d984ef79fdc289fc3e` and
  `archive/search-baseline-pre-hybrid-2026-08-09`; do not move, repurpose or
  delete it.
- `posts/_footer-scr.png` is a permanent production asset.
- `posts/rss.xml` must remain free of local video payloads/URLs.
- Repository hygiene may mutate only explicitly classified ephemeral GitHub objects
  and must not edit tracked project files, `main`, releases, tags, permanent
  archive branches or published/editorial content.
- 32-day content/public cleanup is separate from repository hygiene.
- Hygiene retries only idempotent read-only GET operations after documented
  transient failures; do not automatically retry destructive DELETE/PUT.
- Saved research boundaries, freshness proof, archive dedupe, mandatory
  fail-closed search stages and at-most-once recovery must not be weakened as
  incidental cleanup.
- `daily-production.yml` must preserve durable same-day stage checkpoints after
  completed paid Research/editorial, Coverage/editorial-completion and Image
  boundaries. Recovery may reuse those checkpoints when the final always-run
  artifact is unavailable, but a checkpoint name alone never authorizes a retry
  or bypasses saved-state validation.
- Production API spend is not authorized by a generic code-fix request; any new
  paid retrieval beyond the documented architecture needs separate approval.

## Independent audits and experiments

The canonical audit journal is
`automation/audits/independent-audit-journal.md`; controlled architecture and
retrieval experiments belong in `automation/audits/experiments/`;
machine-readable regression contracts belong in `automation/fixtures/recall/`.

Historical audit README files are evidence. Do not shorten or normalize them just
because maintained entry-point documentation is being consolidated.

Retrieval/search experiments use assistant-owned resources. When Terra is
required, use assistant-side Terra when available and state clearly when it is
used; if unavailable, emulate the required check and state that limitation.
Never spend production API budget to compensate for missing experiment tooling
without explicit permission.

First-party date fallbacks must bind evidence to the exact cited item. Preserve
the independent event-age gate, exclusions and exact-window boundary semantics.
