# Final Astra review — four-blocker remediation

Date: 2026-09-15

## Reviewed head and verdict

Independent Astra reviewed PR #183 exact head:

`7b2fce57695b215399cc68a817af9648d4c8179b`

and returned `REQUEST CHANGES` with four reproducible blockers. This record describes the implementation response. It is not an independent approval and does not authorize merge.

A regression-first head was created before production fixes. PR Gate #444 / run `34964244576` on test-only head `8b9176505e8562cb16dfa222268df4b9c5bcc54a` failed in `Main CI / Offline production checks` at `Run unit tests`, while compile succeeded. That provides durable evidence that the new controls reproduced defects against the old runtime.

No production API, paid Web Search, or Terra call was used. The defects are deterministic parser/recovery semantics and do not require external retrieval.

## Blocker 1 — stale candidate survives request-context drift

### Reproduction

A real six-mandatory + consumed optional seventh plan is persisted as a positive processed P3b snapshot under an obsolete binder evidence version. Recovery then receives an otherwise unrelated archive addition, changing the current request hash.

The preserved v2 layer can return early/deferred on this request-identity mismatch before `_run_p3b_binding_v4` executes. On the reviewed head this meant the stale candidate stayed in the returned plan even though the durable processed proof was obsolete. Ordinary search, protected search and authoritative-page fetch all remained zero, so the failure was purely local recovery semantics.

### Fix

Active v6 now treats stale semantic-proof revocation as a postcondition independent of current request-hash compatibility:

- the durable processed snapshot is inspected before preserved orchestration;
- stale signal identity is recovered from the processed diagnostic or exact admitted candidate provenance;
- after preserved orchestration returns, stale migration is applied to every returned plan even when model/archive/request context drift caused an earlier defer;
- candidate cleanup remains narrow: `audit_direction=weak_source_exact_binding`, exact P3b binding version, non-empty authoritative-page proof and the exact stale `resolution_signal_id` are all required;
- unrelated Coverage candidates and other-signal P3b candidates remain untouched;
- diagnostic becomes `unresolved` / `unresolved_deferred`;
- the already-consumed optional slot remains consumed;
- no new search, provider retry or page refetch occurs.

Permanent regression: `test_stale_evidence_cleanup_survives_archive_request_hash_drift` in `automation/tests/test_p3b_stale_candidate_revocation.py`.

## Blocker 2 — nested/mixed separators hide foreign trailing agent

Reviewed counterexamples include:

```text
DeepSeek says V4 Pro was replaced by V4.1 Flash ((by OpenAI))
DeepSeek says V4 Pro was replaced by V4.1 Flash: — by OpenAI
```

The old trailing-agent regex accepted only one punctuation separator and at most one opening wrapper. The current replacement parser now accepts a bounded sequence of the already-supported punctuation/open-wrapper tokens before `by`, after the complete directed replacement span. The internal `old was replaced by new` relation is still not confused with separate attribution.

Both counterexamples must fail as `organization_event_attribution_mismatch` at direct binder and active admission levels with zero returned candidates.

## Blocker 3 — comma list truncates passive agent identity

Reviewed counterexamples include:

```text
DeepSeek says V4 Pro was replaced by V4.1 Flash by DeepSeek, OpenAI and Anthropic
V4.1 Flash was launched by DeepSeek, OpenAI and Anthropic
```

The old capture stopped at the first comma, so exact identity comparison saw only `DeepSeek`. Replacement and passive launch/update parsing now retain the complete agent surface through commas until a claim terminator (`.`, `;`, or `|`). Full normalized equality therefore sees the multi-agent surface and rejects it.

Existing clean exact-agent and lowercase controls remain positive.

## Blocker 4 — historical foreign attribution vetoes current event

Reviewed surface:

```text
DeepSeek replaces V4 Pro with V4.1 Flash.
DeepSeek says V4 Pro was replaced by V4.1 Flash by OpenAI on September 1, 2025.
```

On the reviewed head the second claim could pass current lifecycle matching, then `_strict_claim_reason` evaluated passive attribution before broad historical-year detection. `organization_event_attribution_mismatch` therefore entered the cross-claim veto set and rejected the otherwise valid current claim.

`_strict_claim_reason` now classifies historical/background context before passive-attribution contradiction. Historical-only proof remains non-positive, but historical background cannot veto a separate current exact-event claim solely because the old event names a foreign agent.

The permanent regression exercises both direct binder and active admission paths using the full-date form that escaped the prior `in 2025` control.

## Semantic evidence migration

Durable request identity remains:

`VERSION=2`

Current semantic positive proof is advanced to:

`EVIDENCE_VERSION=4`

This bump is required, not cosmetic. The reviewed head's evidence-v3 binder could persist positive processed snapshots produced by the newly proven nested-separator and comma-list false positives. Reusing those snapshots after changing runtime parsing would preserve invalid proof.

Therefore positive evidence-v1, evidence-v2 and evidence-v3 processed snapshots are stale under the new runtime and fail closed without new provider search or mutable-page refetch. Current evidence-v4 processed reuse remains allowed.

## Preserved invariants

The remediation does not change query wording, provider/model routing, Primary, Source Pulse, Agency Rescue, Hybrid allocation, Event Freshness, Source Freshness, archive/dedupe policy, editorial ranking, publication validators or P3a.

Search limits remain:

- Primary max 12;
- Agency Rescue max 1;
- Hybrid max 4 normally / 5 only approved double-regional-gap;
- Coverage max 7 = six mandatory + existing optional seventh;
- no eighth Coverage search;
- whole-pipeline ceiling 24 normal / 25 conditional double-gap.

`automation/scripts/ensure_story_coverage_p3a.py` must remain byte-identical with blob:

`14f0e38f57b9285a949ec5083136999c12c81bc0`

The canonical P3b matrix remains exactly 20 cases. These independent-review counterexamples remain supplemental remediation controls rather than creating case 21.

## Final acceptance still required

Before merge, the final exact unchanged head must have:

1. all four new regressions green;
2. relevant existing P3b/Astra/recovery suites green;
3. full `python -m unittest discover -s automation/tests -v` green;
4. Main CI / Offline production checks green;
5. Required PR Gate green;
6. P3a blob unchanged;
7. canonical matrix still exactly 20 cases;
8. `VERSION=2`, `EVIDENCE_VERSION=4` and ceilings 7/24/25 confirmed;
9. a new independent final review, preferably Astra, on the exact final SHA.

Do not merge PR #183 before that independent verdict.