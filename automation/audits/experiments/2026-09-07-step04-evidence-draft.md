# Step 4 evidence handoff — DRAFT / NO-GO

Base: b474b06bc00f365b9737ece4dd0912c1892489e7; tree: 81ddfbf401b95b3411150cd55d6c84f690614e81.
Start: 2026-09-07 12:00:06 MSK. Implementation checkpoint, not accepted architecture.

## Draft delta

Primary preserves URL and a deep copy of raw rejection evidence for unverified
and outside_window. Strict rejection schema adds nullable publication date,
aware timestamp, precision and date evidence. Exact evidence may classify a
source instant inside/outside; unknown is not fabricated. Strong disputed rows
use the existing selector; precisely outside source rows do not request rescue.
No publication eligibility is granted.

Resolution receives original URL/reason/time proof and instructions to verify an
alternative authoritative source after inaccessible evidence, within one search.
Legacy raw Primary rejections can be reprojected without paid Primary work.
The execute entrypoint preserves an already-used supplemental slot and fails
closed rather than freeing it for repayment.

## Development checks — NOT independent acceptance

10 new unit tests and 17 existing Retrieval Quality tests passed.
Isolated baseline and proposed runs each executed 610 tests, each with exactly
the same 4 failures and 4 errors. Several concern missing files in the partial
text checkout; agency recovery also fails on both. Not clean repository CI.
12-input subprocess A/B: baseline retains 4 rows / 0 URLs; proposed 8 rows /
8 URLs. Required signals increase 4 -> 7. Inputs are synthetic controls using
historical instants, not the complete saved production article corpus.
No publication promotion. git diff --check passed. Paid API/Search calls: 0.

## Blocking gaps

Live assistant-side Terra search was not exposed. Real source-resolution A/B
and independently conducted matrix acceptance remain NOT COMPLETED.
Daybreak's Axios 403 occurs after discovery in Source Freshness; retaining model
rejections does not prove that candidate reaches alternative-source rescue.
Recover the exact Sep-5 artifact and trace this handoff before claiming success.
The increased required-signal set needs priority/volume/overlap/regional/recovery
matrix testing. Historical _prepare_prior_for_quality still strips supplemental
attempts; the entrypoint guard is not proof of safety for every direct caller.
No whole-chain non-regression claim. No PR/merge/production dispatch. Stop at 4.

TechCrunch timestamp correction does not remove fact/significance concerns.
Event/Source Freshness, dedupe, six mandatory Coverage directions, 24/25 ceilings
and at-most-once recovery remain required acceptance invariants.

## Usage observations

Current starting/remaining percentages unknown: no meter or new user reading.
Prior user readings: 07:18=11%, 07:19=4%, no parallel paid work. Rounded
06:51–07:19: 96/28 ≈ 3.43 percentage points/minute. Historical arithmetic only,
not a current measurement or per-message cost. No waiting to consume the limit.

