# Source Pulse v1.1 supplemental promotion experiment — 2026-08-27

## Decision

Promote Source Pulse from pure production shadow to a bounded supplemental discovery input for the **first editorial pass**, without adding OpenAI or Web Search calls.

The approved experimental path is deliberately narrower than generic candidate influence:

1. Primary Recall completes normally and preserves its Search-derived `regional_health` gaps.
2. Source Pulse v1.1 polls the existing fixed registry over HTTPS only.
3. The v1.1 parser adds bounded visible-date association for article-like HTML containers; JSON-LD/RSS/time parsing remains inherited from v1.
4. Fusion is computed against the untouched Primary pool.
5. Only `pulse_only` **Tier A + role=official** leads are eligible for promotion.
6. Each eligible lead is fetched directly and must pass deterministic page publication-date proof against the exact saved search window.
7. A deterministic AI-relevance gate must match the title/page summary.
8. The resulting row enters the trusted research pool only as `recommendation=consider`, with `significance_score=3`; Source Pulse does not grant `include` or high significance.
9. Tier B remains lead-only and diagnostic-only.
10. The existing trusted-runtime Source Freshness Proof runs again before the first editorial call, so a Pulse candidate cannot bypass the normal freshness safety boundary.
11. Hybrid still sees the Search-derived regional gap signal and retains its existing 3–4 search operations. Pulse therefore cannot suppress a Russia/China health check or reduce the existing independent search budget.
12. The saved Pulse snapshot is reused by the later shadow/fusion stage; same-day recovery does not repoll mutable sources.

## Cost contract

- Source Pulse OpenAI calls: **0**.
- Source Pulse Web Search operations: **0**.
- Existing ceiling remains **24 = 12 Primary + 1 agency rescue + 4 Hybrid + 7 Coverage**.
- No extra editorial call is introduced: supplementation occurs before the already-existing first editorial pass.

## Diagnostics contract

`automation/preview/production-daily/source-pulse-<DATE>.json` must preserve:

- source transport/parser summary and per-source attempts;
- v1.1 parser counters where available (`parsed_items_before_v11`, `parsed_items_after_v11`, `dated_items_after_v11`, `undated_items_after_v11`, `visible_dates_recovered`);
- pre-promotion Search/Pulse fusion;
- one disposition per Pulse lead;
- deterministic page freshness/relevance rejection reasons;
- proposed/promoted counts and merge rejections;
- accepted Pulse source URLs;
- post-promotion fusion;
- later post-Hybrid fusion via the existing Source Pulse shadow integration;
- explicit paid API/Web Search counters fixed at zero;
- snapshot reuse flag.

The whole `automation/preview/production-daily/` directory is already uploaded in the normal Daily production artifact, so no new workflow upload surface is required.

## Safety boundaries

- No hard Russia/China publication quota.
- No Tier B candidate influence.
- No semantic/LLM matcher added.
- No automatic legal/curiosity elevation.
- No weakening of archive dedupe, source freshness or editorial policy.
- No reduction of Primary/Hybrid/Coverage search obligations.
- Collector/parser/promotion failure is fail-open for the already valid Primary pool and is written to Primary diagnostics.

## Independent test plan

Offline regressions cover:

- Russian and English visible sibling dates;
- Tier-A fresh AI lead promotion;
- Tier-B non-promotion;
- stale source-date fail-closed behavior;
- deterministic non-AI rejection;
- saved snapshot reuse without a second poll;
- preservation of Search-derived regional-health gaps;
- zero paid/API counters.

Promotion beyond this bounded v1.1 policy requires a separate experiment.
