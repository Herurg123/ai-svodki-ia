# Eighth-review two-blocker remediation

## Source review

A fresh independent review of exact SHA `943e2e034368d383b83be9431a76dd56c7399a4b`
returned `REQUEST CHANGES` with two active P3b binder defects. This record is an
evidence pointer only; the review text, regression names and green CI are not
correctness proof.

### Blocker 1: explicit current full date could still be laundered by cited history

Reproduction on the reviewed SHA:

`DeepSeek launches V4.1 Flash | On September 15, 2026, DeepSeek did not launch V4.1 Flash, citing reporting from September 1, 2025`

The v4 binder recognized lexical current markers such as `today` and `now`, but a
full current date was only treated as "not historical" by year. It did not become
a relation-local current marker. A later old cited date could therefore make the
negated relation historical and allow a separate clean positive claim to win.

Remediation:

- parse matched English full dates into real `date` values rather than comparing
  only their year;
- recognize a non-past full date in the local action prefix as an explicit current
  relation marker when it is not merely reporting-time attribution;
- for negated/uncertain/post-state safety vetoes, use a conservative non-past-date
  guard so an old cited date cannot demote an explicitly dated contradiction to
  historical context;
- keep the reporting-time historical control (`On <today>, DeepSeek said it
  launched ... on <old date>`) nonpositive;
- treat an actually past full date as historical even when it is earlier in the
  same calendar year.

### Blocker 2: punctuation after a closing wrapper could hide a foreign agent

Reproduction on the reviewed SHA:

`DeepSeek: [V4 Pro was replaced by V4.1 Flash] / by OpenAI`

The trailing-agent grammar accepted a fixed punctuation whitelist. A slash,
bullet, Unicode ellipsis or equals sign between the complete replacement span and
`by OpenAI` made the matcher return no agent.

Remediation:

The matcher now skips only a run of non-word characters before a directly adjacent
`by <agent>` attribution. This covers neutral punctuation and wrapper combinations
without permitting the parser to jump over substantive words. The complete agent
surface is still retained for exact organization comparison, and `by DeepSeek`
remains the positive control.

## Regression boundary

`automation/tests/test_p3b_astra_eighth_review.py` covers:

- explicit current full date plus old cited date after the action;
- old evidence date before the explicit current date;
- old evidence wording between current date and negated action;
- `based on` and `referencing` neighbors;
- reporting-time and direct historical controls;
- a real past full date independent of calendar-year equality;
- `/`, `•`, `…`, `=` and stacked neutral punctuation before `by OpenAI`;
- positive `by DeepSeek` and a guard proving punctuation normalization does not
  skip intervening words;
- direct binder and active P3b processing assertions.

## Preserved contract

This remediation changes only the active binder plus supplemental regression/audit
evidence. It does not change query generation, providers, routing, ranking,
Freshness, publication policy, P3a, search budgets, provider retries or stale-page
refetch behavior. Canonical P3b matrix membership is unchanged.

Durable request `VERSION` remains `2`. `EVIDENCE_VERSION` remains `6` because v6
is still confined to this open, unmerged PR and has not become a production
positive-proof contract. Production positive evidence v1-v5 remains stale relative
to v6; no new provider search, retry or mutable-page refetch is authorized by
stale-proof handling.

No production/paid external calls are required for this remediation. A new exact
head and PR Gate must pass before another fresh independent final review. Do not
merge on the basis of this audit record or the author's own validation.
