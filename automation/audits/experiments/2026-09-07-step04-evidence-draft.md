# Step 4 evidence handoff — OFFLINE CHECKED / NOT ACCEPTED

Baseline: `b474b06bc00f365b9737ece4dd0912c1892489e7`.
Dedicated branch: `architecture/step04-evidence-20260907`.
The initial checkpoint is preserved in `2026-09-07-step04-initial-checkpoint.md`.
This is a development checkpoint, not independently accepted architecture.
No production PR/merge or paid production API call was performed.

## Evidence recovered

The exact Sep-5 production artifact (run 33934617471, artifact 9959942686,
head 95c566ddd50dee3c7b2d2e7ea72b71eec0227316) was recovered. ZIP SHA-256:
`7a41c86c4e6365981e156aa861a88a3b2b1eaec72ea2e4d7d9291d07a12a53de`.
The fixture records provenance and separates this historical artifact from the
current official OpenAI HTML/RSS, fetched during this continuation.

Daybreak was accepted by Primary, then excluded after Axios returned 403 during
Source Freshness. This is a different handoff from model rejection processing.
The historical seventh Coverage query concerned Thinking Machines Lab and
produced zero candidates; that single outcome cannot prove future priority safety.

## Implemented draft behavior

- Retain raw rejection URL/time evidence. An outside_window rejection without an
  exact aware timestamp contradicting that classification stays diagnostic only;
  the three obsolete May events no longer gain mandatory priority in this case.
- Snapshot eligible candidates before Source Freshness exclusion; reconstruct
  legacy evidence only by exact title/URL identity and Primary cap provenance.
  Exact-window checks and later successful verification prevent stale signals.
- Pass source failure and event identity to the existing bounded resolution slot.
  Preserve excluded rows and all downstream freshness/dedupe/editorial gates.
- Add a narrow OpenAI fallback when generic metadata is absent: the exact cited
  article's visible hero date must agree with the unique exact-URL RSS pubDate.
  Daybreak's controlled source timestamp is 2026-09-03T13:15:00+00:00. Generic
  metadata and the event-age gate remain authoritative; ambiguous/mismatching
  evidence fails closed. One additional public RSS fetch, no extra paid search.
- Save a started seventh attempt with release date/window before transport.
  Error, quality migration and missing diagnostics never free an indeterminate
  slot. Actual artifact recovery recognizes the saved marker.
- Restore diagnostics only from the selected artifact lineage and matching window,
  without network calls. Candidate cap, six mandatory Coverage directions and
  24/25 search ceilings remain unchanged. Full-digest skipped Coverage is not
  newly invoked. Named-event matching limits unrelated same-company clustering.

## Completed development verification

The complete baseline checkout passed 614 tests; the original draft passed 624.
This resolves the former partial-checkout failures; they are not accepted as a
non-regression argument. The final proposal passed **639 tests** and six validators
(editorial contract, archive, production workflow, RSS, sitemap, structured data).

The isolated, network-forbidden replay passed **155 checks**, including **144**
combinations of pool size, region, source state and ordering. Unaffected complete
candidate payloads and normalized source diagnostics matched the baseline.
Original Axios exclusion stayed identical. The proposal retained exactly the
Daybreak required lead; the obsolete May leads were not made mandatory. A
**manually supplied known alternative** failed the old source parser and passed
the proposed exact HTML/RSS adapter. Migration preserved seven paid attempts
instead of reducing seven to six. Paid API calls during replay: zero.

Reproduction:

```bash
python automation/audits/experiments/replay_source_resolution_2026_09_07.py \
  --baseline-root /path/to/complete/b474b06/worktree \
  --output /tmp/step04-replay-results.json
python -m unittest discover -s automation/tests -v
```

Protocol: `2026-09-07-step04-protocol.md`.
Machine-readable result: `2026-09-07-step04-replay-results.json`.
Fixture: `automation/fixtures/recall/source-resolution-daybreak-2026-09-05.json`.

## Remaining admission gates

1. Assistant-side Terra discovery/selection A/B using comparable inputs and the
   same search budget. The direct public lookup above is not that experiment.
2. Independent architecture acceptance: priority/agency displacement, event
   overlap, regional composition, dense candidate caps, Coverage entry/recovery
   and prompt/schema overhead. Deterministic controls do not establish model
   output quality, actual spend, or whole-chain completeness.
3. Only after successful acceptance: acceptance DOCX, PR, authorized merge and
   verified main. Steps 5–6 remain unstarted. On failed independent acceptance,
   write the reason and stop under the user's rule.

A dedicated Terra search tool is not exposed here. A separate Terra executor is
available through collaboration, but session instructions require an explicit
request for delegation before spawning it. No agent was silently substituted and
no user production API was used to fill that gap.

## Usage observations

The historical 12:00:06–12:18:49 MSK run started at 100% and ended at the user's
later reading of 33%: approximately 67 percentage points / 18m43s = 3.58 pp/min.
That run used Astra low per the user; later work used the user's Astra max setting.
The later reported 25% is a separate observation, not a stage-specific measurement.

This continuation first observed 58% (quota kind unspecified) at
2026-09-07 19:17:22 MSK. A later user steering explicitly started a new five-hour
measurement at 100%; the first clock after that message was 22:16:45 MSK.
The intervening idle gap is not counted as active work. No current quota meter
or final remaining percentage is visible. No additional statistics analysis was
used as a substitute for architecture work.
