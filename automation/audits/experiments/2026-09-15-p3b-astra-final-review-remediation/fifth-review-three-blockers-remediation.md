# Astra fifth-review three-blocker remediation

Date: 2026-09-15
PR: #183
Reviewed exact head: `1d54a1556952c82ea13636515ef5bbdc26837210`
Independent verdict: `REQUEST CHANGES`

## Scope

This remediation addresses only the three reproducible exact-binding findings returned by the independent Astra review after Gate #456. Search query wording, provider/model routing, P3a, Primary, Source Pulse, Agency Rescue, Hybrid allocation, Freshness policy, editorial ranking and publication policy remain outside the semantic change.

Durable P3b request identity remains `VERSION=2`. Because the reviewed false positives could have been persisted as positive evidence-v4 `processed` snapshots, current semantic proof is intentionally bumped to `EVIDENCE_VERSION=5`; evidence-v1/v2/v3/v4 positive snapshots are stale under the corrected runtime.

## Finding 1: unrelated old year masked a current cancellation

Counterexample:

```text
DeepSeek launches V4.1 Flash |
DeepSeek V4.1 Flash launch cancelled today due to a 2025 incident
```

The previous v4 `_historical_reason` treated the presence of an old year as enough to classify the whole lifecycle claim as historical. That allowed the current cancellation to disappear from the contradiction set.

The remediation makes historical classification relation-aware around the retained lifecycle span. Current action-state contradiction is evaluated before historical background. A past marker is treated as lifecycle history only when it is bound to that action; causal/background bridges such as `due to ... incident` cannot reclassify a current cancellation as historical.

Expected result: direct binder returns non-positive `lifecycle_noncurrent`; active Coverage admission produces zero candidates and does not become `bound_candidate`.

## Finding 2: quote/curly wrappers hid foreign trailing attribution

Counterexamples:

```text
DeepSeek says V4 Pro was replaced by V4.1 Flash {by OpenAI}
DeepSeek says V4 Pro was replaced by V4.1 Flash "by OpenAI"
DeepSeek says V4 Pro was replaced by V4.1 Flash ({by OpenAI})
```

The trailing replacement-agent grammar now accepts a bounded sequence of the existing separators plus opening round/square/curly/quote wrappers before the separate `by`. The captured agent still uses the complete surface and exact normalized organization equality.

Positive controls with the same wrappers and `by DeepSeek` remain positive.

Expected result: foreign wrapped attribution returns `organization_event_attribution_mismatch`; no candidate or positive processed proof is admitted.

## Finding 3: historical passive launch vetoed a valid current claim

Counterexample:

```text
DeepSeek launches V4.1 Flash |
DeepSeek says V4.1 Flash was launched by OpenAI on September 1, 2025
```

The inherited lifecycle matcher could emit foreign-agent attribution mismatch before the full historical date was classified. The remediation classifies relation-bound historical lifecycle evidence before inherited passive attribution checks. Historical background therefore cannot veto a separate clean current exact-event claim, while historical-only text remains non-positive.

Expected result: combined current + historical surface remains `exact_event_identity`; historical-only surface returns `historical_event_context`.

## Regression-first evidence

Permanent tests were added first in:

`automation/tests/test_p3b_astra_fifth_review.py`

Test-only commit:

`c66862290eea325f6a23f7cecde96d937028cc54`

PR Gate #457 / run `34971074662` failed in unit tests while compile succeeded, reproducing the three findings against the reviewed runtime before the production fix.

## Remediation iterations

Initial runtime remediation:

`b12d1ec53577bb2d30b795d70f6f4d66fb2d3c48`

PR Gate #458 / run `34971578187` showed all three new fifth-review regressions passing. It also exposed two collateral historical controls that had become too permissive, plus expected stale assertions still pinned to evidence-v4.

Collateral historical repair:

`721d1450da494bc27eda9c3d43dd63894a1f45f3`

PR Gate #459 / run `34971959924` restored the older action-bound historical controls and kept all three new Astra regressions green. The remaining failures on that head were only assertions/documentation that still expected `EVIDENCE_VERSION=4` while runtime correctly emitted 5.

The branch then synchronized permanent version contracts and canonical documentation to evidence-v5. A final full PR Gate must be green on the exact unchanged head before this remediation is returned for another independent Astra review.

## Preserved invariants

- active Coverage runtime remains P3b v6;
- active semantic binder remains `weak_source_exact_binding_v4.py`;
- durable request contract remains `VERSION=2`;
- current semantic proof is `EVIDENCE_VERSION=5`;
- positive processed evidence-v1/evidence-v2/evidence-v3/evidence-v4 is stale;
- P3a production blob remains `14f0e38f57b9285a949ec5083136999c12c81bc0`;
- canonical P3b matrix remains exactly 20 numbered cases; fifth-review counterexamples are supplemental controls;
- Coverage remains six mandatory searches plus the existing optional seventh, maximum 7;
- no eighth Coverage search;
- Primary maximum remains 12;
- Agency Rescue maximum remains 1;
- Hybrid remains maximum 4 normally / 5 only for the approved double-regional-gap path;
- whole-pipeline ceilings remain 24 normally / 25 on the approved conditional path.

No production API, paid Web Search or Terra call was used. This remediation is deterministic parser/lifecycle/recovery validation only.

## Final exact-head verification protocol

The literal final Git SHA and final PR Gate run are intentionally pinned in PR #183 metadata only after the exact head is green. They are not self-embedded into this tracked file after the gate: committing a post-gate SHA/run back into the audit would create a new Git head and invalidate that same exact-head proof. The final handoff therefore requires all three pieces to agree without any later Git commit: this durable remediation record, the frozen PR head, and the green PR Gate/run recorded in the PR body.

The final verification must establish all of the following on that frozen head: full offline unit suite green; compile and editorial/archive/workflow/RSS/sitemap/structured-data validators green; protected-path cleanliness green; Required PR Gate green; P3a blob unchanged; canonical matrix exactly 20; `VERSION=2`; `EVIDENCE_VERSION=5`; positive v1-v4 stale; Coverage ceiling 7 with no eighth search; whole-pipeline ceilings 24/25; and PR still open with `merged=false`.

## Merge boundary

**DO NOT MERGE.** The exact final head must first pass the complete PR Gate and then receive a fresh independent Astra final review. This audit records remediation evidence, not independent approval. Regression tests named `astra` are executable controls, not reviewer approval.
