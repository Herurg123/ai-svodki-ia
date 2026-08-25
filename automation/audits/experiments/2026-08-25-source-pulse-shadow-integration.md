# Source Pulse v1 — production shadow integration audit

Дата: 2026-08-25  
Статус: **stage 2 / production shadow only**  
Production API пользователя при подготовке: **не использовался**

## Цель

Подключить проверенный fixed-source Source Pulse v1 к реальному fresh production contour так, чтобы на следующем штатном выпуске появились реальные diagnostics второго discovery-plane, но ни один Pulse lead пока не мог повлиять на candidate pool, editorial или публикацию.

Это намеренно промежуточный этап перед Event Fusion с candidate influence. Он нужен, чтобы ежедневный независимый аудит сначала измерил фактические source health, `pulse_only`, `both`, `search_only`, региональные blind spots и false positives на живом окне.

## Точка интеграции

Source Pulse shadow вызывается внутри `hybrid_search_completeness.py`:

1. Primary Recall 12/12 уже завершён.
2. Conditional agency discovery rescue уже получил свой независимый trigger и, если добавил Reuters candidate, прошёл pre-Hybrid Source Freshness Proof.
3. Только после этого читается фактический post-rescue `candidates.json` и запускается Source Pulse shadow.
4. Shadow сохраняет snapshot + fusion diagnostics.
5. Затем Hybrid рассчитывает regional gaps и выполняет старые 3+1 Web Search passes без изменения входного candidate pool.

Так Pulse не может скрыть `major_agencies raw=0/accepted=0`, изменить rescue trigger, занять Primary cap или подавить adaptive Hybrid.

## Что сохраняется

Артефакт `automation/preview/<DATE>/source-pulse.json` и зеркальная диагностика `automation/preview/production-daily/source-pulse-<DATE>.json` содержат:

- состояние каждого fixed source и HTTP/fallback diagnostics;
- deterministic `snapshot_hash`;
- найденные leads с tier/region/time precision;
- `pulse_only`, `both_exact_url`, `both_event_fingerprint`, `search_only`;
- cutoff-date ambiguity и archive URL duplicate как отдельные non-actionable состояния;
- итоговые counts по Tier A/Tier B, Russia и China/Asia.

Compact Source Pulse summary также прикладывается к `hybrid-completeness.json`, но не меняет Hybrid decisions.

## Fail-open и recovery

- Source Pulse не вызывает OpenAI и Web Search: `paid_api_calls=0`, `web_search_operations=0`.
- Любая DNS/HTTP/parse/source ошибка даёт `complete_with_gaps / error_nonfatal`; старый Hybrid продолжает работу.
- До network fetch сохраняется `state=fetch_started`.
- Повторный вызов для того же artifact переиспользует `source-pulse.json` и не poll'ит mutable sources снова.
- Если сохранён только `fetch_started`, повторный polling в том же artifact также запрещён; состояние становится diagnostic `interrupted_no_repoll`.
- Обычная same-day recovery не запускает `run_digest_preview.py`/Hybrid заново, поэтому сохранённый snapshot приезжает внутри Actions artifact и не обновляется молча.

## Candidate influence

На этом этапе жёстко:

- `candidate_influence=false`;
- Pulse не добавляет candidates;
- Pulse не повышает significance;
- Tier B не является publication authority;
- нет Pulse LLM triage;
- нет alternate-source freshness corroboration;
- нет China/Russia publication quota.

Будущий candidate influence требует отдельного эксперимента и отдельного production PR.

## Search / cost invariants

Без изменений:

- Primary: 12;
- agency discovery rescue: max 1;
- Hybrid: max 4;
- Coverage: max 7;
- Web Search ceiling: **24**;
- Source Freshness Proof v1 unchanged;
- editorial / archive semantic dedupe unchanged.

## Независимый regression review

Добавлены tests для:

- exact URL overlap → `both_exact_url`;
- unmatched Pulse → `pulse_only`;
- unmatched Search candidate → `search_only`;
- cutoff ambiguous и archive duplicate не становятся actionable shadow leads;
- source snapshot вызывается один раз и затем переиспользуется;
- `fetch_started` не вызывает повторный polling;
- collector failure nonfatal и byte-for-byte не меняет `candidates.json`;
- статический order guard: agency freshness → Source Pulse shadow → Hybrid gap planning;
- workflow и `run_digest_preview.py` не получают отдельный прямой Pulse invocation.

## Дополнительный hardening review

Перед финальным CI stage 2 отдельно проверен на production-специфические seam risks. Найдены и исправлены:

- **diagnostic secret hygiene:** Pulse URL normalization теперь удаляет token/signature/credential/API-key query parameters, а opaque source item IDs сохраняются только как hash;
- **runtime config drift:** shadow wrapper сам fail-open проверяет `mode=production_shadow`, `candidate_influence=false` и `repoll_on_recovery=false`, а не полагается только на CI;
- **pre-Hybrid overstatement:** один и тот же snapshot теперь сравнивается повторно после Hybrid без network repoll, поэтому аудит может отличать `pulse_only` до Hybrid от того, что Hybrid позже всё-таки восстановил;
- **latency observability:** snapshot summary сохраняет суммарный и максимальный elapsed fetch time. Sequential collector остаётся bounded (10 s × 2 attempts per URL) и fail-open; реальную задержку надо отдельно измерять в ежедневном аудите первого live shadow sample.

Event-fingerprint matching намеренно остаётся консервативной diagnostic heuristic. `pulse_only` не является автоматически подтверждённым retrieval miss или Must Include; это обязан перепроверить независимый reference-set audit.

## Architecture verdict

**GO для production-shadow этапа при зелёном полном CI.**

Риск влияния на содержание выпуска ограничен тем, что shadow не мутирует candidate pool и не участвует в editorial decisions. Основные новые operational risks — source latency/outage/HTML changes — изолированы fail-open. Следующий meaningful evidence должен прийти не от ещё одного synthetic replay, а от ежедневного независимого аудита первого реального production run с `source-pulse.json`.
