# Nightly preflight architecture audit — 2026-08-29

## Scope

Post-P4 audit of the production path before the next native scheduled digest. The audit is offline/read-only except for the proposed workflow mutex change in this branch. No OpenAI, Web Search or Terra production budget was used.

## Verified active production chain

`daily-production.yml` routes fresh research through `run_digest_preview.py`, `primary_recall_search.py`, Source Pulse v1.3 (`source_pulse_supplement_v13.py`), Event/Source Freshness, first editorial, agency rescue v5, P4 pre-Hybrid regional viability, Hybrid completeness, Coverage, final validation, image generation, site/RSS/sitemap build, protected-main commit and `deploy-posts.yml`.

Recovery uses saved same-day artifacts and `agency_discovery_recovery_entry.py`, which imports agency rescue v5. Completed Hybrid is not repeated by recovery. Saved Source Pulse snapshots are reused rather than silently repolled.

Search architecture remains unchanged by this audit: 12 Primary, at most 1 agency rescue, Hybrid at most 4 normally or 5 only for a simultaneous Russia + China/Asia gap, and Coverage at most 7. The whole-pipeline ceiling remains 24 normally and 25 only on the approved double-gap path.

The active workflow inventory remains the canonical seven workflows. Repository hygiene is scheduled far from the nightly digest and does not write release content.

## Production-path evidence

The successful 2026-08-29 production run `33231413963` completed Coverage, image generation, candidate-site validation, protected-main commit and FTP deploy successfully. This verifies that the publication/deploy tail and its configured credentials were functional on the same day as this audit. It does not substitute for the next fresh retrieval run.

P4 was merged as `cc44010f83ae6504aa898bbbf04224c3fc2d7586`; exact-head PR checks passed before merge. A push-to-main offline CI run was started for the merge commit and is checked separately before this audit is declared complete.

## Finding: two uncoordinated protected-main writers

`repository-cleanup.yml` is scheduled at `43 22 * * *` (01:43 Europe/Moscow) and may push a validated retention commit to protected `main`. `daily-production.yml` is scheduled at `17 23 * * *` (02:17 Europe/Moscow) and may push the validated digest commit. The nominal start separation is 34 minutes, but GitHub scheduled workflows can start late.

Before this branch the workflows used different concurrency groups. If delayed cleanup overlapped paid daily production and pushed `main` first, the daily production commit guard would correctly refuse to push because `main` changed while generation was running. That protects history but can waste a completed paid production run and prevent publication.

Historical commit times confirm that scheduled maintenance/publication does not always start at the nominal minute, so the overlap is a real operational race rather than a purely theoretical ordering argument.

## Fix

Both legitimate protected-main writers use the existing `daily-production-main` concurrency group with `cancel-in-progress: false`. No cron, retention rule, search route, API call, publication rule, recovery rule, FTP behavior or deploy behavior changes.

The later writer queues until the earlier writer finishes. Neither workflow is cancelled, and both retain their existing final `main` race guards.

`automation/tests/test_main_writer_concurrency.py` locks the shared non-cancelling mutex and both native cron expressions.

## Non-blocking archaeology

Two stale descriptive values remain outside runtime control paths:

- the Hybrid-failure synthetic diagnostics in `run_digest_preview.py` still describe the fallback budget as 24 / Hybrid 4 even though the active double-gap path can be 25 / Hybrid 5;
- the `ensure_story_coverage.py` module docstring describes the ordinary 24 ceiling without mentioning the conditional 25 extension.

These values do not select queries, authorize calls, change recovery, or enforce a budget. Active Hybrid code, AGENTS and canonical architecture already enforce 24/25. They should be cleaned in a later semantic-neutral maintenance PR rather than mixed into the pre-nightly writer-race fix.

## README / architecture impact

No retrieval topology, stage order, schedule, workflow inventory, public interface, search budget or user-facing operation changes. The canonical architecture was checked and remains accurate at that level. The newly discovered safety requirement is added to root `AGENTS.md`, while this audit records the operational rationale and evidence. README files require no change for this mutex-only fix.
