# Source Pulse v1 — offline prototype implementation audit

Дата: 2026-08-25  
Статус: **research-only / not wired into production**  
Production OpenAI API: **не использовался**  
Web Search operations: **0**

## Цель первого этапа

Реализовать проверяемый второй discovery-канал как самостоятельный deterministic sidecar, не меняя `Daily production digest`, Primary Recall 12/12, agency rescue, Hybrid, Coverage, Source Freshness Proof, editorial или publication/recovery behavior.

Прототип обязан уметь: читать fixed-source registry, разбирать RSS/Atom и HTML/index pages, fail-open переживать недоступность одного источника, фильтровать effective window, маркировать cutoff-day date-only ambiguity, нормализовать URL, формировать диагностические event/exact fingerprints, сравнивать URL с архивом и сохранять deterministic snapshot identity.

## Реализованный contour

`automation/config/source-pulse-v1.json` содержит fixed registry из 12 source families:

- Tier A / official: Baidu IR, Alibaba IR/HKEX, Alibaba Cloud Blog, Marvell IR, NVIDIA Recent News, Yandex IR, XPENG IR, DeepSeek official news, MWS News, VK Press;
- Tier B / lead-only: ITHome AI, CNews.

Tier B не является authority и не получает никаких publication privileges. Registry — prototype source set, не региональная квота и не whitelist итоговых новостей.

`automation/scripts/source_pulse.py`:

- не импортируется ни одним production workflow/script;
- не вызывает OpenAI и не использует Web Search;
- использует fixed HTTPS host allowlist;
- проверяет literal/private IP и DNS resolution;
- валидирует redirect target до follow;
- bounded fetch: 10 s timeout, 2 attempts, 1.5 MB response cap;
- per-source fail-open;
- RSS/Atom + HTML/JSON-LD parsing;
- поддерживает HTML fallback после неработающего RSS endpoint;
- ограничивает items per source и global lead count;
- exact cutoff timestamp применяется к datetime evidence;
- date-only item на cutoff calendar date сохраняется только как `cutoff_ambiguous=true`, то есть не становится freshness proof;
- archive URL duplicate только маркируется в research snapshot; окончательная semantic/archive fusion остаётся будущим production stage;
- event fingerprint диагностический, а не replacement существующего semantic dedupe;
- `snapshot_hash` не зависит от `fetched_at`, network latency и текста transport exception.

## Независимый architecture review реализации

Перед фиксацией прототипа отдельно проверены failure modes, которые могли бы превратить новый discovery-plane в новый источник регрессий.

### Найдено и исправлено до PR

1. **RSS fallback parser mismatch.** Исторически подтверждённый XPENG RSS endpoint может отвечать HTTP 403. Первая версия prototype наследовала RSS parser и для HTML fallback, из-за чего XPENG control не восстанавливался. Исправлено auto-detection фактического XML/HTML payload. После исправления weekly replay вернулся к ожидаемым 9/13.
2. **Nondeterministic snapshot hash.** Первая версия включала `elapsed_ms` в hash payload. Это делало одинаковый source snapshot разным при recovery. Исправлено: hash строится только по semantic state, source status/http state и leads; wall-clock latency/fetched_at/error text остаются diagnostics, но не identity.
3. **Redirect/SSRF boundary.** Простая final-URL проверка происходила бы уже после автоматического redirect. Добавлен custom redirect handler: redirect target проверяется против fixed HTTPS host allowlist и public DNS **до** follow. Initial host DNS также должен разрешаться только в global IP.

### Что намеренно НЕ реализовано на первом этапе

- никакой интеграции в `daily-production.yml`;
- никакого merge с Primary candidate pool;
- никакого LLM Pulse Triage;
- никакого дополнительного paid API call;
- никакого изменения 24-search ceiling;
- никакого alternate-source freshness corroboration;
- никакой региональной publication quota;
- никакого ослабления Source Freshness Proof.

Это удерживает причинность эксперимента: первый этап проверяет только deterministic source discovery/snapshot layer.

## Historical replay 19–25 августа

Machine-readable fixture: `automation/fixtures/source-pulse/2026-08-19-to-25.json`.

Прототип повторно воспроизводит результат предыдущего независимого bake-off:

- strict miss-day instances: **13**;
- recovered leads: **9**;
- recovery rate: **69.2%**;
- production API calls: **0**;
- Web Search operations: **0**.

По дням:

| День | Strict controls | Pulse v1 |
|---|---|---|
| 19 авг | Round Hill | miss |
| 20 авг | Google/Marvell, Baidu | **2/2 hit** |
| 21 авг | Broadcom debt, Alibaba earnings, Google/Marvell repeat | **2/3 hit** |
| 22 авг | Broadcom debt repeat | miss |
| 23 авг | Nvidia server pricing, DeepSeek Vision | **1/2 hit** |
| 24 авг | Alibaba AI placement | **1/1 hit** |
| 25 авг | Wan3.0, XPENG robotics, NVIDIA Groq 3 LPX | **3/3 hit** |

Negative controls сохраняются: prototype не создаёт искусственный recovery для Round Hill, Broadcom private debt и Nvidia supply-chain pricing. Это снова подтверждает, что Pulse дополняет, но не заменяет Web/agency discovery.

## Offline regression coverage

Добавлены deterministic unit tests для:

- RSS datetime parsing;
- HTML/JSON-LD parsing;
- malformed RSS;
- RSS → HTML fallback;
- 403 + fallback;
- complete source outage fail-open;
- parse error fail-open;
- exact after-cutoff rejection;
- cutoff-day date-only ambiguity;
- archive URL duplicate marking;
- tracking URL normalization;
- mutable URL/event fingerprint separation;
- private/wrong-host rejection;
- quiet stale-only window;
- deterministic snapshot hash;
- full weekly 9/13 replay.

Локальный prototype suite: **16/16 PASS** до отправки в GitHub CI.

## Architecture verdict первого этапа

**PASS / READY FOR PROTOTYPE PR.**

На этом этапе новая архитектура не может ухудшить production recall/freshness, потому что production её ещё не исполняет. При этом кодовая форма второго discovery-plane уже проверяет ключевые будущие invariants: fixed source boundary, fail-open isolation, bounded IO, exact window, no freshness privilege, deterministic recovery identity и историческую воспроизводимость.

Следующий decision gate после CI/merge этого research-only этапа: отдельно решить, подключать ли Source Pulse snapshot к будущему Event Fusion между Primary/rescue и Hybrid. До такого решения ежедневный production и ежедневный независимый аудит остаются без изменений.
