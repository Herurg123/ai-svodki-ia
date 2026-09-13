# P3b exact authoritative binding audit

Date: 2026-09-12 / final remediation audit 2026-09-13

PR: #175 `Add P3b exact authoritative weak-source binding`

Status: implementation, Astra remediation, permanent offline regressions and canonical documentation are complete. Runtime code head `654eada715382789982b2d847e98c0846e5b6a11` passed PR Gate #368 with 803/803 tests. Documentation synchronization follows that green code head, so the final documentation-inclusive exact SHA must pass a fresh PR Gate before independent Astra handoff. The remaining pre-merge gate after that is a new independent Astra review of the unchanged final exact PR head.

## Scope

P3b is a downstream exact-authoritative binding layer for qualified P3a `weak_source` product/model signals. P3a remains evidence-only: its rows stay `resolution_required=false` and `candidate_eligible=false`. P3b can admit at most one candidate only after independently proving the same event against a fetched authoritative page and the existing deterministic freshness/archive gates.

P3b does not make the weak source authoritative, does not use fuzzy same-company matching as proof, and does not add a search slot.

## Search and spend contract

Search ceilings are unchanged:

- Primary: 12 Web Search operations;
- Agency Rescue: at most 1;
- Hybrid: normally at most 4, conditionally 5 only on the existing double-regional-gap path;
- Coverage: 6 mandatory plus at most the existing optional seventh;
- normal whole-pipeline ceiling: 24;
- existing conditional double-gap ceiling: 25.

P3b can use only the existing optional seventh Coverage slot. Existing required high-signal `unverified` resolution has priority. Durable slot occupancy is tracked independently from whether a saved P3b result is reusable under the current model/signal/archive contract, so model/archive/signal mismatch cannot reopen an eighth search.

No production workflow, user production API or paid Web Search was used for implementation/remediation. Terra is not exposed in the implementation environment, so search-side acceptance uses deterministic fixtures, saved-state semantics and offline replay. No query/routing change was introduced by the remediation rounds.

## Active exact identity contract

The active binder implementation is `weak_source_exact_binding_v3.py`. It deliberately preserves binder `VERSION=2` and the existing P3b mode so saved v2 request contracts/journals remain recognizable; v3 is semantic hardening, not a new durable contract generation. The public Coverage entrypoint routes through active v5 → v4 → v3 → v2 compatibility orchestration. Historical P3b v1/v2 semantics and the byte-preserved P3a implementation remain compatibility/reference layers, not active exact-binding semantics.

A positive admission requires all of the following:

- candidate recommendation is `include|consider`, verification is `verified`, and claimed event freshness is `new_event|material_update`;
- exact normalized organization identity;
- organization, every retained product/model/version anchor and lifecycle/action coexist in one local event claim; adjacent title/paragraph claims are never combined into synthetic identity proof;
- lifecycle/action in that local claim is attributable to the signal organization rather than merely co-occurring with it; a foreign named actor or explicit reporting/role attribution between the signal organization and lifecycle/action fails closed;
- every retained product/model/version anchor matches exactly rather than by fuzzy prefix;
- lifecycle/action is compatible with the retained signal;
- for replacement, old/new roles are inferred from the retained signal claim, not anchor-array order, and candidate/page must assert the same direction;
- negated lifecycle claims, historical/background mentions and prospective/planned actions are not current-event proof;
- canonical `general_availability` is normalized to GA semantics; preview and GA remain distinct;
- unknown named/numeric model suffixes do not collapse into a shorter retained anchor;
- primary/final URL is in the existing authoritative allowlist and cannot be the weak-source host;
- the fetched authoritative page contains the exact current event claim;
- deterministic Event/Source Freshness passes;
- archive/dedupe does not independently prove the same event.

The actor-attribution guard is intentionally conservative because P3b is opportunistic. `DeepSeek says OpenAI launches V4.1 Flash`, lowercase foreign-actor/reporting forms, and role-attribution forms such as `DeepSeek says the rival launches V4.1 Flash` do not prove a DeepSeek launch even though the organization, version and lifecycle words occur in one sentence. The inverse `OpenAI says DeepSeek launches V4.1 Flash` still attributes the lifecycle event to DeepSeek and is eligible for the remaining exact-binding checks. A direct form such as `DeepSeek announces V4.1 Flash launch` remains bindable.

Provider/model terminal-negative labels are diagnostic only. The active binder does not treat a model `duplicate`/`unverified` label as proof. A negative disposition needs independent deterministic evidence elsewhere in the pipeline; the model label itself never closes the weak-source signal.

Admitted candidates carry:

- `audit_direction="weak_source_exact_binding"`;
- `resolution_signal_ids=[signal_id]`;
- `p3b_exact_binding_version=2` because v3 intentionally preserves the durable v2 contract version;
- authoritative-page proof metadata.

## Archive exact-event contract

Exact source URL remains conclusive duplicate proof.

For singular lifecycle identities such as a directed replacement, the strict organization/version/lifecycle identity predicate can independently establish the archived same event.

Structured archive `organization` may supply the organization identity for its own story row when the headline omits it, but it cannot reassign a headline that attributes the event to another actor. Thus a row with `organization=DeepSeek` and headline `OpenAI launches V4.1 Flash` is not same-event proof for a DeepSeek launch.

For mutable lifecycle actions such as `update`/`upgrade`/`rollout`, organization + model/version + lifecycle is insufficient because one product can receive many distinct updates. Semantic archive rejection therefore additionally requires an exact normalized ordered event-detail fingerprint after removing identity and generic update words. Partial lexical overlap is deliberately non-terminal. This prevents high-overlap distinct updates such as `video input support` vs `video output support` from being collapsed while preserving exact-URL duplicate proof and exact same-update semantic proof.

## Durable optional-slot / recovery proof

Durable states remain:

`reserved -> request_started -> response_saved -> processed`

Rules:

- any valid/unknown optional-slot journal suppresses fresh legacy optional routing before reuse compatibility is considered;
- `request_started` means outcome/consumption is ambiguous and never auto-retries;
- `response_saved` replays the saved provider response/result offline, with no new provider search and no mutable authoritative-page refetch; if durable page proof was not saved before interruption, replay fails closed rather than inventing proof;
- `processed` reuses the saved hardened result;
- a reserved slot cannot override evidence that the runtime already consumed seven Coverage calls;
- a current unstarted P3b reservation may be released for a higher-priority required `unverified` obligation only when exact request-contract identity is proven and there is independently no admitted wire attempt, consumed/ambiguous flag, response hash/file or concurrent journal mutation;
- release is atomic with respect to the observed journal and only the proven P3b reservation can be removed; foreign/mismatched/invalid reservations remain fail-closed;
- after that release, v5 deliberately suppresses the compatibility scheduler's unjournaled seventh-search path and hands slot seven to P3a's durable resolver;
- v5 preserves the publication-date ContextVar only for the duration of that direct P3a durable handoff, then resets it in `finally`; this is required because P3a's normal `execute_audit_plan` resets the context before v5 performs the handoff;
- a process stop after `request_started` therefore leaves a consumed/ambiguous journal; same-day recovery sees that state and cannot issue another provider search.

These rules preserve at-most-once provider transport and prohibit an eighth Coverage search during normal execution and same-day recovery.

## Import / compatibility proof

The pre-P3b public implementation is preserved byte-for-byte as `ensure_story_coverage_p3a.py`; its Git blob equals the pre-PR `ensure_story_coverage.py` blob.

The active v5 layer installs binder-v3 semantics only around active exact processing and does not mutate historical nested binder identities at import time. Binder v3 inherits and hardens v2 while keeping `VERSION=2`; v2 compatibility helpers remain available for recognizing previously saved contracts, but compatibility failure cannot veto an exact active contract match.

Public `ensure_story_coverage.py` remains the monkeypatch-compatible entrypoint. Active ownership and handoff regressions are asserted through public seams because wrapper synchronization intentionally restores implementation aliases and must not make a test pass or fail merely from import order.

Permanent subprocess controls start clean Python interpreters with different import orders. A dedicated subprocess also runs `test_p3b_astra_regressions.py` as the only discovered test module, so full-suite import order cannot hide the standalone monkeypatch/import defect reported by Astra.

## Permanent 20-case matrix

The canonical matrix is `automation/specs/p3b-exact-authoritative-binding-matrix.md`. It contains exactly these 20 cases:

1. exact positive;
2. same company, different product;
3. similar version;
4. old release;
5. preview vs GA;
6. benchmark vs release;
7. duplicate/reprint;
8. false alias;
9. missing authoritative source;
10. wrong event/date official page;
11. independently valid candidate not binding;
12. result-order permutation;
13. optional seventh occupied;
14. seventh spent before recovery;
15. interrupted/ambiguous transport;
16. saved completed resolution replay;
17. stale authoritative page;
18. archive duplicate;
19. candidate fails Freshness;
20. same company + version, different lifecycle.

Additional permanent controls cover Astra's remediation counterexamples and final self-audit counterexamples: changed-model/missing-signal/changed-archive recovery mismatch, required-resolution priority, durable P3b-to-required handoff and crash recovery, negation/history/prospective language, cross-claim contamination, same-claim named/lowercase/role actor-attribution contamination, structured archive foreign-actor contamination, replacement-role permutation, distinct and high-overlap mutable archive updates, GA alias, unknown/numeric suffixes, active-version matrix wiring and isolated import order.

Permanent executable coverage includes `test_p3b_astra_second_review.py` in addition to the original P3b matrix, Astra, recovery, archive, lifecycle and import-isolation suites.

## Whole-project architecture audit

Audited path:

Primary → Source Pulse → Event Freshness → Source Freshness → first editorial → Agency Rescue → Hybrid → Coverage/P3b → archive/dedupe → durable recovery → publication validation.

### Primary / P3a

Primary retrieval, query matrix, ranking, caps and signal collection are unchanged. P3a remains evidence-only and byte-preserved relative to the pre-P3b public Coverage implementation. Weak evidence never becomes publication proof by itself.

### Source Pulse

Registry, health, promotion and regional-health semantics are unchanged. Pulse cannot authorize P3b binding and P3b cannot close/reopen Pulse-derived regional health.

### Event / Source Freshness

Existing deterministic freshness code/policy files are unchanged. P3b invokes the existing page/date verification before admission. A fresh page containing only a historical exact-event mention is rejected by identity before page freshness can masquerade as event freshness.

### Editorial / Agency Rescue / Hybrid

No editorial ranking, Agency Rescue, regional health or Hybrid implementation file is changed by PR #175. P3b runs only downstream in Coverage and cannot consume Agency/Hybrid slots or change the 4/conditional-5 Hybrid allocation.

### Coverage

Six mandatory directions remain unchanged. P3b is only an alternate consumer of the already-existing optional seventh slot, after mandatory Coverage and behind required legacy `unverified` priority. Slot occupancy is independent from reuse compatibility, closing the recovery-context eighth-search defect. A proven unstarted P3b reservation can hand the seventh slot to required legacy resolution only through the durable P3a transport; `request_started` remains consumed/ambiguous after interruption.

### Archive / dedupe

Archive checks remain before positive admission. Exact URL is conclusive. Mutable same-model updates require exact ordered event-detail identity rather than broad lexical overlap, so a distinct update is not suppressed merely because organization/version/lifecycle or generic words match. Exact-event identity itself is claim-local and actor-bound: organization cannot be borrowed from a neighboring archive/page claim, nor can a same-claim foreign actor receive the lifecycle while the signal organization appears only as speaker/context. Explicit reporting/role attribution is treated conservatively as ambiguous rather than synthetic proof. Structured archive organization is accepted only for its own row and cannot override a foreign headline actor.

### Recovery

Durable journal state is the source of truth for optional-slot occupancy and at-most-once transport. `request_started` never retries, saved/processed work reuses offline, and budget recalculation cannot refund an already consumed seventh operation. The v5 handoff explicitly carries publication-date context into the direct P3a durable resolver and resets it afterwards; this fixes the second-Astra crash case without changing search routing or adding capacity.

### Publication validation

Publication validators, story schema, RSS/sitemap rules, deploy mechanics and ordering policy are unchanged. P3b only changes whether one Coverage candidate is admitted into the existing downstream candidate pool.

## Changed-file / non-regression boundary

PR changes are confined to root/automation documentation, Coverage/P3b compatibility layers and binders, the permanent P3b spec/audit, and P3/P3b tests. It does not directly change workflow files, Primary, Source Pulse, Event/Source Freshness policy, Agency Rescue, Hybrid, editorial ranking or publication validators.

Root `README.md`, `automation/README.md` and `automation/ARCHITECTURE.md` were inspected during final remediation. Their higher-level active P3b descriptions already state the exact authoritative page, organization/version/lifecycle, freshness/archive requirements, durable seventh-slot behavior and unchanged 24/25 ceilings. The implementation-version and durable-handoff details belong in this audit and permanent matrix, so no gratuitous high-level documentation churn is required.

## Validation evidence

The runtime code head `654eada715382789982b2d847e98c0846e5b6a11` passed PR Gate #368 (`34776097208`). Main CI reported `Ran 803 tests ... OK`, including:

- `test_p3b_to_required_legacy_handoff_stays_durable_after_transport_crash`;
- `test_required_unverified_preempts_proven_unstarted_p3b_reservation`;
- active public v5 / binder-v3 wiring;
- binder identity/actor-attribution, Freshness, archive/dedupe, recovery, import-isolation and budget regressions;
- editorial, archive, production-daily, RSS, sitemap, structured-data and protected-path validators.

Because the canonical docs were synchronized after that green code head, exact-head discipline requires a new PR Gate on the final documentation-inclusive SHA. Gate #368 is evidence for the runtime fix, not the final merge gate.

## Independent review gate

The original independent Astra review of head `5332e64c2221670c8c1815811c758d380d27a747` returned `REQUEST CHANGES` with five P1 and two P2 findings. All seven findings now have repository regressions. Final implementer audits additionally found and fixed the high-overlap mutable-update dedupe case, cross-claim organization contamination, same-claim named foreign-actor attribution contamination, ambiguous reporting/role attribution contamination, exact reservation ownership handoff and publication-context loss across the direct durable P3a handoff.

The final exact PR head must pass `PR Gate` / `Required PR Gate` after the last documentation commit. That exact SHA is then handed to Astra for a new independent review, including rerun of the original probes and independent counterexamples. This document is implementer self-audit evidence and does not substitute for Astra's verdict.

Merge remains prohibited until Astra returns explicit `APPROVE` on the unchanged final exact head.
