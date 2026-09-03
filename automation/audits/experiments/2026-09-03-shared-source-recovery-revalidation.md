# 2026-09-03 recovery revalidation for obsolete shared-source error

## Scope

This is the recovery dependency discovered while verifying the fix for production
run `33719317861`. No production API call or Web Search is used by the fix or its
tests.

## Hidden dependency

Run `33719317861` saved a complete seven-story text artifact, but its
`artifact-validation.json` has `status=error` with exactly one code:

`ambiguous_story_mapping`

PR #145 replaces the validator rule that produced that false error. However the
stable recovery engine intentionally rejects any source directory whose saved
`artifact-validation.json` already says `status=error`. Without a narrow migration
rule, recovery from the latest artifact would therefore fail before current code
could re-run the corrected validator.

This is not permission to reuse arbitrary invalid artifacts.

## Bounded migration

The recovery compatibility layer may treat a saved validation error as
revalidatable only when the non-empty set of saved error codes is a subset of:

`{"ambiguous_story_mapping"}`

Every other validation error remains unusable. A mixed error set remains unusable.
An empty/malformed error report remains unusable. Any
`artifact-normalization.json` error remains unusable regardless of validation
codes.

The normal recovery flow already deletes `artifact-validation.json` from the
restored target as an image/final-stage file. Consequently the current #145
validator must run again later in the workflow; the stale report is never promoted
as success and never bypasses current validation.

## Exact recovery target

Artifact `9879665731` from run `33719317861` is the intended same-day recovery
source. It contains the complete text artifact and stopped before image generation,
promotion, commit and deploy. Fresh research must not be repeated.

## Regression coverage

Offline tests cover:

- saved `ambiguous_story_mapping` only -> revalidatable;
- `ambiguous_story_mapping` plus any unrelated validation error -> fail closed;
- empty/unknown validation error -> fail closed;
- any normalization error -> fail closed;
- recovery stage inventory still removes stale `artifact-validation.json` before
  current validation.

Cost: 0 OpenAI calls, 0 Web Search operations, 0 network calls.

## Architecture / publication invariants

Unchanged:

- retrieval/search budgets and source freshness;
- editorial selection and diversity;
- image generation;
- publish validation and commit/deploy ordering;
- recovery at-most-once semantics.

This change only lets a validator error made obsolete by #145 reach current
revalidation. It does not mark the old artifact valid by itself.

## Compatibility lifecycle and docs

The previous `recover_digest_artifact_v1.py` implementation is preserved
byte-for-byte in `recover_digest_artifact_v1_base.py`; the v1 public surface layers
this single migration rule. Consolidate it on the next material recovery refactor
or after 2026-10-03 once Sep-3 recovery fixtures are replayed.

README and `automation/ARCHITECTURE.md` remain accurate because recovery topology,
paid-stage behavior and publication rules are unchanged.
