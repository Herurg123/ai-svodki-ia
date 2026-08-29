# Event Freshness P1 controlled offline replay — 2026-08-29

## Scope

P1 separates event-age freshness from source-page freshness. The experiment is
strictly offline with respect to production OpenAI/Web Search: it reuses the saved
successful daily artifact and assistant-owned verification only. No production
API key, production workflow or paid search operation was invoked.

## Production evidence

- Daily Actions run: `33231413963`.
- Artifact id: `9708618496`.
- Artifact file: `daily-production-2026-08-29-success.zip`.
- Verified SHA-256:
  `b44c096424badb504e9e04be83db589f98cd80699ad4125cbedc051f0b6fe4e0`.
- Saved effective window:
  `2026-08-27T04:43:51+03:00` → `2026-08-29T05:16:40+03:00`.

The saved selected pool contained all three stale-event false positives because
`Source Freshness Proof` validated only the publication time of the cited page:

1. Salesforce + Anthropic / Claudeforce used a fresh secondary page while the
   official announcement was on 2026-08-26; the BusinessWire timestamp was
   2026-08-26T20:21:00Z, before the effective-window start.
2. Gemini Enterprise Legal/Financial used a fresh secondary page while the Google
   Cloud first-party launch pages were dated 2026-08-25.
3. GLM-5.3-Flash used a fresh tracker/documentation surface while the Z.ai
   first-party release page was dated 2026-08-26.

## P1 contract tested

Structured event-origin evidence is independent of article publication metadata:

- `event_date`, `event_at`, `event_time_precision`;
- `event_origin_url`, `event_evidence_kind`, `event_date_evidence`;
- derived `event_freshness_status` = `fresh | stale | unknown`;
- deterministic stale rejection code `event_freshness_stale`.

Reliable evidence classes are official announcement/release/research,
filing/court docket/release note/changelog, unambiguous first-party timestamp and
authoritative secondary evidence when a primary origin is unavailable.

The deterministic rule is deliberately asymmetric:

- reliable + clearly stale event origin → reject before editorial and before any
  source-page fetch;
- reliable + clearly fresh event origin → continue to Source Freshness Proof;
- missing/ambiguous/untrusted origin or date-only evidence on a partial exact
  boundary day → `unknown`, preserve recall, then continue to the existing
  fail-closed Source Freshness Proof.

`unknown` is therefore not a publication bypass. It only means the new event-age
layer does not manufacture a false negative; the cited page still has to prove
its own freshness exactly as before.

## Controls

Machine-readable regression fixture:
`automation/fixtures/recall/event-freshness-2026-08-29.json`.

Expected controls:

| Case | Expected event status | P1 disposition |
|---|---|---|
| Claudeforce | stale | reject |
| Gemini Enterprise Legal/Financial | stale | reject |
| GLM-5.3-Flash | stale | reject |
| Anthropic court ruling, date-only 2026-08-27 | unknown | preserve recall |
| Anthropic Automated Alignment Researcher, 2026-08-28 | fresh | preserve |
| Lambda $1B debt, 2026-08-28 | fresh | preserve |
| unknown origin | unknown | preserve recall |

Exact-boundary regression additionally proves that the exact start timestamp is
fresh while one second before it is stale. A date-only event on that partial
start day remains `unknown`, not rejected.

## Offline result

Assistant-side targeted regression after the corrected P1 semantics: `8/8 PASS`.
The integration controls prove both critical ordering properties:

- a reliably stale event is rejected before the source fetch;
- an unknown event origin still executes the legacy fail-closed source gate.

The existing `test_source_freshness.py` suite is kept unchanged so P1 does not
silently redefine page publication freshness.

## Dependency / regression audit

Affected paths: Primary strict schema/prompt, Source Pulse handoff, source
freshness gate, conditional agency rescue, Hybrid strict schema/prompt, Coverage
strict schema/prompt, same-day rescue freshness diagnostics, editorial handoff,
recovery compatibility and documentation.

Preserved invariants:

- Primary search budget remains 12 operations.
- Agency discovery remains at most 1 search.
- Hybrid remains 4 normally / 5 only for the existing double regional gap.
- Coverage remains at most 7 searches.
- Source Pulse remains 0 OpenAI calls / 0 Web Search operations.
- P1 adds no new model call, Web Search pass or paid second pass.
- Saved legacy candidates without `event_*` evidence become `event=unknown` and
  remain reusable; they are not automatically rejected and do not force paid
  research to rerun.
- Existing Source Freshness remains fail-closed when page publication evidence is
  stale or unavailable.

Conclusion: P1 is a correctness gate before editorial selection, not retrieval
expansion or search tuning. It blocks the reproduced stale-event class while
preserving the previous source-freshness and recovery safety boundaries.
