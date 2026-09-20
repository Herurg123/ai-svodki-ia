# Sep11 remediation program: archival start-to-finish map

Status: **historical audit index / inert evidence only**  
Created: 2026-09-20  
Repository: `Herurg123/ai-svodki-ia`

## Purpose

This document preserves one durable path through the Sep11 incident and the remediation
program that followed it. It exists so a future audit does not have to reconstruct the
story from an open PR, branch names, chat history, or stale PR descriptions.

Historical files copied from PR #167 are preserved as immutable evidence. They describe
what was known on 2026-09-11 and must **not** be read as the current runtime contract.
For current behavior, use `automation/ARCHITECTURE.md`, `AGENTS.md`, the active
runtime/tests/specs, and the final merged remediation records.

No runtime, workflow, search, editorial, publication, budget or provider behavior is
changed by this archive.

## Starting point

### PR #166 — independent Sep11 release audit

- PR: https://github.com/Herurg123/ai-svodki-ia/pull/166
- reviewed/merged head: `0a66b21918046b1020e4794519e2b1376c057244`
- merge commit: `5d15b0f0a220f55a6753412b6e712fd2cd96b06a`
- merged: 2026-09-11

The audit established the Sep11 production/recovery failure surface and recorded the
initial P0–P5 priorities. In particular, Coverage could add a candidate and require an
editorial rerun, yet recovery could still complete after the repair path failed.

### PR #167 — technical follow-up / handoff

- PR: https://github.com/Herurg123/ai-svodki-ia/pull/167
- exact evidence head: `90b654c2ae3c5b7f917ac9fb63344404efbdb316`
- base: `5d15b0f0a220f55a6753412b6e712fd2cd96b06a`
- status at archival time: open, unmerged

PR #167 did **not** implement a runtime fix. It preserved the saved Coverage reports,
artifact identities, baseline probes, corrections to over-strong earlier claims, and a
detailed implementation handoff.

The following files are copied from that exact PR head into `main` as inert historical
evidence, using the same Git blobs:

- `automation/audits/experiments/2026-09-11-technical-followup/HANDOFF_TO_SOL_HIGH.md` — blob `8ab5f8347b0726749c13980783d569d406808c3f`
- `automation/audits/experiments/2026-09-11-technical-followup/README.md` — blob `b7958d51f19e957091d16c8e4f3819368817230a`
- `automation/audits/experiments/2026-09-11-technical-followup/baseline-results.json` — blob `2d46a6ea6d877231fa571b377291e46c0cb3a666`
- `automation/audits/experiments/2026-09-11-technical-followup/manifest.json` — blob `7605fd12b3ee6b38050cde445bef120faac341b3`
- `automation/audits/experiments/2026-09-11-technical-followup/probe_baseline.py` — blob `6f148220a9847a559f4010f5c326257296850eb6`
- `automation/audits/experiments/2026-09-11-technical-followup/saved-coverage-final.json` — blob `64e1d1b2c6fc3f77b41eafb99598e1f5ae3bf890`
- `automation/audits/experiments/2026-09-11-technical-followup/saved-coverage-paid.json` — blob `3333827feef0de9833bbc8032d0e39de203b94d6`
- `automation/audits/experiments/2026-09-11-technical-followup/terra-reference.md` — blob `94bf930bcd39af93d07b982349b848311b01f8b5`

The original PR can therefore later be closed or its branch removed without losing the
technical starting evidence from the canonical repository history.

## Implementation and review chain

| PR | Role in this remediation program | Head SHA | Merge commit |
|---:|---|---|---|
| #168 | P0: durable Coverage editorial-repair recovery | `e68f6899d2bc9adb9e1a1ac9023854a4c09ef5d2` | `5ae060a736d3ff0fa9550255aa4ea4c5b5083d0c` |
| #170 | P1: OpenAI feed freshness fallback | `3281da7e729eba49fc4ebd02b035661f0834a5b1` | `a6110fb0af2a1c6930464146ad6b5b697b825113` |
| #171 | Agency rescue observability diagnostics | `45a2da5a728988a559a9dcd58fed2add6dc74512` | `337a123300dbf783c7e46ffd4be8f6f9d546b2a5` |
| #172 | Preserve qualified weak-source retrieval signals | `aaa9c2564c10d31cc710e780bb0c5eea6261dc0c` | `5b0f305c431aa4e55e07df245751cd84ed2718a0` |
| #173 | Repair P3a diagnostic-only boundary | `d49c720f89e7c6b7a9fe9946a92100177faa7c4c` | `11aebb40ca8ae6e899fa87486e9af175a8db517b` |
| #174 | Make the optional Coverage slot recovery-safe | `69b8e10f696825392dcf8eea56d9ff3dd14e8d8c` | `b88f108199396e9bb0e30906d1e1b9022df9d94c` |
| #175 | Add P3b exact authoritative weak-source binding | `6435dae2ce15b023f777c090ad1c2263b5d56cc8` | `4a6a0f5dff96d24fe237eb182ba673cb54893cd5` |
| #178 | Fix fourth-review historical-control scope | `9f77d9f5145883e2a510fcb348645b6089cec66b` | `33a94a0ee28464ef622667f733158c2e56a5f788` |
| #179 | Harden replacement passive attribution | `cb1074dcee296b9c9097ea49d050c8eb7b8da50e` | `f073b1c7a84eced7610969740a20305af765fab5` |
| #182 | Verify/remediate separator attribution blocker | `174e4a0f9cf006bb7b8e80b7557d4daa4b250bb6` | `28241c86e9ecd5491aa6113db510b3422a537154` |
| #183 | Repeated independent Astra remediation of P3b exact binding through evidence-v6 | `86bab6f4f08ab6239ee6ff79fd86ad8fb4ea10fd` | `41481a7fd4feacbd812cc3de82630ca5078f23e8` |
| #184 | Final stale-positive recovery / durable-lineage remediation; active P3b v7 | `6369eee27a0e80e3d6cd77ca3419541432d9f647` | `227d06e4755ba996829c5f4636c24fe0cd0362b0` |

PR #169 (direct-push policy documentation) and PR #176 (Dzen collection behavior) were
adjacent in time but are **not** part of this Sep11 P0–P5/P3b causal remediation chain.
PR numbers #177, #180 and #181 do not resolve to pull requests in this repository.

## End state after PR #184

The durable end state represented by current `main` is:

- public Coverage orchestration: active P3b v7 over preserved v6;
- binder: `automation/scripts/weak_source_exact_binding_v4.py`;
- durable request contract: `VERSION=2`;
- semantic positive-proof marker: `EVIDENCE_VERSION=6`;
- positive evidence v1..v5 is stale relative to evidence-v6 where current recovery
  requires semantic proof;
- P3a remains diagnostic/evidence-only and its production Git blob is
  `14f0e38f57b9285a949ec5083136999c12c81bc0`;
- canonical P3b exact-authoritative-binding matrix remains exactly 20 cases;
- Coverage maximum remains 7, with no eighth Coverage search;
- whole-pipeline Web Search ceiling remains 24 normally / 25 only on the approved
  double-regional-gap path;
- recovery sanitation/replay remains zero-provider-I/O where the durable contract
  requires offline reuse;
- historical audit evidence is not correctness proof for the current runtime.

Current architecture is the authority if any historical handoff wording conflicts with
later implementation.

## How a future audit should read this history

Use this order:

1. PR #166 for the independent Sep11 production finding.
2. `2026-09-11-technical-followup/README.md` and
   `HANDOFF_TO_SOL_HIGH.md` for the frozen technical starting evidence and corrected
   scope.
3. The implementation/review chain in the table above.
4. PR #184 and its durable remediation record for the last remediation boundary in
   this chain.
5. Current `automation/ARCHITECTURE.md`, active code, specs and tests for present
   truth.

Do not infer current behavior from an old PR body, old evidence version, or historical
probe result. Those are provenance and chronology, not a substitute for re-checking the
current exact head.

## Archival provenance

This archive was created from current `main` parent `6797e0b81063b92e36f0b3d80c0239c5d3a64bb5`.
The machine-readable companion is `manifest.json`.
