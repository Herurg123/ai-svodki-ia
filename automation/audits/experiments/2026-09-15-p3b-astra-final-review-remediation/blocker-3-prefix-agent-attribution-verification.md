# Astra blocker #3 — prefix-agent attribution verification

Date: 2026-09-15

## Scope

This record verifies the third blocker from the independent Astra review of PR #179 old head `769a981b31a87efc1384f125b4e2a91dc5c4700d`:

> Prefix organization matching incorrectly accepts a foreign passive agent such as `DeepSeek's rival OpenAI` as attribution to `DeepSeek`.

Required counterexample:

```text
DeepSeek says V4 Pro was replaced by V4.1 Flash by DeepSeek's rival OpenAI
```

Signal organization:

```text
DeepSeek
```

The correct result is fail-closed attribution rejection. A signal-organization prefix inside a longer foreign agent surface is not exact event attribution.

This follow-up starts from `main` merge commit `28241c86e9ecd5491aa6113db510b3422a537154`, after PR #182 was merged. No separate blocker-3 branch or open PR existed when the work started.

## Historical baseline reproduction

The reviewed SHA `769a981b31a87efc1384f125b4e2a91dc5c4700d` implemented passive-agent checking by constructing an organization boundary pattern and applying `re.match()` to the captured agent string.

For the required agent surface:

```text
DeepSeek's rival OpenAI
```

the historical pattern is effectively:

```python
(?<![\w])DeepSeek(?![\w])
```

A deterministic offline reproduction gives:

```text
old prefix matcher: True
agent normalized identity: deepseeksrivalopenai
signal normalized identity: deepseek
current exact identity equality: False
```

The old check therefore accepted the foreign possessive surface because the apostrophe after `DeepSeek` satisfies the non-word boundary. The bug was not in replacement direction: it was the prefix attribution predicate itself.

No production API, paid Web Search, or Terra call was used for this reproduction.

## Current runtime assessment

On current `main`, `automation/scripts/weak_source_exact_binding_v4.py` contains `_agent_matches_signal_organization()` and uses it from `_passive_attribution_reason()` for both:

- launch/update passive attribution; and
- replacement trailing-agent attribution after the complete directed replacement span.

The helper strips only ordinary wrappers/whitespace and then requires full normalized identity equality:

```text
normalized_org(cleaned_agent) == normalized_org(signal organization)
```

Therefore:

```text
DeepSeek -> deepseek
DeepSeek's rival OpenAI -> deepseeksrivalopenai
```

and the Astra counterexample fails closed as `organization_event_attribution_mismatch`.

The same binder also retains `organization_event_attribution_mismatch` as a same-identity cross-claim veto, so a clean duplicate claim cannot rescue a foreign-attributed claim of the same exact event identity.

Conclusion: blocker #3 existed on the old Astra-reviewed SHA, but the production runtime on the current `main` already contains the semantic remediation. This follow-up intentionally does not make a new production runtime change merely to manufacture a diff.

## Permanent regressions strengthened by this follow-up

`automation/tests/test_p3b_replacement_passive_attribution_hotfix.py` is extended without changing production code.

### Replacement negative controls

The required Astra counterexample remains covered at both binder and active processing/admission levels:

```text
DeepSeek says V4 Pro was replaced by V4.1 Flash by DeepSeek's rival OpenAI
```

Additional exact-agent contamination controls are added:

```text
... by DeepSeek rival OpenAI
... by DeepSeek and OpenAI
... by DeepSeek / OpenAI
... by DeepSeek-owned OpenAI
... by DeepSeek's OpenAI team
```

Every surface must return binder rejection `organization_event_attribution_mismatch`, return no P3b candidate, report `candidate_count=0`, and never report `bound_candidate`.

### Positive exact-agent / case normalization

The clean replacement control remains positive, and a lowercase exact organization control is added:

```text
V4 Pro was replaced by V4.1 Flash by DeepSeek
V4 Pro was replaced by V4.1 Flash by deepseek
```

Both are required to preserve `exact_event_identity` and active candidate admission when the remaining lifecycle/Freshness prerequisites are satisfied.

### Cross-claim rescue

The same-identity surface containing a clean duplicate plus the Astra foreign-attributed claim is asserted at both binder and active admission levels. The result must remain non-positive with zero returned candidates.

### Launch/update passive attribution

Existing lifecycle fixtures are reused rather than expanding production grammar. The same full-agent equality rule is exercised for:

```text
V4.1 Flash was launched by DeepSeek
V4.1 Flash was launched by DeepSeek's rival OpenAI
V4.1 Flash was updated by deepseek
V4.1 Flash was updated by DeepSeek and OpenAI
```

Clean exact organization remains positive; contaminated agents fail closed at binder and active admission levels.

## Evidence-version decision

The durable request contract remains:

```text
VERSION=2
```

The active binder semantic proof marker remains:

```text
EVIDENCE_VERSION=3
```

No bump to evidence v4 is justified. The current evidence-v3 binder on production `main` already uses complete normalized agent identity equality. The historical prefix semantics existed on the old PR #179 reviewed head before the final merged remediation; no reachable current evidence-v3 positive snapshot path was found that would require a new semantic migration boundary.

The existing stale positive evidence-v2 revocation path from blocker #1 remains untouched.

## Protected non-scope and invariants

No production runtime file is modified by this follow-up. In particular, it does not change:

- blocker #1 stale processed candidate revocation or optional-slot recovery;
- blocker #2 punctuation/separator attribution grammar;
- query wording or provider/model routing;
- Primary, Source Pulse, Agency Rescue, Hybrid, or Coverage allocation;
- Event Freshness or Source Freshness;
- archive/dedupe, ranking/editorial, publication validators, or optional-slot handoff;
- P3a;
- lifecycle/version identity semantics beyond testing the already-merged exact-agent boundary.

Search invariants remain:

- Primary max = 12;
- Agency Rescue max = 1;
- Hybrid = 4 normally / 5 only on the approved double-regional-gap path;
- Coverage = 6 mandatory + existing optional seventh;
- Coverage max = 7;
- no eighth Coverage search;
- whole-pipeline ceiling = 24 normal / 25 conditional double-gap.

`automation/scripts/ensure_story_coverage_p3a.py` remains byte-identical with blob:

```text
14f0e38f57b9285a949ec5083136999c12c81bc0
```

The canonical P3b matrix remains exactly 20 cases; blocker #3 stays a supplemental Astra remediation control rather than creating case 21.

## Documentation assessment

The root remediation record for this Astra review already documents H3, full normalized passive-agent equality, launch/update reuse, cross-claim veto, `VERSION=2`, `EVIDENCE_VERSION=3`, and unchanged 7/24/25 budgets. The canonical P3b spec likewise already requires foreign passive/trailing attribution to fail closed. Because this follow-up changes no production contract, root `README.md`, `automation/README.md`, `automation/ARCHITECTURE.md`, `AGENTS.md`, and the canonical validation matrices do not require semantic edits.

## Final verification contract

The PR may be considered ready only after its exact final head has:

1. the focused blocker #3 regression suite green;
2. the relevant P3b/Astra regression suites green;
3. full `python -m unittest discover -s automation/tests -v` green;
4. Main CI / Offline production checks green;
5. Required PR Gate green;
6. expected Video CI behavior for the changed paths;
7. P3a blob still equal to `14f0e38f57b9285a949ec5083136999c12c81bc0`;
8. canonical P3b matrix still exactly 20 cases;
9. `VERSION=2` and `EVIDENCE_VERSION=3` unchanged;
10. Coverage max 7, no eighth search, and whole-pipeline ceilings 24/25 unchanged.

The exact final commit SHA and exact-head Gate/run are recorded in the PR body after GitHub computes the final content-addressed commit and the corresponding Actions run. Embedding the SHA of the commit that contains this file inside the file itself would be self-referential and would necessarily change that SHA.

Do not merge this PR. A new independent Astra review should evaluate the exact unchanged final head before any owner merge decision.
