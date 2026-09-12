# P3b exact authoritative binding audit

Date: 2026-09-12

PR: #175 `Add P3b exact authoritative weak-source binding`

Status: implementation and offline regression evidence complete; final canonical-doc synchronization and independent Astra review remain pre-merge gates.

## Scope

P3b is a downstream exact-authoritative binding layer for qualified P3a `weak_source` product/model signals. P3a remains evidence-only: its queue rows stay `resolution_required=false` and `candidate_eligible=false`. P3b may admit a candidate only after independent same-event authoritative evidence is returned through the already-existing optional seventh Coverage slot.

P3b does not make the weak source authoritative, does not use the legacy fuzzy matcher as proof, and does not create a new search slot.

## Search and spend contract

The whole-pipeline search ceilings are unchanged:

- Primary: 12 searches;
- Agency Rescue: at most 1 search;
- Hybrid: normally at most 4, conditionally 5 only on the existing double-regional-gap path;
- Coverage: 6 mandatory searches plus at most the existing optional seventh search;
- normal whole-pipeline ceiling: 24;
- existing conditional double-gap ceiling: 25.

P3b can use only that existing seventh Coverage slot and only when the older required `unverified` resolution path does not own it. There is no eighth Coverage search.

No production workflow, user production API, paid Web Search, or other user-paid network experiment was used for this PR. Terra is not exposed in the current working environment, so the required independent search-side validation was emulated with deterministic fixtures, saved-state semantics and offline replay. This limitation is intentional and was not compensated by production spend.

## Exact identity contract

Weak-source fields are hints, not proof. A positive P3b binding requires all of the following:

- verified candidate;
- `freshness_status` of `new_event` or `material_update`;
- exact normalized organization identity;
- every model/version anchor present as an ordered exact-token sequence;
- lifecycle/action semantic match, with preview, GA, release, update, replacement and benchmark kept distinct;
- authoritative primary-source host from the existing authoritative-domain policy;
- the authoritative primary source cannot be the original weak-source host.

The binder therefore does not conflate `V4`, `V4.1`, `V4.1 Flash`, preview/GA, launch/update, replacement/benchmark or old/current events. Ambiguous identity stays unresolved.

An `unverified` rejection does not auto-close a weak-source signal. Terminal-negative closure requires independently authoritative exact same-event evidence plus an allowed terminal reason. Contradictory exact positive and exact terminal-negative evidence fails closed as unresolved.

## Determinism

P3b selects at most one weak-source signal, ordered by significance and then `signal_id`. Positive candidates are sorted deterministically by source class and then URL/title. The source-neutral query contains the retained organization/version/action hints without publisher/site/date filters. The saved DeepSeek control produces:

`DeepSeek V4 Pro V4.1 Flash replace latest`

Admitted candidates are marked with:

- `audit_direction="weak_source_exact_binding"`;
- `resolution_signal_ids=[signal_id]`;
- `p3b_exact_binding_version=1`.

## Durable optional-slot / recovery proof

P3b reuses the #174 durable slot states:

`reserved -> request_started -> response_saved -> processed`

Recovery rules remain fail-closed and at-most-once:

- `request_started` with unknown provider outcome is consumed/ambiguous and is never retried automatically;
- `response_saved` replays the saved response offline even when restored runtime accounting reports zero remaining calls;
- `processed` reuses the deterministic processed snapshot even when restored runtime accounting reports zero remaining calls;
- an empty or merely `reserved` journal cannot override a zero runtime budget and start a new search;
- a consumed/ambiguous seventh slot cannot be refunded into an eighth search;
- the older required `unverified` obligation retains priority over P3b.

The journal is inspected before the runtime `remaining_calls` shortcut so saved work is recoverable without reopening paid transport.

## Regression matrix

The permanent offline P3b matrix is encoded in `automation/tests/test_p3b_regression_matrix.py`, with transport/recovery cases exercised by `automation/tests/test_p3b_optional_slot_recovery.py` and the existing optional-slot suites.

| # | Case | Expected P3b state/invariant |
|---|---|---|
| 1 | exact positive | candidate admitted through exact authoritative binding |
| 2 | same company / different product | unresolved; version identity mismatch |
| 3 | similar version | unresolved; exact version mismatch |
| 4 | old release | blocked by Freshness |
| 5 | preview vs GA | unresolved; lifecycle mismatch |
| 6 | benchmark vs release | unresolved; lifecycle mismatch |
| 7 | duplicate/reprint | exact authoritative terminal-negative only when terminal reason is independently proven |
| 8 | false alias | unresolved; no fuzzy alias proof |
| 9 | missing authoritative source | unresolved/fail-closed |
| 10 | wrong event/date official page | blocked by Freshness/event mismatch |
| 11 | independently valid candidate not binding | remains independent; cannot close this signal |
| 12 | result-order permutation | deterministic same selected result |
| 13 | occupied seventh slot | deferred capacity; no eighth search |
| 14 | seventh slot spent before recovery | consumed; not refunded |
| 15 | interrupted/ambiguous transport | `request_started`, deferred/indeterminate, no retry |
| 16 | saved completed resolution replay | offline replay/snapshot reuse, no wire call |
| 17 | stale authoritative page | blocked by Freshness |
| 18 | archive duplicate | excluded/terminal according to archive recommendation, never promoted |
| 19 | candidate fails Freshness | blocked before admission |
| 20 | company+version match but lifecycle differs | unresolved; lifecycle mismatch |

A baseline-vs-treatment control also demonstrates the intended semantic delta: the legacy fuzzy cluster matcher can accept a same-company/different-event candidate that P3b rejects because exact version/lifecycle identity is missing. This delta is the purpose of P3b rather than an accidental ranking change.

## Whole-project architecture audit

The audited data path is:

Primary -> Source Pulse -> Event Freshness -> Source Freshness -> first editorial -> Agency Rescue -> Hybrid -> Coverage -> archive -> repair journal -> recovery -> publication validation.

### Primary / P3a

P3b does not alter Primary retrieval, source ranking, Primary caps or P3a signal collection. The weak-source signal remains diagnostic evidence until P3b independently binds an authoritative event.

### Source Pulse

P3b does not change Pulse registry, Pulse health, Pulse candidate admission or regional-health semantics. Pulse-only evidence cannot authorize a P3b weak-source signal.

### Event Freshness and Source Freshness

P3b requires an already verified/fresh candidate shape and explicitly rejects stale/uncertain event states. It adds no bypass around Event Freshness or Source Freshness. An official URL for an old or wrong event is insufficient.

### First editorial

P3b runs in Coverage after the existing first editorial path. It does not change first-editorial ranking, regional quotas, topic ranking or publisher pressure. P3b admission is at most one exact candidate from the optional Coverage resolution path.

### Agency Rescue

Agency health and the single Reuters rescue slot are untouched. P3b does not treat Agency observability or a Reuters result as weak-signal proof unless the candidate independently satisfies the exact P3b binding contract.

### Hybrid

Regional health and the 4/conditional-5 Hybrid budget are untouched. P3b neither opens nor closes Hybrid regional gaps and cannot consume a Hybrid slot.

### Coverage

The six mandatory Coverage directions are unchanged. P3b runs only after they are complete and only through the existing optional seventh-slot owner. Existing required high-signal `unverified` resolution has priority. P3b cannot create an eighth search.

### Archive / dedupe

P3b does not weaken archive recommendation semantics. Duplicate/stale candidates are not promoted merely because organization/version text matches. Exact terminal-negative handling is separate from positive candidate admission.

### Repair journal / recovery

The durable optional-slot journal remains the source of truth for consumed/ambiguous capacity. Saved response and processed snapshot states replay offline; unknown started transport does not retry. This preserves paid at-most-once behavior across same-day recovery.

### Publication validation

P3b changes only candidate admission into the existing downstream pool. It does not change publication validators, story schema, RSS/sitemap validation, publication ordering rules or deploy mechanics. Existing offline production validators pass on the exact implementation head used for the pre-documentation Gate.

## Compatibility incident found during implementation

The first compatibility wrapper accidentally proxied its own `_pull_runtime_state` helper, producing recursive self-calls and widespread legacy-test failures. The repair renamed the shim-internal pull helper and preserved the historical exported helper separately.

Three remaining compatibility failures showed that late `mock.patch` hooks were not being synchronized through the new wrapper and that `completed_prior_audit` had a historical object-identity contract. The stable public shim now propagates lazy delegated hooks and preserves that identity export. The legacy suite then returned green before the P3b recovery tests were added.

This was a wrapper compatibility defect, not a relaxation of the P3b exact-binding contract.

## CI evidence

Pre-documentation exact-head `f6431d25cf1d0eccfd8be1b7a018dd4bf1dc8da2`:

- PR Gate run `34696297663`;
- compile: success;
- unit/regression suite: success;
- editorial contract validator: success;
- committed archive validator: success;
- production workflow contract validator: success;
- RSS/sitemap/structured-data validator: success;
- protected-path mutation check: success;
- `Required PR Gate`: success.

A new exact-head Gate is still required after canonical documentation/audit commits.

## Independent review gate

The P3b handoff explicitly requires a separate independent Astra audit after final diff, final architecture audit, permanent validation evidence, recovery/budget proof, zero-spend confirmation and exact-head green Gate are available. This document does not claim to substitute the implementer's self-audit for that independent review.

Merge is prohibited until that independent Astra gate is satisfied and the final reviewed head remains unchanged.