# Processed-snapshot durable-identity remediation checkpoint

## Review trigger

A fresh external independent final review inspected exact SHA `7cdf2122ad8f3b23972da6f33b3652e634e3eb42` and returned `FINAL REVIEW: FAIL` with one HIGH blocking durable-recovery finding: a valid outer optional-slot journal for bundle A could contain a structurally valid current-evidence `processed_snapshot` from bundle B, while active v7 proved only the outer journal's identity against the current Coverage bundle.

The review result was treated as a hypothesis until independently reproduced against the exact reviewed head. PR body, audit notes and test names were not used as correctness proof.

## Independent reproduction

Inspection of the production path confirmed the gap:

- active v7 validated outer `search_window_sha256`, `bundle_identity_sha256` and request identity;
- `state="processed"` validated only the inner snapshot's structural shape (`dict`, candidate list and search-budget fields);
- the preserved child path can reuse `processed_snapshot` directly once the slot is already processed;
- a foreign snapshot carrying the current binder evidence version is not stale-semantic evidence and therefore is not rejected by the historical stale-evidence migration guard.

Commit `6e35a4cb8973870f0b3668d645e87bc0104b1eba` added the regression before changing runtime behavior. The control created a valid outer journal for bundle A, substituted only a full current-shape inner processed snapshot from another bundle, prohibited ordinary provider, protected/retry transport and authoritative-page fetch calls, and required fail-closed with byte-identical journal state.

PR Gate #531 / workflow run `35252045593` failed as expected on that regression-first head. The Python suite ran 898 tests and reported exactly one failure: the new identity regression did not receive `CoverageSlotError`. The previous 897 tests passed. This independently reproduced the review finding.

## Runtime remediation

Commit `85a1bc9f5a7ff1e8d9e0a557485e484a24860bab` made one narrow runtime correction in `automation/scripts/ensure_story_coverage_p3b_v7.py`.

For `state="processed"`, after the existing deterministic-plan shape checks, active v7 now independently proves the inner durable result against the outer journal identity:

1. `processed_snapshot.search_window` must be an object and `sha256_value(processed_snapshot.search_window)` must equal outer `search_window_sha256`;
2. `_P3A._bundle_identity(processed_snapshot)` must be computable and `sha256_value(...)` must equal outer `bundle_identity_sha256`.

Any missing, unprovable or mismatching inner identity raises `CoverageSlotError` before child reuse or complete/reusable shortcuts.

The durable optional-slot schema and writer were not changed. The writer already stores the complete Coverage plan as the processed snapshot, so the active v7 recovery validator uses identity already present in production state rather than introducing a new durable field. The preserved reviewed baseline was not modified.

## Fixture correction and stronger counterexample

PR Gate #532 / workflow run `35252585854` showed that the new negative identity regression passed, but older remediation/recovery tests had synthetic processed snapshots truncated to `candidates + diagnostic + search_budget`. Those test-only snapshots did not match the production writer, which persists the full Coverage plan including search-window and bundle-identity inputs. The runtime identity guard was deliberately not weakened to accommodate those fixtures.

Commit `6b7031a17033efe0e3c938c1010e9b44c10909e5` normalized the affected tests to production-shaped processed snapshots and strengthened the new regression suite with a second counterexample:

- outer journal remains valid for bundle A;
- inner snapshot uses the same publication date and the same search window;
- the foreign snapshot differs only in durable P3a bundle identity (via mandatory-attempt response identity);
- both snapshots are full current-shape evidence-v6 plans;
- the foreign inner snapshot must fail closed before child reuse;
- provider, protected/retry transport and authoritative-page fetch seams remain at zero calls;
- journal bytes remain unchanged after rejection.

The same-date/same-window case prevents a future implementation from satisfying the regression with a date-only or search-window-only comparison.

PR Gate #533 / workflow run `35253343809` completed successfully on exact head `6b7031a17033efe0e3c938c1010e9b44c10909e5`: Main CI passed, the full offline Python suite passed, offline validators passed, Required PR Gate passed, and Video CI was skipped by changed-path routing.

## Compatibility boundary

The remediation preserves the existing state distinctions:

- `response_saved` remains replayable offline and does not prematurely require a processed snapshot;
- a valid same-identity generic/legacy processed Coverage plan remains reusable and is not required to carry a P3b-only diagnostic;
- `state="processed"` now additionally requires that its deterministic inner result belong to the same durable bundle identity as its outer journal.

No journal rewrite, optional-slot refund/reopen, provider call, retry transport, Web Search or authoritative-page refetch is introduced by this validation.

## Documentation

Commit `0adfc33216d33e99946e5c8284115949c363952f` synchronized `automation/P3B_V7_RECOVERY.md` with the inner processed-snapshot identity invariant. The runbook now documents the two independent durable bindings:

- outer journal -> current Coverage bundle;
- inner processed snapshot -> the same outer durable search-window and bundle identity.

`automation/ARCHITECTURE.md` already defines same-bundle recovery and compatible processed-state reuse; the new guard is a stricter enforcement of that existing architecture rather than a search/query architecture change. Root `AGENTS.md` and `automation/README.md` were reviewed and did not require changes for this narrow recovery-contract remediation.

## No-spend / unchanged search architecture

This remediation does not change query generation, provider/domain routing, model routing, binder semantics, candidate ranking/caps, Event Freshness, Source Freshness, editorial/publication policy, P3a semantics, mandatory Coverage directions, optional-slot capacity or whole-pipeline ceilings.

Coverage maximum remains 7 and the whole-pipeline ceilings remain 24/25.

No production API, paid Web Search, authoritative-page refetch, retry transport or substitute live search was used for reproduction or validation. Terra was not used because query/search architecture did not change.

## Evidence status

This file records reproduction and remediation evidence only. It is not proof of correctness and does not replace independent inspection of the final diff, active runtime call path, same-bundle recovery contracts or exact-final-head CI.

Because this record itself changes the PR head, a new PR Gate on the resulting exact SHA is required before the PR is handed back for another fresh independent final review.
