# Discovery Health v1 controlled replay — 2026-09-02

## Question

Can the production system distinguish a full-volume digest from healthy retrieval without adding search/model spend or changing publication semantics?

## Production-derived control

Source artifact: Daily production run `33577674132`, publication date `2026-09-02`.

The release published seven stories, but saved retrieval diagnostics simultaneously showed:

- Primary: all 12 mandatory operations complete;
- Source Pulse: `complete_with_gaps`, 13 configured / 10 `ok`, multiple degraded source adapters, one promoted candidate;
- Agency Rescue: correctly triggered and used one search, but provider source metadata was unavailable;
- Hybrid: `complete_with_regional_gaps`, unresolved `asia` gap;
- Coverage: all six mandatory directions complete, 7/7 calls used, Retrieval Quality v1 `complete`.

Independent audit found four hard misses inside the same effective window, giving a conservative demonstrated recall of `7/11 = 63.6%`.

## Treatment

Discovery Health v1 is a deterministic reducer over the saved reports. It does not read final story count when assigning retrieval health.

Expected production-shaped result:

```text
primary          healthy
source_pulse     degraded
major_agencies   indeterminate
hybrid           degraded
coverage         healthy
overall           degraded
```

## Neighboring controls

The regression suite also requires:

1. All completed/healthy lane diagnostics -> `overall=healthy`.
2. A Primary direction with `raw_candidates=[]` alone does **not** degrade Primary.
3. Missing required lane diagnostics -> `overall=indeterminate` unless another lane has explicit degradation.
4. Explicit degradation wins over indeterminate in the overall verdict.
5. Coverage `complete_with_gaps` may still count as healthy when all mandatory directions are checked, there are no partial/unchecked directions, the audit is `completed_usable`, and current Retrieval Quality is `complete`.
6. An executed Agency Rescue without provider source metadata is `indeterminate`, not a false claim of healthy or zero source pool.

## Spend and side effects

```text
OpenAI calls: 0
Web Search operations: 0
network calls: 0
publication changes: 0
editorial changes: 0
query/routing changes: 0
```

## Decision

**GO for diagnostics only.**

Discovery Health v1 should be embedded into final `pipeline-status.json` and shown in the GitHub Actions production summary. It must not block publication in v1.

A future use of this signal to suppress the public `low_news_volume` claim or to block publication is a separate policy change and requires its own regression/audit evidence.
