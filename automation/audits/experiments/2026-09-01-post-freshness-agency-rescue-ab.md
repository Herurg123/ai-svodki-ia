# Experiment: post-freshness Agency Discovery Rescue A/B

Date: `2026-09-01`

## Question

Does the current Agency Discovery Rescue trigger produce a false healthy state when the only accepted `major_agencies` candidate is later rejected by deterministic Source Freshness?

## Constraints

- No production code was changed for this experiment.
- No user-paid API or production search budget was used.
- Saved production artifacts are the control evidence.
- Independent Reuters discovery used assistant-owned web search and is diagnostic only; it is not claimed to reproduce the production provider exactly.
- Any eventual implementation must preserve the existing one-slot Reuters rescue budget and the normal total search ceiling.

## Production control A

Saved `agency-discovery-rescue-2026-09-01.json` reports:

- `major_agencies_status = complete`
- `major_agencies_raw_count = 1`
- `major_agencies_accepted_count = 1`
- `triggered = false`
- `executed = false`
- configured rescue query: `latest AI models research chips infrastructure financing earnings business deals policy security`
- allowed domain: `reuters.com`

The one accepted `major_agencies` item was a Moonshot/Kimi K3 story sourced from AP.

Saved deterministic Source Freshness later fetched that AP page and classified the source as outside the effective window because its publication date was `2026-07-20`.

Therefore the effective fresh survivor count for the agency lane was zero even though the pre-freshness trigger saw one accepted candidate.

### A outcome

`accepted_before_freshness = 1` -> lane considered healthy -> Reuters rescue not executed -> later freshness removes sole candidate -> fresh agency lane ends empty.

## Treatment B: freshness-surviving agency health

Counterfactual treatment uses the same pipeline evidence but evaluates the rescue condition only after deterministic freshness survivorship, or uses an equivalent viability signal that is unavailable to stale candidates.

For this exact production artifact:

`accepted_before_freshness = 1`

`fresh_survivors = 0`

Therefore B would classify the agency lane as degraded and execute the already-reserved single Reuters rescue slot.

No additional theoretical budget is required. The treatment changes the trigger signal, not the maximum number of searches.

## Independent rescue-value check

Using assistant-owned web search with the same broad agency query constrained to Reuters and the production time neighborhood independently surfaced multiple eligible or potentially eligible stories, including:

- Anthropic's `$35B` cloud-computing deal with Nvidia-backed Lambda;
- the LUMI-AI supercomputer contract in Europe;
- Nvidia's `$3.5B` MediaTek investment, which production already had and would be a duplicate.

This does not prove the production provider would have returned the same ranking. It does show that the unused Reuters slot had plausible high-value recall available and was not merely a theoretical fallback with no relevant events in the window.

## Invariants checked

A code prototype based on B must preserve:

- Primary maximum: 12 searches;
- Agency Discovery Rescue maximum: 1 Reuters-only search;
- Hybrid normal maximum: 4 searches, with only the already-approved conditional fifth Hybrid when both Russia and China/Asia gaps exist;
- Coverage maximum: 7 searches;
- normal total maximum: 24, or 25 only under the existing dual-regional-gap Hybrid extension;
- source freshness and event freshness as separate gates;
- archive and intra-release dedupe;
- Source Pulse remaining zero-paid and unable to close Search-derived regional gaps;
- no sixth Hybrid search.

## Risks

Moving the trigger too late could complicate stage ordering or require re-running merge/dedupe logic. A safer implementation may be to expose deterministic freshness survivorship to the rescue decision rather than literally relocating all rescue execution after every downstream stage.

The treatment also needs a regression for the opposite case: when at least one `major_agencies` candidate survives freshness, Reuters rescue must remain suppressed so the one-slot budget is not spent unnecessarily.

## Decision

**GO for a separate production-code prototype plus offline regression tests.**

The current pre-freshness trigger is demonstrably vulnerable to a false healthy agency state. For the 2026-09-01 artifact, the sole reason rescue did not trigger was a candidate later proven stale by the pipeline's own deterministic freshness gate.

This experiment does not authorize or include the runtime change itself.
