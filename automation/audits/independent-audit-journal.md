# Журнал независимых аудитов ИИ-Сводки

Последнее обновление: 2026-09-05  
Назначение: накопление независимых проверок полноты и свежести ежедневной ИИ-Сводки без расходования production API пользователя.

> Историческая часть журнала периодически сжимается: сохраняются ежедневные verdict, подтверждённые misses, повторяющиеся паттерны и принятые архитектурные решения. Детальные отчёты и controlled experiments хранятся в `automation/audits/` и `automation/audits/experiments/` и не дублируются здесь целиком.

## Как использовать журнал

После каждого substantive production-дня:

1. зафиксировать scheduled/final run, production SHA и exact effective window;
2. независимо проверить окно на assistant-owned ресурсах, не используя production API пользователя;
3. разделять retrieval/source-pool miss, source-resolution failure, editorial rejection, stale, duplicate/material update, after-cutoff и infrastructure/API failure;
4. отдельно проверять major agencies, China/Asia, Russia, Source/Event Freshness, Hybrid/Coverage, budgets и source concentration;
5. новый retrieval incident превращать в permanent fixture/test и отражать в `automation/specs/search-change-validation-matrix.md`;
6. query wording/ranking changes проверять на Terra-equivalent assistant tool, когда он exposed; ordinary assistant web search нельзя выдавать за Terra;
7. infrastructure/API failure до meaningful retrieval execution не включать в recall/completeness статистику.

---

## Сжатая историческая серия 17–28 августа 2026

| Дата/серия | Verdict | Ключевой результат |
|---|---|---|
| 17–23 августа | freshness стабилизирован, completeness нестабильна | Source Freshness v1 убрал stale после 17 августа; повторялись Reuters/agency, China/Asia и infrastructure misses; short digest сам по себе не считался дефектом. |
| 24 августа | false-zero | Полный 24-search pipeline пропустил Reuters Alibaba AI-financing control; agency route/rescue дал zero pool. |
| 25 августа, scheduled | excluded | API 429 `credit_balance_exhausted` до завершения первого Primary; не считается retrieval sample. |
| 25 августа, substantive rerun | FAIL completeness / PASS freshness | 12 Primary + rescue + Hybrid + Coverage исполнены; misses Alibaba Wan3.0, Xpeng robotics funding, NVIDIA Groq 3 LPX; agency rescue `consulted_sources=[]`; финал 3/3 TechCrunch. |
| 25 августа Source Pulse experiment | GO bounded sidecar | Fixed-source replay восстановил большую долю historical misses без Web Search; Pulse не заменяет agency/web discovery. |
| 28 августа | architecture PASS | Source Pulse v1.2 + единственный conditional fifth Hybrid search для одновременных Russia+China/Asia gaps; ordinary ceiling 24, double-gap ceiling 25. |

Устойчивые выводы августа:

- freshness fail-closed нельзя ослаблять ради recall;
- `major_agencies raw=0` неоднократно сосуществовал с independently verified Reuters events;
- provider/source-pool routing оказался отдельным классом дефекта, не сводимым к одной broad query;
- China/Asia model/product и infrastructure/chips требуют отдельного наблюдения;
- дополнительный search разрешается только после bounded experiment, а не как реакция на любой short digest.

---

## 29 августа – 2 сентября: deterministic health/freshness hardening

За эту серию в production и offline replays закреплены четыре ключевых механизма:

- **P1 Event Freshness**: event origin отделён от source-page publication; reliable stale event блокируется, unknown origin сохраняет recall и идёт в fail-closed Source Freshness.
- **P2 Source Pulse Yandex date repair**: только corroborated first-party URL/date evidence, без глобального body-date parsing.
- **P3 provider/source routing**: regional/agency representative anchors и Reuters rescue routing при неизменных search ceilings.
- **P4 regional-health viability**: early healthy регион может только переоткрыться, если exact Primary survivor исчез после filtering; Pulse не может скрыть Search gap.

1 сентября post-freshness agency-health replay доказал lifecycle defect: early accepted agency candidate мог подавить rescue после того, как этот candidate позднее был отфильтрован. Исправление разрешает использовать только ранее неистраченный единственный Reuters slot и сохраняет at-most-once recovery.

2 сентября full-volume production показал, что **7+ опубликованных сюжетов не доказывают здоровый retrieval**: независимый reference set дал bounded recall `7/11 = 63.6%`, при этом сохранялись hard upstream misses. После этого введён volume-independent `Discovery Health v1`.

---

## 3 сентября 2026 — business recall treatment

Полный отчёт: `automation/audits/2026-09-03-independent-release-audit.md`.

Ключевые observations:

- original fresh Primary израсходовал 12/12 searches;
- Broadcom был замечен только через weak aggregate и корректно rejected, но независимый Reuters source существовал;
- отдельно подтверждены Enflame и OpenAI automated-shutdown misses;
- проблема классифицирована как source/ranking/resolution seam, а не как разрешение принимать weak source;
- assistant-side A/B показал узкий gain от business query с `revenue monetization ads earnings`; treatment принят без дополнительного search;
- blanket rewrite всех 12 queries и generic `weak_source → verified` отвергнуты.

Принято: PR #147, business-only treatment, Primary ceiling остаётся 12.

---

## 4 сентября 2026 — short digest и свободный 25-й slot

Полный отчёт: `automation/audits/2026-09-04-independent-release-audit.md`.  
Эксперимент: `automation/audits/experiments/2026-09-04-short-digest-reserve-ab.md`.

Production технически успешен, но финальный digest содержал 4 сюжета. Search spend:

- Primary 12;
- Agency Rescue 1;
- Hybrid 5;
- Coverage 6;
- итого 24 при double-gap ceiling 25.

Независимо подтверждены сильные in-window misses:

- OpenAI Daybreak for Frontline Defenders ($1B program);
- Figure × Nscale (до 100k Vera Rubin GPUs, initial compute commitment $3.5B, intent >$6B);
- MBZUAI K2 Horizon (шесть fully-open foundation models 0.9B–375B);
- Microsoft MAI-Transcribe-2.

Editorial short-mode оценён положительно: слабые `consider` не использовались как padding. Upstream recall при этом признан degraded.

Гипотеза seventh-slot short-digest reserve получила assistant-side signal, но **NO-GO** для runtime: отдельного Terra tool не было, а seventh Coverage slot уже имеет приоритетные resolution/agency/sentinel semantics и same-day at-most-once contract.

---

## 5 сентября 2026 — full budget, repeated misses и temporal false rejection

Полный отчёт: `automation/audits/2026-09-05-independent-release-audit.md`.  
Controlled experiment: `automation/audits/experiments/2026-09-05-temporal-boundary-and-accumulated-recall.md`.

### Production

Run `33934617471`, fresh scheduled path, publication commit `7a5fda338f7fe00a320c47995a1ababbc758ef69`.

Effective window:

`2026-09-03T03:58:49+03:00` → `2026-09-05T03:57:22+03:00`.

Опубликовано 6 сюжетов, `publication_mode=short`, validation valid. Discovery Health = `degraded`.

Search spend достиг полного conditional ceiling:

- Primary `12/12`;
- Agency Discovery Rescue `1/1`;
- Hybrid `5/5`;
- Coverage `7/7`;
- **итого 25/25**.

Это снимает простую гипотезу, будто системный recall gap лечится лишь использованием «свободного 25-го search»: на этом дне свободного slot не было, а misses остались.

### Независимые hard/strong controls

В exact window отсутствовали в saved candidate/source pools:

- Reuters ByteDance syndicated loan `$29.6B` для AI expansion/infrastructure;
- Reuters US–China first dedicated AI-safety dialogue;
- Gimlet Labs `$300M` Series B / `$3B` valuation для multi-silicon AI inference;
- Reuters material disclosure про rogue OpenAI agents и немецкий wiki-сайт;
- **повторно** Figure × Nscale;
- **повторно** MBZUAI K2 Horizon.

Figure × Nscale и K2 Horizon пропущены второй production-день подряд, несмотря на healing overlap. Это повышает их из разового ranking miss в repeated cross-day recall signal.

Daybreak на этот раз был найден, но Axios page не прошла Source Freshness из-за HTTP 403. То есть тот же сюжет переместился из pure discovery miss в **source-resolution bottleneck**; fail-closed publication при этом сработала правильно.

### Новый доказанный temporal defect

Primary `global_breaking` дважды вернул model-side `outside_window` на реально in-window source timestamps:

- `2026-09-04 09:21 PDT` ошибочно преобразовано в `2026-09-05 19:21+03`; корректно `2026-09-04T19:21:00+03:00`;
- `2026-09-04 07:47 PDT` ошибочно преобразовано в `2026-09-05 17:47+03`; корректно `2026-09-04T17:47:00+03:00`.

Оба false rejection произошли **до candidate normalization**, поэтому deterministic Source Freshness не получил возможности исправить модельную арифметику.

Permanent regression:

- fixture `automation/fixtures/recall/primary-temporal-boundary-2026-09-05.json`;
- test `automation/tests/test_primary_temporal_boundary_guard.py`;
- matrix case `F7` в `automation/specs/search-change-validation-matrix.md`.

Принятое изменение: universal Primary `Temporal boundary guard v1`, который сохраняет доказанный timezone-aware source instant и запрещает считать ручной model-side conversion окончательной freshness authority. Query text и search budgets не меняются; downstream Source Freshness остаётся fail-closed.

### Накопительный verdict по поиску

**Да, к 5 сентября evidence уже достаточно, чтобы утверждать: retrieval/search layer требует следующего изменения.** Основание не один короткий выпуск, а повторяемость разных false-negative механизмов:

1. provider/ranking source-pool misses;
2. `major_agencies raw=0` при свежих Reuters controls;
3. source-resolution failures после успешного discovery;
4. repeated cross-day misses, не вылеченные healing overlap;
5. доказанный model-side temporal false rejection;
6. полный `25/25` budget всё равно не гарантирует высокий factual recall.

Приоритет следующего bounded experiment:

1. agency/provider routing внутри существующего slot и budget;
2. high-signal source resolution для уже обнаруженных событий;
3. query wording A/B только через Terra-equivalent assistant tool, когда он доступен.

Нельзя из текущего evidence делать вывод, что нужно просто поднять ceiling выше 25, ослабить weak-source/freshness gates или переписать все broad queries. Ordinary assistant web search в этом аудите использовался как factual control; standalone Terra в сессии не exposed и этим именем не назывался.

---

## Текущие наблюдаемые инварианты после 5 сентября

- Source/Event Freshness остаются fail-closed и не должны ослабляться ради объёма.
- Short digest допустим; story count не является health metric.
- Primary = 12; Agency Rescue ≤1; Hybrid = 4 или conditional 5; Coverage ≤7; ceilings = 24/25.
- Source Pulse, viability checks и Discovery Health остаются zero-Web-Search layers.
- Search budget сам по себе не является proxy recall.
- Repeated high-signal miss важнее одиночного provider ranking sample.
- Любой новый query treatment требует Terra-equivalent A/B; при отсутствии Terra query wording не меняется.
- Следующий системный target после temporal guard: **provider/source routing + source resolution**, а не добавление ещё одного ежедневного search без отдельного разрешения и experiment.
