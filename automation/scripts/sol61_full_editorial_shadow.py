#!/usr/bin/env python3
"""V2: exact Terra Editorial prompts -> independent full Sol editorials.

Read-only, post-deployment. The only OpenAI calls here are Sol Editorial;
there is NO research, Web Search, image, publish or retry. Terra outputs are
not opened until all Sol responses have been received and saved.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import generate_digest_preview as gen
from editorial_policy_runtime import patch_editorial_policy, patch_editorial_source_validation

TERRA = "gpt-5.6-terra"
SOL = "gpt-6.1-sol"
FIRST_DAY = date(2026, 11, 1)
MAX_ATTEMPTS = 3
MAX_OUTPUT_TOKENS = 18000
MAX_PROMPT_BYTES = 2_000_000  # fail closed, never silently truncate exact input


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("Expected JSON object")
    return result


def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


@dataclass(frozen=True)
class Attempt:
    prompt: bytes
    candidates: bytes
    prompt_sha256: str
    captured_at: str
    source: str
    is_final: bool = False


def current_date_moscow() -> str:
    return datetime.now(ZoneInfo("Europe/Moscow")).date().isoformat()


def validate_date(value: str) -> None:
    parsed = date.fromisoformat(value)
    if parsed < FIRST_DAY or value != current_date_moscow():
        raise ValueError("Sol full shadow is only permitted on the current Moscow day from 2026-11-01")


def collect_attempts(artifact: Path, publication_date: str) -> tuple[list[Attempt], dict[str, Any]]:
    """Verify original evidence and refuse to silently synthesize any Terra prompt."""
    day = artifact / publication_date
    info = read(day / "run-info.json")
    if info.get("publication_date") != publication_date or info.get("model_requested") != TERRA or info.get("status") != "ok":
        raise ValueError("Original Terra run-info is not a successful matching production run")
    final_prompt = (day / "editorial-prompt-input.txt").read_bytes()
    final_candidates = (day / "candidates.json").read_bytes()
    final_sha = digest(final_prompt)
    if info.get("editorial", {}).get("prompt_sha256") != final_sha:
        raise ValueError("Final Terra editorial prompt SHA mismatch")
    if read(day / "candidates.json").get("publication_date") != publication_date:
        raise ValueError("Final candidate pool date mismatch")

    originals: list[Attempt] = []
    base = artifact / "production-daily" / "editorial-input-snapshots" / publication_date
    if base.exists():
        for folder in sorted(p for p in base.iterdir() if p.is_dir()):
            meta = read(folder / "provenance.json")
            prompt = (folder / "prompt.txt").read_bytes()
            candidate_bytes = (folder / "candidates.json").read_bytes()
            if (folder.name != digest(prompt)
                or meta.get("prompt_sha256") != digest(prompt)
                or meta.get("candidates_sha256") != digest(candidate_bytes)
                or meta.get("publication_date") != publication_date
                or meta.get("model_requested") != TERRA):
                raise ValueError("Corrupted immutable Terra attempt snapshot")
            originals.append(Attempt(
                prompt=prompt, candidates=candidate_bytes, prompt_sha256=digest(prompt),
                captured_at=str(meta.get("captured_at") or ""), source="pre_api_snapshot",
                is_final=digest(prompt) == final_sha,
            ))
    if originals and all(a.prompt_sha256 != final_sha for a in originals):
        # We must not claim all attempts were archived if the final is absent.
        raise ValueError("Archived Terra attempts lack the exact final prompt")
    if not originals:
        originals.append(Attempt(final_prompt, final_candidates, final_sha, "", "final_only_fallback", True))
    # Ensure exact final input and pool match original final artifact.
    final = next(a for a in originals if a.is_final)
    if final.prompt != final_prompt or final.candidates != final_candidates:
        raise ValueError("Final immutable snapshot is inconsistent with final Terra artifact")
    if len({a.prompt_sha256 for a in originals}) != len(originals):
        raise ValueError("Duplicate immutable snapshot")
    originals.sort(key=lambda a: (a.captured_at, a.prompt_sha256))
    if not originals[-1].is_final:
        raise ValueError("Final Editorial prompt is not last; stage order is ambiguous")
    return originals, info


def bounded_attempts(originals: list[Attempt]) -> tuple[list[Attempt], list[str]]:
    """Always keep final attempt; bound total paid calls without inventing repeats."""
    if len(originals) <= MAX_ATTEMPTS:
        return originals, []
    chosen = originals[:MAX_ATTEMPTS - 1] + [originals[-1]]
    skipped = [a.prompt_sha256 for a in originals[MAX_ATTEMPTS - 1:-1]]
    return chosen, skipped


def check_preflight(attempt: Attempt, publication_date: str) -> None:
    if not attempt.prompt or len(attempt.prompt) > MAX_PROMPT_BYTES:
        raise ValueError("Exact prompt missing or exceeds hard byte ceiling")
    pool = json.loads(attempt.candidates)
    if pool.get("publication_date") != publication_date or pool.get("status") != "ok":
        raise ValueError("Terra attempt candidate pool incorrect or incomplete")
    if len(pool.get("candidates") or []) > 24:
        raise ValueError("Candidate count exceeds production editorial limits")
    if f"Дата выпуска: {publication_date}" not in attempt.prompt.decode("utf-8"):
        raise ValueError("Prompt editorial date mismatch")


def validate_like_production(raw: dict[str, Any], research: dict[str, Any], publication_date: str,
                             archive: dict[str, Any], policy: dict[str, Any],
                             site: dict[str, Any], image: dict[str, Any],
                             minimum: int, maximum: int) -> dict[str, Any]:
    """Production's actual editorial policy/source checks on an isolated copy.

    This is a validator probe, not a full release rehearsal. No file mutation
    outside the shadow dir and no publication/recovery/Image/API operations.
    """
    patch_editorial_policy(gen)
    patch_editorial_source_validation(gen)
    value = copy.deepcopy(raw)
    results: dict[str, Any] = {"errors": [], "warnings": [], "normalizations": []}
    try:
        changed = gen.normalize_digest_metadata(value, date.fromisoformat(publication_date), site)
        results["normalizations"].extend(changed)
        value.setdefault("diversity_overrides", [])
        part = value.get("digest")
        if not isinstance(part, dict):
            raise ValueError("Sol Editorial response has no digest object")
        candidates = {str(x.get("id")): x for x in research.get("candidates", []) if isinstance(x, dict)}
        selected = [candidates[k] for k in value.get("selected_candidate_ids", []) if k in candidates]
        repeats = gen.detect_event_repetitions(str(part.get("article_html", "")),
                                                 [x for x in research.get("candidates", []) if isinstance(x, dict)])
        if repeats:
            results["errors"].append("Semantic repeated events: " + json.dumps(repeats, ensure_ascii=False)[:1200])
        ordered, order_errors = gen.order_candidates_by_article_links(str(part.get("article_html", "")), selected)
        results["errors"].extend(order_errors)
        if not order_errors:
            ordered_ids = [str(x.get("id")) for x in ordered]
            if set(ordered_ids) == set(value.get("selected_candidate_ids", [])):
                value["selected_candidate_ids"] = ordered_ids
                selected = ordered
        html, short, changes = gen.normalize_article_html(
            str(part.get("article_html", "")), selected, policy
        )
        part["article_html"] = html
        part["short_digest"] = short
        part["editorial_notes"] = gen.build_editorial_notes(research, selected, policy)
        results["normalizations"].extend(changes)
        results["normalizations"].extend(gen.normalize_image_prompt_constraints(part, image))
        errs, warnings, stories = gen.validate_editorial(
            value, research, date.fromisoformat(publication_date), site,
            archive, policy, minimum, maximum
        )
        results["errors"].extend(errs)
        results["warnings"].extend(warnings)
        results["story_count_after_validation"] = len(stories)
    except Exception as exc:
        results["errors"].append("Validator exception: " + type(exc).__name__)
    results["status"] = "pass" if not results["errors"] else "fail"
    return results


def run(*, publication_date: str, artifact: Path, archive_path: Path, policy_path: Path,
        site_path: Path, image_path: Path, output: Path, client: Any) -> dict[str, Any]:
    validate_date(publication_date)
    if os.getenv("GITHUB_RUN_ATTEMPT", "1") != "1":
        raise ValueError("A rerun may not spend a second time")
    if os.getenv("AI_DIGEST_PUBLICATION_DATE") != publication_date:
        raise ValueError("GitHub publication date differs from requested date")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Shadow evidence exists, refuse another paid run")
    originals, info = collect_attempts(artifact, publication_date)
    selected, skipped = bounded_attempts(originals)
    for attempt in selected:
        check_preflight(attempt, publication_date)

    archive = read(archive_path)
    policy = read(policy_path)
    site = read(site_path)
    image = read(image_path)
    if not archive.get("items") or any(str(x.get("date", "")) >= publication_date for x in archive["items"] if isinstance(x, dict)):
        raise ValueError("Missing or contaminated prepublication archive")
    minimum = int(info["limits"]["minimum_selected_stories"])
    maximum = int(info["limits"]["maximum_selected_stories"])
    if not 1 <= minimum <= maximum <= 12:
        raise ValueError("Unexpected editorial limits")

    output.mkdir(parents=True, exist_ok=False)
    save(output / "frozen-input.json", {
        "date": publication_date, "model": SOL, "terra_model": TERRA,
        "terra_research_artifact": "daily-production-" + publication_date,
        "run_id": os.getenv("GITHUB_RUN_ID"),
        "prepublication_commit": os.getenv("SOL_BASELINE_SHA"),
        "archive_sha256": digest(archive_path.read_bytes()),
        "policy_sha256": digest(policy_path.read_bytes()),
        "prompt_sha256_in_order": [x.prompt_sha256 for x in originals],
        "selected_attempt_prompt_sha256": [x.prompt_sha256 for x in selected],
        "skipped_prompt_sha256_due_to_cap": skipped,
        "captured_every_attempt": len(skipped) == 0 and all(x.source == "pre_api_snapshot" for x in originals),
        "editorial_schema": "generate_digest_preview.EDITORIAL_SCHEMA",
        "reasoning_effort": "medium", "max_output_tokens": MAX_OUTPUT_TOKENS,
        "max_attempts": MAX_ATTEMPTS, "web_search": False,
        "publication_authority": False, "no_terra_editorial_seen_before_sol": True,
    })
    records = []
    # No Terra output files are opened until ALL Sol responses are complete.
    for i, attempt in enumerate(selected, 1):
        name = f"{i:02d}-{'final' if attempt.is_final else 'intermediate'}-{attempt.prompt_sha256[:12]}"
        folder = output / "attempts" / name
        folder.mkdir(parents=True)
        (folder / "terra-request-original.txt").write_bytes(attempt.prompt)
        (folder / "terra-candidates-original.json").write_bytes(attempt.candidates)
        save(folder / "request-info.json", {
            "terra_prompt_sha256": attempt.prompt_sha256,
            "candidate_sha256": digest(attempt.candidates),
            "input_exact_bytes": len(attempt.prompt),
            "source": attempt.source, "final_attempt": attempt.is_final,
        })
        # Exactly the same prompt string and JSON-schema as Terra.
        response = client.responses.create(
            model=SOL, input=attempt.prompt.decode("utf-8"),
            reasoning={"effort": "medium"}, max_output_tokens=MAX_OUTPUT_TOKENS,
            text={"format": {
                "type": "json_schema", "name": "daily_ai_editorial_digest",
                "strict": True, "schema": gen.EDITORIAL_SCHEMA,
            }},
            store=False,
        )
        original_text = getattr(response, "output_text", None) or ""
        (folder / "sol-editorial-original.txt").write_text(original_text, encoding="utf-8")
        usage = getattr(response, "usage", None)
        save(folder / "sol-provider-metadata.json", {
            "id": getattr(response, "id", None),
            "status": getattr(response, "status", None),
            "model_returned": getattr(response, "model", None),
            "service_tier": getattr(response, "service_tier", None),
            "usage": usage.model_dump(mode="json") if hasattr(usage, "model_dump") else usage,
        })
        if getattr(response, "status", None) != "completed" or getattr(response, "model", None) != SOL:
            raise ValueError("Incomplete Sol full Editorial response, original evidence saved")
        sol = json.loads(original_text)
        if not isinstance(sol, dict):
            raise ValueError("Non-object Sol Editorial response")
        save(folder / "sol-full-editorial.json", sol)
        pool = json.loads(attempt.candidates)
        validator = validate_like_production(sol, pool, publication_date, archive, policy, site,
                                             image, minimum, maximum)
        save(folder / "editorial-validation.json", validator)
        records.append({"attempt": name, "final": attempt.is_final, "prompt_sha256": attempt.prompt_sha256,
                        "sol_selected_ids": sol.get("selected_candidate_ids"),
                        "validation": validator.get("status")})
        save(output / "shadow-progress.json", {"completed_attempts": records, "status": "running"})

    # Terra is only read here, after all independent responses were persisted.
    terra_file = artifact / publication_date / "editorial-output-raw.json"
    terra = read(terra_file)
    (output / "terra-editorial-original.json").write_bytes(terra_file.read_bytes())
    last = selected[-1]
    last_name = records[-1]["attempt"]
    final_sol = read(output / "attempts" / last_name / "sol-full-editorial.json")
    terra_ids = terra.get("selected_candidate_ids")
    sol_ids = final_sol.get("selected_candidate_ids")
    if not last.is_final or not isinstance(terra_ids, list) or not isinstance(sol_ids, list):
        raise ValueError("Cannot compare the exact final editorial selection")
    all_ids = [str(c["id"]) for c in json.loads(last.candidates).get("candidates", [])]
    if not (set(terra_ids) <= set(all_ids) and set(sol_ids) <= set(all_ids)):
        raise ValueError("Comparison candidate identities inconsistent")
    a, b = set(terra_ids), set(sol_ids)
    compare = {
        "publication_date": publication_date, "terra_model": TERRA, "sol_model": SOL,
        "mode": "exact_full_editorial_v2", "all_candidate_ids": all_ids,
        "terra_selected_candidate_ids": terra_ids, "sol_selected_candidate_ids": sol_ids,
        "selected_by_both": [k for k in all_ids if k in a & b],
        "terra_only": [k for k in all_ids if k in a - b],
        "sol_only": [k for k in all_ids if k in b - a],
        "excluded_by_both": [k for k in all_ids if k not in a | b],
        "terra_selection_summary": terra.get("selection_summary"),
        "sol_selection_summary": final_sol.get("selection_summary"),
        "terra_full_article_sha256": digest(str(terra.get("digest", {}).get("article_html", "")).encode()),
        "sol_full_article_sha256": digest(str(final_sol.get("digest", {}).get("article_html", "")).encode()),
        "sol_validation": records[-1]["validation"],
        "not_a_live_production_rehearsal": True,
    }
    save(output / "terra-vs-sol-editorial-comparison.json", compare)
    save(output / "shadow-progress.json", {
        "status": "complete" if len(records) == len(originals) else "partial_cap",
        "completed_attempts": records, "skipped_prompt_sha256_due_to_cap": skipped,
    })
    save(output / "manifest.json", {
        "status": "complete" if not skipped else "partial_cap",
        "publication_date": publication_date, "model": SOL,
        "files_sha256": {str(p.relative_to(output)): digest(p.read_bytes())
                         for p in sorted(output.rglob("*")) if p.is_file() and p.name != "manifest.json"},
    })
    return compare


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication-date", required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("No OPENAI_API_KEY")
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], max_retries=0, timeout=400)
        report = run(publication_date=args.publication_date, artifact=args.artifact,
                     archive_path=args.archive, policy_path=args.policy,
                     site_path=args.site, image_path=args.image,
                     output=args.output, client=client)
        print("Full Sol Editorial shadow saved: both=%d Terra-only=%d Sol-only=%d"
              % (len(report["selected_by_both"]), len(report["terra_only"]), len(report["sol_only"])))
    except Exception as exc:
        # Never print exception body: provider messages may contain source data.
        save(args.output / "shadow-error.json", {
            "status": "failed_or_skipped", "error_type": type(exc).__name__,
            "date": args.publication_date, "no_publication": True,
        })
        print("::warning title=Optional full Sol editorial shadow::"
              + type(exc).__name__ + ". Terra remains published.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
