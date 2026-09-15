# Astra blocker #2 — separator attribution verification

Date: 2026-09-15

## Scope

This record closes the independent Astra blocker #2 originally reported against PR #179 head `769a981b31a87efc1384f125b4e2a91dc5c4700d`:

> Parentheses and colon bypass the foreign-agent check.

Required counterexamples:

```text
DeepSeek says V4 Pro was replaced by V4.1 Flash (by OpenAI)
DeepSeek says V4 Pro was replaced by V4.1 Flash: by OpenAI
```

The requested remediation scope is only the immediate trailing-attribution separator grammar after the complete directed replacement span. Blocker #3 identity semantics are not modified in this follow-up.

## Actual baseline after PR #179 merge

Before this follow-up branch was created, PR #179 had already been merged. The current `main` baseline is merge commit `f073b1c7a84eced7610969740a20305af765fab5`, containing PR #179 exact head `cb1074dcee296b9c9097ea49d050c8eb7b8da50e`.

Inspection of that exact baseline shows blocker #2 runtime remediation was already present in `automation/scripts/weak_source_exact_binding_v4.py`:

- replacement direction is resolved first with `_directed_replace_spans()`;
- `_TRAILING_REPLACEMENT_AGENT_RE` is applied only to the suffix after the complete directed replacement span;
- the bounded separator grammar accepts comma, colon, ASCII hyphen, en/em dash and an optional `(` / `[` wrapper before the trailing `by`;
- the captured agent is passed through the existing organization-attribution equality check;
- a foreign explicit trailing agent returns `organization_event_attribution_mismatch`.

The permanent regression file already exercised both Astra counterexamples at binder level and through the active candidate processing/admission path. PR Gate run `34935377333` (run number 438) succeeded on exact head `cb1074dcee296b9c9097ea49d050c8eb7b8da50e`, including the full Python unit suite.

Therefore no new runtime semantic change is required in this follow-up.

## Deterministic follow-up experiment

Hypothesis: the merged bounded parser also fails closed for neighboring separator wrappers that stay inside the same local claim, while ordinary punctuation without an attribution does not create a false foreign-agent rejection.

The permanent regression matrix is expanded with these same-claim negatives:

```text
DeepSeek says V4 Pro was replaced by V4.1 Flash, (by OpenAI)
DeepSeek says V4 Pro was replaced by V4.1 Flash - by OpenAI
DeepSeek says V4 Pro was replaced by V4.1 Flash – by OpenAI
```

Existing controls already cover:

```text
DeepSeek says V4 Pro was replaced by V4.1 Flash by OpenAI
DeepSeek says V4 Pro was replaced by V4.1 Flash by openai
DeepSeek says V4 Pro was replaced by V4.1 Flash, by OpenAI
DeepSeek says V4 Pro was replaced by V4.1 Flash: by OpenAI
DeepSeek says V4 Pro was replaced by V4.1 Flash (by OpenAI)
DeepSeek says V4 Pro was replaced by V4.1 Flash — by OpenAI
```

Positive controls are expanded with ordinary post-replacement punctuation:

```text
DeepSeek says V4 Pro was replaced by V4.1 Flash.
DeepSeek says V4 Pro was replaced by V4.1 Flash: availability starts today
```

Both binder-level identity and the active processing/admission helper are asserted for every added surface.

A semicolon form is intentionally not added to this local separator matrix. The inherited `_CLAIM_SPLIT_RE` splits `;` followed by whitespace into a separate claim, so `; by OpenAI` does not reach the same immediate trailing-attribution claim path. Changing cross-claim semantics would broaden this task beyond blocker #2.

## Contract decisions

- `VERSION=2` remains unchanged.
- `EVIDENCE_VERSION=3` remains unchanged because no new positive-proof semantics are introduced by this follow-up; the runtime behavior under test is already the merged evidence-v3 contract.
- No query wording, routing, ranking, provider, Freshness, archive/dedupe, replacement-direction, P3b→legacy handoff or search allocation changes are made.
- Coverage remains six mandatory operations plus the existing optional seventh P3b slot; no eighth Coverage search is introduced.
- Whole-pipeline ceilings remain 24 normally and 25 only on the approved double-regional-gap path.
- P3a is not modified and must retain blob `14f0e38f57b9285a949ec5083136999c12c81bc0`.
- Blocker #1 stale-candidate revocation behavior is unchanged.
- Blocker #3 semantics are not changed by this follow-up. Any behavior already present in the merged baseline is merely inherited, not remediated here.

Terra is not required because query/search behavior is unchanged. No production API or paid Web Search is used.

## Acceptance

Merge this follow-up only if the exact final head passes PR Gate / Main CI / Required PR Gate, the complete Python suite remains green, changed-file scope is limited to permanent regression evidence, and the P3a blob plus 7/24/25 search ceilings remain unchanged.
