# P3b tenth-review remediation: underscore attribution and future-date boundary

Date: 2026-09-16

Reviewed head that produced the independent REQUEST CHANGES:

`3d96cd53107a117c2e89f8eecb34d0eaafacf2a6`

This record is evidence/history only. It is not correctness proof and does not replace a fresh independent review of the final remediation head.

## Independent findings

The independent review found two HIGH defects in the active P3b v6 binder path.

### 1. Underscore could hide a foreign trailing replacement agent

The trailing replacement matcher used `^\W*\bby ...`. Python classifies `_` as a word character, so direct surfaces such as:

- `DeepSeek: [V4 Pro was replaced by V4.1 Flash] _ by OpenAI`
- `DeepSeek: [V4 Pro was replaced by V4.1 Flash]_by OpenAI`

could bypass the separate trailing-agent comparison even though neighboring punctuation forms failed closed.

Required result: `organization_event_attribution_mismatch`, with no bound P3b candidate.

### 2. Valid future full dates were treated as current markers

The active date helpers accepted any valid full date `>= date.today()` as current/non-past evidence. That collapsed future event-time into current exact-event semantics. Examples include:

- `On <tomorrow>, DeepSeek launches V4.1 Flash`
- `DeepSeek launches V4.1 Flash on <tomorrow>`
- `On <tomorrow>, DeepSeek did not launch V4.1 Flash`

Future lifecycle assertions must not become current proof or current contradiction. Relation-bound future dates must fail closed as `lifecycle_noncurrent`.

## Remediation boundary

The remediation remains inside the already-unmerged evidence-v6 P3b binder contract.

### Runtime

`automation/scripts/weak_source_exact_binding_v4.py` now:

- treats `_` as a neutral direct trailing-attribution separator alongside punctuation/wrappers without allowing the matcher to jump over substantive words;
- keeps complete agent surfaces for exact organization comparison;
- limits explicit full-date current evidence to `value == date.today()`;
- no longer lets future full dates participate in current-prefix evidence used to distinguish reporting dates from historical event dates;
- adds a relation-local future-date classifier for valid full dates before or after the lifecycle action;
- respects reporting/attribution boundaries when deciding whether a future date belongs to the lifecycle relation;
- returns `lifecycle_noncurrent` before inherited active-lifecycle matching when a future date governs the relation;
- therefore keeps future negation/noncurrent assertions out of current contradiction semantics while preserving today and historical controls.

The compatibility helper name `_action_span_has_nonpast_full_date_prefix` is retained for import/test stability, but its semantics are now deliberately today-only. Future dates are handled by `_action_span_has_future_full_date`.

## Permanent regressions

`automation/tests/test_p3b_astra_tenth_review.py` covers:

- `] _ by OpenAI`;
- `]_by OpenAI`;
- Unicode/fullwidth/nested wrapper plus underscore variants;
- multi-agent foreign attribution;
- positive underscore `by DeepSeek` controls;
- proof that the matcher still does not jump substantive words;
- future full date before the action;
- future full date after the action;
- future negation classified as `lifecycle_noncurrent`;
- future reporting date plus historical event date;
- today and yesterday controls;
- invalid calendar date not becoming current/future evidence;
- unchanged `VERSION=2` / `EVIDENCE_VERSION=6`.

Direct binder assertions are paired with the active P3b processor for candidate-admission behavior where applicable.

## Search-change validation matrix

`automation/specs/search-change-validation-matrix.md` adds:

- **O12**: underscore trailing-attribution separator;
- **O13**: future event-time boundary;
- corresponding critical combinations and a permanent incident record.

These are supplemental retrieval-safety cases. They do not expand the canonical P3b exact-authoritative-binding matrix, which remains exactly 20 cases.

## Version and recovery rationale

No new evidence generation is introduced. Evidence-v6 has not been merged into production and this remediation hardens that same unmerged semantic contract, so:

- durable request `VERSION` remains **2**;
- semantic `EVIDENCE_VERSION` remains **6**;
- positive evidence v1-v5 remains stale relative to v6;
- stale recovery still authorizes zero new provider search/retry/mutable-page refetch;
- `request_started` remains consumed/ambiguous;
- `response_saved` replay remains offline;
- optional seventh Coverage capacity is not refunded.

## Budget and scope invariants

Unchanged:

- Primary maximum 12;
- Agency Rescue maximum 1;
- Hybrid maximum 4 normally / 5 only on the approved double-regional-gap path;
- Coverage maximum 7, with no eighth Coverage search;
- whole-pipeline ceiling 24 normally / 25 conditional;
- P3a remains evidence-only;
- P3a production blob expectation remains `14f0e38f57b9285a949ec5083136999c12c81bc0`;
- no query generation, provider choice, model routing, ranking, candidate caps, Freshness policy, editorial policy or publication policy is changed by this remediation.

## Independent-review requirement

A green CI run is necessary but not sufficient. A fresh reviewer must inspect the exact final SHA after this remediation, reproduce both defect classes and adjacent variants, re-check prior P3b blocker classes, verify active runtime/recovery/budget invariants, and confirm CI tested the final content-identical head/merge-ref tree before APPROVE.
