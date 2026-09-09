# Step 5 independent evidence review — 2026-09-08

**Verdict: FAIL.** This is a read-only, offline assessment of the three named
modules as present before the planned observation-ID-only update. It does not
assess the new `source_value_period.py` aggregation.

## Scope and baseline

- Repository: `/workspace/scratch/b0ff9bbd56a1/ai-svodki-step05`
- Claimed remote checkpoint: `1cdbb4bafa834d214edaa4a770d9a838242538cc`.
  Its object is not present in this local clone, so this audit evaluated the
  supplied working files, as instructed.
- SHA-256 at inspection: `source_pulse_value.py`
  `d0b9ed44386da4d42017a63fbce406f79bf2d71a67252793a8df459c0bfb3b4b`;
  `source_pulse_trace.py`
  `88439856812443aaf202c1d257150243333ded4197cf3611ebe957afacf612db`;
  `source_value_publication.py`
  `e97a8b7c8294c09cfaed312b6b6059ddcdcff79ae96f405d027596460e746764`.
- The controls use no network, no API, no Git mutation, and do not write into
  the repository. Reproduce with:

```bash
python /workspace/scratch/b0ff9bbd56a1/audit-work/step05-independent/independent_controls.py
```

All four controls fail; the result is saved in
`independent_controls_result.json`.

## Material evidence-attribution defects

1. **Malformed disposition rows become a confirmed zero.**
   `records()` filters non-object members out of `lead_dispositions` but
   `promotion_available` remains true. With `['not-a-disposition-object']` and
   an empty accepted-URL list, output is `confirmed_promoted_count=0`,
   `promotion_evidence_complete=true`, and no evidence gap. This is a
   false-zero attribution: corrupted source→candidate evidence is reported as
   a complete observed zero. Relevant logic: `source_pulse_value.py:20-34,
   55-84`.

2. **Duplicate promotion artifacts become a complete source→candidate join.**
   Two identical promoted dispositions and duplicate accepted URLs are reduced
   to one by `set()`. Output claims one confirmed promotion, complete evidence,
   and no gap. Duplicated disposition records are therefore not preserved as
   unknown/malformed. Relevant logic: `source_pulse_value.py:34,55-71`.

3. **Null event-identity fields are accepted as an exact selected story.**
   A candidate and selected story with the same recycled ID and URL but all five
   comparison fields (`organization`, `topic`, `event_type`, `published_date`,
   `published_at`) explicitly set to `null` produce
   `editorial_selected=1`, `assembled_stories=1`, and no gap. Presence plus
   equality of nulls is not sufficient structural story identity. Relevant
   logic: `source_pulse_trace.py:17-27,48-54`.

4. **Repository-page validation does not bind a source URL to its story.**
   A committed page that contains headline A linked to B's URL and headline B
   linked to A's URL passes `verify_page()`. It checks global page text and a
   global set of links, then `repository_published` inherits
   `assembled_stories`. Thus it can falsely attribute a Pulse source to the
   committed main-content block for that story. It still correctly leaves FTP
   delivery unknown. Relevant logic: `source_value_publication.py:44-55` and
   `source_pulse_value.py:149-154`.

## What is supported

The modules correctly keep FTP delivery as `unknown`; this review does not ask
for semantic identity beyond the stated structural evidence. The failure is
that the stated structural evidence itself accepts malformed, duplicate, empty
identity, or cross-wired page artifacts as complete/positive evidence.

## Acceptance conditions

Before acceptance, malformed rows and duplicate accepted/disposition records
must yield explicit gaps and downstream `null`, story identity needs meaningful
typed values (or another non-null canonical identity commitment), and the
committed-page check must establish headline/source co-location within each
story's content structure. The planned observation hash alone does not repair
any of these joins.
