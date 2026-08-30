# 2026-08-30 source-health targetability incident replay

## Scope

This is an offline incident replay for Daily production run `33285232043`, job
`99187187727`, at commit `a66468f09f4e9f274009b0f98f70b1607e9bf112`.
The saved Actions artifact is `9724285083`, `daily-production-2026-08-30`, with
GitHub artifact digest
`sha256:8964ddb6fd65661a3e50e3f831bb4857114b88fb8c7143f9ba972e7037125dcd`.
No production API, OpenAI Web Search or Terra call was made for this replay.

Editorial/search window:

```text
2026-08-28T05:16:40+03:00 -> 2026-08-30T04:15:21+03:00
```

## Observed failure

Full research and the first editorial completed. The saved candidate pool had
three non-excluded candidates, while the initial short digest already had two
publishable stories. Coverage then completed all six mandatory directions:

```text
security_world
security_russia
security_asia
legal_copyright_scraping
curiosity
general_coverage_gaps
```

The Coverage budget was still healthy: six completed search operations out of a
maximum of seven, one operation remaining, no provider overrun and no incomplete
mandatory direction.

The usable candidate classes were:

- `legal` / `lawsuit filed` / TechCrunch / include;
- `coding` / `product release / developer-tool update` / Havoptic / include;
- `coding` / `product release / developer-tool update` / Havoptic / consider.

A Bloomberg model-release candidate existed in the saved research but had
`recommendation=exclude`, so it could not satisfy fresh-agency source health.

The source-health predicate therefore reported a real gap: the current usable
pool contained no fresh Reuters/AP/Bloomberg/FT primary source. The independent
agency-corroboration selector, however, intentionally targets only event families
where agency last-mile corroboration is useful: funding, M&A, investment,
data-center/infrastructure/chips and partnership. None of the three usable
production candidates belonged to those families.

The old contract nevertheless treated the gap as an unconditional requirement,
entered `_run_agency_rescue()`, found no target and converted an otherwise
complete Coverage audit into:

```text
source_health_rescue_needed = true
agency_rescue.status = error
agency_rescue.error = no suitable corroboration target in current pool
audit_status = partial
search_budget.stop_reason = agency_corroboration_target_missing
```

Publication, image generation and deploy then stopped fail-closed.

## Root cause

The trigger domain was wider than the selector domain:

```text
fresh-agency source absent
        !=
agency corroboration applicable
```

A missing agency primary is evidence about source diversity, not proof that the
current pool contains an event for which the bounded agency corroboration policy
is defined. The old orchestration failed to test targetability before making the
seventh operation mandatory.

## Offline reproduction

The saved `2026-08-30/candidates.json` was replayed locally on assistant-owned
resources. Applying the production selector rules produced zero targetable rows:

```text
cand-001 -> family=lawsuit_filed -> no agency target priority
cand-003 -> family=product_release_developer_tool_update -> no agency target priority
cand-004 -> family=product_release_developer_tool_update -> no agency target priority
```

This is deterministic post-retrieval behavior. Terra/provider ranking is not
involved, so no Terra experiment or paid search was necessary.

## Fix contract

The active Coverage v8 layer now distinguishes:

1. `source_health_gap_detected`: usable pool exists and has no fresh direct
   Reuters/AP/Bloomberg/FT primary source;
2. `source_health_rescue_applicable`: the existing selector can identify a
   permitted target event;
3. `agency_rescue_needed`: both conditions are true.

If the source-health gap is real but the selector has no permitted target, the
seventh operation is `not_applicable`, not an error. The six completed mandatory
Coverage directions remain authoritative, no new search is run, and publication
is not blocked solely because a deliberately narrow rescue has nothing to act
on.

The selector itself is unchanged. If a targetable funding/M&A/investment/
infrastructure/chips/partnership event exists, the existing bounded one-search
agency rescue remains required. Transport/API ambiguity or failure on that
applicable path remains fail-closed.

Source-health contract version advances from 7 to 8 so recovery cannot confuse
old completion semantics with the corrected applicability contract.

## Regression and neighboring cases

`automation/tests/test_aug30_source_health_targetability.py` protects:

- the exact production-shaped legal/coding/no-target case: six mandatory passes
  remain complete, the seventh paid operation is not called, and the stop reason
  is `agency_rescue_not_applicable`;
- a targetable funding row still produces an agency corroboration target;
- finalized diagnostics preserve the source-health gap while recording
  `source_health_rescue_applicable=false` and `source_health_rescue_needed=false`;
- source-health contract version is advanced and synchronized with the policy
  module.

Existing agency corroboration tests continue to protect target ranking,
same-event matching, fresh-agency promotion and cutoff behavior.

## Architecture-wide non-regression audit

- Primary Recall remains exactly 12 search operations.
- Conditional pre-Hybrid agency discovery rescue remains at most one search and
  is not modified by this change.
- Source Pulse v1.3 remains 0 OpenAI / 0 Web Search and same-day recovery does not
  repoll mutable sources.
- P1 Event Freshness and fail-closed Source Freshness are unchanged.
- P3 provider/query routing is unchanged.
- P4 regional-health viability and Hybrid 4/5 allocation are unchanged.
- Coverage remains six mandatory directions and at most seven search operations.
- The ordinary whole-pipeline theoretical ceiling remains 24; the approved
  double-regional-gap ceiling remains 25.
- No regional or publisher publication quota is introduced.
- A genuinely applicable agency-rescue technical failure still blocks
  publication.
- Same-day recovery may reuse the six already completed Coverage operations from
  run `33285232043`; this fix does not require repeating them or fresh research.

Result: **PASS** for the deterministic incident class. The invalid state
`agency rescue required + no permitted corroboration target` is removed without
broadening the selector or increasing paid retrieval.
