# Astra blocker #1: stale P3b candidate revocation

Date: 2026-09-15
PR: #179 (`hotfix/p3b-replacement-passive-attribution`)
Reviewed Astra head where the blocker was reported: `769a981b31a87efc1384f125b4e2a91dc5c4700d`

## Blocker

A positive P3b `processed` snapshot admitted under binder evidence version 2 could be recognized as semantically stale after the runtime moved to binder `EVIDENCE_VERSION=3`, while its already-admitted candidate remained in the recovered plan. The stale branch in `_run_p3b_binding_v4` changed the diagnostic to `unresolved` / `unresolved_deferred`, but `_annotation()` deep-copied the caller plan, including the candidate whose semantic proof had just been revoked. A downstream `story_coverage.merge_candidates` therefore still had an admissible object to merge.

This is an evidence-v2 -> evidence-v3 migration defect. It does not introduce a new binder rule and does not justify incrementing the evidence version.

## Baseline reproduction

A permanent regression was added first in `automation/tests/test_p3b_stale_candidate_revocation.py` at test-only commit `31bd8eda523316bbf0d04d2bc2624a6f15c17a64`.

The fixture builds a real six-pass Coverage plan, consumes the optional seventh slot, then persists a full processed snapshot containing:

- a stale, positively admitted P3b candidate with the actual admission provenance fields;
- an independent mandatory Coverage candidate;
- unrelated P3b-like marker data on another audit direction;
- a fully marked P3b candidate bound to a different signal;
- a positive P3b diagnostic with `binder_evidence_version=2`.

Recovery runs under the current binder evidence version 3. The test also uses the real `story_coverage.merge_candidates` as a downstream control: before recovery the stale candidate is structurally acceptable to merge, while after correct migration it must no longer be present.

The test-only Required PR Gate #433 was red before the runtime correction, providing a durable failing baseline rather than a post-hoc regression.

## Fix hypotheses and offline decision

Three implementation placements were considered deterministically, without provider calls:

1. revoke stale P3b provenance next to the stale processed-evidence migration in `_run_p3b_binding_v4`;
2. use a broad helper that removes any candidate carrying a P3b-like marker;
3. change generic `_annotation()` so it strips candidates during annotation.

Option 2 was rejected because it deletes unrelated P3b-like data and candidates for other signals. Option 3 was rejected because `_annotation()` is a shared compatibility primitive and would widen the blast radius to callers that are not performing evidence migration.

The selected design keeps cleanup local to the stale-evidence recovery path and requires the actual admitted provenance of the candidate being revoked:

- `audit_direction == "weak_source_exact_binding"`;
- `p3b_exact_binding_version == P3B_EXACT_BINDING_VERSION`;
- non-empty `p3b_authoritative_page_proof`;
- the active stale signal id is present in `resolution_signal_ids`.

The migration source is the durable journal `processed_snapshot`, not a transient scheduler plan. This preserves unrelated candidates that were already in the seven-pass processed result while revoking only the object admitted by the stale proof.

A pre-existing third-review regression used a marker-only synthetic candidate. The historical v2 admission code always stamped the provenance fields above, so that fixture was corrected to model an actually admitted candidate rather than weakening production cleanup to broad marker matching.

## Required controls

The regression suite asserts all of the following:

- stale evidence-v2 P3b candidate is revoked under current evidence-v3 runtime;
- independent Coverage candidate remains;
- unrelated P3b-like data remains;
- P3b candidate for a different signal remains;
- current evidence-v3 processed reuse does not trigger stale cleanup;
- diagnostic remains fail-closed: `status=unresolved`, `disposition=unresolved_deferred`;
- ordinary `run_audit_request` calls are zero;
- protected/paid retry calls are zero;
- authoritative page fetch calls are zero;
- the optional seventh slot remains consumed and `remaining_calls == 0`;
- downstream `story_coverage.merge_candidates` cannot re-admit the revoked stale candidate.

## Contract preservation

No search/routing/query semantics were changed, so Terra was not needed for this remediation. No production API or paid Web Search was used.

The existing contracts remain unchanged:

- durable P3b request contract: `VERSION=2`;
- active binder semantic evidence: `EVIDENCE_VERSION=3`;
- active runtime wrapper: v6;
- active exact binder: v4;
- Coverage ceiling: 7 searches total, with no eighth Coverage search;
- whole-pipeline ceiling: 24 normally, 25 only on the existing double-regional-gap path;
- optional seventh-slot ownership remains consumed after stale recovery;
- no page refetch is introduced for processed migration;
- P3a implementation is not changed by this remediation.

The canonical architecture and validation documents already state the fail-closed evidence-migration and search-ceiling contracts, so they require no semantic rewrite for this implementation-only cleanup.
