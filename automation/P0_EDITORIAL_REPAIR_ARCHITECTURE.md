# P0: durable Coverage editorial-repair recovery

Status: active production contract from 2026-09-11.

This note documents the narrow P0 repair introduced after the 2026-09-11 recovery incident. It changes recovery/completion semantics only. It does not increase Primary, Agency, Hybrid or Coverage Web Search budgets, does not weaken Event/Source Freshness, and does not change editorial ranking.

## Incident and required invariant

The 2026-09-11 paid Research and first Editorial had already completed when Mandatory Coverage added a candidate and required a saved-research editorial rerun. The recovery workflow correctly reused the paid same-day artifact and skipped full Research, but the recovery path did not have the pinned OpenAI text runtime available. The required rerun failed before provider admission with `ModuleNotFoundError: No module named 'openai'`, after which the pre-repair digest could still be published.

The P0 invariant is therefore:

1. already-paid full Research is never repeated merely to repair Coverage editorial completion;
2. once Coverage creates a required editorial-repair obligation, that obligation survives process/recovery boundaries;
3. publication is fail-closed while that obligation is unresolved;
4. an ambiguous provider outcome is never automatically retried;
5. a durable provider response is replayed offline rather than sent again.

## Durable state and request identity

`editorial_repair_guard.py` owns a same-day journal under `automation/preview/production-daily/`. Before the protected provider boundary it binds the exact persisted Coverage research SHA-256, the post-Freshness candidate-pool identity, archive identity, prompt/schema/model request contract and release date.

The state machine is intentionally small:

- `required`: the completion obligation exists but provider admission has not started;
- `request_started`: provider admission may have happened;
- `response_saved`: the raw provider response is durably saved and can be replayed without transport;
- `validated`: the saved response passed the editorial/artifact contract and exactly matches the final raw editorial output.

A failure proven to occur before `request_started` is retryable. `request_started` without a durable response is `unknown-after-request` and is never automatically sent again. `response_saved` is always parsed/validated from the saved bytes on recovery.

The only legacy admission exception is the proven 2026-09-11 missing-SDK failure, because that failure occurred before provider construction/admission. The exception is deliberately narrow and does not generalize arbitrary historical errors into safe retries.

## Protected editorial-only transport

`run_editorial_repair.py` executes only the saved-research editorial completion path. The protected SDK callback has retries disabled (`max_retries=0`) so the durable journal, not an SDK retry loop, owns at-most-once semantics. The repair does not authorize Web Search and does not repeat Primary/Agency/Hybrid/Coverage retrieval.

The raw response is written and fsynced before parse/validation and before the journal can advance to `response_saved`. If validation later fails, the same response is replayed offline. A second provider request is not used as a repair mechanism.

## Recovery and same-bundle evidence

`recover_digest_artifact.py` may restore repair journal/response/merged Coverage research only from the exact extracted artifact bundle that supplied the selected dated recovery source. A same-date sibling artifact is not interchangeable evidence.

A recovered `full` artifact is downgraded to `partial_editorial` only when there is positive same-day evidence that Coverage can still require text completion, or an unresolved P0 repair journal exists. Missing optional diagnostics alone do not downgrade an otherwise current full artifact. The downgrade makes the pinned text runtime available while preserving the no-repeat full-Research contract.

Historical artifacts without a P0 journal remain recoverable. If P0 state is present, its source identity and integrity are mandatory and recovery fails closed on ambiguity.

## Publication guard

`validate_digest_artifact.py` and the Coverage entrypoint consult the same durable repair state. Any unresolved repair obligation blocks publication even if an older digest is otherwise structurally valid. A seven-story pre-repair digest therefore cannot silently erase a later Coverage completion obligation.

Only `validated` clears the P0 publication block. The final raw editorial must exactly correspond to the validated saved response.

## Compatibility seam and removal condition

The active public consumers remain:

- `scripts/ensure_story_coverage.py` for Mandatory Coverage and editorial completion;
- `scripts/recover_digest_artifact.py` for same-day paid-stage recovery;
- `scripts/validate_digest_artifact.py` for publication safety;
- `tests/test_sep11_editorial_repair_recovery.py` plus the existing offline suite.

The temporary `ensure_story_coverage_pre_p0.py`, `recover_digest_artifact_pre_p0.py` and `validate_digest_artifact_pre_p0.py` files preserve the historical import/monkeypatch surfaces while the P0 state machine is introduced. They are not independent production policies.

Removal target: no earlier than 2026-10-03, and only after a consolidated implementation passes the same-bundle recovery matrix, public/private hook compatibility tests, the interruption matrix, the full offline suite and Required PR Gate without changing paid/search ceilings.

## Acceptance matrix

The offline acceptance matrix covers at least:

- no added Coverage candidate / no repair obligation;
- one added candidate requiring editorial completion;
- pre-request failure and safe retry;
- `request_started` without response and no retry;
- response persisted before journal transition and offline replay;
- response-saved validation failure and offline replay;
- post-Freshness candidate-pool mutation rejection;
- request-contract mutation rejection;
- legacy 2026-09-11 missing-SDK admission;
- old pre-repair digest with pending repair blocked from publication;
- same-bundle recovery only;
- no second full paid Research stage.

All acceptance work for this P0 change is offline/fixture based. A production API call or paid Web Search is not part of validation.