# 2026-09-03 shared-source artifact mapping incident

## Incident

Production recovery run `33719317861` ran on `main` commit
`c90ae0911e9fab77db9dd5bed21ae91ac8365b74` and reused the already-paid artifact
from run `33716335547`. Fresh Primary research was skipped. The deterministic
publisher repair from PR #144 worked: Coverage/editorial completion succeeded and
the resulting full digest contained seven stories.

Publication then stopped later at `Validate complete text artifact before
image/promotion` with:

`Сюжет «Meta выпустила Muse Spark 1.3 для программирования и агентных задач» должен однозначно сопоставляться по ссылкам с одним кандидатом; найдено: ['cand-001', 'cand-006'].`

The image, promotion, commit and deploy stages did not run. Artifact `9879665731`
was saved for same-day recovery.

## Exact artifact evidence

The final selection explicitly identifies the Meta story as `cand-006` and
`stories.json` preserves the same candidate order. Its final source is Axios:

`https://www.axios.com/2026/09/02/meta-debuts-muse-spark-13-as-personal-agent-work-continues`

The same Axios URL also exists inside the raw source set of `cand-001` (Google) as
a supporting source, even though the final Google story cites Google's first-party
Gemini page. Therefore the old final validator sees the Meta HTML URL in both raw
candidate URL sets and reports an artificial two-candidate ambiguity.

The contamination is already present in the saved Primary research evidence: it
is not introduced by #144 or by recovery. This change does not try to repair that
semantic research-source mistake automatically because determining whether a
supporting source is topically relevant is not a safe deterministic operation.
The existing retrieval diagnostics can continue to expose shared source URLs.

## Root cause

`validate_digest_artifact.py` used two conflicting identity contracts at once:

1. it required `stories[].candidate_id` to exactly equal
   `selection.selected_candidate_ids` in order;
2. it then ignored that explicit identity and attempted to rediscover each HTML
   story by finding a URL that occurred in exactly one selected raw candidate.

The broader pipeline already permits a source URL to occur in more than one
candidate subject to later editorial verification, so global raw-URL uniqueness
is not a valid final-artifact invariant.

## Fix

Final story identity now follows the explicit deterministic contract already
present in the artifact:

- `selection.selected_candidate_ids` defines expected order;
- `stories[].candidate_id` must match that order exactly;
- each HTML `<h3>` headline must match the corresponding `stories[].headline`;
- each HTML story link must be present in that final story's `stories[].sources`;
- every `stories[].sources` URL must still exist in the expected raw candidate's
  provenance URL set.

A URL may therefore be shared by multiple raw candidates without making final
story identity ambiguous. This is not a relaxed source check: final HTML links are
now checked against the narrower story-specific source set instead of any URL that
happened to appear somewhere in the candidate.

## Offline replay

`automation/fixtures/recall/artifact-shared-source-2026-09-03.json` is a compact
zero-network replay derived from run `33719317861`. It preserves the exact Google
/ Meta shared Axios shape.

Regression coverage proves:

- the exact shared-source shape passes when candidate ID, headline and final story
  source agree;
- an HTML link to another URL from the same raw candidate still fails because it
  was not selected as the final story source;
- a final story source absent from the expected candidate fails;
- swapped HTML headlines fail even if a shared URL could otherwise blur identity;
- reversed `stories[].candidate_id` order remains fail-closed.

Replay cost: 0 OpenAI calls, 0 Web Search operations, 0 network calls.

## Architecture / budget / recovery audit

Unchanged:

- Primary, Agency Rescue, Hybrid and Coverage search budgets;
- Event Freshness and Source Freshness gates;
- editorial selection/diversity policy;
- image generation behavior;
- publication commit/deploy gates;
- same-day at-most-once recovery semantics.

The failure occurred after text editorial completion and before image generation.
Recovery must reuse artifact `9879665731` / run `33719317861`; fresh research is
not needed and would repeat already-paid work.

The previous validator implementation is kept byte-for-byte in
`validate_digest_artifact_base.py` only as an active compatibility base for the
public wrapper while this narrow incident fix is isolated. Consolidate the base
back into the public file on the next material artifact-validator refactor or
after 2026-10-03, after re-running the saved replay and neighboring failure cases.

## Documentation impact

README files and `automation/ARCHITECTURE.md` were checked. Production topology,
search budgets, recovery flow and public editorial rules do not change, so no
entry-point documentation update is required. This incident note records the
narrow final-validator identity correction.
