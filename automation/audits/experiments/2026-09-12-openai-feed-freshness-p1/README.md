# P1: OpenAI trusted-feed publication evidence → Source Freshness

Date: 2026-09-12  
Scope: offline/fixture architecture repair only  
Production API / paid Web Search / workflow dispatch: **not used**

## Incident path reproduced from Astra handoff

The Sep 11 audit established a two-gate loss path for official OpenAI news:

1. `openai_news_rss` successfully produces an exact `openai.com` item URL and publication timestamp from the official RSS feed.
2. Source Pulse v1.3 promotion opens the item page again. When OpenAI returns HTTP 403, the lead is rejected as `source_fetch_error` before candidate creation.
3. Even if such a candidate were already present, the later trusted-runtime Source Freshness gate opens the same article URL and fail-closes it when the page cannot yield publication evidence.

Therefore changing only the later Source Freshness gate would leave the earlier Source Pulse promotion loss intact.

## P1 contract

P1 introduces one shared deterministic contract used by both gates. It is deliberately narrower than a generic RSS fallback.

A saved feed timestamp can become publication evidence only when all of the following are true:

- the source is explicitly approved in code **and** still exists in the current production registry as Tier-A `official` + `rss_atom`;
- initial approved source: `openai_news_rss` only;
- accepted original-publication fields: RSS `pubDate` or Atom `published` only;
- Atom `updated` and generic feed `date` are never publication authority;
- feed URL and item URL are HTTPS and the item host exactly equals the configured feed host;
- normalized `source_item_id` exactly equals the normalized item URL;
- publication timestamp is timezone-aware and internally consistent with `published_date`;
- exact item/canonical URL identity is unchanged at the direct-page gate;
- direct page publication metadata, when parseable, remains authoritative;
- a direct-page publication date conflicting with the feed fails closed;
- a direct canonical/redirect mismatch fails closed;
- the normal exact saved search window still applies, so old feed evidence proves stale rather than fresh.

The feed is **not repolled** to repair either gate. Source Pulse persists the exact trusted-feed proof into the candidate. Later Source Freshness independently validates that saved proof against the current registry and candidate primary URL.

## Versioned implementation

- `trusted_feed_publication.py`: shared proof/identity contract.
- `source_pulse_supplement_v14.py`: active Source Pulse wrapper over preserved v1.3.
- `source_freshness.py`: active Source Freshness v3 wrapper over preserved byte-identical `source_freshness_v2.py`.
- `trusted_feed_source_freshness.py`: candidate-local bridge into the preserved v1 source-page verifier.
- `primary_recall_search.py`: only switches the zero-paid supplement import/version from v1.3 to v1.4.

Yandex v1.3 repair, existing first-party page adapters, Event Freshness, Primary/Agency/Hybrid/Coverage query policy, editorial ranking and recovery budgets are not changed.

## Whole-project dependency audit

P1 was traced across the full fresh/recovery path rather than treating Source Pulse in isolation:

`Primary Recall → Source Pulse v1.4 → trusted runtime Source Freshness v3 → first editorial → agency/Hybrid → Source Freshness on merged research → Coverage → saved research/recovery`.

Effects:

- Search-derived `regional_health` remains Primary-only; a Pulse candidate cannot suppress Hybrid regional recovery.
- Major-agency health remains based on exact Primary provenance; OpenAI feed evidence cannot make that lane healthy.
- Agency Rescue, Hybrid and Coverage Web Search allocation is unchanged.
- Same-day recovery reuses the candidate's persisted feed evidence; it does not poll the RSS feed again.
- Source Freshness still fail-closes every non-approved feed/source and every approved proof with identity/date ambiguity.
- Discovery Health continues to consume saved Source Pulse/Source Freshness diagnostics; no story-volume shortcut is introduced.
- theoretical ceilings remain 24 ordinary / 25 conditional double-regional-gap Web Search operations.

## Offline validation

Before repository implementation, the proof contract was independently reproduced on assistant-owned offline resources. The standalone matrix passed:

- valid OpenAI RSS `pubDate` → accepted proof;
- Atom `updated` only → rejected;
- cross-host item → rejected;
- exact item identity mismatch → rejected;
- timestamp outside exact window → rejected as fresh proof / remains stale.

Repository fixture: `automation/fixtures/recall/openai-feed-freshness-2026-09-11.json`.

Regression tests additionally exercise both production gates:

- direct 403 at Source Pulse promotion;
- direct page without publication metadata;
- second 403 at Source Freshness after candidate persistence;
- direct publication-date conflict;
- canonical redirect drift;
- old feed timestamp;
- no feed repoll, no OpenAI call and no Web Search operation.

## Acceptance gate

P1 is accepted only when all of the following are true on the exact PR head:

1. new positive and negative fixture tests pass;
2. existing Source Pulse v1.3/Yandex and Source Freshness tests remain green;
3. full Main CI and configured validators pass;
4. final diff contains no search-budget, ranking, workflow-dispatch or provider-routing expansion;
5. architecture/README documentation matches the active v1.4/v3 behavior;
6. Required PR Gate succeeds.

Until those conditions are met, PR #170 remains draft and must not be merged.
