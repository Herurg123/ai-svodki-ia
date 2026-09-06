# Step 1 — independent usage accounting comparison

Baseline: `0e9cc144b5cd8c039eee6be52fb52e4ee072fa31`.
Authorization: owner instruction of 2026-09-06 permits sequential local changes,
independent experiments, DOCX reports, PR creation and exact-head merge after
success. No production API spend is authorized.

Freeze before implementation:

1. Replay the saved September 2, 4 and 5 artifacts against the independently
   compiled September 5 audit ledger, not an oracle produced by the new reducer.
   Expected text totals (input / cached / cache-write / output / responses):
   - September 2: 1271856 / 91888 / 698083 / 33355 / 25.
   - September 4: 1397084 / 91878 / 836926 / 35688 / 26.
   - September 5: 1434723 / 96969 / 848856 / 37561 / 27.
2. The final editorial-only September 5 baseline shows 136295 total tokens;
   the proposed observed whole text trajectory must show 1472284, without
   counting copied response IDs twice.
3. Controlled independent cases: copied artifacts, same-day recovery, an older
   unrelated day, multiple legitimate calls, conflicting usage, truncated
   JSON/JSONL, missing usage/cache metadata, a failed call, a hard interruption
   after start, a late validation failure after a returned paid response, and
   unwritable telemetry. No false zero or false complete-account claim.
4. Transport comparison with recording stubs must preserve exact request kwargs,
   return object identity, exception identity and one underlying call. Telemetry
   adds no API/network call, retry, selection, freshness or recovery decision.
5. Existing offline suite and relevant workflow/archive/editorial validators
   must pass. Public content must remain byte-identical to baseline.

Independent acceptance is PASS only if all above relevant checks pass. A failed
independent final experiment stops the sequence and requires a failure DOCX;
it is not followed by an unreported change to the acceptance criteria.

Implementation-format note before the independent final replay: the observer
uses atomically replaced per-attempt JSON files instead of append-only JSONL.
The interrupted/partially written journal case is tested on that actual format;
there is no historical production JSONL format to migrate. After unexpected
concurrent edits in the first working directory, the proposal was frozen into
isolated worktree `ai-svodki-astra-4f7a21`; only that fixed proposal is tested.

## Authorized correction and second acceptance

The first acceptance failed on a synthetic two-call image accounting case; it
did not demonstrate double generation in production. Work stopped and a failure
DOCX was delivered. The owner then explicitly authorized correction and resumption.
The resumed branch is `codex/audit-01-accounting-resume`, with the same main base.

Acceptance retains every original check and adds the actual image generator with
an offline transport: exactly one `n=1` call, valid cover, real recovery selection,
and unchanged cost after copying the saved cover and prior ledger. The artificial
two-call case remains labelled separately as accounting resilience. AST comparison
removes only the observer wrapper/import and its new local metadata dictionary
and report field; original transport arguments and control flow must match.

Reproduce with `replay_usage_accounting_2026_09_06.py --evidence-root <prior-audit-workspace>
--output <scratch-results>`; the evidence root contains `audit-work/` from the
September 5 audit and the unchanged `ai-svodki-ia/automation/content/` archive.
No network or production API is permitted. A second failed acceptance again stops
the sequence and requires an explanatory DOCX.
