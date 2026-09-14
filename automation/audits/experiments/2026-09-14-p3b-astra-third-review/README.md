# P3b Astra third-review / v6 atomic-handoff remediation

Date: 2026-09-14

PR: #175 `Add P3b exact authoritative weak-source binding`

This note supersedes implementation-version and handoff details in the 2026-09-13 second-review note. Earlier experiment results remain valid historical evidence, but the active public runtime is now P3b v6 with binder v4.

No search query, provider/domain routing, paid-search allocation, Primary, Source Pulse, Agency Rescue, Hybrid, editorial ranking, Event/Source Freshness policy or publication contract changes in this remediation. Coverage remains six mandatory searches plus at most its existing optional seventh. Whole-pipeline ceilings remain 24 normally and 25 only on the existing double-regional-gap Hybrid path. Terra is therefore not applicable to these v6/binder-v4 corrections; all acceptance is deterministic/offline and uses no user production API or paid Web Search.

## Trigger

After the second Astra remediation, independent/self-audit counterexamples showed that semantic proof and seventh-slot ownership still needed stronger fail-closed boundaries. In particular, a two-step "remove P3b reservation, then prepare legacy reservation" handoff contains a crash window even if both individual operations are correct: a process stop between them can leave no durable owner for an already-allocated optional slot.

Additional exact-identity counterexamples also covered passive attribution, lifecycle language after the action, conditional/rumor/history forms, punctuation continuations, GA+preview contradiction, mutable single-digit direction and stale positive processed snapshots created before the current hardened proof version.

## Hypotheses and controlled results

1. **Handoff ownership must move atomically, not by release-then-reserve.** A required legacy `unverified` obligation may preempt only a proven current P3b journal that is still `reserved`, has no admitted wire attempt, no response/snapshot and no consumed/ambiguous evidence. Replacing that journal with the complete legacy request/bundle contract under the same slot lock removes the unowned crash gap. Crash injection immediately after transfer left a complete legacy `reserved` journal; the next run could start that exact legacy intent once. Crash injection after `request_started` left the slot consumed/ambiguous and recovery issued no retry/eighth search.
2. **The transfer lock must be the admission lock.** `coverage_slot_handoff.install_locked_slot_transitions()` puts `prepare_slot`, `activate_slot` and the transfer helper behind the same per-slot inter-thread/inter-process lock. A concurrently changed or already-started source journal therefore cannot be overwritten by a stale preemption decision.
3. **Passive attribution must identify the signal organization as agent.** `V4.1 Flash was launched by OpenAI` cannot prove a DeepSeek launch merely because DeepSeek appears elsewhere in the claim; positive control `... launched by DeepSeek` remains valid.
4. **Current lifecycle proof must remain current after the action token.** Cancelled/planned/not-happened suffixes, `if/unless/whether`, rumor/speculation and historical relative/year evidence fail closed even when the exact action and product anchor occur earlier in the claim.
5. **Exact anchors must reject punctuation continuations.** `/v2`, `+...` and product-like dash continuations are distinct variants; normal prose continuation such as `for developers` remains valid.
6. **GA and preview cannot be simultaneously positive.** A GA signal with active preview/beta/early-access language is a lifecycle mismatch.
7. **Mutable archive direction must preserve small numeric changes.** Ordered event-detail identity distinguishes `4→8` from `8→4` just as it distinguishes larger directions.
8. **Positive processed replay needs current semantic-proof evidence.** Binder v4 keeps durable request `VERSION=2`/mode for journal compatibility but adds `EVIDENCE_VERSION=1`. A historical positive processed snapshot lacking the current evidence marker cannot be trusted as current hardened proof; it is downgraded fail-closed without another provider search or page refetch.

## Decision

Active topology:

- public `automation/scripts/ensure_story_coverage.py` → `ensure_story_coverage_p3b_v6.py`;
- v6 preserves v5/v4/v3/v2/v1/P3a compatibility layers but owns atomic P3b→legacy transfer;
- active semantic binder is `weak_source_exact_binding_v4.py`;
- durable request identity remains P3b `VERSION=2`; binder v4 versions only positive semantic proof through `EVIDENCE_VERSION=1`;
- `automation/scripts/coverage_slot_handoff.py` provides the shared lock and atomic transfer primitive;
- preserved `ensure_story_coverage_p3a.py` is not modified.

Required legacy `unverified` resolution remains higher priority than an unstarted P3b reservation. Priority does not authorize deletion of unknown/foreign/started state. The transfer succeeds only from the exact expected current journal and writes the full target legacy durable identity atomically. The final legacy resolver still uses P3a's protected transport, so its normal `reserved → request_started → response_saved → processed` at-most-once semantics remain the authority.

## Permanent regressions

`automation/tests/test_p3b_astra_third_review.py` permanently covers:

- public runtime v6 + binder v4;
- passive attribution agent identity;
- suffix-negative, conditional, historical and rumor lifecycle failures;
- punctuation version continuations;
- GA/preview contradiction;
- single-digit mutable archive direction;
- stale positive processed snapshot without current evidence version;
- process crash immediately after atomic transfer;
- process crash after legacy request admission and no-retry recovery;
- refusal to transfer an already-started P3b reservation.

`automation/tests/test_p3b_recovery_ownership_priority.py` additionally proves the real six-pass priority path: an exact unstarted P3b intent is replaced by a legacy request-contract identity while the journal remains durable `reserved`, wire admission is false and consumed/ambiguous is false. The owner label is intentionally not used as transfer proof because both contracts can share the historical optional-slot owner string; request/bundle identity is the durable distinction.

The second-review semantic suite, original Astra regressions, import-isolation subprocesses, archive tests, lifecycle/replacement tests and the permanent 20-case matrix remain required.

## Stage-1 exact-head evidence

Exact code/test head before documentation synchronization:

`34bec64249d1746446d169b38eebc13650189399`

PR Gate #387, run `34869753652`, passed completely:

- Classify changed paths: success;
- Main CI / Offline production checks: success;
- Video CI / Offline video checks: success;
- Required PR Gate: success;
- Python unit suite: `Ran 812 tests ... OK`;
- editorial/archive/production/RSS/sitemap/structured-data/protected-path validators: success.

This exact head proves the runtime and permanent regressions. Documentation commits after it require their own final exact-head PR Gate before reviewer handoff.

## Whole-project non-regression boundary

The remediation was checked against the complete retrieval path rather than only the P3b module:

Primary → Source Pulse → Event Freshness → Source Freshness → editorial → Agency Rescue → Hybrid → Coverage/P3b → archive/dedupe → same-day recovery → publication validation.

Invariants preserved:

- P3a remains evidence-only and byte-preserved;
- six mandatory Coverage directions remain unchanged;
- no eighth Coverage search;
- required legacy `unverified` retains priority;
- `request_started` never auto-retries;
- `response_saved` and compatible `processed` work reuse offline; stale positive binder evidence fails closed without new paid work;
- Freshness remains deterministic/fail-closed for positive admission;
- archive exact URL remains conclusive and mutable semantic identity preserves direction;
- public/direct/CLI entrypoints use one active v6 path while historical imports remain compatibility/replay assets;
- Primary 12, Agency Rescue ≤1, Hybrid 4/conditional 5 and Coverage ≤7 keep whole-pipeline ceilings 24/25.

## Remaining merge gate

After the final documentation-inclusive SHA passes a fresh `PR Gate` / `Required PR Gate`, that unchanged exact SHA must receive a new independent Astra review. Regression tests named `astra` are executable controls, not a substitute for the reviewer verdict. Required final verdict: explicit `APPROVE` or `REQUEST CHANGES`.
