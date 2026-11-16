# 2026-11-16 | Duplicate generic primary URL and retention-broken Editorial Repair

## Incident facts (immutable source evidence)

- Original [run 43790005874](https://github.com/Herurg123/ai-svodki-ia/actions/runs/43790005874), failed first Coverage completion after all six mandatory passes and seven Web Search operations; Research and initial Editorial completed. No cover/FTP yet.
- Original failed artifact `daily-production-2026-11-16`, ID `14191919661`, downloaded unchanged; ZIP SHA-256 `018d36ed353cba592caa7ca86ad404e10dbea23bf94e9e0c6315212c4813a25c`. Research checkpoint ID `14192825128` also exists.
- Failure in the protected pre-request Editorial rerun: `cand-006: основной URL уже присутствует в архиве, но кандидат не помечен как update`. `cand-006` concerned Huawei openPangu-2.1-Pro but used shared Startrise model catalog `https://www.startrise.io/models` as primary. The source was already in archive, but the original model item has distinct authoritative Huawei documentation. **No inference of an authorized material update** is made; the invalid candidate is excluded and the rest retained.
- Saved durable journal `editorial-repair-2026-11-16.json`: state `failed_before_request`, `request_sha256=null`, `response_sha256=null`, model `gpt-5.6-terra`. It proves that no second paid Editorial request was sent during the failed coverage stage.
- Additional attempts [43793845090](https://github.com/Herurg123/ai-svodki-ia/actions/runs/43793845090) and [43796102152](https://github.com/Herurg123/ai-svodki-ia/actions/runs/43796102152) reported `EditorialRepairError: editorial repair input changed: archive_sha256` after the repository's retention cleanup. Neither completed the needed Editorial call.

## Independent stand on frozen Nov 16 evidence

Assistant-owned Python offline policy-equivalence stand consumed original ZIP, its saved editorial prompt and merged Coverage candidate pool. **No network, Terra inference, external requests, paid API or production run.** Its purpose is to disprove unsafe recovery hypotheses and quantify the effect of the proposed rule. Edited production Python is independently tested by PR Gate.

- Full saved editorial prompt embedded archive has 121 dated items. Its canonical SHA-256 is **`284c76f09c502962487f1a6328bb483cb85be5ded1207ce5503e2f3565b08a1a`**, exactly the sealed v2 journal's archive SHA.
- Retention-only simulation deleted the original 2026-10-13 item (34 days before the 2026-11-16 publication date), retaining identical all other rows in order. Its archive SHA changes, but the original sealed archive is exactly reconstructable from the prompt. Positive replay PASS.
- Negative controls PASS: removal of a recent story, insertion of a new story, modification of a retained story, change of archive origin, reorder, or tampering with the saved prompt/snapshot does not authorize replay. Unknown provider outcome is explicitly rejected by production helper.
- Original merged pool contained **7 candidates**, one (`cand-006`) with `archive_status=none` and primary URL already archived. It is excluded without fabricated update classification, while the other 6 candidates remain; original research and signed journal unchanged. PASS.
- Model comparisons were not attempted; retrieval prompts and provider configuration have not changed.

Standalone stand result: **14/14 safety and recovery controls PASS**. It uses an independent policy-equivalence oracle on the original ZIP; it is not described as actual production-code integration or a paid end-to-end digest. The local stand and JSON report remain assistant-owned artifacts, not faux original repository snapshots.

## Production-code change

- `generate_digest_preview.sanitize_research_candidates` excludes non-update candidates with already archived primary URLs and records `reason_code=archived_primary_without_update` in `research-filtered-out.json`. Strict `validate_research` and `validate_digest` still block invalid archived links; valid `update` and all other candidates remain available. No changes to paid research output.
- `editorial_repair_guard.select_bound_archive_for_replay` retrieves an exact journal-verified v2 source snapshot only when the current archive is a retention-only deletion of identical records dated at least 32 days earlier. Modified/reordered/new/recently deleted stories and missing proof remain blocked; unknown API outcome always blocked. New journals optionally preserve their proven snapshot.
- `ensure_story_coverage_p0.rerun_editorial` uses the **same** verified archive path to prepare the journal and launch the protected Editorial child; `run_editorial_repair` binds `generate_digest_preview.ARCHIVE_PATH` to that already authenticated archive. The request hash/response replay contract and at-most-once guard stay unchanged.
- `restore_state_from_bundle` also restores a preexisting sealed snapshot. Research, Coverage, Hybrid, Image, FTP workflows and maximum search/paid limits remain untouched.

## Verification gates and limits

- New regression tests in `automation/tests/test_nov16_retention_bound_editorial_repair.py` cover signed snapshot recovery and integrity, dangerous changes, no transport, the public Coverage rerun command and child's actual archive binding, and deterministic source exclusion without fabricated update.
- Existing broad regression suite: PR Gate required before merge. A green suite establishes local validation, not a successful live paid editorial request.
- **Recovery instructions (not automatically executed):** choose `daily-production-2026-11-16` from run `43790005874`, `publication_date=2026-11-16`, `recovery_run_id=43790005874`, `publish=true`, `force_fresh_research=false`. The published RSS gate must still allow it. Explicit paid authorization is required for the one outstanding Editorial and one Image API call; no repeated Primary/Coverage.
