# 2026-09-09 Meta headline artifact-validation incident

## Incident

Recovery run `34307360855` ran on `main` commit
`ab3995a6d8eb5f9afb75f6bfee49b64d6bb3269a` after PR #159 fixed the earlier
false regional editorial stop. The saved paid artifact from run `34298397080`
was reused; fresh Primary/Hybrid research was not repeated. Editorial completion
produced the intended seven-story full digest.

Publication then stopped at `Validate complete text artifact before
image/promotion` with the only artifact error:

```text
story_headline_order: HTML-сюжет #3 не соответствует cand-003:
'Meta* запустила потребительского агента Muse' !=
'Meta запустила потребительского агента Muse'.
```

The failed recovery saved artifact `10087148289`. Image generation, promotion,
commit and deploy did not complete.

## Root cause

The canonical editorial policy intentionally uses two representations:

- visible `article_html`: the first visible Meta mention must be `Meta*`;
- `stories.json`, `sources.json` and service fields: `Meta` without the marker.

The final artifact mapper added in PR #145 compared HTML `<h3>` and
`stories[].headline` byte-for-byte after whitespace normalization. Therefore a
correct public headline could not equal its correct service headline whenever
the first visible Meta mention happened inside the story heading.

This is a validator-contract conflict, not a research, freshness, selection or
source-provenance failure.

## Fix

`validate_digest_artifact.py` now removes only the exact public `Meta*` display
marker for the story-headline identity comparison. `SomeMeta*`, `Meta**`, other
asterisks and every actual wording/order difference remain unequal. The strict
article validator and the existing service-field `Meta*` prohibition are not
changed.

`recover_digest_artifact_v1.py` adds `story_headline_order` to the bounded set of
saved artifact-validation codes that may be restored for current-code
revalidation. This does not waive validation: recovery removes stale stage
reports and the production workflow runs the current artifact validator again.
Any genuine headline mismatch or any unrelated saved error remains fail-closed.
The earlier `ambiguous_story_mapping` revalidation path remains intact.

## Permanent replay

`automation/fixtures/recall/artifact-meta-headline-2026-09-09.json` preserves the
exact `cand-003` headline, source URLs, run/artifact IDs and saved validator error
from `34307360855` / `10087148289`.

`automation/tests/test_sep9_meta_headline_recovery.py` verifies:

- exact `Meta*` HTML vs `Meta` service headline passes story identity;
- only the exact Meta display marker is normalized;
- real headline changes still fail with `story_headline_order`;
- service-field `Meta*` detection remains active;
- the saved Sep-9 error is eligible only for current-code revalidation;
- a mixed/unrelated provenance error stays non-reusable;
- the Sep-3 shared-source revalidation code remains allowed.

Replay uses 0 OpenAI calls, 0 Web Search operations and 0 network calls.

## Architecture / documentation / recovery boundary

Unchanged:

- Primary 12, Agency Rescue 1, Hybrid 4/5 and Coverage 7 budgets;
- Event Freshness and Source Freshness gates;
- regional policy and editorial selection;
- story/source provenance checks;
- image generation and publication commit/deploy gates;
- same-day at-most-once paid research semantics.

Root `README.md`, `automation/README.md`, `automation/ARCHITECTURE.md`, `AGENTS.md`
and `automation/specs/editorial-policy.md` were checked. The policy already
explicitly requires visible `Meta*` and service-field `Meta`, while the recovery
and validator architecture remain the same. No contract-document change is
required beyond this incident record and regression.

Safe publication recovery after merge should use `recovery_run_id=34307360855`,
`publication_date=2026-09-09`, `publish=true`, `force_fresh_research=false`.
