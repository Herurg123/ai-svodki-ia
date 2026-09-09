# Step 5 independent offline acceptance — 2026-09-09

**Verdict: PASS** for checkpoint `b328d4169d719f3367b1c0e15daafe3d58175329` within the defined autonomous diagnostic CLI scope.

## Scope and method

Read-only review of the following checkpoint files:

| File | SHA-256 |
|---|---|
| `automation/scripts/source_pulse_value.py` | `ab0ace1c82f49b1d6db132f7a84abe126082787609f994258fbb89ea0316af5e` |
| `automation/scripts/source_pulse_trace.py` | `4efdcd8316f54717ec2218ccc7ca205d75a9a12046d6fc13f7ccef865a2febe0` |
| `automation/scripts/source_value_identity.py` | `528b15a4fc63c75ac8fd476a85a72aea7741ce1753907e27682f95b4ae76a8db` |
| `automation/scripts/source_value_publication.py` | `22c12e9f3979fa62cf520b5288f7f363745dc7db8c73b41416f157f0dd4fa54b` |
| `automation/scripts/source_value_period.py` | `1d75176489139afa4b7e73b1df8039440f7d144086d58a44b718bed311645bd4` |

I read `AGENTS.md`, the Source Value inventory section of `automation/ARCHITECTURE.md` (lines 835–865), the resumed conditions, and the preserved 2026-09-08 FAIL and controls. The baseline `c9c151f25aeb2a8620222d36a5943befe9ae8a51` was compared using `git show` only; its original producer/trace hashes are retained in this directory. The current tree still matches the requested checkpoint.

`independent_controls.py` contains 16 independent, reproducible, local controls. It writes only `independent_controls_result.json` here. Execution used no source polling, network/API calls, production imports, checkout/commit/ref mutation, or project-file writes.

## Results

All 16 controls passed; `failed_controls` is empty.

- A non-object disposition, invalid disposition URL, accepted/disposition conflict, and duplicate accepted URLs or disposition URLs produce explicit gaps and `confirmed_promoted_count=null`. They do not yield a false zero or positive.
- Recycled candidate/story IDs with null identity fields are unresolved. Meaningful nonempty `organization`, `topic`, and `event_type`, a valid source date, and a valid date-only or timezone-bearing timestamp are required.
- Cross-wired URLs, a link in hidden template markup, and a link in the next story block all fail publication evidence. Every ordered visible `<h3>` block must contain its own exact headline and each exact story URL.
- Exact same-day copies and recovery metadata variants give one release observation and no double count. Differing source-observation IDs and differing final trace IDs leave totals unknown (`observed_total=null`, `complete_total=null`) instead of choosing an observation.
- A synthetically valid committed repository proof takes priority over a conflicting local draft trace. Invalid publication proof cannot promote a draft. FTP remains outside the evidence and unknown.
- The no-trace case has `observed_total=null`, not zero.
- Preserved reduced fixtures continue to produce NVIDIA 2026-09-02 `editorial_selected=1`, Yandex 2026-09-06 `editorial_selected=0`, and the saved Yandex no-promotion input has confirmed promotion count zero only with complete, unambiguous promotion evidence.

The complete observed values and gaps are in `independent_controls_result.json`.

## Architecture/dependency conclusion

This change conforms to the documented boundary. The five modules form an offline diagnostic chain: producer -> trace/identity/publication evidence -> period reducer. They are not referenced by active `.github` workflows or other production orchestration scripts; references outside these modules are tests/documentation. The implementation preserves the required properties: no network or paid calls, no retrieval/search ranking or source disabling, no alteration of source freshness/editorial/recovery semantics, no publication action, and FTP delivery unknown.

The repository-publication branch reads only a specified local `origin/main` commit and requires byte-identical Pulse input, so a worktree draft or an unmerged commit is not evidence. The reducer uses observation/trace identities and explicit completeness denominators; it does not infer missing observations as zero.

## Limits

This acceptance covers only the requested Step 5 diagnostic CLI contract and saved fixtures. It does not certify FTP delivery, factual correctness of stories, source polling, search/ranking changes, production workflows, or any deferred/future item outside the stated scope.
