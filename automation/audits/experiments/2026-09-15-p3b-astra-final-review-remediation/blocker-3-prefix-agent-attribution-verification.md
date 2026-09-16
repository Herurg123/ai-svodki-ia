# Astra blocker #3 — prefix-agent attribution verification

Date: 2026-09-15

> **Superseded status:** this record describes the initial PR #183 verification head `7b2fce57695b215399cc68a817af9648d4c8179b`. A later independent Astra review of that exact head returned `REQUEST CHANGES` with four reproducible blockers, including additional passive-attribution cases. The active remediation record is `final-review-four-blockers-remediation.md`. Statements below about no production change and `EVIDENCE_VERSION=3` are historical to the initial verification and are not the final PR contract.

## Scope

This record originally verified the third blocker from the independent Astra review of PR #179 old head `769a981b31a87efc1384f125b4e2a91dc5c4700d`:

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

This follow-up started from `main` merge commit `28241c86e9ecd5491aa6113db510b3422a537154`, after PR #182 was merged.

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

A deterministic offline reproduction gave:

```text
old prefix matcher: True
agent normalized identity: deepseeksrivalopenai
signal normalized identity: deepseek
current exact identity equality: False
```

The old check therefore accepted the foreign possessive surface because the apostrophe after `DeepSeek` satisfied the non-word boundary. No production API, paid Web Search, or Terra call was used.

## Initial runtime assessment at `7b2fce5`

At the initial verification head, `automation/scripts/weak_source_exact_binding_v4.py` already contained `_agent_matches_signal_organization()` and used full normalized equality for both launch/update passive attribution and replacement trailing-agent attribution after the complete directed replacement span.

That correctly closed the original possessive-prefix counterexample and motivated the first PR #183 test-only scope. The later independent review proved that this assessment was incomplete: nested/mixed separators, comma-separated co-agents, and a historical-background cross-claim case still escaped the surrounding parser/control flow even though the equality helper itself was strict.

## Initial regressions

The initial follow-up added or strengthened:

- the possessive-prefix counterexample at binder and active admission levels;
- `DeepSeek rival OpenAI`, `DeepSeek and OpenAI`, `DeepSeek / OpenAI`, `DeepSeek-owned OpenAI`, `DeepSeek's OpenAI team`;
- zero-candidate diagnostics;
- lowercase exact-agent positive control;
- clean duplicate + foreign-attributed same-identity veto;
- passive launch/update exact-agent controls.

Those regressions remain useful but are no longer the complete acceptance set. The later final-review remediation additionally covers nested/mixed separators, comma-separated agent lists, full-date historical background, stale cleanup across request-context drift, and semantic evidence migration through evidence-v3.

## Evidence-version history

At initial head `7b2fce5`, the durable request contract and semantic marker were:

```text
VERSION=2
EVIDENCE_VERSION=3
```

The initial assessment concluded that no evidence-v4 bump was necessary. The later independent review invalidated that conclusion by demonstrating false-positive surfaces that could be persisted as evidence-v3 positive processed snapshots.

The final remediation therefore keeps durable `VERSION=2` but advances current semantic proof to:

```text
EVIDENCE_VERSION=4
```

Evidence-v1, evidence-v2 and evidence-v3 positives are stale under the remediated runtime. See `final-review-four-blockers-remediation.md` for rationale and controls.

## Preserved invariants

Across both the initial verification and later remediation:

- query wording and provider/model routing are unchanged;
- Primary, Source Pulse, Agency Rescue and Hybrid allocation are unchanged;
- Event/Source Freshness and archive/dedupe policy are unchanged;
- P3a remains outside semantic mutation;
- Coverage remains six mandatory + existing optional seventh, maximum 7, no eighth search;
- whole-pipeline ceilings remain 24 normal / 25 conditional double-gap;
- canonical P3b matrix remains exactly 20 cases.

Expected preserved P3a blob:

`14f0e38f57b9285a949ec5083136999c12c81bc0`

## Final verification boundary

This historical record is not merge evidence for the later head. The final exact PR #183 head must separately pass the full offline PR Gate, retain the invariants above, and receive a fresh independent review after the four-blocker remediation.

Do not merge PR #183 based on the initial `7b2fce5` verification.