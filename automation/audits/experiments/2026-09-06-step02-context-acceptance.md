# Step 2: lossless context and editorial cache boundary

Baseline: 03474ed5493a52fce32cca29b72343ba6fc7ed68 (merged step 1).
Acceptance criteria frozen after local development, before final independent replay.

- Rebuild the saved September 1–5 editorial prompts using compact archive,
  candidates and policy JSON. Parse each region independently and require exact
  data equality, including array order, strings, URLs, dates and excluded rows.
  Require fewer characters and fewer o200k_base tokens for every saved prompt.
  Token counts are an offline proxy, not provider billing measurements.
- Exercise the real Coverage builder across empty, sparse, normal and dense pools,
  nested identities, regions, null/exact dates, shared URLs and status variations.
  Compare parsed payloads and instruction text to baseline. No ranking, field
  projection, truncation, schema, search slot, model or ordering change allowed.
- Serialize an editorial request through production-pinned openai==2.45.0 using
  httpx.MockTransport. Require one request, identical concatenated text and role,
  implicit mode plus explicit breakpoint after archive. No API credential or
  production network is used. Unsupported models/markers preserve plain input.
- Verify repeated editorial prompts with changed candidates have identical
  cacheable prefix. Model cost scenarios include cold/no-hit, warm reuse and
  exact duplicate requests. Do not claim measured dollar savings or identical
  stochastic LLM outputs from offline tests.
- Full offline regressions and canonical validators must pass. Saved artifacts,
  transport limits, recovery gates and public files remain unchanged.

The cache proposal keeps the implicit full-message boundary and adds an explicit
shared archive boundary. Exact-repeat/SDK-retry reuse is retained; changing
suffix writes are not disabled. Development rejected explicit-only mode because
it could increase the input cost of exact repeats. Real cache hits depend on matching rendered context and
availability; cache lifetime is at least 30 minutes after reuse according to
https://developers.openai.com/api/docs/guides/prompt-caching (checked 2026-09-06).
No paid API is authorized for experiments. Any failed independent acceptance
stops this sequence for an explanatory DOCX; no production merge follows.
