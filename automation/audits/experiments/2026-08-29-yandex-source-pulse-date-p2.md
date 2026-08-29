# P2 Yandex Source Pulse publication-date repair, 2026-08-29

## Scope

Controlled offline regression for the deterministic Source Pulse Yandex date failure observed in the successful production artifact of 2026-08-29. This experiment does not run production, OpenAI or Web Search.

## Production evidence

- workflow run: `33231413963`
- artifact id: `9708618496`
- artifact SHA256: `b44c096424badb504e9e04be83db589f98cd80699ad4125cbedc051f0b6fe4e0`
- saved Source Pulse supplement: v1.2
- exact research window: `2026-08-27T04:43:51+03:00` through `2026-08-29T05:16:40+03:00`

The saved `source-pulse.json` shows eight distinct Yandex IR releases dated 18, 20, 21, 21, 24, 24, 26 and 28 August in their first-party title/URL ids. V1.2 assigned `published_date=2026-08-28` to all eight. All eight direct HTTP 200 pages then failed promotion as `source_freshness_no_publication_date` because the generic Source Freshness parser deliberately requires machine-readable publication metadata and does not scrape arbitrary body dates.

The fresh control that should have survived is:

- `28 августа 2026 ИИ-помощник Яндекса встроится в мобильную связь`
- IR id: `28-08-2026-01`
- company-news path: `/company/news/28-08-2026-01`

The seven 18–26 August rows are outside the exact saved window and must not be made fresh by the bad shared 28 August parser value.

Machine-readable regression data is stored in `automation/fixtures/recall/source-pulse-yandex-2026-08-29.json`.

## Root cause

Two deterministic failures interact.

1. The HTML index stack can retain a wrong non-null base parser date. V1.1 replaces a base date with bounded visible-date recovery only when the base date is null. V1.2 then appends sequential recovered items after the V1.1 output and dedupes in original-first order. A wrong non-null inherited date can therefore win over the local visible date.
2. Promotion reopens the Yandex article and correctly asks the generic Source Freshness parser for publication evidence. Yandex company-news pages expose the article date visibly but do not reliably expose one of the generic parser's accepted machine-readable publication fields, so the generic gate returns no date.

Broadening the generic Source Freshness parser to scan article body text would weaken the repository-wide freshness contract because unrelated dates, related-story dates and dates mentioned in the article can be mistaken for publication time.

## P2 design

Source Pulse v1.3 is a versioned wrapper over preserved v1.2.

### Index repair

Only Yandex IR/company-news article URLs are eligible. The URL must encode a valid `DD-MM-YYYY` article id and the same date must be corroborated by either the item's visible title/neighborhood or an already matching parser date. A conflicting non-null parser date is not allowed to win merely because it exists. Without corroboration the row becomes undated/fail-closed.

Duplicate Yandex URLs created by the old parser/recovery combination are collapsed. Non-Yandex parser behavior is inherited unchanged from v1.2.

### Direct-page fallback

The generic Source Freshness parser is not changed. V1.3 first gives it the original page unchanged. Only when generic machine-readable evidence is absent does a Yandex-specific fallback run. It accepts a date only when:

- the final/requested first-party Yandex URL encodes a valid dated article id; and
- the beginning of the visible Yandex page contains the same calendar date.

The two-signal result is then passed through the existing Source Freshness exact-window check. Existing machine-readable metadata remains authoritative and bypasses the fallback.

### Recovery

Same-day recovery does not repoll mutable Pulse sources. A saved v1.2 snapshot is repaired deterministically from its existing first-party Yandex URL/title evidence, and Yandex rows that are outside the current saved window are removed before fusion. This does not repeat any paid stage.

## Architecture and budget audit

Affected path:

`Primary Recall -> Source Pulse supplement -> trusted runtime research -> Event/Source Freshness -> first editorial -> later Hybrid fusion/recovery`

Unaffected contracts:

- Primary search matrix and queries;
- agency rescue, Hybrid and Coverage search routing;
- ordinary 24 / conditional 25 Web Search ceilings;
- Event Freshness semantics from P1;
- generic Source Freshness parser/fetcher semantics;
- candidate `consider`-only Source Pulse policy;
- Search-derived regional-health preservation;
- same-day no-repoll Pulse recovery;
- publication, image, site, RSS and deploy stages.

Budget impact: `0` new OpenAI calls and `0` new Web Search operations.

## Required regressions

The PR test contract covers:

- IR and company-news dated URL forms;
- non-Yandex URL exclusion;
- URL/visible-date agreement and mismatch;
- repair of the production-shaped false-uniform eight-row snapshot;
- seven old Yandex rows removed/rejected outside the saved window;
- Aug-28 Yandex Sim survives page freshness and can enter as `consider`;
- conflicting non-null index date fails closed without corroboration;
- existing machine-readable publication metadata remains authoritative;
- zero paid/search operations.

## Conclusion

P2 should be safe to deploy only after the exact PR head passes the full offline Main CI / Required PR Gate. It is intentionally a deterministic Yandex adapter repair, not a global Source Freshness relaxation and not a new retrieval/search layer.
