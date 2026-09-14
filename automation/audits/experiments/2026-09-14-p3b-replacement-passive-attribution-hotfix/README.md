# P3b replacement passive-attribution hotfix

Date: 2026-09-14

Baseline production `main`: `33a94a0ee28464ef622667f733158c2e56a5f788`.

## Incident

Independent post-merge review found one remaining F2 / exact-event-identity counterexample in active `weak_source_exact_binding_v4.py`:

```text
DeepSeek says V4 Pro was replaced by V4.1 Flash by OpenAI
```

The full directed replacement span ended at `V4.1 Flash`. Historical v3 organization/action binding accepted `DeepSeek` from the reporting prefix, while v4 passive attribution hardening only covered launch/update actions. The explicit trailing `by OpenAI` therefore did not veto the replacement claim.

This is merge-blocking because a fresh authoritative page could otherwise pass page identity, deterministic freshness and archive checks with the event attributed to the wrong organization.

## Hypothesis

For replacement lifecycle only, inspect attribution beginning **after the complete directed replacement span**. A trailing `by <agent>` is a separate event-agent assertion. It must match the signal organization or the claim fails closed with `organization_event_attribution_mismatch`.

The guard must not treat the internal replacement grammar `old was replaced by new` as passive-agent attribution.

Because this changes semantic positive proof, binder evidence must advance independently of the durable request contract:

- durable request `VERSION` remains `2`;
- active binder stays `weak_source_exact_binding_v4.py`;
- `EVIDENCE_VERSION` advances `2 -> 3`;
- positive evidence-v1/v2 processed snapshots become stale and cannot be reused;
- stale processed evidence cannot authorize a new paid search or mutable-page refetch.

## Independent zero-paid experiment

Assistant-side controlled replay compared the current rule and proposed trailing-agent rule on the same replacement identity (`DeepSeek`, old `V4 Pro`, new `V4.1 Flash`). No production API, Web Search or owner budget was used.

Terra was not used because this treatment does not change query wording, search provider, routing, ranking or retrieval count. The experiment is deterministic event-identity parsing only.

| Case | Surface | Baseline | Proposed / expected |
|---|---|---|---|
| foreign passive agent | `DeepSeek says V4 Pro was replaced by V4.1 Flash by OpenAI` | positive | reject |
| foreign active-tail attribution | `DeepSeek replaces V4 Pro with V4.1 Flash by OpenAI` | positive | reject |
| lowercase foreign agent | `DeepSeek says V4 Pro was replaced by V4.1 Flash by openai` | positive | reject |
| comma-separated foreign agent | `DeepSeek says V4 Pro was replaced by V4.1 Flash, by OpenAI` | positive | reject |
| ordinary active replacement | `DeepSeek replaces V4 Pro with V4.1 Flash` | positive | positive |
| reporting without explicit foreign agent | `DeepSeek says V4 Pro was replaced by V4.1 Flash` | positive | positive |
| explicit signal organization agent | `V4 Pro was replaced by V4.1 Flash by DeepSeek` | positive | positive |
| direction control | reverse replacement | reject | reject |

Result: the proposed guard changes only the known false-positive attribution class in the controlled set and preserves positive/directional controls.

## Implementation

`automation/scripts/weak_source_exact_binding_v4.py`:

- adds `_TRAILING_REPLACEMENT_AGENT_RE`;
- extends `_passive_attribution_reason()` only for `replace`;
- obtains semantic old/new roles using the preserved replacement-role contract;
- inspects only text after each complete `_directed_replace_spans()` span;
- rejects a trailing `by` agent that is not the signal organization;
- advances semantic `EVIDENCE_VERSION` to `3` while retaining durable `VERSION=2`.

Permanent regression:

`automation/tests/test_p3b_replacement_passive_attribution_hotfix.py`.

Canonical search-change matrix now includes `O8`; the P3b 20-case count remains unchanged while its remediation controls explicitly cover this incident and evidence-v2 migration.

## Architecture-wide audit

The change is intentionally local to post-retrieval P3b exact-event identity.

Unchanged invariants:

- Primary maximum: 12 searches;
- Agency Rescue maximum: 1 search;
- Hybrid normal maximum: 4, double-regional-gap maximum: 5;
- Coverage maximum: 7 total, six mandatory plus the existing optional seventh slot;
- whole-pipeline ceilings: 24 normally / 25 only on the approved double-gap path;
- no eighth Coverage search;
- P3b->legacy atomic slot handoff and at-most-once recovery;
- Event Freshness and Source Freshness contracts;
- archive/dedupe logic and replacement direction;
- candidate ranking/editorial policy;
- query text, routing, provider/model and search allocation;
- preserved P3a bytes and historical compatibility modules.

The semantic evidence-version bump is required specifically so saved positive proof produced before the attribution hardening cannot bypass the new rule during `processed` recovery.

## Acceptance

Before merge the exact final PR head must have:

1. the new hotfix regression green;
2. full Main CI / PR Gate green;
3. unchanged search-budget and recovery contracts;
4. preserved P3a blob;
5. final diff/architecture audit on the exact head SHA;
6. the repository-required independent final review for that exact head.
