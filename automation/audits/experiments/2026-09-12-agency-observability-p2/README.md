# P2: Agency rescue observability before routing changes

Date: 2026-09-12  
Scope: diagnostics-only retrieval instrumentation  
Production API / paid Web Search / workflow dispatch during implementation: **not used**

## Why P2 exists

The Sep 11 Astra follow-up showed that an Agency Rescue report ending in
`completed_no_addition` did not identify which boundary produced the zero. The
same surface state could represent a transport/response defect, missing provider
source metadata, an explicit empty source list, model-side rejection, direct-host
rejection, schema/window validation, dedupe/cap, or a genuinely empty result.

Historical saved reports therefore do **not** prove that Reuters provider routing
was broken and also do not prove a healthy provider zero. P2 is intentionally an
observability repair before any query/routing experiment.

## Preserved request and budget contract

Active Agency discovery remains one global Reuters-only publisher route:

- query: `latest AI models research chips infrastructure financing earnings business deals policy security`;
- `allowed_domains=["reuters.com"]`;
- search context: `high`;
- exactly one Web Search operation maximum;
- `max_tool_calls=4` (one search plus the existing navigation allowance);
- include `web_search_call.action.sources`;
- reasoning effort `medium`;
- maximum output tokens `5000`;
- SDK client retry setting remains `max_retries=2`;
- pipeline ceilings remain 24 ordinary / 25 only on the existing Hybrid double-regional-gap path.

P2 adds no second Agency slot, no retry entitlement, no provider/domain expansion,
no publisher quota, no ranking change, and no Freshness exception.

## Versioning and compatibility

The exact pre-P2 v5 implementation is preserved as
`automation/scripts/agency_discovery_rescue_v5_base.py`. Its blob SHA is
`a04b7ade1ac20bb61beaf963bb36bf74daf1a74d`, identical to the former active v5
blob on the P2 base commit.

`agency_discovery_rescue_v6.py` is the active additive observability layer.
`agency_discovery_rescue_v5.py` remains the stable compatibility import surface
used by Hybrid and same-day recovery, and forwards active behavior to v6 while
retaining the private `_persist_report` recovery hook. The shim is temporary and
may be collapsed only after Hybrid, recovery, monkeypatch/source-inspection tests,
and saved-artifact compatibility no longer depend on the v5 path; review no
earlier than 2026-10-12.

## Diagnostic axes

P2 persists and reports the following independently rather than inferring one
from another:

1. **Request contract**: model, exact query, tool/filter contract, limits and
   hashes of the prompt/schema. The API key and full prompt are not persisted.
2. **Transport state**: request prepared/started, response saved, or transport
   error.
3. **Response parse/schema state**: valid parsed response versus response error.
4. **Provider source metadata** for each search action:
   `missing | null | empty | nonempty | malformed | mixed | unknown`.
5. **Model output**: raw candidate count and model rejection count.
6. **Post-model route checks**: direct Reuters host rejection, existing-event
   duplicate and archive exact-URL duplicate.
7. **Merge validation**: schema/window rejection, cap rejection and an explicitly
   named `post_validation_count`.
8. **Final outcome**: accepted/addition counts and saved lifecycle state.

The historical `validated_count` field is preserved unchanged for compatibility.
It actually means candidates that survived the pre-merge Agency route checks.
P2 therefore publishes the clearer alias `pre_merge_eligible_count` and a separate
`post_validation_count` instead of silently changing the old field's meaning.

Unknown stays unknown. In particular, missing source metadata is not converted to
an empty source list, and absence of an observed search action is not converted to
zero.

## Bounded redacted transport capture

For the default production runner, v6 writes
`agency-discovery-rescue-transport.json` into the dated artifact and a dated copy
under `preview/production-daily/`.

Before transport it persists a redacted request contract. After a response is
returned, it serializes through the repository's existing diagnostic sanitizer and
persists the bounded raw response **before JSON parsing**. Normal captures are
limited to 256 KiB; larger responses retain the full-response hash/size plus a
bounded diagnostic projection. URL query credentials recognized by the existing
sanitizer are removed. API credentials are never part of the capture.

This capture is diagnostic evidence, not a replay authorization journal. P2 does
not weaken the existing at-most-once lifecycle: `search_started` without a saved
search result remains indeterminate and cannot automatically search again.
`search_completed`/`merge_failed` continue to consume the saved response offline.
Missing P2 capture on legacy or injected-test paths is reported as unobserved and
never authorizes another operation.

## Whole-project dependency audit

The P2 change was traced across:

`Primary major_agencies → post-filter agency-health trigger → active Agency rescue → saved Agency report → Hybrid → same-day recovery entry → Discovery Health / final diagnostics`.

Observed invariants:

- Primary's 12 mandatory searches are unchanged.
- The zero-paid agency-health bridge still decides whether the existing single
  Agency slot is available.
- Hybrid imports the same stable `agency_discovery_rescue_v5` module path; that
  path now forwards to v6 without changing Hybrid search allocation.
- Same-day recovery still calls the same stable module path and private report
  persistence hook. Completed/started states retain their old at-most-once rules.
- Coverage receives no new Agency operation and its seven-slot ceiling is unchanged.
- Source/Event Freshness and editorial ranking are untouched.
- Discovery Health may consume richer saved diagnostics later, but P2 itself does
  not alter health or publication policy.
- No workflow/config/provider-routing/search-budget file is changed by P2.

## Controlled evidence and regression matrix

Fixture:
`automation/fixtures/recall/agency-observability-2026-09-11.json`.

It preserves the Sep6-Sep11 availability/state matrix from the Astra handoff and
the offline wire-probe distinction between a missing `sources` field, explicit
`null`, explicit empty list and nonempty list. Sep8 remains `missing_committed_report`;
Sep9 remains `diagnostics_missing`. Neither is rewritten into an executed zero.

New offline tests cover:

- exact v5 preservation and the active compatibility shim;
- unchanged query/tool/filter/limit request contract;
- all source-metadata states;
- raw response persistence before malformed-JSON parsing failure;
- credential non-persistence;
- successful zero-candidate response with explicit empty source metadata;
- host/schema/window/dedupe/archive/cap diagnostic separation;
- completed rescue reuse without a second injected wire call.

The existing Agency, recovery, health, Hybrid and global repository suites remain
the regression authority for behavior outside the new fields.

## Search-change validation interpretation

P2 does not change retrieval policy, query text, routing, slot allocation or
provider parameters. Therefore the treatment is compared against the production
baseline for **request-contract identity, budget identity, lifecycle/recovery
identity and diagnostic truthfulness**, not for retrieval uplift. The fixture and
strict fake transports exercise missing/empty/nonempty metadata, parse failure,
validation/rejection and replay intersections without spending a search.

A future query/routing change is a separate search architecture change. It must
use equal-budget production-equivalent evidence across the historical problem
shape, retain negative results and costs, and pass the canonical search-change
validation matrix. P2 does not pre-authorize that experiment.

## What P2 does not prove

P2 does not determine why Reuters returned no addition on Sep6, Sep7, Sep10 or
Sep11. Historical source metadata was unavailable on those saved reports, and
there is no committed Sep8 report. The instrumentation only makes future runs
capable of distinguishing the relevant boundaries.

Accordingly, no claim is made that the current Reuters route is optimal or
broken. Query/routing repair remains deferred until an eligible fixed-budget A/B
provides evidence without spending the owner's production API budget absent
separate permission.

## Acceptance gate

P2 is ready for merge only after all of these are true on the exact final head:

1. P2 positive/negative offline tests pass;
2. existing Agency discovery/recovery/health tests pass;
3. full Main CI and configured validators pass;
4. final diff proves zero request/routing/search-budget/Freshness/ranking changes;
5. root/automation README and canonical architecture describe active v6
   observability and preserved v5 compatibility;
6. Required PR Gate succeeds.

This PR is diagnostics-only. It must remain separate from P3 weak-source signal
retention and from any future Agency query/routing experiment.
