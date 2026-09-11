# Независимый аудит выпуска 2026-09-11

## Итог

- **Publication / FTP mechanics:** PASS.
- **Paid research/editorial at-most-once recovery:** PASS.
- **Recovery editorial-repair path:** **FAIL**.
- **Freshness policy:** PASS как fail-closed контракт, но **Source Freshness proof coverage:** FAIL по практической полноте.
- **High-signal completeness:** **FAIL**.
- **Strict Must Include publication recall:** **`3/10 = 30.0%`**.
- **Strict production awareness:** `7/10 = 70.0%`.
- **Strict final candidate recall:** `4/10 = 40.0%`.
- **Strict fresh+eligible / selected / published:** `3/10 = 30.0%`.
- **Search spend:** `12 Primary + 1 Agency Rescue + 4 Hybrid + 7 Coverage = 24/24` для фактического single-regional-gap ceiling.
- **Discovery Health v1:** `degraded`.
- **Strict editorial loss после fresh+eligible:** `0`.

Главный вывод: recall снова слабый, но сам editor не является главным bottleneck. Основные потери находятся в discovery/source-resolution/freshness, а сегодня добавился отдельный production defect в recovery: Coverage нашёл дополнительный candidate, после чего обязательный editorial rerun не смог запуститься.

## Production chain

Исходный scheduled run `34549170782` выполнил full research/editorial и сохранил paid artifact `daily-production-2026-09-11` (artifact `10180407321`), но остановился на mandatory Coverage audit с `retrieval_quality_resolution_unresolved`.

Recovery run `34553236194` восстановил already-paid same-day artifact, не повторял full research/editorial, завершил Coverage и опубликовал выпуск. Финальный artifact: `10181609687`. Publication commit: `67ba38be203d72281b2e3873508ea7257b78c81f`.

Последующий dispatch `34557161150` пришёл после публикации и не создал второй release.

**At-most-once paid behavior: PASS.**

## Production defect: Coverage добавил candidate, но editorial repair упал

Финальный Coverage artifact:

- `audit_status = complete_with_gaps`;
- `completed_calls = 7/7`;
- `audit_added_candidates = 1`;
- `editorial_rerun_required = true`;
- `editorial_rerun_performed = false`;
- `mode = existing_digest_after_editorial_repair_error`;
- `audit_state = not_started`.

Добавлен candidate: «Расследование: сотни постов премьер-министра Нидерландов и его партии были подготовлены ИИ».

После добавления recovery попытался вызвать `run_digest_preview.py`, но path editorial completion упал:

```text
ModuleNotFoundError: No module named 'openai'
```

`generate_digest_preview.py` импортирует OpenAI SDK, а recovery artifact-reuse path к этому моменту не имел установленного dependency, потому что fresh paid research был пропущен.

Workflow затем продолжил со старым seven-story digest. Нельзя утверждать, что новый candidate обязательно был бы выбран редактором, но rerun был обязателен и не состоялся. Следовательно, recovery способен потерять late-added Coverage candidate.

## Exact historical window

Saved diagnostics:

- healing/effective start: `2026-09-09T04:04:18+03:00`;
- continuity boundary `latest_archive_at`: `2026-09-10T04:04:18+03:00`;
- cutoff: `2026-09-11T04:05:09+03:00`.

Strict main window:

**`2026-09-10T01:04:18Z → 2026-09-11T01:05:09Z`.**

Healing-overlap допускается для публикации, но не улучшает strict recall. Qualcomm × AWS, например, относится к Sep9 core event и потому не является strict Sep11 hit.

## Опубликованные 7 сюжетов

1. Qualcomm × AWS custom AI chips / optical interconnect — healing overlap.
2. d-Matrix × NVIDIA NVLink Fusion.
3. OpenAI pause новых ChatGPT Pro $200 sign-ups из-за спроса на Astra.
4. UMG × ElevenLabs licensed AI remix platform.
5. Pocket FM: $500M run rate, 93% каталога и 99% нового контента создаются с AI.
6. OpenAI antimicrobial research use-case с Codex/ChatGPT.
7. Сбер GigaChat 3.5 Reasoning.

## Независимый B/reference control

B-проверка выполнена assistant-owned ordinary web/reference search по exact historical window. Production API/Web Search бюджет владельца не использовался.

Standalone assistant-side Terra в этой сессии не exposed. По проектному правилу выполнена **Terra-emulation/reference проверка**; ordinary web search не называется настоящим Terra run.

Сопоставление выполняется по event identity.

### Conservative strict Must Include set: 10

| # | Event | Independent evidence | Production path | Verdict |
|---|---|---|---|---|
| 1 | DeepSeek V4.1-Flash | Reuters `2026-09-10 06:32 UTC` + exact DeepSeek first-party Sep10 | замечен только через HuggingNews; `weak_source`; official release не разрешён | **MISS: source upgrade** |
| 2 | Positron AI: `$875M`, valuation `$5B` | Reuters Sep10; syndicated timestamp соответствует примерно `15:47 UTC` | current event отсутствует в saved production surface | **MISS: discovery** |
| 3 | Anthropic Threat Intelligence: Russia-linked espionage + alleged China-lab Claude distillation | Reuters Sep10; syndicated timestamp соответствует примерно `20:23 UTC` | новый Sep10 event отсутствует; есть только отдельный Sep9 alignment report | **MISS: discovery** |
| 4 | ChatGPT for Financial Services | exact OpenAI RSS lead `07:00 UTC` + Reuters Sep10 | Pulse нашёл exact official URL; promotion → `source_fetch_error`, HTTP 403 | **MISS: Pulse/freshness acceptance** |
| 5 | OpenAI × GSA multi-year government access / cyber-defense agreement | OpenAI first-party Sep10 + exact RSS lead `07:00 UTC` | Pulse нашёл exact official URL; promotion → HTTP 403 | **MISS: Pulse/freshness acceptance** |
| 6 | China AI-chip vendors повысили цены из-за HBM shortage | Reuters `2026-09-10 05:03 UTC` | current Huawei/Cambricon pricing event отсутствует | **MISS: discovery / Asia** |
| 7 | Senate probe по OpenAI/Hugging Face incident | Reuters Sep10 около `09:14 UTC`; AP candidate в Primary | initial `include + verified`, score 3; final `exclude + unconfirmed` из-за недоказанной source date | **MISS: Source Freshness Proof** |
| 8 | OpenAI pause ChatGPT Pro $200 sign-ups | official Help Center Sep10 | include, опубликовано | **HIT** |
| 9 | UMG × ElevenLabs licensed AI music platform | UMG first-party Sep10 + The Verge | include, опубликовано | **HIT** |
| 10 | Сбер GigaChat 3.5 Reasoning | Ведомости Sep10 + Sber/Habr material | include, опубликовано | **HIT** |

Reference URLs:

- https://www.reuters.com/world/asia-pacific/chinas-deepseek-launches-v41-flash-model-2026-09-10/
- https://www.deepseek.com/en/news/deepseek-v4-1-flash/
- https://www.reuters.com/business/ai-chip-startup-positrons-valuation-skyrockets-latest-funding-round-2026-09-10/
- https://www.reuters.com/legal/litigation/anthropic-disrupts-russian-chinese-ai-campaigns-targeting-its-claude-models-2026-09-10/
- https://www.reuters.com/business/openai-launches-chatgpt-financial-services-industry-2026-09-10/
- https://openai.com/index/expanding-ai-access-us-government/
- https://www.reuters.com/world/asia-pacific/chinas-ai-chipmakers-raise-prices-high-bandwidth-memory-shortage-bites-2026-09-10/
- https://www.reuters.com/business/openai-faces-senate-probe-into-hugging-face-incident-axios-reports-2026-09-10/
- https://help.openai.com/en/articles/9793128-about-chatgpt-pro-tiers
- https://www.universalmusic.com/universal-music-group-and-elevenlabs-announce-multi-year-strategic-agreement-beginning-with-a-new-licensed-ai-music-creation-platform/
- https://www.vedomosti.ru/technology/news/2026/09/10/1227662-sber-vipustil-ii-s-rezhimom

### Strong secondary controls вне strict denominator

- OpenAI Data agent: exact official RSS lead `2026-09-10T15:00:00Z`; Pulse promotion отклонён тем же HTTP 403; first-party page Sep10.
- ENISA получила доступ и тестирует Anthropic Mythos 5 и OpenAI GPT-6 Astra: Reuters `2026-09-10 08:56 UTC`; production event отсутствует.
- Moonshot рассматривает dual Hong Kong/Shanghai IPO: Reuters Sep10, но это ранняя стадия и secondary reporting, поэтому conservative Consider.
- d-Matrix × NVIDIA и Pocket FM опубликованы, но оставлены вне strict denominator как ниже по broad materiality.

## A/B metrics по слоям

Strict denominator: **10 Must Include**.

- reference controls independently verified: `10/10` по конструкции set;
- production awareness: `7/10 = 70.0%`;
- final candidate surface: `4/10 = 40.0%`;
- fresh+eligible: `3/10 = 30.0%`;
- selected: `3/10 = 30.0%`;
- published: **`3/10 = 30.0%`**.

Awareness hits: DeepSeek, Financial Services, GSA, Senate probe, OpenAI Pro, UMG × ElevenLabs, Sber.

Hard awareness misses: Positron, Anthropic Sep10 threat report, China HBM pricing.

Loss accounting:

- hard discovery: `3`;
- source upgrade: DeepSeek;
- Pulse/freshness transport: Finance + GSA;
- Source Freshness Proof: Senate;
- editor after fresh+eligible: `0` strict losses;
- publication after selected: `0` strict losses.

Production знает заметно больше (`70% awareness`), чем способен довести до публикации (`30%`). Основной leakage сегодня находится между awareness и publishable state.

## Retrieval anatomy

### Primary

- `12/12` mandatory searches;
- raw candidates `11`;
- final candidates `10`;
- five raw-zero/model-rejections-only directions: `major_agencies`, `business_investment_partnerships`, `china_asia_models`, `china_asia_integrations`, `legal_regulation`.

Positive control: Senate probe найден как `include + verified`.

Negative control: DeepSeek V4.1 замечен, но умер на `weak_source`, хотя exact first-party release существовал.

### Agency Rescue

- trigger `major_agencies_raw_zero`;
- Reuters-only;
- `1/1` operation;
- state `completed_no_addition`;
- raw / validated / accepted / added: `0 / 0 / 0 / 0`;
- `source_metadata_available = false`.

В том же window Reuters имел DeepSeek, Positron, Anthropic threat report, ChatGPT Financial Services, China HBM pricing и Senate/OpenAI follow-up.

После Sep9–Sep11 repeated zero-addition Reuters rescue является recurring provider/routing defect signal.

### Hybrid

- `4/4`;
- conditional +1 не нужен: unresolved regional gap только Asia;
- additions `0`;
- Asia остался unresolved.

Это плохо согласуется с наличием exact-window DeepSeek launch и China HBM story.

### Coverage

- `7/7` calls;
- все шесть required directions checked;
- added candidates `1`;
- `complete_with_gaps`;
- затем editorial repair упал на missing `openai` module.

Coverage retrieval сегодня реально нашёл новое, но downstream recovery не смог использовать результат.

### Search budget

**`12 + 1 + 4 + 7 = 24/24`.**

Добавлять ещё один search slot первым шагом не обосновано. Budget уже выбран полностью; потери концентрируются в routing/source-resolution/freshness.

## Source Pulse live status

- configured sources `16`;
- sources OK `12`;
- unavailable `4`;
- accepted leads `18`;
- promoted `6`;
- paid OpenAI calls `0`;
- Web Search operations `0`.

OpenAI RSS:

- HTTP 200;
- parsed `16`;
- window items `9`;
- exact fresh leads: GSA `07:00Z`, Financial Services `07:00Z`, Data agent `15:00Z`, antimicrobial `16:00Z`.

GSA, Financial Services и Data agent были `pulse_only` и все получили:

```text
SourceFreshnessError: source fetch failed: HTTPError: HTTP Error 403: Forbidden
```

Antimicrobial уже был найден Primary (`both_exact_url`), поэтому не доказывает unique Pulse uplift.

**Вывод:** OpenAI RSS discovery работает. Downstream direct-page proof блокирует значительную часть его ценности.

Qualcomm newsroom снова: HTTP 200, `parsed_items=0`, leads 0.

NSA AI route снова: HTTP 403, unavailable, contribution 0.

## Temporal/date reasoning defect

Saved Primary evidence для ответа Китая на американский AI-distillation advisory утверждает:

```text
AP датирует реакцию Китая средой ... календарная дата события установлена как 10 сентября 2026 года.
```

Но **10 сентября 2026 года — четверг; среда — 9 сентября**. Independent reporting также относит реакцию к среде 9 сентября.

То есть LLM-date reasoning сдвинул overlap event в Sep11 main window на +1 день. Candidate не был опубликован, потому что Source Freshness Proof fail-closed перевёл его в `exclude/unconfirmed`, поэтому фактической false-fresh публикации не произошло.

Сам defect реален: weekday/date consistency должна проверяться детерминированно.

## Discovery Health v1

Final status: **degraded**.

- Primary: healthy;
- Source Pulse: degraded;
- major agencies: indeterminate из-за missing source metadata;
- Hybrid: degraded, unresolved Asia;
- Coverage: degraded (`audit_state:not_started`) после editorial repair error, несмотря на completed retrieval.

Диагностика правильно не считает наличие семи stories доказательством healthy discovery.

## Что хорошо

1. Paid stages at-most-once работают: full research/editorial не повторился.
2. Публикация/FTP завершились после late-stage failure.
3. Search ceiling не нарушен.
4. Coverage реально добавил candidate.
5. OpenAI RSS уверенно обнаруживает exact first-party leads без paid search.
6. Freshness остаётся fail-closed.
7. Editor не потерял strict Must Include после fresh+eligible.

## Что плохо

1. Strict publication recall: **30%**. Это немного выше исправленных 25% Sep10, но denominators разные, поэтому устойчивым улучшением это не считается.
2. Awareness 70%, publication 30%: сильный leakage после discovery signal.
3. Recovery editorial repair сломан: новый Coverage candidate найден, rerun не состоялся, старый digest опубликован.
4. Reuters Agency Rescue снова zero-addition и без source metadata.
5. DeepSeek V4.1 умер на weak-source surface при существующем official release.
6. OpenAI Pulse exact leads снова блокируются direct-page HTTP 403.
7. Asia recall остаётся degraded при наличии DeepSeek и China-chip/HBM events.
8. Calendar reasoning дал Wednesday → Sep10, то есть +1-day error.
9. Qualcomm `200 + parsed 0`; NSA 403. Новые official routes всё ещё не прошли live acceptance.

## Что уже точно пора менять

### P0. Recovery editorial-repair environment

Доказательство production-level: Coverage добавил candidate и потребовал rerun, но `run_digest_preview.py` упал `ModuleNotFoundError: openai`.

Нужно гарантировать pinned runtime dependencies на любом artifact-reuse path, который способен вызвать editorial completion/repair. Нельзя повторять paid research. Acceptance: exact Sep11 artifact replay + no-addition/addition/rerun-success/rerun-failure/at-most-once соседние cases.

### P1. Exact official feed evidence → Source Freshness Proof

Два дня подряд OpenAI RSS имеет exact official URL + authoritative timestamp, но direct article HTTP 403 уничтожает pulse-only leads.

Нужен controlled contract: timestamp fixed official feed может участвовать в freshness proof только при exact canonical URL/host binding и строгих stale/conflict checks. `unknown` не становится fresh; fuzzy matches и произвольные feeds запрещены.

Acceptance: saved Sep10/Sep11 fixtures + stale, redirect, canonical mismatch, conflicting date, spoofed host negatives.

### P2. Agency/provider Reuters routing в существующем одном slot

Sep9–Sep11 Reuters rescue repeatedly даёт zero additions при наличии independently verified controls; Sep11 metadata unavailable.

Менять routing/diagnostics текущей одной operation. Не увеличивать Agency budget и общий ceiling. Acceptance: fixed-budget historical A/B Sep6–Sep11.

### P3. Weak-source high-signal authoritative upgrade

DeepSeek V4.1 найден, но только через weak source; exact first-party release существовал.

Нужен bounded source-neutral upgrade по event identity внутри существующего budget. Weak-source fail-closed сохраняется. Acceptance: positives + false-match/old-release/same-company-different-event negatives.

### P4. Deterministic weekday/date validation

Saved reasoning превратил Wednesday в Sep10, хотя это Thursday.

Нужно детерминированно проверять weekday/date/timezone consistency. Conflict должен снижать precision или давать unknown/recheck, а не сдвигать дату.

Acceptance: weekday-only, explicit weekday/date conflict, UTC/local boundary, month/year rollover.

### P5. Source Pulse route health

Qualcomm `200 + parsed 0`, NSA 403, OpenAI discovery работает, promotion transport нет.

Сначала чинить уже добавленные routes и health semantics, а не плодить новые registry rows.

## Что пока не пора менять

**Editorial ranking/prompt.** Strict Must Include, оставшиеся fresh+eligible, были выбраны. Чистого ranking failure сегодня нет.

**Search budget.** `24/24` уже использовано. Сначала repair routing/source-resolution/evidence reuse.

**Freshness strictness.** Gate предотвратил недоказанный candidate и candidate с ошибочным date reasoning. Ослаблять правило нельзя; нужно добывать лучшее доказательство.

## Historical comparison

- corrected Sep10 strict publication recall: `2/8 = 25.0%`;
- Sep11: **`3/10 = 30.0%`**.

Denominators различаются, поэтому это не статистический time-series KPI. Два последовательных live выпуска после #162 всё ещё существенно слабее controlled historical fixture result; новый сигнал Sep11 состоит в том, что Pulse awareness улучшается, но value блокируется acceptance/freshness transport.

## Scope / documentation

Audit-only change. Runtime, workflows, search queries, source registry, budget, editorial, freshness, recovery и publication behavior не меняются.

Проверены `README.md`, `automation/README.md`, `automation/ARCHITECTURE.md` и `AGENTS.md`; обновление не требуется, потому что runtime contract не меняется.

Любой runtime PR по P0–P5 требует отдельного architecture-wide dependency/regression audit и controlled experiment согласно repository contract.

## Финальный вердикт

**Техническая публикация 11 сентября состоялась, но completeness остаётся degraded. Strict Must Include publication recall = `3/10 = 30%`.**

Самая срочная новая проблема: **recovery editorial-repair path**. Система нашла дополнительный Coverage candidate, но не смогла прогнать обязательный editorial rerun из-за отсутствующего dependency и опубликовала старый digest.

Рекомендуемый порядок runtime work по силе evidence:

**P0 recovery editorial repair → P1 official-feed freshness evidence → P2 Agency Reuters routing → P3 source upgrade → P4 deterministic dates → P5 Source Pulse route health.**