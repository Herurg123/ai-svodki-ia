# 2026-11-02 — seventh Coverage search: validated eligibility preflight

## Scope and preregistered hypothesis

Incident: original production [run 41375795360](https://github.com/Herurg123/ai-svodki-ia/actions/runs/41375795360), attempt 1. Its six mandatory Coverage directions completed, and exactly one optional slot remained unused. The old sentinel counter treated any raw candidate with `recommendation=include|consider` as eligible, whereas final `story_coverage.merge_candidates` rejected both (date/source precision). This masked zero-pool state and suppressed the seventh search.

**Change:** `ensure_story_coverage_v8._validated_eligible_pool` uses `merge_candidates` on a copy of the existing and added candidates *before* deciding whether the optional seventh search is warranted. It also supplies the validated-only list to existing agency source-health selection. No additional search slot or query string is introduced. Exact original response bytes are not modified.

## Independent assistant-owned local stand

- **External production evidence:** local original `production-2026-11-02-original-artifact.zip` archived from run 41375795360, SHA-256 `d16466632b81da6cde68e58ac07867eaa35201fa4b27b31e82f8f17e9bed065c`.
- Inputs read **directly from the original archive**: `production-daily/coverage-audit-output.txt`, `production-daily/coverage-audit.json`, `2026-11-02/candidates.json`. Exact window: `2026-10-31T05:06:28+03:00` to `2026-11-02T05:06:26+03:00`.
- **Stand type:** fully offline, independently coded **policy-equivalence oracle** (not an import of production modules), executed on assistant-owned local Python. Its purpose is to challenge the proposed decision boundary against the frozen data and controlled negatives. Actual edited production functions are separately covered by repository unit tests and CI. No Terra inference was used or required, because prompt wording and provider-dependent search output are unchanged. No OpenAI API, paid Web Search, external HTTP or GitHub Actions production run was used for this experiment.

| Case | Historical/raw count | Correct validated count | Expected sentinel | Local stand |
|---|---:|---:|---|---|
| Original Northflank + ChatGPT Chat/Work, **after already-merged PR #238 date correction** | 2 | 1 | no (valid Chat/Work remains) | PASS |
| Same frozen record, **controlled negative**: Chat/Work verification changed to unconfirmed | 2 | 0 | yes, exactly one unused seventh slot | PASS |
| Zero valid, 7/7 budget already consumed | 2 | 0 | no | PASS |
| Zero valid, mandatory directions incomplete | 2 | 0 | no | PASS |
| Zero valid, previously completed sentinel already present | 2 | 0 | no | PASS |
| Zero valid, maximum Coverage budget below 7 | 2 | 0 | no | PASS |
| Identical candidate offered twice | 2 | 1 | no | PASS |
| Frozen original candidate payload mutated by preflight? | n/a | n/a | **no mutations** | PASS |

**Crucial distinction:** The 2026-11-02 historical production rejected both candidates before PR #238 fixed date-only precision. After that fix, the original Work story *correctly* qualifies, so the current system **must not** spend a seventh search merely to replay an outdated error. The controlled negative validates the formerly broken zero-after-filter branch.

The local oracle wrote a JSON report with the above results; the historical original ZIP is not recopied into the repository and its contents/hashes remain unchanged.

## Tests on the actual modified production code

Four new tests extend `automation/tests/test_recall_sentinel.py`:
- exact Nov 2 window + verified Work admission, read-only saved payload;
- exact Nov 2 window + controlled unconfirmed Work → one mocked sentinel, budget 6→7 and remaining 1→0;
- exhausted seventh-slot case → zero calls;
- duplicate matched to previously accepted candidate → counted once.

Existing cases cover six mandatory directions, already-completed/old-version sentinel recovery, failures before/after provider calls, search budget, source health and durable slot ownership. Full PR Gate must pass before merge, and a post-merge Main CI must remain green.

## Architecture invariants

- `maximum_audit_web_search_calls=7`; mandatory directions=6; optional seventh shared with existing P3b/agency rescue priorities; maximum **never** increases to 8.
- Overall search ceiling 24 normal / 25 double-gap unchanged.
- `story_coverage.merge_candidates` remains final admission; no bypass for stale, unsupported, unverified, outside-window or duplicate stories.
- This is a local deterministic preflight, **not** a new paid API call. No model or query text changes.
- Saved sentinel evidence is reused; completed or ambiguous requests are not repeated. Failure remains fail-closed.
- Potential cost delta: a seventh call may now occur when old logic incorrectly skipped it, but still inside the existing approved daily search budget.

## Verdict

Independent local decision-oracle replay: **PASS** (8 controls). Production-code status to be filled by CI; this evidence report alone does not claim production API equivalence or a real paid model result.
