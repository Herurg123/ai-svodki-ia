# Source Pulse official-newsroom feasibility replay — 2026-09-02

## Question

Can the zero-paid Source Pulse plane safely add OpenAI, Anthropic and European
Commission official news surfaces to reduce repeated upstream misses without
weakening Source Freshness or adding Web Search/OpenAI spend?

## Scope and cost

- Production run control: `33577674132`.
- Saved window: `2026-08-31T04:49:39+03:00` → `2026-09-02T04:01:28+03:00`.
- Production API/Web Search used by this experiment: **0**.
- Production registry mutations in this experiment: **0**.
- Generic Source Freshness body-date scraping: **not allowed**.
- No source-specific date repair is authorized by this experiment.

The machine-readable fixture is
`automation/fixtures/recall/source-pulse-official-newsrooms-2026-09-02.json`.
The offline replay is
`automation/tests/test_source_pulse_official_newsroom_experiment.py`.

## Why these surfaces

The Sep-2 independent audit found four hard upstream misses. Three had official
first-party publication surfaces that are not present in the fixed Source Pulse
registry:

1. OpenAI — `https://openai.com/index/expanding-access-to-ai-with-chatgpt-ads/`;
2. Anthropic — `https://www.anthropic.com/news/improving-alignment-security-efforts`;
3. European Commission — `https://digital-strategy.ec.europa.eu/en/news/commission-designates-chatgpt-reddit-roblox-under-digital-services-act`.

The fourth hard miss was Reuters Anthropic/Lambda and remains an agency-routing
control rather than an official-newsroom candidate.

## External source observations

### OpenAI

`https://openai.com/news/` visibly exposes dated newsroom entries, including the
Aug-31 control `A milestone in expanding access to AI`. The direct article also
visibly exposes Aug 31, 2026.

However, the saved Sep-2 production evidence already showed that an OpenAI
first-party freshness fetch can return HTTP 403. Source Pulse promotion performs
a direct page fetch and then the normal trusted-runtime Source Freshness Proof
checks the merged candidate again. Therefore index discoverability alone is not
enough to declare this source production-safe.

**Current decision: NO-GO for registry addition.** First prove a stable bounded
fetch/page-date path without weakening the generic freshness gate.

### Anthropic

`https://www.anthropic.com/news` visibly exposes the Aug-31 control
`Improving our alignment and security efforts` with its date. The direct article
is also publicly reachable and visibly dated.

The saved Sep-2 production evidence showed the neighboring first-party risk:
Anthropic can return HTTP 200 while generic machine-readable publication evidence
is insufficient for the current fail-closed Source Freshness parser. Visible body
text is intentionally not accepted as publication authority.

**Current decision: NO-GO for registry addition.** A future treatment must prove
narrow first-party date evidence or a stable machine-readable field; generic body
scraping remains prohibited.

### European Commission / Digital Strategy

The direct DSA article is publicly reachable and visibly marks `Publication 31
August 2026`. The generic `https://digital-strategy.ec.europa.eu/en/news` landing
page is large/paginated and the current first extracted result set did not expose
the Aug-31 control, so a stable index/listing contract is not yet proved.

**Current decision: NO-GO for registry addition.** First identify a bounded
listing/filter/pagination surface that deterministically exposes current DSA/news
items and then prove direct-page publication metadata under the existing gate.

## Offline parser replay

The replay deliberately uses minimal synthetic HTML, not copied live pages. For
each of the three hosts it supplies one bounded `<article>` card containing the
real control URL/title and an Aug-31 visible date. Current v1.3 delegates
non-Yandex HTML parsing through v1.2/v1.1, and the bounded card parser recovers the
correct date without any network or model call.

This proves only a narrow capability:

> If a first-party index exposes an article-like bounded card with a visible date,
> the existing generic Source Pulse parser can recover the lead.

It does **not** prove that the current live DOM for every source has that exact
stable shape.

The replay also protects the downstream safety boundary:

- visible date text alone on a direct article remains insufficient for
  `source_freshness.extract_publication_evidence()`;
- an existing machine-readable `article:published_time` field is accepted by the
  unchanged Source Freshness contract;
- none of the experimental source IDs is allowed to appear in
  `source-pulse-v1.json` in this PR.

## Result

**Feasibility: promising. Production promotion: NOT READY.**

The experiment supports keeping official-newsroom expansion as the next bounded
zero-paid recall hedge, but it does not support adding these sources to the live
registry today. The remaining work is source-specific transport/index/date proof,
not a reason to relax generic Source Freshness.

This is deliberately compatible with the Sep-2 decision to leave retrieval
semantics unchanged until another full production sample is available.
