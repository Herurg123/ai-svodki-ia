# Независимый аудит выпуска 2026-09-11

## Итог

- **Publication / FTP mechanics:** PASS.
- **Paid research/editorial at-most-once recovery:** PASS.
- **Recovery editorial-repair path:** **FAIL**.
- **Freshness policy:** PASS как fail-closed контракт, но **Source Freshness proof coverage:** FAIL по практической полноте.
- **High-signal completeness:** **FAIL**.
- **Strict Must Include main-window publication recall:** **`3/10 = 30.0%`**.
- **Strict production awareness:** `7/10 = 70.0%`.
- **Strict final candidate recall:** `4/10 = 40.0%`.
- **Strict fresh+eligible / selected / published:** `3/10 = 30.0%`.
- **Search spend:** `12 Primary + 1 Agency Rescue + 4 Hybrid + 7 Coverage = 24/24` для фактического single-regional-gap ceiling.
- **Discovery Health v1:** `degraded`.
- **Strict editorial loss после fresh+eligible:** `0`.

Главный вывод: выпуск снова технически опубликован, но recall остаётся слабым. Сегодня особенно хорошо разделяются четыре причины потерь:

1. hard upstream discovery misses;
2. weak-source event не повышается до authoritative source;
3. exact official Source Pulse leads теряются на direct-page Source Freshness transport;
4. уже после Coverage recovery не может выполнить обязательный editorial repair из-за отсутствующего Python dependency.

Поэтому менять editor/ranking первым снова не следует. Все strict Must Include, которые дошли до fresh+eligible состояния, редактор выбрал.

## Production chain

### Scheduled run

Исходный scheduled production run: `34549170782`.

- full research/editorial выполнен;
- paid artifact сохранён: `daily-production-2026-09-11`, artifact ID `10180407321`;
- обязательный Coverage audit дошёл до полного лимита попыток, но завершился `retrieval_quality_resolution_unresolved`;
- production job завершился failure до публикации.

### Recovery run

Recovery: `34553236194`.

- восстановил уже оплаченный same-day artifact;
- full research/editorial не повторялся;
- Coverage был продолжен и завершён;
- найден один дополнительный candidate;
- затем normalize/build/image/commit/deploy завершили публикацию;
- final artifact: `daily-production-2026-09-11`, artifact ID `10181609687`;
- publication commit: `67ba38be203d72281b2e3873508ea7257b78c81f`.

Следующий dispatch `34557161150` пришёл уже после публикации и не создал второй release.

**At-most-once paid behavior: PASS.** Downstream failure не заставил повторно оплачивать основной research/editorial.

## Новый recovery defect: Coverage нашёл candidate, но editorial repair не запустился

Финальный Coverage artifact:

- `audit_status = complete_with_gaps`;
- `completed_calls = 7/7`;
- `audit_added_candidates = 1`;
- `editorial_rerun_required = true`;
- `editorial_rerun_performed = false`;
- `mode = existing_digest_after_editorial_repair_error`;
- `audit_state = not_started`.

Добавленный candidate:

> «Расследование: сотни постов премьер-министра Нидерландов и его партии были подготовлены ИИ».

После добавления кандидата recovery попытался вызвать `run_digest_preview.py`, но путь editorial completion упал:

```text
ModuleNotFoundError: No module named 'openai'
```

Ошибка возникает при импорте `generate_digest_preview.py`, который импортирует `OpenAI`. Recovery окружение к этому моменту не имело установленного SDK, потому что основной paid research был восстановлен из artifact и install-stage для fresh research был пропущен.

После этого workflow сохранил старый seven-story digest и продолжил публикацию.

Это **реальный production defect**, а не гипотеза. Нельзя утверждать, что новый coverage candidate обязательно был бы выбран редактором, но система была обязана выполнить rerun и не смогла. Следовательно, текущий recovery path способен молча потерять late-added candidate после успешного Coverage rescue.

## Exact historical window

Saved research diagnostics:

- healing/effective start: `2026-09-09T04:04:18+03:00`;
- canonical continuity boundary `latest_archive_at`: `2026-09-10T04:04:18+03:00`;
- saved cutoff: `2026-09-11T04:05:09+03:00`.

Strict denominator использует только события после continuity boundary и до cutoff:

**`2026-09-10T01:04:18Z → 2026-09-11T01:05:09Z`.**

Healing-overlap события допустимы для выпуска, но не улучшают strict recall 11 сентября. Например, Qualcomm × AWS core event датирован 9 сентября и поэтому не является strict Sep11 hit, хотя опубликован корректно.

## Опубликованные 7 сюжетов

1. Qualcomm × AWS: многопоколенческое соглашение по кастомным AI-чипам и optical interconnect — healing overlap.
2. d-Matrix × NVIDIA NVLink Fusion для rack-scale XPU.
3. OpenAI временно приостановила новые подписки ChatGPT Pro $200 из-за спроса на Astra.
4. Universal Music Group × ElevenLabs: лицензированная AI-платформа для ремиксов.
5. Pocket FM: run rate $500 млн, AI производит 93% каталога и 99% нового аудиоконтента.
6. OpenAI: кейс Codex/ChatGPT для поиска антимикробных молекул.
7. Сбер: GigaChat 3.5 Reasoning.

## Независимый B/reference control

B-проверка выполнена assistant-owned ordinary web/reference search по exact historical window, без production API/Web Search бюджета владельца.

Standalone assistant-side Terra в этой сессии не exposed. По проектному правилу выполнена **Terra-emulation/reference проверка**, но ordinary web search не выдаётся за настоящий Terra run.

События сопоставляются по event identity, а не по совпадению заголовков.

### Conservative strict Must Include set: 10 событий

| # | Event | Независимое evidence | Production path | Verdict |
|---|---|---|---|---|
| 1 | DeepSeek V4.1-Flash | Reuters Sep10 06:32 UTC + exact DeepSeek first-party Sep10 | Primary заметил событие только через HuggingNews и отклонил `weak_source`; официальный release не был разрешён | **MISS: source upgrade** |
| 2 | Positron AI: $875M, valuation $5B | Reuters Sep10 10:47 ET / 14:47 UTC; funding details independently corroborated | current event отсутствует в saved candidate/rejection surface | **MISS: discovery** |
| 3 | Anthropic Threat Intelligence: Russia-linked espionage + alleged China-lab Claude distillation | Reuters Sep10 15:23 ET / 19:23 UTC | saved production содержит старый Sep9 alignment report, но новый Sep10 threat-intelligence event отсутствует | **MISS: discovery** |
| 4 | ChatGPT for Financial Services | OpenAI RSS exact URL Sep10 07:00 UTC + Reuters Sep10 | Source Pulse обнаружил exact official lead; `pulse_only` promotion отклонён: `source_fetch_error`, HTTP 403 | **MISS: Pulse → freshness acceptance** |
| 5 | OpenAI × GSA: multi-year government access / cyber-defense agreement | OpenAI first-party Sep10; exact RSS lead 07:00 UTC | Source Pulse обнаружил exact official lead; promotion отклонён HTTP 403 | **MISS: Pulse → freshness acceptance** |
| 6 | Китайские AI-chip vendors повышают цены из-за HBM shortage | Reuters Sep10 05:03 UTC; Huawei/Cambricon и другие | current Sep10 pricing event отсутствует в saved candidate/rejection surface | **MISS: discovery / Asia** |
| 7 | Senate probe / OpenAI × Hugging Face incident | Reuters Sep10 04:14 ET; AP candidate в Primary | Primary: initial `include + verified`, score 3; final candidate стал `exclude + unconfirmed` из-за недоказанной source publication date | **MISS: Source Freshness Proof** |
| 8 | OpenAI pause новых ChatGPT Pro $200 sign-ups | official Help Center Sep10 + production source | final candidate include, опубликовано | **HIT** |
| 9 | UMG × ElevenLabs licensed AI music platform | UMG first-party Sep10 + The Verge | final candidate include, опубликовано | **HIT** |
| 10 | Сбер GigaChat 3.5 Reasoning | Ведомости Sep10 + Sber/Habr first-party material | final candidate include, опубликовано | **HIT** |

Reference URLs:

- DeepSeek Reuters: https://www.reuters.com/world/asia-pacific/chinas-deepseek-launches-v41-flash-model-2026-09-10/
- DeepSeek official: https://www.deepseek.com/en/news/deepseek-v4-1-flash/
- Positron Reuters: https://www.reuters.com/business/ai-chip-startup-positrons-valuation-skyrockets-latest-funding-round-2026-09-10/
- Anthropic threat report Reuters: https://www.reuters.com/legal/litigation/anthropic-disrupts-russian-chinese-ai-campaigns-targeting-its-claude-models-2026-09-10/
- ChatGPT for Financial Services Reuters: https://www.reuters.com/business/openai-launches-chatgpt-financial-services-industry-2026-09-10/
- OpenAI government agreement: https://openai.com/index/expanding-ai-access-us-government/
- China AI chips / HBM: https://www.reuters.com/world/asia-pacific/chinas-ai-chipmakers-raise-prices-high-bandwidth-memory-shortage-bites-2026-09-10/
- Senate probe Reuters: https://www.reuters.com/business/openai-faces-senate-probe-into-hugging-face-incident-axios-reports-2026-09-10/
- OpenAI Pro tiers: https://help.openai.com/en/articles/9793128-about-chatgpt-pro-tiers
- UMG first-party: https://www.universalmusic.com/universal-music-group-and-elevenlabs-announce-multi-year-strategic-agreement-beginning-with-a-new-licensed-ai-music-creation-platform/
- Sber/Vedomosti: https://www.vedomosti.ru/technology/news/2026/09/10/1227662-sber-vipustil-ii-s-rezhimom

### Strong secondary controls вне strict denominator

Эти события подтверждают тот же root-cause pattern, но не добавляются в denominator, чтобы не раздувать его менее однозначными Must Include оценками:

- OpenAI Data agent in ChatGPT Work: exact official RSS lead `2026-09-10T15:00:00Z`, Source Pulse promotion отклонён тем же HTTP 403; first-party page Sep10.
- ENISA получила доступ и тестирует Anthropic Mythos 5 и OpenAI GPT-6 Astra: Reuters Sep10 08:56 UTC; production event отсутствует.
- Moonshot рассматривает dual Hong Kong/Shanghai IPO: Reuters Sep10, но сведения опираются на secondary reporting и раннюю стадию, поэтому conservative Consider.
- d-Matrix × NVIDIA и Pocket FM — опубликованные сильные/интересные сюжеты, но для conservative strict denominator ниже по broad materiality, чем controls выше.

## A/B metrics по слоям

Strict denominator: **10 Must Include**.

- independent reference controls verified: `10/10` по конструкции reference set;
- production awareness: `7/10 = 70.0%`;
- final candidate surface: `4/10 = 40.0%`;
- fresh + eligible к реальному editorial choice: `3/10 = 30.0%`;
- selected: `3/10 = 30.0%`;
- published: **`3/10 = 30.0%`**.

Awareness accounting:

- DeepSeek — seen, но only weak-source rejection;
- Financial Services — seen exact by Pulse;
- GSA agreement — seen exact by Pulse;
- Senate probe — candidate;
- OpenAI Pro — candidate;
- UMG × ElevenLabs — candidate;
- Sber — candidate;
- Positron — not seen as current event;
- Anthropic Sep10 threat report — not seen as current event;
- China HBM pricing — not seen as current event.

Loss accounting:

- **hard discovery:** Positron, Anthropic threat report, China HBM pricing;
- **source upgrade:** DeepSeek V4.1-Flash;
- **Pulse/freshness transport:** ChatGPT Financial Services, OpenAI × GSA;
- **Source Freshness Proof:** Senate probe;
- **editor after fresh+eligible:** `0` strict losses;
- **publication after selected:** `0` strict losses.

Таким образом, production знает заметно больше (`70% awareness`), чем способен довести до публикации (`30%`). Сегодняшний основной leakage находится между discovery-awareness и publishable candidate state.

## Retrieval anatomy

### Primary

- mandatory directions: `12/12`;
- raw candidates: `11`;
- validated/final: `10`;
- raw-zero/model-rejections-only directions: `5/12`:
  - `major_agencies`;
  - `business_investment_partnerships`;
  - `china_asia_models`;
  - `china_asia_integrations`;
  - `legal_regulation`.

Положительный control: Senate probe был найден как verified/include.

Негативный control: DeepSeek V4.1 был замечен, но только на weak-source surface; event умер до candidate, хотя exact first-party DeepSeek release существовал.

### Agency Rescue

- trigger: `major_agencies_raw_zero`;
- executed: `true`;
- one Reuters-only search;
- state: `completed_no_addition`;
- raw / validated / accepted / added: `0 / 0 / 0 / 0`;
- `source_metadata_available = false`.

В том же exact main window independently verified Reuters имел как минимум DeepSeek V4.1, Positron, Anthropic threat report, ChatGPT Financial Services, China AI-chip/HBM story и Senate/OpenAI follow-up.

После Sep9, Sep10 и Sep11 zero-addition Reuters rescue при наличии таких controls уже является recurring provider/routing defect signal, а не «неудачным днём».

### Hybrid

- `4/4` searches;
- conditional +1 не использовался, потому что unresolved regional gap был только Asia;
- additions: `0`;
- Asia gap остался unresolved.

Это особенно заметно на фоне exact-window DeepSeek launch и China AI-chip/HBM story.

### Coverage

Финальный recovery state:

- `7/7` calls;
- all six required directions checked;
- one candidate added;
- status `complete_with_gaps`;
- затем editorial repair упал на missing `openai` module.

То есть Coverage сегодня не был бесполезен: он реально добавил candidate. Но downstream recovery не смог воспользоваться результатом.

### Search budget

Фактический budget для single regional gap:

**`12 Primary + 1 Agency + 4 Hybrid + 7 Coverage = 24/24`.**

Поэтому увеличение search ceiling не является первым лекарством. Система уже тратит весь разрешённый budget и всё равно теряет события в source-resolution/freshness/routing layers.

## Source Pulse live status

Saved Source Pulse:

- configured sources: `16`;
- sources OK: `12`;
- unavailable: `4`;
- accepted leads: `18`;
- promoted: `6`;
- paid OpenAI calls: `0`;
- Web Search operations: `0`.

### OpenAI RSS

- HTTP `200`;
- `parsed_items=16`;
- `window_items=9`;
- свежие exact official leads включали:
  - OpenAI × GSA government agreement — `07:00Z`;
  - ChatGPT for Financial Services — `07:00Z`;
  - Data agent — `15:00Z`;
  - antimicrobial use-case — `16:00Z`.

Три `pulse_only` significant leads GSA / Financial Services / Data agent были отвергнуты одинаково:

```text
SourceFreshnessError: source fetch failed: HTTPError: HTTP Error 403: Forbidden
```

Antimicrobial story уже был найден Primary (`both_exact_url`), поэтому не является доказательством unique uplift Pulse.

**Вывод:** OpenAI RSS discovery plane работает; exact official feed timestamp и URL уже существуют, но downstream direct-page requirement уничтожает значительную часть ценности.

### Qualcomm newsroom

Повторяется предыдущий live defect:

- HTTP `200`;
- `parsed_items=0`;
- `accepted_leads=0`.

Transport-level `ok` при заведомо непустой newsroom не является достаточным parser-health proof.

### NSA AI route

- HTTP `403`;
- source unavailable;
- contribution `0`.

## Temporal/date reasoning defect

Saved Primary candidate про ответ Китая американскому AI-distillation advisory содержит:

```text
AP датирует реакцию Китая средой ... календарная дата события установлена как 10 сентября 2026 года.
```

Но **10 сентября 2026 года — четверг**, а среда — 9 сентября.

Independent reporting также относит китайскую реакцию к среде 9 сентября. Следовательно, current reasoning сдвинул event из healing overlap в Sep11 main-window на +1 день.

Candidate всё равно не был опубликован, потому что Source Freshness Proof fail-closed перевёл его в `exclude/unconfirmed`. Поэтому фактического false-fresh publication сегодня не произошло. Но сам calendar/date resolver defect реален и уже опасен: при успешном source proof он способен искажать main-window membership.

Это отдельный deterministic-layer repair: weekday/date consistency не должна зависеть от свободного LLM calendar reasoning.

## Discovery Health v1

Финальный status: **`degraded`**.

- Primary: healthy;
- Source Pulse: degraded;
- major agencies: indeterminate из-за missing source metadata;
- Hybrid: degraded, unresolved Asia;
- Coverage: degraded, потому что final status сохранил `audit_state:not_started` после editorial repair error несмотря на completed Coverage retrieval.

Диагностика правильно не считает seven-story volume доказательством healthy discovery.

## Что хорошо

1. **Paid stages at-most-once работают.** Recovery не повторил full research/editorial.
2. **Публикация и deploy завершились.** После late-stage failure выпуск всё же вышел.
3. **Search ceilings соблюдены.** Никакого budget overrun.
4. **Coverage сегодня реально добавил candidate.** Сам retrieval rescue способен находить новое.
5. **OpenAI RSS уверенно обнаруживает exact first-party события без paid search.** Discovery route имеет реальную ценность.
6. **Freshness остаётся fail-closed.** Senate и ошибочно датированный China follow-up не были опубликованы без source proof.
7. **Editor не потерял strict Must Include после fresh+eligible.** Ranking не является главным доказанным bottleneck сегодняшнего выпуска.

## Что плохо

1. **Strict publication recall остаётся низким: 30%.** Это немного выше исправленных 25% Sep10, но denominators различаются, поэтому считать это устойчивым улучшением нельзя.
2. **Production awareness 70%, publication 30%.** Большая часть ущерба происходит уже после того, как система получила сигнал о событии.
3. **Recovery editorial repair сломан.** Coverage нашёл новый candidate, но rerun не запустился из-за отсутствующего `openai` package, а workflow продолжил со старым digest.
4. **Agency Rescue третий день демонстрирует практически бесполезный Reuters path:** zero additions, а Sep11 ещё и source metadata unavailable.
5. **DeepSeek V4.1 показывает weak-source → dead-end.** Exact official release существовал, но production не разрешил его.
6. **OpenAI Source Pulse снова блокируется direct-page 403.** GSA, Financial Services и Data agent были обнаружены точным official RSS, но не promoted.
7. **Asia recall остаётся красным.** Hybrid 4/4 дал zero additions, хотя в exact window были DeepSeek launch и существенный China-chip/HBM story.
8. **Calendar reasoning снова ненадёжен.** Wednesday ошибочно преобразован в Sep10, хотя это Thursday.
9. **Qualcomm route по-прежнему `200 + parsed 0`; NSA route по-прежнему 403.** Добавленные official routes пока не прошли live acceptance.

## Что уже точно пора менять

### P0. Recovery editorial-repair environment

**Доказательство:** production recovery добавил Coverage candidate, установил `editorial_rerun_required=true`, но rerun упал `ModuleNotFoundError: openai`.

**Что менять:** recovery/runtime dependency setup так, чтобы любой путь, способный вызвать `run_digest_preview.py` / editorial completion после artifact reuse, гарантированно имел необходимые pinned dependencies.

**Что сохранить:**

- не повторять уже оплаченный full research;
- не ломать at-most-once publication;
- не превращать repair в новый paid discovery pass;
- fail-closed или явно доказанный fallback, а не тихое игнорирование найденного candidate.

**Приёмка:** offline replay exact Sep11 recovery artifact + neighboring cases: no added candidate, one added candidate, rerun success, rerun failure, pre-existing valid digest, at-most-once paid-stage proof.

### P1. Exact official feed evidence → Source Freshness Proof

**Доказательство:** два дня подряд OpenAI official RSS видит exact URL + authoritative feed timestamp, но direct article fetch 403 уничтожает pulse-only leads. Sep11 потеряны как минимум GSA, Financial Services и Data agent.

**Что менять:** controlled contract для exact canonical first-party feed entry: authoritative publication timestamp из fixed official feed может участвовать в source-freshness proof, если URL identity, host, date/window и canonical binding доказаны детерминированно.

**Что не менять:**

- `unknown` не становится fresh;
- arbitrary RSS/aggregator не получает такой privilege;
- никаких fuzzy URL matches;
- stale/conflicting timestamps должны fail-closed.

**Приёмка:** saved Sep10/Sep11 OpenAI fixtures + stale, redirect, canonical mismatch, conflicting-date и spoofed-host negatives.

### P2. Agency/provider Reuters routing в существующем одном slot

**Доказательство:** repeated zero-addition Reuters rescue при множестве independently verified Reuters controls; Sep11 source metadata снова unavailable.

**Что менять:** provider/domain routing и diagnostics текущей одной Agency operation, чтобы была доказуема фактическая Reuters retrieval surface и различались `provider no result`, `metadata unavailable`, `model reject`, `source resolution failure`.

**Что не менять:** Agency budget `<=1` и общий search ceiling.

**Приёмка:** historical fixed-budget A/B Sep6–Sep11 на тех же Reuters controls.

### P3. Weak-source high-signal authoritative upgrade

**Доказательство:** DeepSeek V4.1 production увидел через HuggingNews и correctly отказался публиковать weak source, но exact DeepSeek first-party release существовал в том же окне.

**Что менять:** bounded source-neutral upgrade path, использующий event identity как seed для authoritative proof внутри существующего search budget.

**Что не менять:** weak-source fail-closed; нельзя публиковать aggregator просто потому, что событие выглядит важным.

**Приёмка:** fixed-budget historical positives + false-match / old-release / same-company-different-event negatives.

### P4. Deterministic weekday/date consistency

**Доказательство:** saved evidence преобразовал `Wednesday` в `2026-09-10`, хотя Sep10 был Thursday.

**Что менять:** deterministic weekday/date validation вокруг LLM-derived date. Несовпадение weekday/calendar должно снижать precision или давать unknown/recheck, но не свободно сдвигать event на день.

**Приёмка:** timezone boundary, weekday-only, explicit date+weekday conflict, UTC/local conversion, month/year rollover.

### P5. Source Pulse route health

**Доказательство:** Qualcomm `HTTP 200 + parsed 0`, NSA 403, OpenAI discovery works but promotion transport fails.

**Что менять:** route-health semantics и parser/transport fixtures для уже добавленных official rows.

**Что не делать:** не добавлять новые registry rows, пока текущие routes не дают доказанного live contribution.

## Что пока не пора менять

### Editorial ranking / prompt

Сегодня нет clean evidence, что editor отбрасывает strict Must Include после того, как candidate действительно fresh+eligible:

- DeepSeek не дошёл до candidate;
- Positron/Anthropic/HBM не найдены;
- Finance/GSA умерли на Pulse freshness transport;
- Senate умер на Source Freshness Proof;
- OpenAI Pro, UMG и Sber, оставшиеся fresh+eligible, были выбраны.

Поэтому изменение ranking prompt сейчас смешает причинность и не исправит основной leakage.

### Search budget

`24/24` уже использовано. Следующий полезный эксперимент должен улучшать routing/source-resolution/evidence reuse при том же ceiling, а не добавлять 25-й запрос по принципу «ещё раз поискать, вдруг теперь интернет проникнется».

### Ослабление freshness

Freshness gate предотвратил как минимум один кандидат с недоказанной source date и один кандидат с ошибочным date reasoning. Ослаблять его нельзя; нужно улучшать доказательство.

## Historical comparison

Исправленный Sep10 audit: strict publication recall `2/8 = 25.0%`.

Sep11: **`3/10 = 30.0%`**.

Denominator различается, поэтому это не статистический time-series KPI. Однако два последовательных live выпуска после #162 остаются значительно слабее controlled historical fixture result. Более важное новое наблюдение Sep11: Source Pulse awareness становится заметно лучше, но value не доходит до publication из-за acceptance/freshness transport.

## Scope / documentation

Этот PR является audit-only evidence change. Он не меняет runtime, workflows, search queries, source registry, budget, editorial, freshness, recovery или publication behavior.

Проверены `README.md`, `automation/README.md`, `automation/ARCHITECTURE.md` и `AGENTS.md`; обновление не требуется, потому что runtime contract не изменяется.

Любой runtime PR по P0–P5 должен отдельно выполнить architecture-wide dependency/regression audit и controlled experiment согласно repository contract.

## Финальный вердикт

**Выпуск 11 сентября опубликован технически успешно, но retrieval/completeness остаётся degraded. Strict Must Include publication recall = `3/10 = 30%`.**

Самая срочная новая проблема сегодня — не ranking и не количество search calls, а **сломанный recovery editorial-repair path**: система нашла дополнительный Coverage candidate, но не смогла повторно прогнать editorial из-за отсутствующего dependency и всё равно опубликовала старый digest.

Следующий порядок runtime work по силе evidence:

**P0 recovery editorial repair → P1 official-feed freshness evidence → P2 Agency Reuters routing → P3 source upgrade → P4 deterministic dates → P5 Source Pulse route health.**