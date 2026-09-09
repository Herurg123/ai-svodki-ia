# Exact offline replay for run 34307360855

The downloaded Actions artifact `10087148289` from recovery run `34307360855`
was inspected offline with no network or API calls. All seven HTML `<h3>` values
were compared against the exact seven `stories.json` headlines using the proposed
identity normalization.

Result: `7/7 PASS`. The only transformation needed was
`Meta* запустила потребительского агента Muse` →
`Meta запустила потребительского агента Muse` for identity comparison.

Neighbor controls also passed: a real wording change remains unequal,
`SomeMeta*` is unchanged, `Meta**` is unchanged, the saved error set containing
only `story_headline_order` is eligible for current-code revalidation, and a
mixed set containing `story_source_not_candidate` remains ineligible.

Machine-readable result:
`2026-09-09-meta-headline-artifact-validation-replay.json`.

This replay is intentionally independent of production. It consumed 0 OpenAI
calls, 0 Web Search operations and 0 network calls. Full repository integration
is still required to pass `Required PR Gate` on the exact pull-request head.
