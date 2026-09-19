# External final-review remediation checkpoint

## Review trigger

A fresh external independent final review inspected exact SHA `f866b1bb28a10167bfe632a179b6938afb3b2f47` and returned `FINAL REVIEW: FAIL` with two blocking composition-level findings:

1. active v7 installed the hardened historical stale-P3b revocation predicate into preserved v6, but the reviewed v7 baseline could subsequently run its own compatibility sync and restore the old v6 predicate immediately before child execution;
2. `state="processed"` durable optional-slot journals were validated for transport/identity integrity but did not fail closed when their deterministic `processed_snapshot` was missing or structurally invalid.

The review result was treated as a hypothesis until independently reproduced against the exact reviewed head. PR body, audit notes and regression names were not used as correctness proof.

## Regression-first reproduction

Commit `ed4a9bf55933bfa7bcf8a9efd3cd356b529a619c` added composition-level controls before changing runtime behavior.

PR Gate #525 / workflow run `35215504440` failed as expected on that regression-first head. The full suite ran 896 tests and reported exactly five new failures, all in the new external-review regression module:

- nested baseline sync restored the old v6 revocation predicate;
- `processed_snapshot` missing;
- `processed_snapshot` list;
- `processed_snapshot` scalar;
- `processed_snapshot` empty object.

Existing tests outside those new controls remained green. This reproduced both external findings independently rather than accepting the review text as proof.

## Runtime remediation

Commit `3d02fae2beeab99863a46a1d13d6fc717b76c776` made two narrow runtime corrections in `automation/scripts/ensure_story_coverage_p3b_v7.py`:

- `_install_revocation_predicate()` installs the remediation-owned predicate into both the reviewed baseline namespace and preserved v6. The reviewed baseline's nested compatibility sync therefore propagates the hardened predicate instead of restoring the historical v6 implementation;
- `state="processed"` durable journals must contain a deterministic processed Coverage plan: `processed_snapshot` must be an object, `candidates` must be a list, and `search_budget` must contain `maximum_calls`, `completed_calls`, and `remaining_calls`. Invalid processed evidence raises `CoverageSlotError` before complete/reusable shortcuts.

The preserved reviewed baseline file itself was not modified.

## Compatibility and experiment controls

Commit `4abead9ec3caa7e44a0e855b1b4bc3f93e7403fa` made the controlled baseline/proposed fixture production-shaped by including the deterministic processed-plan search budget.

Commit `619137da497dce3f90f2432def44c0ecdc2e26d9` added controls proving both sides of the processed-state contract:

- malformed `candidates` and malformed `search_budget` fail closed;
- a valid generic/legacy processed Coverage plan remains reusable and is not forced to contain a P3b-specific diagnostic.

This preserves the existing `response_saved` contract: a saved raw response without a parsed deterministic snapshot remains replayable offline because it is not yet in `processed` state.

Commit `c8afa1aaf7b7c2f17ae64ec79c582141979262d5` synchronized `automation/P3B_V7_RECOVERY.md` with the nested-sync and deterministic-processed-snapshot invariants.

## Green implementation checkpoint

PR Gate #529 / workflow run `35216734757` completed successfully on exact implementation head `c8afa1aaf7b7c2f17ae64ec79c582141979262d5` and merge ref `4d8e5ac91688419cfa54952aa4a64f0c7068a7e5` against base `c8c88ceffd26a97b48be9bf16913dc4b90c9f8c8`.

Exact-head evidence from Main CI:

- compile: pass;
- full offline unit suite: `897` tests, `OK`;
- `test_nested_baseline_sync_cannot_restore_old_v6_revocation_predicate`: pass;
- `test_processed_journal_requires_deterministic_processed_snapshot`: pass;
- `test_valid_generic_processed_plan_remains_reusable`: pass;
- controlled baseline/proposed corpus: pass;
- five crash/restart fault-injection boundaries plus completed-restart/current-evidence controls: pass;
- original final-review P1/P2/P3 remediation controls: pass;
- recovery-preflight, durable-research and same-bundle recovery controls: pass;
- import-isolation controls: pass;
- canonical P3b semantic matrix ownership test: pass, exactly 20 named cases;
- editorial contract, archive, production workflow, Dzen RSS, sitemap, structured-data and protected-path checks: pass;
- Required PR Gate: pass.

The CI artifact for that merge ref was `main-ci-4d8e5ac91688419cfa54952aa4a64f0c7068a7e5`.

## No-spend / scope boundary

This external-review remediation did not change query generation, provider/domain routing, model routing, binder semantics, ranking, candidate cap, Event Freshness, Source Freshness, editorial policy, publication policy, P3a semantics, mandatory Coverage directions, optional-slot capacity, or the 24/25 whole-pipeline ceilings.

Terra was not used because query/search architecture did not change. No production API, paid Web Search, authoritative-page refetch, retry transport or substitute live search was used to reproduce or validate these two recovery-state defects.

## Evidence status

This file records reproduction and validation evidence only. It is not proof of correctness and does not replace independent inspection of the final diff, runtime call path, durable-state contracts, or exact-final-head CI.

Because this record itself changes the PR head, a new PR Gate on the resulting exact SHA is required before handing the PR back for another fresh independent review.
