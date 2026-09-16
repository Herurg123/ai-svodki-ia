# P3b ninth-review remediation: reporting time, semicolon attribution, historical veto

Date: 2026-09-16
PR: #183
Independently reviewed head: `66ca44c46f652ee09bfd2341351f19cb0c6da1cd`
Independent verdict on that head: `REQUEST CHANGES`

This record documents remediation scope and validation intent only. It is not a substitute for a fresh independent review of the final exact head.

## Independent findings remediated

### 1. Reporting-time full date could promote an old lifecycle event

Counterexample on the reviewed head:

`On September 15, 2026, according to DeepSeek, DeepSeek launched V4.1 Flash on September 1, 2025`

Neighboring reproductions used `citing`, `based on`, `referencing`, and `per`. The active v4 path inherited an attribution-break vocabulary that recognized forms such as `said`/`reported` but not these surfaces. A current reporting date could therefore be treated as relation-local current evidence and prevent the explicit old event date from classifying the lifecycle relation as historical.

Required result: `historical_event_context`, with no bound P3b candidate.

### 2. Natural semicolon could split away a foreign trailing replacement agent

Counterexample on the reviewed head:

`DeepSeek: [V4 Pro was replaced by V4.1 Flash]; by OpenAI`

The structural trailing-agent matcher itself accepted punctuation/wrappers, but inherited claim segmentation split at `;` first. `by OpenAI` became a separate claim without retained organization/product anchors, so the foreign agent disappeared from the candidate claim.

Required result: `organization_event_attribution_mismatch`, with no bound P3b candidate.

### 3. Historical negation could become a global current veto

Counterexample on the reviewed head:

`DeepSeek launches V4.1 Flash | On September 15, 2026, DeepSeek said it did not launch V4.1 Flash on September 1, 2025`

The relation was initially historical, but the veto path reclassified the same relation with a more permissive current-date rule. That turned historical negative background into `lifecycle_negated`, which globally vetoed the separate clean current-positive claim.

Required result for page event identity: `exact_event_identity`; ordinary Freshness/archive gates remain responsible for downstream admission.

## Runtime remediation

`automation/scripts/weak_source_exact_binding_v4.py` is changed only inside the active v4 binder compatibility surface.

- A v4-local reporting/attribution boundary extends the inherited vocabulary with `according to`, `citing`, `based on`, `referencing`, and `per`. Historical v2/v3 source files are not mutated.
- Event-time ownership and current-veto classification now reuse the same relation-local reporting boundary rather than recomputing a relation with a more permissive rule.
- A past full date before an action is treated as report/evidence metadata only when explicit current/non-past evidence precedes it and a reporting boundary connects that evidence to the old date without a new clause boundary. Otherwise the old date remains conservative historical evidence.
- A past full date after an action can be ignored as cited/report evidence only when the local relation already has explicit current evidence and the action-to-date bridge contains a reporting boundary. Without current evidence the old date remains historical rather than being promoted by ambiguity.
- The active claim splitter protects only the immediate natural `; by <agent>` surface before delegating to inherited segmentation. This keeps foreign trailing attribution visible while substantive words remain non-skippable.
- Historical negated/noncurrent background does not globally veto a separate clean current-positive exact claim. Genuine current contradiction/foreign attribution remains a veto.

Durable request identity and semantic evidence marker remain:

- `VERSION=2`
- `EVIDENCE_VERSION=6`

Evidence v6 is still confined to this open, unmerged PR. This remediation hardens the unreleased v6 semantics in place. Positive processed evidence v1-v5 remains stale relative to v6; no new provider search, retry, or mutable-page refetch is authorized.

## Permanent regressions

`automation/tests/test_p3b_astra_ninth_review.py` adds direct-binder and active-processor coverage for:

- reporting-time current date plus explicitly historical lifecycle date through `according to`, `citing`, `based on`, `referencing`, and `per`;
- the reciprocal safety case where old report/evidence dates must not hide a genuinely current negation;
- separate current-positive claim plus historical negative background through `said`, `reported`, `according to`, and `citing`;
- `; by OpenAI` after ASCII/Unicode/fullwidth/nested wrappers and whitespace variants;
- multi-agent foreign attribution;
- positive `; by DeepSeek` control;
- shared reporting-boundary vocabulary;
- unchanged `VERSION=2` / `EVIDENCE_VERSION=6`.

During CI, Gate #485 exposed an unrelated calendar-fragile seventh-review regression: it hard-coded `Today, on September 15, 2026` and was run on September 16. `automation/tests/test_p3b_astra_seventh_review.py` now derives the explicit current date from `date.today()`. This is test maintenance only; runtime semantics were not weakened to make an expired fixture pass.

## Retrieval validation matrix

Per repository instructions, `automation/specs/search-change-validation-matrix.md` is permanently enriched with:

- O9: natural-semicolon trailing-agent segmentation;
- O10: reporting-time versus event-time date ownership;
- O11: cross-claim historical contradiction isolation;
- corresponding critical combinations and a permanent 2026-09-16 incident note.

This does not expand the canonical P3b exact-authoritative-binding matrix. That matrix remains exactly 20 cases; Astra review counterexamples remain supplemental retrieval-safety regressions.

## Current-main synchronization boundary

While this remediation was being validated, `main` advanced from the PR's original base `28241c86e9ecd5491aa6113db510b3422a537154` to `fc395080c222bb728d46b74e4a486a661729e745` through the normal 2026-09-16 publication/retention commits. The base delta contains archive/content/posts publication material and old-content cleanup only; it does not modify P3b runtime, binder, tests, retrieval specs, query/provider routing, Freshness policy, recovery implementation, editorial implementation, or search-budget code.

Gate #488 on pre-sync remediation head `f88f41b579fcc458e6f814d003a64c63904c9169` was green, but GitHub correctly tested a merge ref against the advanced current `main`. Therefore its merge-ref tree was not byte-identical to the standalone feature-head tree. To remove that ambiguity before the next independent final review, the feature branch is synchronized with exact current-main SHA `fc395080c222bb728d46b74e4a486a661729e745` and a fresh Gate is required afterward.

The **semantic remediation delta itself** from the independently reviewed head is limited to five paths:

- `automation/scripts/weak_source_exact_binding_v4.py`
- `automation/tests/test_p3b_astra_ninth_review.py`
- `automation/tests/test_p3b_astra_seventh_review.py` (calendar-stable fixture only)
- `automation/specs/search-change-validation-matrix.md`
- this audit record

A raw git compare from the old reviewed SHA to the post-sync final head will additionally contain the intervening current-main publication/retention delta. That inherited base advancement is not part of the P3b remediation and must not be misrepresented as such. The PR diff against current `main` is the relevant scope check after synchronization.

## Preserved architecture and budgets

No change is intended or authorized outside exact P3b event-binding semantics and its validation evidence.

Preserved invariants:

- Active Coverage runtime remains P3b v6 using `weak_source_exact_binding_v4.py`.
- P3a production blob remains expected to stay `14f0e38f57b9285a949ec5083136999c12c81bc0` and is rechecked separately.
- Primary maximum remains 12.
- Agency Rescue maximum remains 1.
- Hybrid maximum remains 4 normally / 5 only on the approved double-regional-gap path.
- Coverage maximum remains 7: six mandatory plus the existing optional seventh.
- No eighth Coverage search is authorized.
- Whole-pipeline ceiling remains 24 normally / 25 conditional.
- `reserved -> request_started -> response_saved -> processed` durability semantics remain unchanged.
- `request_started` remains consumed/ambiguous and is not automatically retried.
- `response_saved` replay and compatible current-evidence reuse remain offline.
- stale v1-v5 positive proof revocation keeps unrelated durable candidates and does not refund optional search capacity.
- query generation, provider/model routing, ranking, candidate caps, Freshness policy, editorial policy, publication path, P3a runtime, and recovery I/O authorization are unchanged.

README, `automation/README.md`, `AGENTS.md`, and `automation/ARCHITECTURE.md` were rechecked. The high-level contract already requires relation-local fail-closed exact event identity, durable at-most-once recovery, and unchanged budgets; no new operator-facing workflow or repository rule is introduced by this remediation, so no further documentation edit is required beyond the retrieval validation matrix and this audit record.

## Validation boundary and spend

The remediation uses deterministic/offline tests and GitHub CI only.

- production API calls: 0
- paid Web Search calls: 0
- Terra calls: 0

A local `git clone` was not relied upon because DNS resolution in the sandbox was unavailable. Exact source, Git objects, compare state, PR state, and CI are obtained through the GitHub connector; semantic branches are additionally exercised through deterministic offline regressions.

## Final-review requirement

A new exact final head and successful PR Gate must be pinned only after all remediation, matrix, test-maintenance, audit, and current-main synchronization commits are present. The remediation author must not self-approve that head.

Fresh independent Astra review must independently inspect the final PR diff against current `main` and the active runtime, distinguish inherited base-sync content from remediation, reproduce all three defect classes plus adjacent variants, re-check prior P3b remediation groups, verify evidence-v6 recovery semantics and all search budgets, and verify that final CI tested content-identical final head/merge-ref trees.

**DO NOT MERGE until that fresh independent review returns APPROVE on the exact final SHA.**