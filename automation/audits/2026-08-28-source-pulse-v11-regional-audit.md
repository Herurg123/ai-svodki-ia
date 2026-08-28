# Independent audit — 2026-08-28 Source Pulse v1.1 + regional completeness

## Scope

This audit reviews the first full production digest after Source Pulse v1.1 was allowed to supplement the Primary candidate pool.

Production evidence:
- workflow run: `33133711979`;
- publication date: `2026-08-28`;
- producing base SHA: `c585bc2d52ad2823d4f4566e3ecfe82466e6295c`;
- published SHA: `c52b348dfe6b8dd1a424c6c6796274c12edcbc7c`;
- artifact: `daily-production-2026-08-28`, ID `9671422792`;
- artifact digest: `sha256:2ca9bfbb43c1052a6157abe3a9c3f89ac6675695544023c43663455b2f518dfa`;
- fresh research was explicitly forced; no same-day recovery was reused.

The audit used the saved production artifact, current repository contracts and independent assistant-side web research. No user production OpenAI API budget was used by the audit. A separate standalone Terra search surface was not exposed in the audit environment; the independent controls below therefore use the assistant web-search surface and are not described as Terra results.

## Verdict

| Dimension | Verdict | Evidence |
|---|---|---|
| Publication integrity | PASS | Full artifact validated and published; 8 final stories |
| Source freshness | PASS | Primary freshness 8→7; Hybrid freshness 9→8; excluded candidates failed closed |
| Search budget safety | PASS | 12 Primary + 1 agency rescue + 4 Hybrid + 0 Coverage = 17 search operations, below ceiling 24 |
| Source Pulse paid isolation | PASS | 0 OpenAI calls / 0 Web Search operations |
| Source Pulse candidate influence | PARTIAL PASS | One Pulse-only Tier-A lead, NVIDIA Vera, was promoted and selected |
| Source Pulse regional utility | FAIL | 0 Russia / 0 China-Asia Pulse leads |
| Primary regional recall | FAIL | Dedicated China/Asia and Russia passes accepted 0 |
| Hybrid regional recovery | FAIL | Regional gaps were checked, but one combined Russia+China/Asia query produced 0 candidates |
| Coverage last-mile regional recovery | FAIL BY DESIGN | Coverage did not run because 8 global stories already met volume target |
| Overall completeness | FAIL | Multiple independently verified in-window Russia/China controls never reached the final candidate pool |

**Overall: KEEP the dual-discovery architecture, but treat 2026-08-28 as a failed regional-completeness production test. Source Pulse v1.1 is safe and can add useful stories, but it has not solved the Russia/China blind spot.**

## Production reconstruction

### Effective window

The continuity anchor from the prior successful release was:

`2026-08-27T06:55:27+03:00`

Primary correctly applied the 24-hour healing overlap and used:

`2026-08-26T06:55:27+03:00 → 2026-08-28T04:43:51+03:00`

No calendar day was skipped.

### Primary Recall

Primary completed all 12 mandatory one-search passes and returned 8 candidates after the Source Pulse supplement; the Search-only pool before Pulse contained 7 candidates.

Search-derived regional health was correctly retained:

- China/Asia: `accepted_candidates=0`, `health_check_needed=true`;
- Russia: `accepted_candidates=0`, `health_check_needed=true`.

This was the intended v1.1 behavior: Pulse was not allowed to erase Search evidence of a regional gap.

The Search-only accepted candidates were all world stories:
- Google AI Mode travel transactions;
- OpenAI ads in India;
- Instinct Series B;
- Anthropic hardware interface standard;
- multi-company AI cyber-defense initiative;
- Hugging Face Microduck;
- Meta/Iran influence story, later excluded on freshness proof.

### Source Freshness after Primary

The first deterministic Source Freshness Proof processed 8 candidates and retained 7. It failed closed on the Axios/Meta item because freshness could not be proven.

The Pulse-promoted NVIDIA Vera candidate passed direct publication-date proof and then the normal Source Freshness Proof.

Freshness was therefore not the cause of the Russia/China absence.

## Why Primary missed Russia and China

### China/Asia Primary

Both dedicated directions completed but accepted zero candidates.

`china_asia_models` did see `Z.ai / Zhipu: GLM-5.3-Flash`, but rejected it as `unverified` because the selected official BigModel documentation URL timed out. This was a real current event, not a stale tracker artifact.

The same pass instead surfaced old Qwen and DeepSeek entries:
- Qwen3.8-27B dated August 19: outside window;
- DeepSeek V4 Flash Vision Exp dated August 21: outside window.

`china_asia_integrations` likewise returned older Alibaba/AsiaInfo material and accepted nothing.

The actual search queries were broad:
- `latest China Asia AI model releases agents open source coding`
- `latest China Asia AI business earnings revenue strategy cloud partnerships deployments`

The consulted-source inventory was dominated by trackers, generic analysis, Reddit and older result pages. It did not surface several fresh official/major-agency controls described below.

### Russia Primary

The dedicated Russia pass ran:

`последние новости ИИ Яндекс Сбер российские компании внедрения безопасность`

It accepted zero candidates and mostly consulted old Yandex/Sber pages and unrelated older material.

Its model rejections included:
- Yandex Alice AI safety, July 16;
- Yandex B2B Tech cyber insurance, August 4;
- Sber B2B naming change, August 10;
- Yandex B2B Tech H1 listing interpreted as having no newer item after August 12.

This is a ranking/retrieval failure, because fresh August 26–27 Russian AI events were independently available from Yandex, the Ministry of Education, Softline and CNews.

## Agency rescue also failed

`agency_discovery_rescue` triggered correctly:

- trigger: `major_agencies_raw_zero`;
- Reuters-only;
- one search operation;
- query: `latest AI chips infrastructure financing earnings business deals policy security`;
- raw candidates: 0;
- accepted: 0.

The rescue therefore contributed no candidate even though Reuters had in-window China AI stories, including Huawei AI-pharma expansion and Alibaba Qwen3.8-Flash.

This reproduces the already-known failure mode: a generic Reuters-only query can return no usable recent item even when Reuters has relevant current coverage. The transport and budget contract worked; recall did not.

## Source Pulse v1.1 production result

### Overall

Snapshot summary:
- configured sources: 12;
- transport/parser `sources_ok`: 9;
- unavailable: 3;
- leads: 3;
- Tier-A leads: 3;
- Tier-B leads: 0;
- all three leads were global NVIDIA stories;
- total fetch elapsed: 79.3 s;
- slowest fetch: 20.5 s.

Source Pulse itself used:
- OpenAI calls: 0;
- Web Search operations: 0.

### Candidate influence worked once

The three Pulse leads were:
1. NVIDIA NVLink Fusion / NVHBM;
2. NVIDIA Vera CPU shipping;
3. GeForce NOW Gamescom.

Only NVIDIA Vera passed the deterministic AI-relevance + direct source freshness gate and was promoted as a conservative `consider` candidate. It became `cand-008` and was selected into the final digest.

This is the first production proof in this series that Source Pulse can actually supplement Search at zero additional search/model calls.

The late log line:

`candidate influence=0`

is misleading. It prints the legacy top-level shadow flag `candidate_influence=false`, while the effective production behavior is `supplemental_candidate_influence=true`. Runtime diagnostics prove `promoted_count=1`.

### Regional Source Pulse failure

The new parser repaired only a subset of registered HTML shapes.

#### China/Asia Tier A

- `baidu_ir`: unavailable, read timeout.
- `alibaba_ir_hkex`: HTTP 200, 51 parsed links, **0 dated**.
- `alibaba_cloud_blog`: HTTP 200, **0 parsed**.
- `xpeng_ir`: RSS timeout + HTML fallback timeout.
- `deepseek_official_news`: HTTP 200, 30 parsed links, **0 dated**.

#### Russia Tier A / Tier B

- `yandex_ir`: unavailable because `SourcePulseError: response exceeds size cap`.
- `mws_news`: HTTP 200, 120 parsed links, only **1 dated**.
- `vk_press`: HTTP 200, 52 parsed links, **0 dated**.
- `cnews_ai` Tier B: HTTP 200, 127 parsed links, **0 dated**.

The parser-v1.1 change therefore fixed NVIDIA well, but did not make the important Russia/China registry surfaces operational.

### `status=complete` is still too optimistic

`source_pulse_supplement.py` currently sets:

`status = "complete" if snapshot.get("summary") is not None else "complete_with_gaps"`

That means a snapshot with 3 unavailable sources and several HTTP-200 sources yielding zero dated items is still globally labelled `complete`.

The diagnostics are now good enough to diagnose the failure, which is progress. The top-level health semantic is not.

## Independent regional controls

These controls are a **targeted diagnostic sample**, not a global-recall estimate and not an assertion that every item must be published. Their purpose is to establish whether meaningful fresh regional events existed and whether the retrieval architecture could see them.

### China

#### 1. Alibaba Qwen3.8-Flash — high-signal model release

Reuters, August 26, 2026:
`https://www.reuters.com/business/retail-consumer/alibabas-qwen-launches-qwen38-flash-ai-model-with-lower-training-costs-2026-08-26/`

A Reuters mirror timestamps it at 11:01 EDT on August 26, safely inside the production effective window.

The new multimodal model targets coding and office work, cuts training cost and includes open weights for the Flash-Next architecture.

Production result: **missed entirely** by Primary, agency rescue, Pulse and Hybrid.

#### 2. Huawei expands AI pharma partnerships — high/medium signal

Reuters, August 27, 2026:
`https://www.reuters.com/legal/litigation/huawei-plans-more-ai-pharma-tie-ups-says-healthcare-president-2026-08-27/`

Reuters mirror timestamp: 04:26 EDT on August 27, inside window.

Huawei said it plans to deepen AI cooperation with Chinese pharmaceutical companies from drug manufacturing toward clinical/final implementation.

Production result: **missed entirely**, including by the Reuters-only agency rescue.

#### 3. GLM-5.3-Flash — high-signal model release

Official Z.ai:
`https://z.ai/blog/glm-5.3-flash`

Dated August 26. It is the first natively multimodal GLM-5 model, 320B total / 18B active, public weights, with the anonymous Ox Alpha preview served on Chinese AI chips.

Production result:
- Primary **partially discovered** the release but rejected it when a different official documentation URL timed out;
- Hybrid rediscovered an aggregator version and rejected it as a `duplicate` of the prior archive story that Z.ai was the developer behind Ox Alpha.

That duplicate decision is materially wrong. “Identity/reveal of the developer behind an anonymous preview” and “final named model release with weights, architecture, pricing/benchmarks and deployment claims” are separate event types / at least a material update.

#### 4. DeepSeek funding at $74B valuation — high-signal business event

WSJ, August 27 at 05:18 UTC:
`https://www.wsj.com/tech/ai/ai-startup-deepseek-poised-to-reach-74-billion-valuation-1e093592`

DeepSeek was reported to be raising about $7.4B at a $74B valuation for R&D and computing infrastructure.

Production result: **missed entirely**.

#### Additional registry controls

Alibaba's own investor site visibly listed August 26 completion of the HK$80B placement and explicitly stated the AI-infrastructure allocation:
`https://www.alibabagroup.com/en-US/document-2029365886510432256`

The registered Alibaba HKEX index also visibly shows August 26 rows:
`https://www.alibabagroup.com/en-US/ir-filings-hkex`

Production Source Pulse fetched that index successfully but dated **0/51** items.

Alibaba Cloud Community visibly lists August 26 QwenWork and August 27 Qwen3.8-Flash material. The registered Alibaba Cloud blog returned HTTP 200 but Pulse parsed **0 items**.

### Russia

#### 1. Yandex federal teacher AI program — clear in-window control

Official Yandex:
`https://yandex.ru/company/news/26-08-2026-01`

Ministry of Education timestamp:
`https://edu.gov.ru/press/11968/uchiteley-so-vsey-rossii-obuchat-rabote-s-ii/`
August 26, 11:00.

The program is for up to 250,000 teachers and is described as the first federal initiative specifically focused on practical AI use by teachers.

Production result: **missed entirely**.

Crucially, the registered Yandex IR index currently lists this exact August 26 item:
`https://ir.yandex.ru/press-releases?year=2026`

Pulse did not parse it because the entire response was rejected by the source size cap.

#### 2. Softline Q2 / AI optimization — medium/high business control

Official Softline:
`https://softline.ru/about/news/pao-softlayn-obyavlyaet-o-roste-skorr-ebitda-v-1-5-raza-vo-2-kvartale-2026-goda-za-schet-uspeshnoy-i`

Dated August 27. CNews timestamp: 10:03 Moscow.

Softline reported Q2 adjusted EBITDA +53% and explicitly connected part of the efficiency improvement to AI adoption; its own-solution mix includes fabricaONE.AI.

Production result: **missed entirely**.

#### 3. SberBoom 2.0 with GigaChat — medium product control

CNews, August 27, 13:26 Moscow:
`https://www.cnews.ru/news/line/2026-08-27_sber_predstavil_novuyu`

Production result: **missed entirely**.

#### 4. REG Cloud token-based LLM platform — medium product/business control

CNews, August 27, 10:28 Moscow:
`https://www.cnews.ru/news/line/2026-08-27_regoblako_perevel_dostup`

Production result: **missed entirely**.

#### Additional CNews controls

CNews also carried, inside the window:
- August 26, 15:50: 86% of large Russian companies use/pilot LLMs;
- August 27, 12:52: DOM.RF AI ecosystem for construction.

The registered `cnews_ai` source fetched 127 links but dated zero, so none became even a Tier-B lead.

## Targeted A/B interpretation

For eight selected regional controls above (four China, four Russia):

- actual production Search/Hybrid/agency accepted: **0/8**;
- actual Source Pulse regional accepted/promoted: **0/8**;
- GLM-5.3-Flash was the only item partially discovered by production, but it was first lost on verification and then false-deduped;
- independent source-aware inspection found all eight.

This is not a global recall percentage. It is a targeted regional stress test proving that the architecture still has a severe Russia/China completeness failure.

Source Pulse nevertheless showed one global incremental success: NVIDIA Vera was Pulse-only, safely promoted, freshness-verified and selected.

## Hybrid regional recovery analysis

Hybrid used all four search operations:

1. `latest major AI model agent product research releases`
2. `latest AI chips data centers cloud investment acquisition earnings`
3. `latest AI safety cybersecurity regulation China Russia developments`
4. `latest major AI Russia China Asia models products partnerships infrastructure`

The fourth slot correctly existed because both regional gaps were unresolved. The problem is that it combined Russia and China/Asia into a single broad English query.

Its results were stale or analytical:
- Moscow Times August 13;
- July China policy;
- July Russia law;
- WAIC July;
- generic China-Russia analysis.

No regional candidate was accepted.

This health check is structurally underpowered: one query attempts to cover two very different ecosystems, languages and source graphs.

## Coverage did not run despite unresolved regional gaps

After Hybrid, editorial selected 8 world stories. The Coverage report therefore set:

- `audit_needed=false`;
- `mode=existing_full_digest`;
- `usual_target_met=true`;
- `candidate_pool: total=8, world=8, russia=0`;
- all six Coverage directions remained unchecked;
- 0 Coverage search operations were performed.

This explains why `security_russia`, `security_asia` and general last-mile coverage never had a chance to repair the regional miss.

The behavior is internally consistent with the current volume-based Coverage contract, but it defeats the purpose of carrying `regional_health` all the way through Primary/Hybrid. The system knows Russia and Asia are blind, then declares no further completeness work necessary solely because enough global stories were selected.

No hard regional **publication quota** is needed. The missing piece is a regional **retrieval-health trigger**.

## Editorial assessment

The final candidate pool contained 10 candidates, all `geography=world`. Two were excluded for freshness/eligibility; eight were selected.

Therefore the lack of Russia/China was **not caused by editorial selection**. Editorial never received a usable regional candidate.

The only editorial-adjacent issue is the false semantic duplicate on GLM-5.3-Flash, which happened in Hybrid candidate validation before final selection.

## Root causes ranked

### P0 — Source Pulse regional adapters are still non-functional

Evidence:
- Yandex: response-size failure despite a real registered fresh item;
- CNews: 127 parsed / 0 dated;
- Alibaba IR: 51 parsed / 0 dated;
- Alibaba Cloud: HTTP 200 / 0 parsed;
- DeepSeek: 30 parsed / 0 dated;
- XPeng/Baidu: repeated timeouts.

The generic v1.1 visible-date heuristic is insufficient for the real registered source shapes.

### P0 — Hybrid regional health combines Russia and China/Asia

One broad combined query cannot reliably recover both regions. It produced old analysis instead of current primary/regional sources.

### P0 — Coverage trigger is volume-only for this case

A full global digest suppresses Coverage even when Search's own regional-health contract still says Russia/Asia are blind.

### P0 — GLM semantic dedupe conflates event types

Developer identity disclosure / anonymous preview attribution was treated as equivalent to final named model release. This suppresses a material model release.

### P1 — Reuters rescue query remains too generic

The one Reuters-only rescue executed exactly as designed but returned zero raw candidates while Reuters had fresh Huawei and Qwen China AI coverage.

### P1 — Source Pulse health/status wording is misleading

The report says `status=complete` when significant sources are unavailable or cannot date any item. The runtime log says `candidate influence=0` even though supplemental influence promoted NVIDIA Vera.

### P1 — Search source concentration remains high

Five final selected stories came from TechCrunch. This is not itself invalid, but it is another symptom that broad global search ranking overwhelms regional source discovery.

## Recommended architecture repair

### 1. Keep Source Pulse enabled; do not roll it back

It proved safe and incrementally useful:
- no extra model/search calls;
- one real Pulse-only story reached publication;
- freshness and editorial boundaries remained intact.

The problem is adapter coverage, not the existence of the second discovery plane.

### 2. Replace generic HTML recovery with source-specific bounded adapters

Priority:
1. Yandex IR: avoid whole-page size-cap failure by a bounded source-specific route/parser or a narrowly justified source-specific cap; retain public-host and byte limits.
2. CNews: parse the actual date/title row/card structure; keep Tier B lead-only.
3. Alibaba IR: row-aware date association.
4. Alibaba Cloud Community/blog: use the real listing surface that exposes article cards/dates instead of the current parsed-zero payload.
5. DeepSeek official news: source-specific date extraction.
6. Re-evaluate Baidu/XPeng fallbacks and timeout behavior.

Do not replace this with an unbounded generic nearest-date scraper.

### 3. Reallocate Hybrid's existing four calls, not increase the ceiling

When both regional gaps exist, use separate regional searches within the same four-call hard cap.

Example policy:
- fixed global models/products;
- fixed infrastructure/business;
- Russia regional health;
- China/Asia regional health.

If only one region is unhealthy, the remaining slot can retain safety/adaptive behavior.

Queries should be source-aware and region/language appropriate, not a combined `Russia China Asia` English string.

### 4. Make regional-health survive into last-mile completeness

Coverage should distinguish:
- publication volume completeness;
- retrieval-health completeness.

If `regional_health` remains unresolved after Hybrid, one bounded regional last-mile check may be justified even when 7+ global stories already exist.

This is a retrieval-health check, **not** a rule that a regional story must be published.

If maintaining today's typical paid-call count is a hard constraint, first implement item 3 so Hybrid's existing four calls carry the regional responsibility; use Coverage regional repair only for explicit high-confidence unresolved signals.

### 5. Fix event-type/material-update dedupe

At minimum distinguish:
- anonymous model identity/developer reveal;
- final named model release;
- weights release;
- material architecture/capability/pricing release;
- financing announcement vs financing completion.

The GLM-5.3-Flash case should become a regression fixture.

### 6. Improve Reuters rescue without widening its budget

Keep one Reuters-only search and direct-Reuters acceptance, but make the rescue query conditional on missing clusters/regions or split the query vocabulary by detected gap. The current generic financing/earnings/policy string did not retrieve current China model/product stories.

### 7. Fix observability semantics

Source Pulse summary should report at least:
- `transport_ok_sources`;
- `dated_sources`;
- `degraded_sources`;
- per-region Tier-A healthy source count;
- `promoted_count`.

Global status should become `complete_with_gaps` when a required regional Tier-A source is unavailable or when a source returns many links but zero dated items.

Runtime summary should separately print:
- legacy shadow candidate influence;
- supplemental candidate influence;
- promoted candidate count.

## Regression requirements

Add real captured/redacted fixtures for:
- Yandex IR August 26 listing and response-size behavior;
- CNews August 26/27 listing rows;
- Alibaba IR August 26 row;
- Alibaba Cloud Community August 26/27 cards;
- DeepSeek news listing;
- NVIDIA known-good control.

Add retrieval regressions for:
- Russia and China independent Hybrid queries under the same 4-call ceiling;
- unresolved regional-health propagation without a publication quota;
- GLM identity-reveal vs final-release dedupe;
- Source Pulse health status on HTTP-200/0-dated sources;
- log/summary `promoted_count`.

## Decision

**Do not disable Source Pulse v1.1. Do not enable hard regional publication quotas. Do not increase the 24-search ceiling as the first response.**

The next patch should focus on:
1. source-specific regional Pulse adapters;
2. zero-extra-call Hybrid regional split;
3. GLM-style event-type dedupe;
4. regional-health completeness semantics;
5. truthful Pulse health/promotion diagnostics.

After those changes, repeat the same multi-day independent regional A/B before claiming the Russia/China blind spot is solved.
