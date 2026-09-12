# P3a — weak-source signal retention, zero-paid replay

## Scope

This is the first independently finishable boundary from the Sep11 Astra technical handoff P3. It fixes evidence loss only: a qualified product/model `weak_source` rejection may remain visible as unresolved evidence, but it is **not** a candidate, does **not** reserve the Coverage resolution slot, and does **not** authorize a new search.

The current production baseline is merge commit `337a123300dbf783c7e46ffd4be8f6f9d546b2a5` (P2 merged). The controlled input is the saved Sep11 DeepSeek rejection copied into `automation/fixtures/recall/weak-source-signal-retention-2026-09-11.json` from the technical follow-up evidence. No production API, OpenAI call, Web Search operation, workflow dispatch or mutable source fetch was used for this P3a replay.

Assistant-side Terra is not exposed in this session. P3a does not change a search query, routing, ranking, provider or candidate pool, so no substitute live search was used. The saved deterministic baseline/proposed replay is sufficient for this evidence-retention boundary. Any P3b authoritative-binding/query behavior still requires its own fixed-budget empirical acceptance before production use.

## Baseline vs proposed

| Case | Current baseline | P3a proposed | Allowed delta |
|---|---|---|---|
| Sep11 DeepSeek `weak_source` | rejection persists, `unresolved_signals=[]` | one `weak_source_product` unresolved evidence row | evidence becomes observable only |
| Candidate eligibility | rejected | rejected | none |
| Coverage `_required_signals` | no DeepSeek obligation | still no DeepSeek obligation | none |
| New Web Search operations | 0 | 0 | none |
| Search ceilings | 24 ordinary / 25 double-gap | 24 / 25 | none |
| Freshness / archive / editorial | existing contracts | unchanged | none |
| Existing high-signal `unverified` | may reserve existing seventh Coverage slot | unchanged | none |

The proposed row retains the original source URL and reason, a conservative organization hint, product/version anchors and lifecycle/action anchors. These values are evidence hints, not proof of event identity. The row explicitly carries `resolution_required=false`, `candidate_eligible=false`, `additional_search_operations=0`, and `resolution_eligibility=deferred_exact_authoritative_binding`.

## Search-change validation matrix coverage

P3a changes provenance retention inside Primary diagnostics but not retrieval execution. The matrix was therefore evaluated for semantic delta on all affected dimensions, with unchanged dimensions protected by the existing full offline suite.

| Dimension | Controlled case | Result |
|---|---|---|
| Volume V1–V5 | weak-source row is not added to `candidates` | candidate volume unchanged |
| Identity O3 | same organization alone is not event proof | no authoritative binding exists in P3a |
| Region R1–R7 | queue is diagnostic-only | regional health and Hybrid allocation unchanged |
| Freshness F1–F7 | queue never reaches freshness admission as candidate | no freshness bypass |
| Degradation D1–D5 | qualified weak source is retained as unresolved evidence | no false `verified`/healthy claim |
| Budget B1–B3 | `additional_search_operations=0`; Coverage ignores `resolution_required=false` | ceilings unchanged |
| Continuity C1–C2 | no query/search/window mutation | unchanged |
| Recovery P1–P4 | Retrieval Quality contract version remains compatible; evidence row creates no paid obligation | no repeat paid retrieval |
| Ordering P5–P6 | semantic identity fields survive a rejection-list ordering perturbation; legacy index-based signal IDs remain compatibility metadata | no candidate/search delta |

### Critical combinations

1. **Weak-source signal + occupied seventh Coverage slot.** P3a does not reserve or replace the existing slot because the signal is not `resolution_required`. The Sep11 incident therefore remains truthfully unresolved rather than pretending DeepSeek was recovered.
2. **Weak-source signal + authoritative reference exists elsewhere.** The fixture preserves DeepSeek official/Reuters reference URLs only as future P3b evidence. P3a must not consume them automatically.
3. **Weak-source signal + same organization / different event.** No event binding is attempted, so company overlap cannot close anything.
4. **Weak-source signal + stale/duplicate/other terminal reason.** Only `reason_code=weak_source` with HTTPS provenance, version/model anchor and lifecycle/action anchor enters the evidence queue; terminal reasons remain outside it.
5. **Weak-source queue + existing high-signal `unverified` obligation.** Existing `unverified` resolution semantics remain unchanged and keep their priority in the existing Coverage seventh-slot logic.

## Acceptance boundaries

P3a is accepted only if all of the following remain true:

- saved Sep11 DeepSeek evidence is retained with original source/reason provenance;
- weak-source retention alone never sets `resolution_required=true`;
- weak-source retention alone never makes a candidate eligible or publishable;
- no new search/query/provider/domain-filter/ranking behavior appears;
- existing high-signal `unverified` resolution remains unchanged;
- no freshness, archive dedupe, regional quota, recovery or publication policy is weakened;
- full offline PR Gate passes on the exact final head.

## Deferred P3b

Exact authoritative binding is deliberately deferred from this PR. Before activation it needs negative identity controls for same-company/different-event, old release, similar version, preview-vs-GA, duplicate announcement, false alias, missing source proof, provider ordering, occupied seventh slot and interrupted/restored spent-slot states. A positive queue row is **not** a retrieval positive and is not evidence that P3b improves recall.
