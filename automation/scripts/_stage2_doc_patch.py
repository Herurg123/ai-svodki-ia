from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"marker not found in {path}: {old[:80]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"marker is not unique in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


root = Path(__file__).resolve().parents[2]
readme = root / "README.md"
auto_readme = root / "automation" / "README.md"
agents = root / "AGENTS.md"

replace_once(
    readme,
    "| `.github/workflows/daily-production.yml` | Gate, Primary Recall v2, bounded agency discovery rescue при подтверждённом gap, независимый hybrid completeness, editorial, ограниченный coverage audit, обложка, сборка сайта, commit в `main` и вызов FTP-деплоя. |",
    "| `.github/workflows/daily-production.yml` | Gate, Primary Recall v2, bounded agency discovery rescue, Source Pulse v1 production shadow, независимый hybrid completeness, editorial, ограниченный coverage audit, обложка, сборка сайта, commit в `main` и вызов FTP-деплоя. |",
)

readme_section = """## Source Pulse v1: второй discovery-plane в production shadow\n\nПосле Primary Recall и conditional agency discovery rescue, но **до расчёта Hybrid gaps**,\nproduction запускает фиксированный Source Pulse v1. Это второй discovery-plane, который\nобычным bounded HTTPS polling читает registry официальных newsroom/IR/release/index\nисточников и региональных lead-only источников для China/Asia и Russia. На текущем\nэтапе он работает строго как **production shadow**: `candidate_influence=false`.\n\nShadow не добавляет, не удаляет и не ранжирует candidates, не меняет editorial и не\nможет скрыть деградацию `major_agencies`. Он выполняется только после независимого\nagency-rescue trigger и его freshness gate. Source Pulse не вызывает OpenAI и Web\nSearch, поэтому потолок остаётся **24 Web Search operations**. Ошибка DNS/HTTP/parser\nfail-open: сохраняется diagnostics, а прежний Hybrid продолжает работу.\n\nВ artifact сохраняется `source-pulse.json` с deterministic snapshot/source-health и\nfusion diagnostics: `pulse_only`, `both_exact_url`, `both_event_fingerprint`,\n`search_only`, cutoff ambiguity и archive duplicates. Повторный запуск на том же\nartifact использует сохранённый snapshot и не poll'ит mutable sources молча; обычный\nsame-day recovery также восстанавливает этот файл из Actions artifact.\n\nTier B остаётся только lead-only и не получает publication privileges. Source Freshness\nProof, semantic/archive dedupe, regional no-quota rule и editorial остаются без\nизменений. Любое будущее влияние Pulse на candidate pool или отдельный LLM triage\nтребует нового controlled experiment и отдельного production PR. Ежедневный\nнезависимый аудит должен отдельно сравнивать Search/Pulse coverage и source health.\n\n"""
replace_once(readme, "## Возобновляемые платные стадии\n", readme_section + "## Возобновляемые платные стадии\n")

replace_once(
    auto_readme,
    "применяется после discovery**. Двенадцать обязательных Primary search operations\nраспределяются детерминированно; отдельный bounded agency discovery rescue может\nдобавить максимум одну search operation только при доказанном gap\n`major_agencies`.",
    "применяется после discovery**. Двенадцать обязательных Primary search operations\nраспределяются детерминированно; отдельный bounded agency discovery rescue может\nдобавить максимум одну search operation только при доказанном gap\n`major_agencies`. После rescue/freshness и до Hybrid gap planning работает\nSource Pulse v1 в production-shadow режиме без candidate influence и без OpenAI/Web\nSearch расходов.",
)
replace_once(
    auto_readme,
    "- `scripts/agency_discovery_recovery_entry.py` — idempotent recovery-entry\n  rescue перед Coverage;",
    "- `scripts/agency_discovery_recovery_entry.py` — idempotent recovery-entry\n  rescue перед Coverage;\n- `scripts/source_pulse.py` — bounded fixed-source RSS/HTML discovery collector;\n- `scripts/source_pulse_shadow.py` — fail-open production-shadow snapshot и\n  Search/Pulse fusion diagnostics перед Hybrid;\n- `config/source-pulse-v1.json` — fixed source registry; Tier B остаётся lead-only;",
)
replace_once(
    auto_readme,
    "- `daily-production.yml` — ежедневный Primary Recall v2, conditional agency\n  discovery rescue, hybrid completeness, editorial, fallback coverage, обложка,\n  сборка и публикация;",
    "- `daily-production.yml` — ежедневный Primary Recall v2, conditional agency\n  discovery rescue, Source Pulse v1 production shadow, hybrid completeness,\n  editorial, fallback coverage, обложка, сборка и публикация;",
)
auto_section = """### 3. Source Pulse v1 production shadow\n\nПосле conditional agency rescue и его Source Freshness Proof wrapper запускает\n`source_pulse_shadow.py`, а уже затем Hybrid считает gaps. Registry фиксирован в\n`config/source-pulse-v1.json`: Tier A содержит official/newsroom/IR surfaces, Tier B\n— региональные lead-only surfaces. Polling bounded и fail-open; каждый source имеет\nHTTPS host allowlist, DNS/private-IP и redirect guards, timeout/retry/response caps.\n\nТекущий stage намеренно диагностический: `candidate_influence=false`. Pulse не\nмутирует `candidates.json`, не участвует в significance/editorial и не меняет\nregional/adaptive decisions. Он не вызывает OpenAI/Web Search; глобальный лимит\nпо-прежнему 12 + 1 + 4 + 7 = **24 Web Search operations**.\n\n`preview/<DATE>/source-pulse.json` и\n`preview/production-daily/source-pulse-<DATE>.json` сохраняют deterministic snapshot,\nsource health и `pulse_only / both / search_only` diagnostics. Snapshot является\nчастью обычного Actions artifact. Повтор на том же artifact и same-day recovery не\nдолжны молча repoll'ить mutable sources. Любая Pulse transport/parser ошибка\n`complete_with_gaps/error_nonfatal` и не блокирует старый retrieval pipeline.\n\nЕжедневный независимый аудит сохраняется и должен использовать эти diagnostics для\nоценки реального дополнительного recall, false positives и отказов источников. До\nотдельного controlled experiment Pulse lead не становится candidate.\n\n### 4. Hybrid completeness v1\n"""
replace_once(auto_readme, "### 3. Hybrid completeness v1\n", auto_section)

agents_section = """## Source Pulse v1 production shadow contract\n\nStage 2 Dual Discovery runs `source_pulse_shadow.py` only after mandatory Primary and\nconditional agency-discovery rescue (including rescue Source Freshness Proof), and\nstrictly before Hybrid gap planning. This placement is intentional: Pulse must never\nmask `major_agencies raw=0/accepted=0`, change the rescue trigger, occupy Primary caps,\nor suppress the existing optional regional Hybrid health check.\n\nThe current production mode is **shadow only**. `automation/config/source-pulse-v1.json`\nmust keep `candidate_influence=false` and `repoll_on_recovery=false`. Source Pulse may\ncollect fixed-source leads and produce Search/Pulse fusion diagnostics, but it must not\nadd/remove/rank candidates, grant significance, bypass Source Freshness Proof, or create\na China/Russia publication quota. Tier B sources are lead-only and have no authority\nprivilege. Candidate influence or any model-based Pulse triage requires a separate\ncontrolled experiment, explicit production-cost review, documentation update and PR.\n\nSource Pulse itself performs zero OpenAI calls and zero Web Search operations. The\nglobal Web Search ceiling remains **24 = 12 Primary + 1 agency rescue + 4 Hybrid + 7\nCoverage**. Source/HTTP/DNS/parser failure is fail-open and must leave `candidates.json`\nunchanged. Persist `source-pulse.json` in the dated artifact plus a production-daily\ndiagnostic mirror. Persist `fetch_started` before network polling; a second invocation\nfor the same artifact reuses the saved snapshot and must not silently repoll mutable\nsources, including an interrupted `fetch_started` state. Normal same-day recovery reuses\nthe saved artifact and does not create a fresh Pulse snapshot.\n\nDiagnostics must expose source health plus `pulse_only`, exact/event `both`,\n`search_only`, cutoff ambiguity and archive duplicates. The daily independent audit is\npermanent and, whenever Source Pulse diagnostics are present, must separately assess\nSearch-vs-Pulse recall, Pulse-only high-signal leads, false positives/noise, source\noutages/parser drift, China/Asia and Russia benefit, and whether any shadow behavior\naccidentally influenced publication. Do not interpret a Pulse-only lead as automatic\nMust Include; the independent reference set remains authoritative for recall analysis.\n\n"""
replace_once(agents, "## Hybrid search completeness contract\n", agents_section + "## Hybrid search completeness contract\n")
