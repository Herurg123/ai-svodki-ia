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

## Rollback

Canonical rollback procedure: `automation/P3B_V7_RECOVERY.md`.

Quarantine backups are forensic evidence. They are never an automatic publication fallback. Code rollback may return the public shim to preserved v6 only while sanitized research/report state is retained and stale complete `stories.json` is not restored.

## Acceptance

Before merge:

- full PR Gate on exact final head;
- inspection of exact final diff and current architecture docs;
- independent Astra final review of exact final SHA;
- no reliance on this document or regression test names as proof of correctness.
