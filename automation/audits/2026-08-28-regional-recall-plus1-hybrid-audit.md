# Independent architecture audit: regional recall + conditional fifth Hybrid

Date: 2026-08-28
Scope: retrieval/search architecture, Source Pulse v1.2, regional Hybrid v3,
search-cost and recovery boundaries.

## Executive verdict

**Architecture verdict: PASS, subject to repository CI before merge.**

The change keeps the dual-discovery architecture and fixes the regional recall
path without introducing an uncontrolled search multiplier. The only new paid
operation is one fifth Hybrid Web Search when both Search-derived Russia and
China/Asia health flags are open. The normal ceiling remains 24 Web Search
operations; the exceptional double-gap ceiling is 25.

The audit does not approve additional regional Coverage searches or an LLM
semantic dedupe stage. Those are deferred future options.

## Architecture inventory checked

The dependency review covered:

- `primary_recall_search.py` and preserved Primary v2 engine;
- Source Pulse registry and Source Pulse v1/v1.1/v1.2 supplement/shadow layers;
- deterministic Source Freshness Proof;
- agency discovery rescue and v4 gap-aware wrapper;
- Hybrid preserved regional/v2 layers and new v3 public behavior;
- `run_digest_preview.py` Hybrid caller contract;
- candidate merge/dedupe boundary;
- fallback Coverage boundary;
- same-day recovery/saved-artifact assumptions;
- README, `automation/README.md`, `AGENTS.md` and `ARCHITECTURE.md`;
- retrieval tests and controlled experiment requirements.

No video/RSS, deploy, cleanup or repository-hygiene behavior is intentionally
changed by this retrieval PR.

## Layer-order audit

Expected fresh-production order remains:

```text
Primary Recall (12)
-> Source Pulse v1.2 supplement (0 Search / 0 OpenAI)
-> Source Freshness Proof
-> first editorial
-> conditional agency discovery rescue (0 or 1)
-> rescue Source Freshness Proof
-> saved Source Pulse snapshot/fusion reuse
-> Hybrid v3 (normal <=4; double-gap <=5)
-> editorial rerun only if candidate added
-> Coverage when existing policy requires it (<=7)
-> Source Freshness Proof
-> final editorial when needed
```

PASS. No new paid stage is inserted before/after Coverage, and Source Pulse does
not gain hidden Search/model calls.

## Search-budget audit

### Primary

Unchanged: exactly 12 mandatory one-search routes.

### Agency rescue

Unchanged maximum: 1 Web Search operation. V4 only changes the single query's
regional hints when Primary already reports a gap; it does not add a second
agency rescue.

### Hybrid

V3 contract:

- no regional gap: normal baseline, maximum 4;
- one regional gap: 3 broad + 1 dedicated regional, maximum 4;
- both Russia and China/Asia gaps: 3 broad + China/Asia + Russia, maximum 5;
- lowered baseline cannot activate the extension;
- oversized caller limit cannot create a sixth call.

PASS.

### Coverage

Unchanged maximum: 7 Web Search operations. No new regional Coverage call is
introduced merely because `retrieval_health` remains red.

### Whole pipeline

```text
ordinary:   12 + 1 + 4 + 7 = 24 maximum Web Search operations
both gaps:  12 + 1 + 5 + 7 = 25 maximum Web Search operations
```

PASS. The delta is exactly one operation and only on the double-gap path.

## Source Pulse v1.2 audit

The fixed-source plane remains independent of Web Search and OpenAI calls.

Registry and policy changes:

- TASS AI tag added as Russian Tier-A `trusted_news`;
- Yandex IR, MWS and VK remain Tier-A official;
- CNews remains Tier-B lead-only;
- Alibaba Cloud gains bounded community fallbacks;
- other China/Asia official/Tier-B roles remain separated.

Promotion boundary:

- only `pulse_only` Tier-A `official` or `trusted_news` leads are eligible;
- `trusted_news` is not treated as an official company source;
- candidate can enter only as conservative `consider`;
- final URL for trusted news must remain inside the allowed host set;
- deterministic publication evidence must be inside the saved exact window;
- deterministic AI relevance gate is mandatory;
- downstream Source Freshness Proof remains publication authority.

Health semantics:

- transport/parser/source failures remain diagnostics;
- HTTP-success with parsed items but no usable date evidence is degraded rather
  than silently healthy;
- direct TASS automated access currently returning HTTP 403 is therefore a
  visible source gap, not a successful poll;
- same-day recovery reuses the saved Pulse snapshot and does not repoll.

PASS for bounded supplemental use. Pulse remains 0 paid API calls and 0 Web Search.

## Regional retrieval audit

The former mixed Russia+China last-mile query was structurally weak: two
linguistic/source ecosystems competed for one ranked result set. V2 separated the
regional queries within four calls by sacrificing one broad pass. V3 uses the
explicitly approved fifth call only when both regional gaps are simultaneously
open, restoring the third broad pass while keeping both dedicated regional checks.

The Russia query is Russian-language and source-neutral. The China/Asia query is
separate and source-neutral. Company names are retrieval hints, not whitelists.

Independent assistant-side web probing found current China AI signal through the
dedicated China/Asia geometry and confirmed fresh Russian first-party items on
Yandex's company-news surface that broad Russian retrieval can miss. This supports
separate regional passes and the fixed-source second plane. The test was targeted,
not a global recall benchmark.

PASS.

## Dedupe audit

The Hybrid prompt now explicitly distinguishes material event lifecycle stages:

- anonymous preview attribution vs final named release;
- financing announcement vs deal close;
- preview vs weights/public production availability.

This addresses the observed GLM/Ox-Alpha false-collapse class without adding a
paid semantic matcher. Existing schema/window/archive validation remains in force.

PASS as a deterministic/prompt-level repair. A separate LLM semantic-event
matcher is deferred and not authorized here.

## Volume health vs retrieval health

The architecture now distinguishes a full-volume digest from regional retrieval
health. A pool can contain enough global stories while retaining
`complete_with_regional_gaps`.

This signal does **not** create a regional publication quota and does not trigger
new Coverage spend. It is diagnostic truthfulness only.

PASS.

## Recovery and at-most-once audit

- agency rescue retains its persisted at-most-once state machine;
- Source Pulse snapshot remains same-artifact reusable and non-repolled;
- Hybrid report records whether the conditional extension was used;
- the fifth double-gap search is not an authorization for a sixth retry/search;
- stable public wrappers preserve versioned implementation/recovery surfaces.

No evidence was found that this change intentionally weakens Source Freshness,
exact saved-window handling or archive dedupe.

PASS at architecture/code-review level; repository CI remains the final executable
regression gate before merge.

## Independent assistant-owned test

A separate deterministic state-machine test was run outside the user's production
API budget. It enumerated all four regional flag combinations and boundary limits.
The expected 3/4/4/5 allocation was observed, with the fifth call confined to the
double-gap state. Lowered baseline and oversized-limit guards were also tested.

A separate assistant web probe was run for regional retrieval geometry. Standalone
Terra was not exposed in this environment; ordinary assistant web search was used
and must not be described as Terra. No user production OpenAI/API spend was used
for the audit or controlled experiment.

## Deferred paid options

Recorded for future audits, not implemented:

1. 1–2 dedicated regional Coverage searches if regional health stays red after
   Hybrid even when volume is sufficient;
2. a separate LLM semantic-event matcher for difficult dedupe.

Both require a future production-quality audit and explicit cost approval.

## Merge gate

Before production merge the PR must satisfy:

- branch based on current `main`;
- relevant Python compile/unit/contract checks through Main CI;
- `Required PR Gate` success;
- final diff review showing no unrelated video/deploy mutation;
- post-merge verification of `main` head and resulting retrieval constants.

Until those checks are green, this document's executable verdict remains
conditional even though the architecture review itself passes.
