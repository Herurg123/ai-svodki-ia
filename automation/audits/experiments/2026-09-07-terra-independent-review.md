# Independent Terra architecture acceptance — FAIL

Reviewed commit: `1383da3c3718150a9cbc9164f9c44ad420524ca6`.
Baseline: `b474b06bc00f365b9737ece4dd0912c1892489e7`.

## Blocking counterexample

The new Source Freshness bridge can allow a different event from the same
organization to resolve a saved 403 failure.

The offline control constructs a valid saved Source Freshness failure for:

`OpenAI launches new model for science`

Its organization is `OpenAI`. `collect_source_failure_signals()` removes that
organization from `event_identity_tokens`. Since it is the only capitalized
entity in this title, the resulting identity-token list is empty. The existing
source-freshness branch of `_candidate_matches_cluster()` therefore falls back
to a two-token title overlap and accepts this different candidate:

`OpenAI launches new model for coding`

The actual control result is `candidate_matches_cluster=true`; the same pair is
also related by `_signals_related()`.

The extended control runs the real proposed `_run_resolution()` accounting path,
with a transport-free synthetic result containing that fully eligible coding
candidate. It has a distinct event summary and source URL. Both events have
separate fresh `event_date`/`event_at` evidence and are on the same calendar
date with different exact timestamps. The alternative is schema-admissible and
has an empty error list from a recursive check of every schema feature used by
the local strict candidate schema, including nested sources. It passes both
Event Freshness and Source Freshness as `fresh`/`verified_fresh`. The response
first enters `_run_resolution` as the raw schema-valid candidate; the ordinary
Source Freshness gate then runs on the accepted candidate. The already-written
resolution quality remains `complete`. It then
then produces `candidate_count=1`, `resolution_disposition=positive`,
`retrieval_quality.status=complete`, and a seven-of-seven Coverage budget.
Neither of those downstream gates compares the accepted candidate's event
identity with the saved 403 event. Therefore they do not block the wrong close.

This is a **synthetic admissible control**, not an observed production search
result. The observed production case remains the Sep-5 Daybreak/Axios 403
artifact; it establishes that the new source-failure route is real, but it does
not establish that a provider returned the coding candidate above.

The baseline comparison is asymmetric by design: baseline commit
`b474b06bc00f365b9737ece4dd0912c1892489e7` has no
`source_resolution_evidence.py`, so a Source Freshness 403 cannot create this
Coverage resolution lead at all. The matching weakness becomes blocking with
this change because the new bridge introduces the saved 403 event into the
resolution cluster and then marks that cluster complete on the unrelated
candidate. It is not a claim that baseline handled the 403 correctly; baseline
simply excluded it and had no opportunity for this wrong source-failure rescue.

Reproduce, without network or paid APIs:

```bash
python automation/audits/experiments/2026-09-07-terra-independent-review.py
```

Machine-readable result: `2026-09-07-terra-independent-review.json`.

## Decision

**FAIL.** This is a concrete blocking defect. No implementation was edited and
no production API, publication, GitHub mutation, or Terra search was invoked.
Under the requested stop rule, further acceptance work, PR preparation, and
merge must stop until this defect is addressed and independently re-reviewed.

## Scope and limits

I read `AGENTS.md`, `automation/ARCHITECTURE.md`, and
`automation/specs/search-change-validation-matrix.md`, and compared the stated
baseline and reviewed commit. The control traverses the newly added saved
Source Freshness evidence bridge into the actual Coverage candidate/cluster
matching helpers. It does not replace the separately assigned Terra discovery
A/B, which was intentionally not duplicated. The blocking identity failure is
sufficient to reject the change before claiming the remaining budget 24/25,
regional, agency, cap/priority, prompt/schema, and backward-recovery matrix.
