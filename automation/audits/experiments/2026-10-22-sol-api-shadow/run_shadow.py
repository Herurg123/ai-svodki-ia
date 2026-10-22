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
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "automation" / "scripts"
PREVIEW = ROOT / "automation" / "preview"
OUT = PREVIEW / "sol-shadow-2026-10-22"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(SCRIPTS))
MODEL = "gpt-6.1-sol"
DATE = "2026-10-22"
CUTOFF = "2026-10-22T04:32:02+03:00"
PARENT_SHA = "eb3c8840df022eaac4e12038709eaccf898de8c4"
MAX_DOLLARS = 10.0
MAX_REQUESTS = 32
# Worst-case additional single request: 1.05M long-input tokens at $4/M,
# <=20k long-output tokens at $15/M and one search. Reserve >=$4.5.
MAX_NEW_REQUEST_RESERVE = 4.5
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
    "warnings": ["Index and live pages on 22 Oct can differ from the overnight search snapshot.",
                 "Source Pulse uses live read-only sources, not a saved original feed snapshot.",
                 "Observed usage is not an OpenAI invoice; failed transport without usage is unknown."]
}

def save():
    p = OUT / "execution.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)

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
            raise RuntimeError("Превышен лимит 32 API-запроса")
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
        completed = sum(
            1 for obj in outputs
            if getattr(obj, "type", None) == "web_search_call"
            and getattr(obj, "status", None) == "completed"
        )
        if state["completed_searches"] + completed > 25:
            attempt["outcome"] = "search_budget_breached"
            save()
            raise RuntimeError("Превышено 25 поисков: остановка")
        # Conservative upper estimate relative to Standard Sol:
        # account ALL input tokens as uncached/cache-write at $2.50/M.
        # Long context >272k: $4/M, output $15/M.
        long_context = inp > 272000
        est = (inp * (4.0 if long_context else 2.5)
               + out * (15.0 if long_context else 10.0)) / 1000000 + completed * 0.01
        attempt.update({
            "outcome": "response_received", "response_id": getattr(response, "id", None),
            "input_tokens": inp, "output_tokens": out,
            "cached_input_tokens": getattr(getattr(usage, "input_tokens_details", None),
                                           "cached_tokens", None),
            "completed_searches": completed,
            "estimate_conservative_usd": round(est, 8)
        })
        state["estimate_conservative_usd"] = round(
            state["estimate_conservative_usd"] + est, 8
        )
        state["completed_searches"] += completed
        save()
        return response

    openai.OpenAI.__init__ = disable_retry
    Responses.create = tracked_create

    import primary_recall_search
    original_primary = primary_recall_search.run_primary_recall_search
    def frozen_primary(*args, **kwargs):
        kwargs["cutoff_at"] = datetime.fromisoformat(CUTOFF)
        return original_primary(*args, **kwargs)
    primary_recall_search.run_primary_recall_search = frozen_primary

    common = [
        "--publication-date", DATE, "--minimum-candidates", "12",
        "--maximum-candidates", "20", "--minimum-selected-stories", "7",
        "--maximum-selected-stories", "12",
        "--maximum-research-web-search-calls", "12",
        "--model", MODEL, "--allow-provisional-editorial"
    ]
    rc = run_stage("research_editorial_hybrid",
                   SCRIPTS / "run_digest_preview.py", common)
    artifact_dir = PREVIEW / DATE
    if rc == 0 and artifact_dir.exists():
        coverargs = [
            "--artifact-dir", str(artifact_dir),
            "--archive", str(ROOT / "automation/archive/index.json"),
            "--publication-date", DATE, "--model", MODEL,
            "--usual-total", "7", "--minimum-publishable", "1",
            "--maximum-audit-web-search-calls", "7",
            "--maximum-candidates", "20", "--maximum-selected-stories", "12",
            "--report", str(PREVIEW / "production-daily" / "coverage-audit.json")
        ]
        rc = run_stage("coverage", SCRIPTS / "ensure_story_coverage.py", coverargs)
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
    try:
        raise SystemExit(main())
    except Exception as exc:
        state["status"] = "aborted"
        state["fatal_error"] = type(exc).__name__ + ": " + str(exc)
        save()
        traceback.print_exc()
        raise SystemExit(1)
