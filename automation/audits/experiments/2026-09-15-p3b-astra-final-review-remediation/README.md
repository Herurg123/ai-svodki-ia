# P3b Astra final-review remediation — 2026-09-15

## Scope

This record covers remediation of the independent Astra `REQUEST CHANGES` verdict for PR #179 on exact head:

`769a981b31a87efc1384f125b4e2a91dc5c4700d`

The review found three merge blockers inside the already documented P3b exact-attribution / evidence-migration contract. No query wording, provider/model routing, search allocation, ranking, Freshness policy, archive implementation, editorial policy, publication path, or slot-handoff ownership contract is changed by this remediation.

Terra was not used because search/query semantics are unchanged. No production API or owner paid Web Search budget was used.

## Hypotheses

### H1 — stale processed proof can leak its candidate through `prior_plan`

Baseline mechanism: `ensure_story_coverage_p3b_v6._run_p3b_binding_v4()` calls v2 `_annotation(plan, ...)` for stale positive processed evidence. `_annotation()` deep-copies the complete plan, so a P3b candidate already present in a seven-pass `prior_plan` survives even though the diagnostic becomes `unresolved`.

Expected treatment: stale evidence consumes the optional slot and remains fail-closed, but every candidate whose eligibility depends on P3b proof must be removed before returning the unresolved plan. Non-P3b candidates must remain untouched. No ordinary search, protected retry, or authoritative-page refetch is allowed.

### H2 — punctuation can hide a foreign trailing replacement agent

Baseline counterexamples independently reproduced by Astra:

- `DeepSeek says V4 Pro was replaced by V4.1 Flash (by OpenAI)`
- `DeepSeek says V4 Pro was replaced by V4.1 Flash: by OpenAI`

The original replacement trailing-agent matcher allowed only whitespace and an optional comma before `by`.

Expected treatment: ordinary comma/colon/dash separators and parenthesized attribution after the complete directed replacement span are still attribution syntax and must fail closed for a foreign organization. Internal `old was replaced by new` grammar must remain valid.

### H3 — prefix matching can accept a foreign possessive agent

Baseline counterexample independently reproduced by Astra:

`DeepSeek says V4 Pro was replaced by V4.1 Flash by DeepSeek's rival OpenAI`

The original agent check used `re.match()` against the signal organization, so any agent phrase beginning with `DeepSeek` could pass.

Expected treatment: the complete captured agent identity must normalize exactly to the signal organization. Lowercase equality remains valid; possessive/role/foreign suffix contamination fails closed. The same exact-agent rule is also applied to existing launch/update passive attribution.

## Gate #428 findings during remediation

The first strengthened full-suite run deliberately failed in two places and exposed useful test/semantic detail rather than an unrelated regression.

1. The first migration fixture called preserved P3a with `maximum_web_search_calls=7`. That path may legitimately consume the existing legacy optional slot, so it produced seven transport calls before the synthetic P3b state was installed. This was a fixture error, not a runtime budget defect. The corrected fixture starts from the established real six-mandatory plan, then reconstructs the historical pre-P3b budget contract (`maximum_calls=7`, six consumed, one optional remaining) without running the legacy seventh-slot resolver. `_p3b_force_consumed()` then records the historical P3b slot as the seventh consumed operation.

2. The possessive foreign-agent end-to-end control exposed an additional same-identity cross-claim seam. The test page fixture places the surface in HTML metadata as well as body text; an apostrophe in `DeepSeek's` can produce a second clean-looking local claim beside the full foreign-attributed claim. Binder-level matching rejected the foreign claim, but the clean duplicate could still make the complete page surface positive because attribution mismatch was not a cross-claim veto. This is a real fail-closed issue independent of the fixture shape: one exact-identity local claim attributing the event to a foreign actor must not be rescued by another clean-looking duplicate on the same authoritative surface.

Decision: `organization_event_attribution_mismatch` is now a same-identity cross-claim veto alongside the existing active lifecycle contradiction vetoes. Historical/background claims remain non-vetoing, preserving the existing current-event-plus-history positive contract.

## Implementation decision

1. `automation/scripts/weak_source_exact_binding_v4.py`
   - broaden only the post-directed-replacement separator grammar;
   - compare the complete normalized captured agent with the signal organization;
   - reuse that exact-agent check for existing launch/update passive attribution;
   - make `organization_event_attribution_mismatch` a cross-claim veto when another exact-identity claim looks positive;
   - keep durable request `VERSION=2` and semantic `EVIDENCE_VERSION=3` unchanged because evidence v3 has not yet been merged to production and this remediation completes the same pending v3 contract.

2. `automation/scripts/ensure_story_coverage_p3b_v6.py`
   - add `_without_stale_p3b_candidates()`;
   - on stale processed positive evidence, remove candidates carrying P3b admission markers before building the unresolved annotation;
   - keep slot consumption sealed and do not retry retrieval or refetch the authoritative page.

3. `automation/tests/test_p3b_replacement_passive_attribution_hotfix.py`
   - add comma/colon/parentheses/dash foreign-agent negatives;
   - add possessive-prefix foreign-agent negative;
   - add a same-identity positive-duplicate + foreign-attribution contradiction control;
   - preserve SignalOrg and ordinary replacement positive controls;
   - reconstruct six mandatory operations plus the existing optional seventh slot, consume that slot as historical P3b, and pass the complete seven-pass saved plan including the stale P3b candidate as `prior_plan`;
   - assert zero ordinary calls, zero protected retries, zero page refetches, zero surviving P3b candidates, unresolved diagnostic, and no optional capacity refund.

## Architecture / budget decision

The existing canonical contracts already state the desired semantics:

- search validation O8 requires foreign trailing replacement attribution to fail closed;
- the required critical combination requires an evidence-v2 positive snapshot to migrate to unresolved without paid retry or page refetch;
- Coverage remains six mandatory plus one optional seventh operation;
- the eighth Coverage search remains forbidden;
- whole-pipeline ceilings remain 24 normally and 25 only on the approved double-regional-gap path;
- P3b→legacy atomic handoff, Event/Source Freshness, archive/dedupe, Primary, Agency Rescue, Hybrid allocation, ranking/editorial policy, publication validation, and preserved P3a are not modified.

Because this remediation makes implementation satisfy already-written contracts rather than changing those contracts, no additional architecture prose or new canonical matrix case is required. The permanent executable regression is strengthened instead.

## Acceptance gate

Before merge:

1. full PR Gate must pass on the final exact head;
2. P3a byte preservation must be rechecked;
3. final diff must be re-audited for unchanged 7/24/25 search ceilings and unaffected handoff/Freshness/archive paths;
4. the previous Astra verdict is invalidated by these commits;
5. a new independent Astra review must return explicit `APPROVE` on the new exact head before merge.
