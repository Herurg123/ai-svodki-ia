# P3b Astra second-review remediation

Date: 2026-09-13

Baseline reviewed head: `e114e94898c6c1841c01eea862154c229eaab046`

Independent Astra verdict on that exact head: `REQUEST CHANGES`.

This experiment covers the six merge blockers from the second independent review. It does not change retrieval queries, provider routing, paid-search allocation, Primary, Source Pulse, Hybrid, Agency Rescue, Event/Source Freshness policy, or the whole-pipeline ceilings 24/25. Terra is therefore not applicable to this remediation. All counterexample work is deterministic/offline and uses no production or paid API.

## Hypotheses

1. A P3b `reserved` journal can be released to higher-priority legacy `unverified`, after which the compatibility preparation path can restore the historical unprotected `_run_resolution`; a process stop after transport admission can therefore make recovery issue an eighth Coverage operation.
2. Claim-local organization/action co-occurrence is insufficient when the retained model anchor belongs to another subject in the same sentence.
3. The v2 temporal regexes are too narrow for planned, modal, cancelled and explicit-year historical lifecycle assertions.
4. Authoritative evidence containing both replacement directions is contradictory and must not be accepted merely because one matching direction exists.
5. Exact version matching is not fail-closed for unknown lowercase lexical continuations such as `v2` or `experimental`.
6. Mutable archive identity loses ordered change direction when it compares unordered discriminator token sets, and structured organization can still contaminate lowercase/role-actor headlines.

## Independent reproduction

The baseline implementation was inspected through the public Coverage path and each reported mechanism was reproduced offline before changing production code.

- The handoff state machine reproduced an unprotected legacy transport after a released P3b reservation. The safe design is to delegate only the six mandatory Coverage passes while legacy resolution is pending, then call the already-existing P3a protected resolver directly for slot seven. This preserves its `reserved → request_started → response_saved → processed` journal semantics without modifying preserved P3a.
- Actor/model experiments reproduced positive identity for `DeepSeek launches R2 while OpenAI launches V4.1 Flash`, `DeepSeek's competitor launches V4.1 Flash`, and `DeepSeek confirms openai launches V4.1 Flash` under the old binder.
- Temporal experiments reproduced positive identity for `plans to launch`, `cancels launch`, `might launch`, and `In 2025 ... launched`.
- Replacement experiments reproduced acceptance when the authoritative page asserted both old→new and new→old.
- Version experiments reproduced acceptance of `V4.1 Flash v2` and `V4.1 Flash experimental` while confirming ordinary prose such as `V4.1 Flash for developers` must remain valid.
- Archive experiments showed unordered detail tokens cannot distinguish `32K → 64K` from `64K → 32K`; ordered discriminator sequences can. Lowercase/role foreign-headline contamination was also reproduced.

## Decision

The active path is hardened by new layers rather than mutating preserved compatibility evidence:

- `weak_source_exact_binding_v3.py` keeps the existing durable P3b request-contract generation but tightens exact-event proof. It requires the signal organization, lifecycle action and every model/version anchor to form one attributable relation; unknown adjacent version continuations fail closed; modal/planned/cancelled and explicit-year historical actions fail closed; and any active reverse replacement relation rejects the evidence.
- `ensure_story_coverage_p3b_v5.py` wraps preserved v4. Required legacy resolution is never allowed to spend slot seven through a compatibility path that can restore the historical resolver. The delegated scheduler is clamped to six while a required obligation may own slot seven, then the protected P3a resolver starts or resumes the legacy durable journal directly. A started P3b/foreign/invalid journal remains fail-closed and cannot be stolen by legacy resolution.
- v5 archive matching preserves exact-URL duplicate proof, but mutable semantic proof now compares ordered event-detail discriminator sequences. Structured archive organization is accepted only as context for the same story row and cannot reassign lowercase or role-attributed foreign actors.
- `ensure_story_coverage_p3a.py` is intentionally unchanged.

## Final durable-handoff integration correction

A later exact-path regression exposed one integration gap in the first v5 handoff implementation.

Hypothesis: calling `_P3A._run_resolution()` directly after delegated `_P3A.execute_audit_plan()` may lose the publication identity that selects P3a's durable resolver, because the normal P3a execute wrapper stores the date in `_CURRENT_PUBLICATION_DATE` only for the duration of that call and resets the ContextVar on return. The resulting plan is not required to retain `publication_date`, so the subsequent direct resolver can incorrectly treat the call as undated and fall back to the historical `_PRE_RUN_RESOLUTION` path.

Result: the crash regression behaved exactly this way. Exact P3b reservation ownership and required-`unverified` priority were already correct, but the simulated process stop after transport admission was not raised because the direct handoff never entered P3a's durable journal transport. Once ownership was asserted independently, this became the sole remaining failing P3b regression.

Decision: v5 now sets P3a `_CURRENT_PUBLICATION_DATE` from the active `publication_date` only around `_P3A._run_resolution()` and resets the token in `finally`. The change does not alter P3a, queries, provider routing, capacity or binder/Freshness semantics. It only preserves the context that P3a's own durable resolver expects. On code head `654eada715382789982b2d847e98c0846e5b6a11`, PR Gate #368 completed 803/803 tests successfully, including the crash-after-`request_started` recovery regression and required-priority regression.

## Permanent regression controls

`automation/tests/test_p3b_astra_second_review.py` covers:

1. public runtime ownership (`v5` + binder v3 implementation with preserved contract `VERSION=2`);
2. real six-pass P3b→required-legacy handoff, simulated transport stop after durable `request_started`, and recovery with no provider retry/eighth search;
3. all three actor/action/model counterexamples plus a positive current control through authoritative-page binding and deterministic Freshness;
4. all four planned/cancelled/modal/historical counterexamples;
5. contradictory replacement directions in one sentence and semicolon-separated claims;
6. lowercase `v2`/`experimental` version continuations plus normal prose control;
7. mutable archive `32K→64K` versus `64K→32K` direction;
8. lowercase and role-actor structured-archive contamination.

The pre-existing original Astra regression suite, 20-case canonical matrix, import-order isolation, recovery ownership tests, archive controls, lifecycle/suffix controls and whole-project CI remain required. Any final handoff must cite a new exact SHA and green exact-head PR Gate; the `e114...` handoff is permanently invalidated by these code commits.
