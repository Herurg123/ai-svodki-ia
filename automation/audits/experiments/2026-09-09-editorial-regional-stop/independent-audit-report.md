# Independent offline audit — production run 34298397080

**Verdict: PASS**

Scope: offline review of the incident fix against base
`d3ed784ec8a9f3450d723e2565b3ab1509d0facf`. No production API, source requests,
production/recovery workflow, git mutation, or new cover generation was run.

## Reproduction

The saved ZIP SHA-256 is
`71bdd4f1c2427f91ed800ff8477df9ddcfd3941c9fb761ce997d3af02d536c90`.
Its full archive SHA-256 is
`d57cf5dafd189373dc058b003b2bfd21d8f634b9f02873febf4220df5fd18150`.

`run_independent_controls.py` loads the saved fixture, applies the same runtime
policy/source-validation patches as production, uses the saved production
`publication_hour=6`, and validates against the full archive.

* Base validator, loaded directly from
  `git show d3ed784ec8a9f3450d723e2565b3ab1509d0facf:automation/scripts/generate_digest_preview.py`,
  returns exactly the production-stopping error: `В пуле есть достойные российские
  кандидаты, но ни один не выбран.`
* Candidate validator returns no errors, emits a diagnostic containing `cand-008`,
  and returns seven stories.
* The digest SHA-256 is identical on both paths:
  `692faa835741c45ec94439d1a93649714a6a10f278ead2ecae7e0ac485c15898`.

This establishes causality: the previous validator imposed a Russian publication
quota from preliminary `include|consider` and score metadata even though
`regional_story_quotas_enabled=false` and the editorial policy permits a
content-based rejection. The saved editor explicitly rejected `cand-008` because
its description lacked sufficient verifiable product detail.

## Controls

The independent control replay passed these neighboring cases:

* selected regional story; excluded high-score regional lead; weak lead;
  stale/excluded lead;
* all candidates excluded; unknown candidate ID;
* diversity override and article-source provenance failures remain hard errors;
* input objects are unchanged by validation;
* agency recovery retains at-most-once behavior for an indeterminate
  `search_started` state, and completed coverage audit is restored without repeat.

The focused independent suite passed 52 tests. The owner-reported final project
run passed 624 tests and 6 validators; its logs are outside this independent
folder at `../unit-tests.log` and `../validators.json`.

## Boundaries

The reviewed change only changes the former regional hard error into a warning
with IDs and documents that existing policy. It does not change selected IDs,
article text, retrieval/search limits, freshness, coverage, image generation, or
recovery state. Recovery may reuse already-paid searches; this audit did not run
today's recovery or production. Generating a new cover would require an API call
and remains outside this verification.

## Preservation note

The full archive used by this comparison is the archive committed at the base
SHA, not a member of the Actions ZIP. The preserved runner now reads that exact
archive and baseline source with git show, checks the saved archive hash, and
uses a temporary directory. This portability adaptation changes no control
expectations. The original scratch-path run and the portable replay have the
same JSON results. The 52-test focused suite includes existing regression tests;
it is not a claim that 52 new independent tests were authored.
