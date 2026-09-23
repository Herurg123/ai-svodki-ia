# 2026-09-23 durable paid-stage checkpoint replay

Status: controlled zero-paid recovery hardening and saved-artifact replay.

## Goal

Protect completed paid work from loss when a later production stage or the
GitHub runner fails before the final `if: always()` artifact is uploaded.

The change adds same-day 14-day GitHub Actions checkpoints after the existing
workflow boundaries:

1. completed fresh `Run full research and editorial`;
2. completed Coverage/editorial-completion step;
3. generated or revalidated Image artifact.

The final `daily-production-<date>` artifact remains unchanged and is still
uploaded with `if: always()`.

No retrieval query, provider model, prompt, candidate ranking, editorial policy,
search budget or publication rule changes.

## Real saved artifacts used

### Incident replay: 2026-09-22

- production run: `35676364066`
- saved artifact id: `10673466564`
- artifact: `daily-production-2026-09-22`
- original failure: publisher-diversity validation after paid Research/Coverage
- saved dated pool: 13 candidates
- saved Coverage: 7 calls, provider status `completed`
- saved editorial-repair journal: `response_saved`

Assistant-owned offline replay copied the real extracted bundle into the exact two
directories used by checkpoint upload and removed later-stage outputs to emulate
a runner loss immediately after the Research boundary.

Result:

- the dated source remains classifiable as `partial_editorial`;
- research state remains reusable under the current saved-state contract;
- if the final artifact is absent, the Research checkpoint is selected;
- if the real final failed-run artifact exists, it wins the same-rank tie because
  it is later and preserves the additional partial Coverage/editorial state,
  including `response_saved`.

No OpenAI, Terra, Web Search, page fetch or image call was made.

### Successful weekday control: 2026-09-21

- weekday: Monday
- successful production run: `35549672808`
- saved artifact id: `10617358513`
- artifact: `daily-production-2026-09-21`

The real saved bundle was replayed as three stage snapshots matching the proposed
checkpoint paths.

Result:

- Research snapshot: reusable;
- Coverage snapshot: reusable, Coverage provider state `completed`;
- Image snapshot: reusable; saved image-manifest SHA-256 matches the real
  `cover.png` and cover validation is `ok`;
- with the final artifact removed, resolver ranking selects Image checkpoint;
- if Image checkpoint is removed, it selects Coverage checkpoint;
- if only Research checkpoint survives, it remains a valid recovery source.

No provider calls were made.

## Resolver safety

Checkpoint names do not prove completeness by themselves. The production
resolver cross-checks the selected artifact against successful steps in the same
`production` job:

- Research rank 1 requires successful fresh Research or saved-artifact restore;
- Coverage rank 2 requires successful Coverage (or the preserved later validation
  proof for historical final artifacts);
- Image rank 3 requires successful generated/revalidated cover.

A checkpoint that claims a later stage than the run actually completed is
ignored. Manual `recovery_run_id` uses the same ranking inside the requested
run.

At equal rank, the later artifact wins. If timestamps are equal, the final
`daily-production-<date>` snapshot wins over a stage checkpoint because it may
contain partial state from the next stage.

## Architecture audit

- Primary remains 12 Web Search operations.
- Agency Rescue, Hybrid 4/5, Coverage 7 and whole-pipeline 24/25 ceilings are
  unchanged.
- Checkpoint uploads make zero OpenAI/Web Search calls.
- Existing `request_started`, `response_saved`, exact same-bundle and
  fail-closed recovery rules are unchanged.
- The Sep23 automatic-recovery spend guard remains authoritative: failure to
  restore a selected checkpoint does not authorize fresh paid Research.
- Legacy/final artifacts remain selectable; no artifact migration is required.
- Checkpoints are ephemeral GitHub Actions artifacts with 14-day retention and do
  not enter tracked content, archive dedupe, RSS, site generation, FTP deploy,
  repository cleanup or NotebookLM-video.
- Final publication, writer concurrency and protected-main push boundaries are
  unchanged.

## Boundary

This hardening protects the last **completed workflow paid-stage boundary** from a
later runner/process failure. It intentionally does not split Primary/Hybrid or
individual Coverage directions into new workflow jobs; therefore a catastrophic
runner loss in the middle of one still-running paid stage can only recover from
the previous completed checkpoint. Changing that would require a broader
retrieval-orchestration redesign and is outside this bounded change.
