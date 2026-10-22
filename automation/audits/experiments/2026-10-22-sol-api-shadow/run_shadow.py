#!/usr/bin/env python3
"""Однократное изолированное сравнение Sol API с Terra run 39706110827.

Не запускает публикацию, изображения, изменение GitHub или FTP.
Воспроизводит историческое окно и архив production до выпуска 22 октября.
Защита бюджета консервативная, по полученной usage-телеметрии; не провайдерский spending cap.
"""
from __future__ import annotations

import hashlib
import json
import os
import runpy
import subprocess
import sys
import traceback
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = ROOT / "automation" / "scripts"
PREVIEW = ROOT / "automation" / "preview"
OUT = PREVIEW / "sol-shadow-2026-10-22"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(SCRIPTS))
MODEL = "gpt-6.1-sol"
DATE = "2026-10-22"
CUTOFF = "2026-10-22T04:32:02+03:00"
PARENT_SHA = "eb3c8840df022eaac4e12038709eaccf898de8c4"
MAX_DOLLARS = 1.0
MAX_REQUESTS = 5
# Budget is enforced on a client-side conservative estimate, NOT a hard provider cap.
# Reserve $0.20 for one next model call; stop if observed estimate approaches $1.
MAX_NEW_REQUEST_RESERVE = 0.20
state = {
    "model": MODEL,
    "date": DATE,
    "cutoff": CUTOFF,
    "production_run": 39706110827,
    "code_sha": PARENT_SHA,
    "budget_usd": MAX_DOLLARS,
    "estimate_conservative_usd": 0.0,
    "request_count": 0,
    "completed_searches": 0,
    "requests": [],
    "stages": {},
    "warnings": ["Budget cap is a conservative client-side estimate, not a provider hard spend ceiling.", "Index and live pages on 22 Oct can differ from the overnight search snapshot.",
                 "Source Pulse uses live read-only sources, not a saved original feed snapshot.",
                 "Observed usage is not an OpenAI invoice; failed transport without usage is unknown."]
}

def save():
    p = OUT / "execution.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)


def count_billable_search_actions(output) -> int:
    """Only action.type=search incurs a Web Search operation charge.
    Reasoning-model open_page and find_in_page are navigation, not searches.
    """
    return sum(
        getattr(item, "type", None) == "web_search_call"
        and getattr(item, "status", None) == "completed"
        and getattr(getattr(item, "action", None), "type", None) == "search"
        for item in (output or [])
    )


def estimate_standard_usd(input_tokens: int, output_tokens: int,
                          written_tokens: int, cached_tokens: int,
                          searches: int) -> float:
    """GPT-6.1 Sol Standard, <=272k input; cache writes are not additive."""
    if min(input_tokens, output_tokens, written_tokens, cached_tokens, searches) < 0:
        raise ValueError("Negative usage tokens")
    if written_tokens + cached_tokens > input_tokens:
        raise ValueError("Invalid cache token partition")
    return (
        (input_tokens - written_tokens - cached_tokens) * 2.0
        + written_tokens * 2.5 + cached_tokens * 0.1
        + output_tokens * 10.0
    ) / 1_000_000 + searches * 0.01


# The seven previously paid passes are allowed to be replayed offline. Missing
# evidence, changed order/model/window, or incomplete usage fails before API.
EXPECTED_FROZEN_DIRECTION_IDS = (
    "global_breaking", "major_agencies", "models_products_agents",
    "infrastructure_chips_cloud", "business_investment_partnerships",
    "china_asia_models", "china_asia_integrations",
)
EXPECTED_FROZEN_ARCHIVE_SHA = "ef01085d0ef74dd2f0b80a5c1ba89dd99d8dafc85c25e8ac5fa4c3ea3a4a4568"


def load_frozen_replay(artifact_path: str):
    if not artifact_path or not Path(artifact_path).is_file():
        raise RuntimeError("Нужен исходный ZIP уже оплаченных семи проходов")
    raw_zip = Path(artifact_path).read_bytes()
    try:
        with zipfile.ZipFile(artifact_path) as data:
            if data.testzip() is not None:
                raise RuntimeError("Повреждён ZIP frozen-артефакта")
            frozen = json.loads(data.read(
                "production-daily/primary-recall-2026-10-22.json"
            ))
            execution = json.loads(data.read(
                "sol-shadow-2026-10-22/execution.json"
            ))
    except (zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise RuntimeError("Не удалось прочитать исходный frozen-артефакт") from exc
    if (
        frozen.get("publication_date") != DATE
        or frozen.get("search_window", {}).get("start_at") !=
            "2026-10-20T04:35:44+03:00"
        or frozen.get("search_window", {}).get("end_at") != CUTOFF
        or execution.get("model") != MODEL
        or execution.get("frozen_archive_sha256") != EXPECTED_FROZEN_ARCHIVE_SHA
        or execution.get("request_count") != 8
    ):
        raise RuntimeError("Frozen archive/model/date/cutoff/provenance отличается")
    rows = frozen.get("directions", [])
    if (not isinstance(rows, list) or
            [r.get("direction_id") for r in rows] != list(EXPECTED_FROZEN_DIRECTION_IDS)):
        raise RuntimeError("Неверный порядок семи сохранённых проходов")
    for i, row in enumerate(rows):
        api = row.get("api") or {}
        usage = api.get("usage") or {}
        if (api.get("model") != MODEL or
                api.get("status") != "completed" or
                api.get("web_search_calls_completed") != 1 or
                api.get("web_search_search_operations_performed") != 1 or
                not isinstance(usage.get("input_tokens"), int) or
                not isinstance(usage.get("output_tokens"), int) or
                not isinstance(row.get("raw_candidates"), list) or
                not isinstance(row.get("model_rejections"), list) or
                row.get("status") not in {"complete", "complete_with_gaps"}):
            raise RuntimeError(f"Проход {i+1} не имеет полного provenance для replay")
    return rows, hashlib.sha256(raw_zip).hexdigest()


def build_replay_runner(rows, live_runner):
    progress = {"replayed": 0, "new_queries": 0}
    def runner(*, direction_id, **kwargs):
        if progress["replayed"] < len(rows):
            row = rows[progress["replayed"]]
            if row["direction_id"] != direction_id:
                raise RuntimeError(
                    f"Replay order mismatch {direction_id} vs {row['direction_id']}"
                )
            progress["replayed"] += 1
            return ({
                "direction_id": direction_id, "status": row["status"],
                "notes": row.get("notes"),
                "candidates": row["raw_candidates"],
                "rejections": row["model_rejections"],
            }, row["api"])
        progress["new_queries"] += 1
        return live_runner(direction_id=direction_id, **kwargs)
    return runner, progress


def verify_replay_offline(artifact_path: str) -> dict:
    """Zero-API probe over the EXACT archived seven responses and five no-op passes.
    Exercise the real public Primary matrix, including schema/merge.
    """
    rows, archive_zip_sha = load_frozen_replay(artifact_path)
    import primary_recall_search
    from primary_recall_search import PRIMARY_DIRECTIONS
    actual_directions = [d["id"] for d in PRIMARY_DIRECTIONS]
    if actual_directions[:7] != list(EXPECTED_FROZEN_DIRECTION_IDS):
        raise RuntimeError("Текущая Primary matrix несовместима с saved order")
    unexpected_live = []
    def offline_only(*, direction_id, **kwargs):
        unexpected_live.append(direction_id)
        return ({
            "direction_id": direction_id, "status": "complete_with_gaps",
            "notes": "Offline no-op for future paid pass",
            "candidates": [], "rejections": []
        }, {"model": MODEL, "status": "completed",
             "web_search_calls_completed": 1,
             "usage": {"input_tokens": 0, "output_tokens": 0}})
    replay, progress = build_replay_runner(rows, offline_only)
    # Source is frozen git parent; do not take current published archive.\n    # Production archive after Oct 22 would include newly published articles;
    # load the true frozen Oct 21 archive from git without touching production.
    earlier = subprocess.check_output(
        ["git", "show", PARENT_SHA + ":automation/archive/index.json"], cwd=ROOT
    )
    frozen_archive = json.loads(earlier)
    if hashlib.sha256(earlier).hexdigest() != EXPECTED_FROZEN_ARCHIVE_SHA:
        raise RuntimeError("Отличается frozen archive SHA")
    result, report = primary_recall_search.run_primary_recall_matrix(
        publication_date=DATE,
        search_window={
            "start_at": "2026-10-20T04:35:44+03:00",
            "end_at": CUTOFF,
            "latest_archive_at": "2026-10-21T04:35:44+03:00",
            "start_date": "2026-10-20", "end_date": "2026-10-22",
            "latest_archive_date": "2026-10-21"
        },
        archive=frozen_archive, api_key="OFFLINE_NO_API", model=MODEL,
        maximum_candidates=20, search_runner=replay,
    )
    if (progress["replayed"] != 7 or progress["new_queries"] != 5 or
            unexpected_live != actual_directions[7:] or
            len(report.get("directions", [])) != 12):
        raise RuntimeError("Replay пошёл не по 7 frozen + 5 simulated passes")
    for i, old in enumerate(rows):
        now = report["directions"][i]
        if (now["direction_id"] != old["direction_id"] or
                now.get("raw_candidates") != old.get("raw_candidates") or
                now.get("model_rejections") != old.get("model_rejections") or
                now.get("accepted_count") != old.get("accepted_count")):
            raise RuntimeError(f"Replay не воспроизвёл сохранённый pass {i+1}")
    return {
        "status": "offline_pass", "model": MODEL,
        "frozen_artifact_sha256": archive_zip_sha,
        "frozen_passes": 7, "simulated_future_passes": 5,
        "real_api_calls": 0,
        "first_seven_raw_candidates": sum(len(x["raw_candidates"]) for x in rows),
        "first_seven_accepted": sum(x["accepted_count"] for x in rows),
        "whole_matrix_candidate_count_in_offline_simulation":
            report.get("final_candidate_count"),
        "notes": "Last five are mocked no-ops, NOT actual Sol findings"
    }

def run_stage(label: str, path: Path, args: list[str]) -> int:
    old = list(sys.argv)
    sys.argv = [str(path), *args]
    try:
        runpy.run_path(str(path), run_name="__main__")
        rc = 0
    except SystemExit as e:
        rc = int(e.code or 0) if isinstance(e.code, (int, type(None))) else 1
    except Exception as e:
        rc = 1
        state["stages"][label + "_exception"] = type(e).__name__ + ": " + str(e)
        traceback.print_exc()
    finally:
        sys.argv = old
    state["stages"][label] = {"return_code": rc, "cumulative_searches": state["completed_searches"],
                               "cumulative_estimate_usd": round(state["estimate_conservative_usd"], 6)}
    save()
    return rc

def main() -> int:
    if os.environ.get("GITHUB_RUN_ATTEMPT", "1") != "1":
        raise RuntimeError("Повтор GitHub Actions запрещён: бюджет имеет one-shot контракт")
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Отсутствует OPENAI_API_KEY; нельзя выполнить платный тест")
    if (ROOT / "automation" / "scripts" / "primary_recall_search_v2.py").is_file() is False:
        raise RuntimeError("Нет исходного production конвейера")
    archive = subprocess.check_output(
        ["git", "show", PARENT_SHA + ":automation/archive/index.json"], cwd=ROOT
    )
    (ROOT / "automation" / "archive" / "index.json").write_bytes(archive)
    state["frozen_archive_sha256"] = hashlib.sha256(archive).hexdigest()
    frozen_window = {"start_at": "2026-10-20T04:35:44+03:00",
                     "end_at": CUTOFF}
    state["fixed_window"] = frozen_window
    save()

    import openai
    from openai.resources.responses import Responses
    original_init = openai.OpenAI.__init__
    original_create = Responses.create

    def disable_retry(self, *args, **kwargs):
        kwargs["max_retries"] = 0
        return original_init(self, *args, **kwargs)

    def tracked_create(self, *args, **kwargs):
        model = kwargs.get("model")
        if model != MODEL:
            raise RuntimeError("Запрещён вызов не-Sol модели: " + str(model))
        reasoning = kwargs.get("reasoning")
        if not isinstance(reasoning, dict) or reasoning.get("effort") != "medium":
            raise RuntimeError("Ожидается reasoning effort medium")
        output_cap = kwargs.get("max_output_tokens")
        if not isinstance(output_cap, int) or not (1 <= output_cap <= 20000):
            raise RuntimeError("Нет безопасного max_output_tokens <=20000")
        if state["request_count"] >= MAX_REQUESTS:
            raise RuntimeError("Превышен лимит 5 новых Primary API-запросов")
        if state["estimate_conservative_usd"] + MAX_NEW_REQUEST_RESERVE > MAX_DOLLARS:
            raise RuntimeError("Бюджетный guard: недостаточно резерва на следующий вызов")
        state["request_count"] += 1
        number = state["request_count"]
        attempt = {"number": number, "model": model, "max_output_tokens": output_cap,
                   "reasoning": "medium", "outcome": "request_started"}
        state["requests"].append(attempt)
        save()
        try:
            response = original_create(self, *args, **kwargs)
        except Exception as e:
            attempt["outcome"] = "response_unknown_after_request"
            attempt["error_type"] = type(e).__name__
            save()
            # no further calls after ambiguous spend, even if consumer catches exception
            state["estimate_conservative_usd"] = MAX_DOLLARS
            save()
            raise
        usage = getattr(response, "usage", None)
        inp = getattr(usage, "input_tokens", None)
        out = getattr(usage, "output_tokens", None)
        if inp is None or out is None:
            attempt["outcome"] = "usage_missing_stop"
            state["estimate_conservative_usd"] = MAX_DOLLARS
            save()
            raise RuntimeError("API response without usage: further paid calls disallowed")
        outputs = getattr(response, "output", []) or []
        completed = count_billable_search_actions(outputs)
        navigation = sum(
            getattr(item, "type", None) == "web_search_call"
            and getattr(getattr(item, "action", None), "type", None)
                in {"open_page", "find_in_page"}
            for item in outputs
        )
        details = getattr(usage, "input_tokens_details", None)
        written = getattr(details, "cache_write_tokens", 0) or 0
        cached = getattr(details, "cached_tokens", 0) or 0
        # Capture returned response usage BEFORE enforcement checks. The prior
        # attempt lost its eighth API response by checking tool items first.
        long_context = inp > 272000
        estimate = estimate_standard_usd(inp, out, written, cached, completed)
        conservative = (
            inp * (4.0 if long_context else 2.5)
            + out * (15.0 if long_context else 10.0)
        ) / 1000000 + completed * 0.01
        attempt.update({
            "outcome": "response_received",
            "response_id": getattr(response, "id", None),
            "input_tokens": inp, "output_tokens": out,
            "cache_write_tokens": written, "cached_input_tokens": cached,
            "completed_searches": completed, "navigation_items": navigation,
            "estimate_standard_usd": round(estimate, 8),
            "estimate_conservative_usd": round(conservative, 8)
        })
        state["estimate_standard_usd"] = round(
            state.get("estimate_standard_usd", 0.0) + estimate, 8
        )
        state["estimate_conservative_usd"] = round(
            state["estimate_conservative_usd"] + conservative, 8
        )
        state["completed_searches"] += completed
        save()
        if state["completed_searches"] > 25:
            attempt["outcome"] = "search_budget_breached_after_response"
            save()
            raise RuntimeError("Превышено 25 настоящих поисков; usage сохранён")
        if state["estimate_conservative_usd"] > MAX_DOLLARS:
            attempt["outcome"] = "budget_breached_after_response"
            save()
            raise RuntimeError("Оценка бюджета превышена; usage сохранён")
        return response

    openai.OpenAI.__init__ = disable_retry
    Responses.create = tracked_create

    import primary_recall_search
    # Seven saved paid Primary passes are always replayed, not paid again.
    artifact_raw = os.environ.get("SOL_SHADOW_REPLAY_ARTIFACT", "").strip()
    frozen_rows, frozen_sha = load_frozen_replay(artifact_raw)
    original_matrix = primary_recall_search._BASE_RUN_MATRIX
    replay_or_live, replay_state = build_replay_runner(
        frozen_rows, primary_recall_search._base.run_search_request
    )
    def replay_matrix(*args, **kwargs):
        kwargs["search_runner"] = replay_or_live
        return original_matrix(*args, **kwargs)
    primary_recall_search._BASE_RUN_MATRIX = replay_matrix
    state["frozen_replayed_directions"] = len(frozen_rows)
    state["frozen_replay_sha256"] = frozen_sha
    save()
    original_primary = primary_recall_search.run_primary_recall_search
    def frozen_primary(*args, **kwargs):
        kwargs["cutoff_at"] = datetime.fromisoformat(CUTOFF)
        return original_primary(*args, **kwargs)
    primary_recall_search.run_primary_recall_search = frozen_primary

    # Only finish the 12 Primary passes. Never trigger Editorial, Hybrid or
    # Coverage in this experiment: a Research-only A/B is cheaper and cleaner.
    try:
        research_path, report = primary_recall_search.run_primary_recall_search(
            publication_date=DATE, api_key=os.environ["OPENAI_API_KEY"],
            model=MODEL, maximum_candidates=20
        )
        state["stages"]["primary_only"] = {
            "status": report.get("status"), "final_candidate_count":
                report.get("final_candidate_count"),
            "replayed_passes": replay_state["replayed"],
            "new_passes": replay_state["new_queries"],
            "report_path": str(research_path),
        }
        if replay_state["replayed"] != 7 or replay_state["new_queries"] != 5:
            raise RuntimeError("Primary не завершил именно 7 frozen + 5 fresh")
        rc = 0
    except Exception as exc:
        state["stages"]["primary_only"] = {
            "status": "error", "error_type": type(exc).__name__,
            "error": str(exc), "replayed_passes": replay_state["replayed"],
            "new_passes": replay_state["new_queries"],
        }
        save()
        raise
    state["status"] = "completed" if rc == 0 else "incomplete"
    state["api_budget_not_invoice"] = True
    state["no_publication_or_image"] = True
    # Reference machine-readable release inputs without mutating them.
    ref = ROOT / "automation" / "content" / DATE
    state["terra_baseline"] = {
        "candidates": str(ref / "candidates.json"),
        "selection": str(ref / "selection.json")
    }
    save()
    return rc

if __name__ == "__main__":
    # The old branch ran paid API on import/CLI invocation and had a $10 limit.
    # Keep this historical runner inert unless separately re-authorized.
    if "--offline-verify" in sys.argv:
        at = os.environ.get("SOL_SHADOW_REPLAY_ARTIFACT", "")
        try:
            report = verify_replay_offline(at)
        except Exception as exc:
            print("OFFLINE REPLAY FAILED:", type(exc).__name__, str(exc))
            raise SystemExit(1)
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "offline-verification.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False))
        raise SystemExit(0)
    if "--paid" not in sys.argv or os.getenv("SOL_SHADOW_OWNER_APPROVAL_USD") != "1.00":
        print("OFFLINE ONLY: API-запуск заблокирован. Новое разрешение на платный тест отсутствует.")
        raise SystemExit(2)
    sys.argv.remove("--paid")
    try:
        raise SystemExit(main())
    except Exception as exc:
        state["status"] = "aborted"
        state["fatal_error"] = type(exc).__name__ + ": " + str(exc)
        save()
        traceback.print_exc()
        raise SystemExit(1)
