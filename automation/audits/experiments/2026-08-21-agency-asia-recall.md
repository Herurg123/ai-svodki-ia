# Retrieval experiment: agency + Asia recall, 2026-08-21

Status: accepted for production patch after architecture-wide review.

## Scope

This experiment evaluates two changes only:

1. broaden the mandatory `major_agencies` one-search query toward AI infrastructure financing, earnings and business while preserving the Reuters/AP/Bloomberg/FT API route;
2. broaden the second China/Asia pass toward AI business, earnings, revenue and strategy while preserving the separate model/release pass.

It deliberately does **not** change Source Freshness Proof, exact-window validation, Russia routing, Hybrid adaptive capacity, Coverage, mutable-changelog dedupe or editorial selection.

## Evidence base

Historical repository fixtures and production observations were compared across the most recent retrieval period:

| Control | Historical evidence | What it says |
|---|---|---|
| 2026-08-11 | `automation/fixtures/recall/2026-08-11.json` | keeping two separate China/Asia passes raised the control set from 5/6 to 6/6; do not collapse model and integration/business routing |
| 2026-08-12 | `automation/fixtures/recall/2026-08-12.json` | fresh Reuters controls included IBM/Together AI/Nvidia, Nvidia Nemotron and CoreWeave; `major_agencies` is expected to contribute to these classes |
| 2026-08-13 | `automation/fixtures/recall/2026-08-13.json` | production `major_agencies` found 0 controls and was dominated by stale Bloomberg/FT material; source-focused natural-language queries recovered the five recorded controls without increasing the 12-search Primary budget |
| 2026-08-17 | independent audit journal | Nvidia/SB Energy/OpenAI infrastructure financing was a Must Include miss |
| 2026-08-18 | independent audit journal | freshness recovered; recall misses remained; China product-launch discovery stayed suspicious |
| 2026-08-19 | independent audit journal | Baidu AI-business/earnings was missed; separate China business semantics became a stronger hypothesis |
| 2026-08-20 | independent audit journal | Google/Marvell was a Must Include infrastructure/business miss; Baidu remained unhealed |
| 2026-08-21 | production artifact + independent audit | `major_agencies` consulted 18 URLs dominated by 12 Bloomberg + 6 AP, returned 0 accepted candidates and missed Broadcom/Alibaba/Google-Marvell; Alibaba confirmed the Asia business/earnings blind spot |

## Query A/B

### Major agencies

Production baseline:

`latest AI chips data centers investments deals policy security`

Candidate:

`latest AI chips infrastructure financing earnings business deals policy security`

Independent assistant-side web replay on 2026-08-21 surfaced the relevant current high-signal layer including Broadcom AI-chip financing, Alibaba AI/cloud earnings and Google/Marvell. The same experiment also reproduced the known limitation that search ranking is nondeterministic: the old query can surface some of these stories on a later replay even though the actual production Terra run did not.

Conclusion: semantic undercoverage is confirmed; ranking instability is real but does not yet justify adding a 13th Primary search. The repository's 2026-08-13 experiment already showed that better source-focused natural-language semantics can recover the control set inside the existing 12-search budget.

### China / Asia second pass

Production baseline:

`latest China Asia AI integrations partnerships deployments`

Candidate:

`latest China Asia AI business earnings revenue strategy cloud partnerships deployments`

Independent assistant-side web replay surfaced both Alibaba's 2026-08-20 AI/cloud earnings and Baidu's 2026-08-18 AI-business results while retaining partnership/deployment semantics. The separate `china_asia_models` pass is unchanged because production on 2026-08-21 successfully discovered Qwen3.8 and GLM-5.3 signals through it.

Conclusion: Asia business/earnings undercoverage is strongly confirmed and is best fixed by expanding the second Asia pass, not by collapsing the two regional passes or imposing a geographic publication quota.

## Architecture-wide regression review

### Preserved invariants

- Primary remains exactly 12 mandatory one-search passes.
- `major_agencies` remains a distinct Reuters/AP/Bloomberg/FT API-domain route.
- `global_breaking` and `independent_missing_events` remain source-neutral.
- `china_asia_models` remains separate and unchanged.
- `china_asia_integrations` remains a separate slot, now with business/earnings/revenue/strategy semantics added.
- `russia` remains its own mandatory Primary slot.
- Hybrid remains capped at 4 searches with its one adaptive gap slot intact.
- Coverage budget and trigger are unchanged.
- Source Freshness Proof and exact-window validation are unchanged.
- Candidate-pool fairness and editorial significance rules are unchanged.

### Rejected alternative

A local conditional 13th `major_agencies` rescue search was considered. It is **not** included in this patch because:

1. historical repository evidence on 2026-08-13 already demonstrated recall recovery without increasing the 12-search budget;
2. a new paid search would raise the global worst-case search ceiling and complicate existing Primary/Hybrid/Coverage accounting;
3. the known failure is partly semantic and can be addressed at lower architectural cost first;
4. daily independent monitoring will show whether agency ranking instability still causes Must Include misses after the query change.

If the same agency miss class repeats after this patch, the journal should treat that as evidence for a separate bounded-rescue experiment rather than silently adding more search budget.

## Method limitation

The historical production artifacts used `gpt-5.6-terra`. The current interactive assistant environment did not expose a standalone Terra search tool for a clean historical A/B replay, so the new query replays were performed with the assistant's available web search. They are **not** represented as Terra A/B results. No user's production API budget was spent on this experiment.

## Decision

Adopt the two query-semantic changes while keeping all search budgets and regional slots unchanged. Preserve the independent daily audit journal in Git and continue monitoring freshness, Must Include recall, agency source concentration, Asia business/earnings recall and Russia zero-pool correctness.
