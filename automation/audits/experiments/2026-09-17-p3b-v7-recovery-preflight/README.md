# 2026-09-17 P3b v7 recovery-preflight remediation

## Trigger

Post-merge independent audit after PR #183 found a production integration gap above active v6 `execute_audit_plan`: a stale positive P3b candidate admitted by evidence-v1..v5 could survive current evidence-v6 invalidation when production took either the complete `existing_full_digest` shortcut or the `prior_complete` reusable Coverage-report branch. Both paths could avoid the v6 stale-positive postcondition entirely.

## Scope

This remediation is intentionally narrow:

- add active runtime v7 over preserved v6;
- keep binder `weak_source_exact_binding_v4.py` and `EVIDENCE_VERSION=6` unchanged;
- keep durable request contract `VERSION=2` unchanged;
- add deterministic recovery preflight before production complete/reuse shortcuts;
- preserve optional-slot journal bytes and consumed capacity;
- sanitize only exact stale signal-bound P3b provenance;
- require a clean rebuilt `stories.json` before a quarantined complete artifact is publishable again;
- add explicit rollback/quarantine runbook;
- do not change query, provider/domain routing, source/event freshness semantics, candidate ranking, Coverage capacity or 24/25 whole-pipeline ceilings.

## No-spend boundary

Implementation and regression work uses repository code, saved semantics and offline controls only. No production OpenAI API, paid Web Search, mutable authoritative-page refetch or Terra call is used for this remediation. Search-side semantics are unchanged, so a live search experiment would not test the defect being fixed.

## Required controls

`automation/tests/test_p3b_v7_recovery_preflight.py` must prove at least:

1. stale complete artifact + reusable prior report are sanitized before shortcuts;
2. optional-slot journal bytes stay unchanged;
3. ordinary/protected provider call and page refetch count remain zero in preflight;
4. pending marker survives loss of the original journal and preserves first backup metadata;
5. current evidence-v6 positive is not treated as stale;
6. report-only stale provenance is cleaned without invalidating a clean complete digest;
7. child failure leaves publishable `stories.json` quarantined;
8. clean rebuild completes the marker;
9. false success that reintroduces revoked story fails closed.

Existing v1-v6 P3b tests remain mandatory non-regression coverage, especially at-most-once optional-slot recovery, atomic P3b→legacy handoff, exact binder matrix, request/context drift cleanup, Coverage 7 and whole-pipeline 24/25 ceilings.

## Final-review remediation checkpoint

The independent final review of the initial v7 implementation found three additional recovery defects. The remediation branch now has permanent controls for each one:

1. genuine production P3b v1 positive provenance is revoked without broad title/URL heuristics, while same-looking unrelated candidates survive;
2. a present but invalid durable optional-slot journal fails closed before complete/reusable shortcuts instead of being treated as journal absence;
3. a crash after sanitation mutations but before the final `completed` marker can restart idempotently and complete a recovery-input-only pending marker.

The reviewed baseline used by the controlled baseline/proposed experiment is preserved byte-for-byte. `ensure_story_coverage_p3b_v7.py` at reviewed SHA `52e110b0a4127deea22753f82871c5a9a4469d22` and current `ensure_story_coverage_p3b_v7_base.py` both have Git blob SHA `ded1165fe0e1e689c587488d91d967b0b4bed9ed`.

Validation checkpoint for implementation head `e115da7ed852be3bfbc2238b5dbccb3fbfa12bac`:

- PR Gate #523, workflow run `35208576710`: success, including Required PR Gate;
- full offline unit suite: `894` tests, `OK`;
- controlled baseline/proposed corpus: pass;
- five crash/restart fault-injection boundaries plus completed-restart noop and current evidence-v6 identity-drift control: pass;
- final-review regression tests for genuine v1 revocation, invalid-journal fail-closed behavior and restart finalization: pass;
- import-isolation regressions: pass;
- canonical P3a blob remains exactly `14f0e38f57b9285a949ec5083136999c12c81bc0`;
- canonical P3b exact-authoritative-binding matrix remains exactly 20 named cases and its active-runtime matrix test passes;
- active P3b runtime remains v7 over preserved v6 with binder v4 / `EVIDENCE_VERSION=6`, Coverage maximum 7, and whole-pipeline 24/25 search ceilings;
- remediation zero-I/O controls replace ordinary provider call, protected/retry provider call and authoritative-page fetch with assertion failures and observe zero calls during preflight;
- optional-slot journal bytes remain unchanged in the stale-v1 remediation control.

This checkpoint records validation evidence only. It does not replace independent inspection of the final diff or exact-final-head CI after this record itself is committed.

## Rollback

Canonical rollback procedure: `automation/P3B_V7_RECOVERY.md`.

Quarantine backups are forensic evidence. They are never an automatic publication fallback. Code rollback may return the public shim to preserved v6 only while sanitized research/report state is retained and stale complete `stories.json` is not restored.

## Acceptance

Before merge:

- full PR Gate on exact final head;
- inspection of exact final diff and current architecture docs;
- independent Astra final review of exact final SHA;
- no reliance on this document or regression test names as proof of correctness.
