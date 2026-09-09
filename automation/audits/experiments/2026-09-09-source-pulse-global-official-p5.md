# Source Pulse Global Official P5 — controlled A/B, 2026-09-09

## Decision

**GO**, narrowly for the tested zero-paid Source Pulse source-routing treatment.

The change adds three bounded Tier-A `official` routes to the existing fixed-source
Source Pulse plane:

- OpenAI official RSS: `https://openai.com/news/rss.xml`;
- Qualcomm official newsroom: `https://www.qualcomm.com/news`;
- NSA AI-tagged official news surface: `https://www.nsa.gov/Press-Room/News-Highlights/Tag/116894/`.

It does **not** change Primary, Agency Rescue, Hybrid or Coverage queries, provider
selection, search count, editorial rules, regional quotas, Event Freshness,
Source Freshness, candidate cap or recovery repoll semantics.

Search-query wording was intentionally not changed because standalone assistant-side
Terra is not exposed in this session. This experiment therefore does not pretend
ordinary web search is Terra. The treatment is a deterministic fixed-source HTTPS
route and consumes `0` OpenAI calls and `0` Web Search operations.

## Why this treatment

Independent release audits Sep-6 through Sep-9 repeatedly showed a specific
upstream failure mode: high-signal events existed on authoritative first-party
surfaces but never reached the production candidate pool even when paid search
used nearly or exactly the full `24/25` or `25/25` budget.

The Sep-9 audit was the strongest current control: four strict hard misses remained
outside the saved candidate/source surface despite `25/25` searches. Three of
those four have stable first-party discovery surfaces that fit the already active
Source Pulse contract:

1. OpenAI — `Introducing ChatGPT Images 2.5`, Sep 8;
2. Qualcomm — Amazon multi-generational AI data-center silicon collaboration,
   Sep 8;
3. NSA — China-based AI companies / industrial-scale frontier-model distillation,
   Sep 8.

The same OpenAI official route also covers the Sep-7 hard miss cluster from Sep 6:
`Research acceleration: The view inside OpenAI` plus `An Alien Mind`.

This is deliberately not a company whitelist inside paid search. Source Pulse is
already a fixed, bounded first-party registry whose purpose is exactly this second
discovery plane.

## A/B corpus

### A — production baseline

Saved production artifacts and already merged independent audits:

- Sep 6: strict recall `1/2`;
- Sep 7: strict recall `0/1`;
- Sep 8: strict main-window recall `0/1`;
- Sep 9: strict recall `5/9`.

The union is a conservative denominator of `13` high-signal controls. The two Sep-6
OpenAI publications are one event cluster for recall accounting.

Baseline: **`6/13 = 46.2%`**.

### B — proposed P5

The proposed fixed-source routes add deterministic source visibility for four
previously missed strict controls/clusters:

- OpenAI Sep-6 research/safety cluster;
- OpenAI ChatGPT Images 2.5;
- Qualcomm × Amazon AI data-center silicon;
- NSA / FBI / CISA China-AI distillation advisory.

Proposed bounded recall: **`10/13 = 76.9%`**.

Absolute gain: **`+4/13 = +30.8 percentage points`**.

This is intentionally not reported as 100%. Three known strict misses stay misses:

- TCS / HyperVault Sep-5 infrastructure event;
- Reuters Sep-7 OpenAI/EU incident-report follow-up;
- Firmus × OpenAI Malaysia compute-capacity deal.

Those controls still require work on agency/provider routing or other discovery
surfaces. P5 is not presented as a Reuters fix.

## Independent source verification

Assistant-owned ordinary web verification on Sep 9 confirmed that the proposed
surfaces expose the relevant first-party material without spending the owner's
production API budget:

- OpenAI News currently exposes the Sep-6 research/safety items and Sep-8 Images
  2.5; OpenAI also publishes an official RSS endpoint linked from its News page.
- Qualcomm News currently exposes the Sep-8 Amazon AI data-center collaboration
  and the direct press release carries the same date.
- NSA's official AI-tagged News surface and direct press release expose the Sep-8
  distillation advisory.

The runtime still applies the existing direct-page Source Freshness Proof after a
lead is found. A future anti-bot response or missing publication metadata therefore
causes a visible rejection/degraded source, not a false fresh candidate.

## Controlled parser / promotion replay

Reusable fixture:

`automation/fixtures/recall/source-pulse-global-official-2026-09-09.json`

Offline contract:

`automation/tests/test_source_pulse_global_official_p5.py`

The replay exercises the real Source Pulse parsers and supplement path using
representative saved payloads:

- OpenAI RSS yields Sep-6 `Research acceleration`, Sep-6 `An Alien Mind`, and
  Sep-8 `ChatGPT Images 2.5`;
- Qualcomm newsroom card yields the Sep-8 Amazon AI/data-center control;
- Qualcomm executive appointment is rejected by the bounded title filter;
- NSA AI card yields the Sep-8 distillation control;
- unrelated NSA Zimbra security news is rejected by the title filter;
- an old Qualcomm AI item remains outside the exact saved window;
- all five first-party rows can pass the existing direct-page machine-readable
  Source Freshness gate and enter only as `consider` candidates;
- both Search-derived regional gaps remain open after Pulse promotion;
- a second same-day supplement invocation reuses the saved Pulse snapshot and
  does not repoll the three mutable sources.

## First PR Gate findings and corrections

The first `PR Gate` run, `34320193885`, was intentionally treated as experiment
evidence rather than something to silence. It ran 639 tests and found four
failures:

1. the historical supplement replay used raw fixture URLs while fusion normalizes
   trailing slashes; this made the synthetic direct-page freshness fetcher raise a
   lookup error and produced `0` promotions;
2. the NSA title filter used bare case-insensitive `AI`, which also matched normal
   words containing those letters, so one unrelated security card survived;
3. Qualcomm's live newsroom card date shape is abbreviated English (`Sep 8, 2026`),
   while the bounded article-card parser recognized full English month names but
   not standard abbreviations;
4. an older boundary test froze the source registry size at 13 instead of checking
   the registry contract semantically.

Corrections were deliberately narrow:

- replay URL lookup now uses the same deterministic `norm_url()` as fusion;
- NSA uses a word-bounded `\bAI\b` plus explicit AI/model/distillation terms;
- the existing bounded article-card date parser now accepts standard English
  month abbreviations such as `Sep`; generic body scraping and direct-page
  freshness rules were not broadened;
- the old registry test now checks configured/loaded identity, uniqueness and
  shadow/recovery invariants rather than a permanent magic count.

No failure was fixed by lowering significance, weakening Event/Source Freshness,
turning a source error into success, closing regional gaps from Pulse, increasing
candidate/search budgets or enabling recovery repoll.

## Matrix coverage

Relevant permanent cases:

- V2/V4/V5: sparse through normal/dense candidate pools and unchanged cap;
- O3/O5/O7: multiple OpenAI events, duplicate/fusion pressure, publisher flood;
- R6: Pulse-only candidates cannot close Search-derived regional gaps;
- F1/F5: in-window direct-page proof passes; missing/stale proof remains
  fail-closed;
- D4/D5: source/network/parser failure stays degraded and cannot be masked by
  another discovery plane;
- B1/B3: no paid search slot is added, `24/25` ceilings remain unchanged;
- C1: exact saved windows are reused;
- P1/P2/P4: saved Source Pulse snapshot is reused and never repolled in same-day
  recovery.

The new permanent matrix case is `S1`, global official Source Pulse routing after
an upstream paid-search miss.

## Precision and concentration checks

The treatment is intentionally narrow:

- every new source is Tier A + `official` + `global`;
- OpenAI uses its official RSS and remains bounded to 16 items;
- Qualcomm is limited to AI / data-center / inference / Dragonfly / agentic
  titles and 15 items;
- NSA uses the official AI-tag surface plus a word-bounded AI/model/distillation
  title filter and 15 items;
- all promoted rows remain `recommendation=consider`, score is not elevated by
  source identity, and normal editorial remains authoritative;
- direct article freshness is still mandatory;
- Source Pulse does not suppress Primary/Agency/Hybrid/Coverage and does not close
  regional health gaps;
- three additional publishers increase source diversity rather than concentrating
  the candidate pool in the publisher that already dominated Sep-9 production.

## Budget and recovery

No search budget changes:

- Primary: 12;
- Agency Rescue: max 1;
- Hybrid: normal max 4, conditional double-gap max 5;
- Coverage: max 7;
- whole pipeline: ordinary max 24, double-gap max 25;
- P5 additional OpenAI calls: 0;
- P5 additional Web Search operations: 0.

Same-day recovery keeps `repoll_on_recovery=false`; the saved Source Pulse snapshot
is reused. No paid stage is repeated.

## Residual risks

1. Fixed source pages are mutable. If OpenAI/Qualcomm/NSA change HTML/RSS shape,
   Source Pulse can degrade until the parser/registry is updated. Existing
   diagnostics make this visible.
2. OpenAI direct pages have historically produced an HTTP 403 in one saved
   freshness path. P5 does not bypass that gate. If the condition recurs, the
   candidate is rejected rather than published with weak proof; realized recall
   will be lower than the controlled replay, but precision/freshness does not
   regress.
3. P5 does not repair Reuters Agency Rescue. The three residual strict misses are
   preserved as controls for the next routing experiment.

## Verdict

The controlled treatment improves the bounded historical strict recall from
`46.2%` to `76.9%` while adding no paid search operation and preserving freshness,
regional-health, candidate-cap and recovery-at-most-once contracts.

**GO for production registry activation of these three routes, conditional on a
green exact-head PR Gate after the corrections above.**
