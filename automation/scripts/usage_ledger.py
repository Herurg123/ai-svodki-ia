"""Deduplicate observed release costs across saved artifacts and recovery.

No API, network, publication or recovery decisions. This is an estimate of
observed calls, never an account invoice or proof that unseen attempts cost zero.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

PRICING = {
    "verified_at": "2026-09-06",
    "source": "https://developers.openai.com/api/docs/pricing",
    "context_source": "https://developers.openai.com/api/docs/models/gpt-5.6-terra",
    "cache_source": "https://developers.openai.com/api/docs/guides/prompt-caching",
    "basis": "Standard USD list prices, no tax, discounts or regional uplift",
    "text_model": "gpt-5.6-terra", "short_context_max_input_tokens": 272000,
    "text_per_million": {"input": 2, "cached": 0.2, "cache_write": 2.5, "output": 12},
    "image_model": "gpt-image-2",
    "image_per_million": {"text_input": 5, "image_input": 8, "image_output": 30},
    "search_operation": 0.01,
}
STAGES = ("primary", "agency", "hybrid", "coverage", "research", "editorial", "image")
COUNTERS = ("input_tokens", "output_tokens", "total_tokens", "cached_tokens", "cache_write_tokens")


def walk(value: Any, pointer: str = "") -> Iterable[tuple[dict[str, Any], str]]:
    if isinstance(value, dict):
        yield value, pointer
        for key, child in value.items():
            yield from walk(child, f"{pointer}/{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, f"{pointer}/{index}")


def stage_for(path: str, pointer: str) -> str:
    if "editorial/response" in pointer:
        return "editorial"
    if "research/response" in pointer:
        return "research"
    text = (path + pointer).lower()
    for needle, stage in (("agency_discovery", "agency"), ("agency-discovery", "agency"),
                          ("primary-recall", "primary"), ("hybrid", "hybrid"),
                          ("coverage", "coverage"), ("image-api", "image")):
        if needle in text:
            return stage
    return "unknown"


def integer(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def counts(usage: Any) -> dict[str, int | None]:
    usage = usage if isinstance(usage, dict) else {}
    details = usage.get("input_tokens_details") or {}
    if not isinstance(details, dict):
        details = {}
    return {**{key: integer(usage.get(key)) for key in COUNTERS[:3]},
            **{key: integer(details.get(key)) for key in COUNTERS[3:]}}


def cost(record: dict[str, Any]) -> tuple[float | None, list[str]]:
    u = record.get("usage") or {}
    if not isinstance(u, dict):
        return None, ["usage_missing"]
    c = counts(u)
    inp, out = c["input_tokens"], c["output_tokens"]
    if inp is None or out is None:
        return None, ["token_counts_missing_or_invalid"]
    if c["total_tokens"] is not None and c["total_tokens"] != inp + out:
        return None, ["inconsistent_total_tokens"]
    if record.get("service_tier") not in {None, "default", "standard", "auto"}:
        return None, ["unsupported_service_tier"]
    if record["kind"] == "image":
        if record.get("model") != PRICING["image_model"]:
            return None, ["unknown_image_price"]
        details = u.get("input_tokens_details") or {}
        if not isinstance(details, dict):
            return None, ["image_modalities_missing_or_invalid"]
        text, image = integer(details.get("text_tokens")), integer(details.get("image_tokens"))
        if text is None or image is None or text + image != inp:
            return None, ["image_modalities_missing_or_invalid"]
        # The production Images endpoint is text-only. Do not guess cache
        # modality prices if a future caller introduces cached image input.
        if details.get("cached_tokens", 0) or details.get("cache_write_tokens", 0):
            return None, ["image_cache_breakdown_unsupported"]
        output_details = u.get("output_tokens_details") or {}
        if not isinstance(output_details, dict):
            return None, ["image_output_modalities_invalid"]
        if output_details.get("text_tokens", 0):
            return None, ["image_text_output_price_unknown"]
        return (text * 5 + image * 8 + out * 30) / 1e6, []
    if record.get("model") != PRICING["text_model"]:
        return None, ["unknown_text_price"]
    cached, written = c["cached_tokens"], c["cache_write_tokens"]
    if cached is None or written is None:
        return None, ["cache_counts_missing_or_invalid"]
    if cached + written > inp:
        return None, ["cache_exceeds_input"]
    long = inp > PRICING["short_context_max_input_tokens"]
    weighted = ((inp - cached - written) * 2 + cached * 0.2 + written * 2.5)
    return (weighted * (2 if long else 1) + out * (18 if long else 12)) / 1e6, []


def _observation(node: dict[str, Any], path: str, pointer: str) -> dict[str, Any] | None:
    event = node.get("usage_event_version") == 1
    rid = node.get("response_id") or node.get("id")
    image = path.endswith("image-api-response.json") and pointer == ""
    if not event and not image and not (isinstance(rid, str) and rid.startswith("resp_")):
        return None
    # Never add aggregate usage without a provider response identity.
    if not event and not image and "usage" not in node:
        return None
    kind = node.get("kind", "text") if event else ("image" if image else "text")
    provider_id = node.get("provider_request_id") or node.get("openai_request_id")
    attempt_id = node.get("attempt_id") if event else node.get("usage_attempt_id")
    if rid:
        identity = "response:" + str(rid)
    elif provider_id:
        identity = "image:" + str(provider_id)
    elif attempt_id:
        # The release/request ID is reusable and cannot identify a paid call.
        # This UUID is shared by the journal and the saved image response.
        identity = "attempt:" + str(attempt_id)
    elif image:
        # A content identity allows copied historical image reports to dedupe;
        # absence of the provider ID stays visible as an accounting gap.
        identity = "legacy-image:" + hashlib.sha256(json.dumps(node, sort_keys=True).encode()).hexdigest()
    else:
        return None
    image_response = node.get("response")
    usage = (image_response.get("usage") if isinstance(image_response, dict) else None) if image else node.get("usage")
    searches = node.get("search_operations")
    if searches is None:
        searches = node.get("web_search_calls_completed", node.get("web_search_calls"))
    if searches is None and isinstance(node.get("output"), list):
        searches = sum(1 for item in node["output"] if isinstance(item, dict)
                       and item.get("type") == "web_search_call" and item.get("status") == "completed"
                       and (item.get("action") or {}).get("type") == "search")
    stage = node.get("stage") if event else stage_for(path, pointer)
    if searches is None and stage in {"editorial", "image"}:
        searches = 0
    return {"identity": identity, "response_id": rid, "kind": kind, "stage": stage,
            "attempt_id": attempt_id,
            "model": node.get("model") or node.get("model_returned"),
            "service_tier": node.get("service_tier"), "usage": usage,
            "search_operations": integer(searches),
            "incomplete_search_operations": node.get("incomplete_search_operations", 0),
            "state": node.get("state", "response_received"),
            "run_ids": [str(node["run_id"])] if node.get("run_id") else [],
            "observed_in": [path + "#" + pointer],
            "identity_uncertain": identity.startswith("legacy-image:")}


def _merge(existing: dict[str, Any], new: dict[str, Any]) -> None:
    existing["observed_in"] = sorted(set(existing["observed_in"] + new["observed_in"]))
    existing["run_ids"] = sorted(set(existing["run_ids"] + new["run_ids"]))
    conflicts = existing.setdefault("conflicts", [])
    if new.get("state") == "response_received":
        existing["state"] = "response_received"
    if not existing.get("attempt_id"):
        existing["attempt_id"] = new.get("attempt_id")
    existing["identity_uncertain"] = bool(existing.get("identity_uncertain") or new.get("identity_uncertain"))
    existing["incomplete_search_operations"] = max(existing.get("incomplete_search_operations", 0),
                                                  new.get("incomplete_search_operations", 0))
    old_cost, _ = cost(existing)
    new_cost, _ = cost(new)
    if old_cost is not None and new_cost is not None and abs(old_cost - new_cost) > 1e-12:
        conflicts.append("usage_price_breakdown")
    for key in ("model", "service_tier", "search_operations"):
        a, b = existing.get(key), new.get(key)
        if a is None:
            existing[key] = b
        elif b is not None and a != b:
            conflicts.append(key)
    a, b = counts(existing.get("usage")), counts(new.get("usage"))
    for key in COUNTERS:
        if a[key] is not None and b[key] is not None and a[key] != b[key]:
            conflicts.append(key)
    if sum(v is not None for v in b.values()) > sum(v is not None for v in a.values()):
        existing["usage"] = new["usage"]
    # Nested saved reports must not turn an editorial/agency response into the
    # name of the directory holding its copy.
    rank = {"editorial": 4, "agency": 3, "primary": 2, "hybrid": 2, "coverage": 2}
    if rank.get(new["stage"], 0) > rank.get(existing["stage"], 0):
        existing["stage"] = new["stage"]
    existing["conflicts"] = sorted(set(conflicts))


def build_ledger(roots: list[Path], publication_date: str) -> dict[str, Any]:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", publication_date):
        raise ValueError("publication_date must be YYYY-MM-DD")
    records: dict[str, dict[str, Any]] = {}
    gaps: list[str] = []
    reports: dict[str, set[str]] = {stage: set() for stage in STAGES}
    files = sorted({p.resolve() for root in roots if root.exists() for p in root.rglob("*.json")
                    if not p.is_symlink() and p.name != "pipeline-status.json"
                    and not any(re.fullmatch(r"\d{4}-\d{2}-\d{2}", part) and part != publication_date for part in p.parts)})
    for path in files:
        name = path.name
        if not (name == "usage-ledger.json" or "usage-events" in path.parts or any(s in name for s in
                ("run-info", "primary-recall", "hybrid-completeness", "agency-discovery", "coverage", "response"))):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            gaps.append(f"unreadable:{path}")
            continue
        if isinstance(data, dict):
            date = data.get("publication_date")
            if date and date != publication_date:
                gaps.append(f"foreign_date_skipped:{path}")
                continue
            if name == "usage-ledger.json":
                if data.get("version") != 1 or data.get("publication_date") != publication_date:
                    gaps.append(f"unsupported_saved_ledger:{path}")
                    continue
                # Carry the complete selected recovery chain, including failed
                # calls whose stage report was never written. Never infer new
                # paid work or change the recovery planner.
                for item in data.get("records") or []:
                    if not isinstance(item, dict) or not item.get("identity"):
                        gaps.append(f"invalid_saved_ledger_record:{path}")
                        continue
                    if item["identity"] in records:
                        _merge(records[item["identity"]], item)
                    else:
                        records[item["identity"]] = item
                # Structural gaps remain visible; missing-stage diagnostics
                # are recomputed because recovery may now supply that stage.
                gaps.extend(g for g in data.get("accounting_gaps") or []
                            if not g.startswith("stage_not_observed:"))
                continue
            if data.get("usage_event_version") == 1 and not data.get("attempt_id"):
                gaps.append(f"malformed_usage_event:{path}")
                continue
            lane = stage_for(str(path), "")
            if lane in reports:
                reports[lane].add(str(data.get("state") or data.get("status") or "unknown"))
        for node, pointer in walk(data):
            item = _observation(node, str(path), pointer)
            if item is None:
                continue
            identity = item["identity"]
            if identity in records:
                _merge(records[identity], item)
            else:
                records[identity] = item
    resolved_attempts = {r.get("attempt_id") for r in records.values()
                         if r.get("state") == "response_received" and r.get("attempt_id")}
    records = {key: row for key, row in records.items()
               if not (key.startswith("attempt:") and row.get("state") != "response_received"
                       and row.get("attempt_id") in resolved_attempts)}
    stages = {stage: {"unique_calls": 0, "tokens_observed": {key: 0 for key in COUNTERS},
                      "search_operations_observed": 0, "estimated_observed_usd": 0.0,
                      "unknown_cost_calls": 0, "report_states": sorted(reports.get(stage, set()))}
              for stage in (*STAGES, "unknown")}
    for record in records.values():
        stage = stages.get(record["stage"], stages["unknown"])
        stage["unique_calls"] += 1
        for key, value in counts(record.get("usage")).items():
            if value is not None:
                stage["tokens_observed"][key] += value
        estimate, problems = cost(record)
        if record.get("conflicts"):
            estimate = None
            problems.append("conflicting_copies")
        if record["state"] != "response_received":
            problems.append("api_outcome_unknown")
        if record["identity_uncertain"]:
            problems.append("provider_identity_missing")
        searches = record.get("search_operations")
        if searches is None:
            problems.append("search_count_unknown")
        else:
            stage["search_operations_observed"] += searches
        if record.get("incomplete_search_operations"):
            problems.append("incomplete_search_cost_unknown")
        record["model_cost_estimate_usd"] = round(estimate, 9) if estimate is not None else None
        record["search_cost_estimate_usd"] = round(searches * PRICING["search_operation"], 9) if searches is not None else None
        record["accounting_gaps"] = sorted(set(problems))
        stage["estimated_observed_usd"] += (estimate or 0) + (record["search_cost_estimate_usd"] or 0)
        if problems:
            stage["unknown_cost_calls"] += 1
    for name, stage in stages.items():
        stage["estimated_observed_usd"] = round(stage["estimated_observed_usd"], 9)
        stage["accounting_status"] = ("partial" if stage["unknown_cost_calls"] else
                                      "observed" if stage["unique_calls"] else
                                      "reported_no_observed_calls" if stage["report_states"] else "not_observed")
    for stage in ("primary", "hybrid", "coverage", "editorial", "image"):
        if not stages[stage]["unique_calls"] and not reports[stage]:
            gaps.append(f"stage_not_observed:{stage}")
    return {
        "version": 1, "publication_date": publication_date, "is_invoice": False,
        "scope": "unique observed calls in supplied release and recovery artifacts",
        "pricing": PRICING, "source_roots": [str(p) for p in roots],
        "unique_calls": len(records), "stages": stages,
        "estimated_observed_usd": round(sum(s["estimated_observed_usd"] for s in stages.values()), 9),
        "accounting_gaps": sorted(set(gaps)),
        "accounting_status": "partial" if gaps or any(s["unknown_cost_calls"] for s in stages.values()) else "observed",
        "limitations": ["Unlinked runs and provider/SDK retries without returned usage are not observable here.",
                        "Missing evidence is unknown, never evidence of zero charge.",
                        "Search-operation estimate excludes open/find navigation; provider invoice was not reconciled."],
        "records": sorted(records.values(), key=lambda r: r["identity"]),
    }


def summary_lines(report: dict[str, Any]) -> list[str]:
    lines = ["", "### Расходы выпуска и загруженного recovery",
             f"Расчёт по наблюдаемым вызовам: **${report['estimated_observed_usd']:.4f} USD**; "
             f"учёт `{report['accounting_status']}`. Это не счёт провайдера.", "",
             "| Стадия | Уникальные вызовы | Поиски | Оценка USD | Учёт |",
             "|---|---:|---:|---:|---|"]
    for name, value in report["stages"].items():
        if name in {"unknown", "research"} and not value["unique_calls"]:
            continue
        shown = f"{value['estimated_observed_usd']:.4f}" if value["unique_calls"] else "неизвестно"
        lines.append(f"| {name} | {value['unique_calls']} | {value['search_operations_observed']} | "
                     f"{shown} | {value['accounting_status']} |")
    lines.append("\nПропуски данных и неучтённые попытки не означают нулевой расход. Подробности: usage-ledger.json.")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", action="append", type=Path, required=True)
    parser.add_argument("--publication-date", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_ledger(args.root, args.publication_date)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print("\n".join(summary_lines(report)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
