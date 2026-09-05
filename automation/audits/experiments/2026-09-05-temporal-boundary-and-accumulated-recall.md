# Эксперимент 2026-09-05: temporal boundary guard и накопительный recall verdict

## Цель

Проверить два разных вопроса, которые нельзя честно смешивать в один «фикс поиска»:

1. есть ли доказанный локальный дефект, из-за которого уже найденные свежие события ошибочно отбрасываются как `outside_window`;
2. накопилось ли достаточно независимых production samples, чтобы утверждать, что broader retrieval/search layer требует следующего изменения.

Production API/Web Search budget пользователя в эксперименте не использовался.

## Control A: текущий Primary prompt без temporal guard

Production artifact run `33934617471` сохранил два model-side rejection с `reason_code=outside_window`.

### A1 — 09:21 PDT

Source timestamp:

`2026-09-04T09:21:00-07:00`

Saved model conversion:

`2026-09-05T19:21:00+03:00`

Корректный эквивалент того же instant:

`2026-09-04T19:21:00+03:00`

### A2 — 07:47 PDT

Source timestamp:

`2026-09-04T07:47:00-07:00`

Saved model conversion:

`2026-09-05T17:47:00+03:00`

Корректный эквивалент:

`2026-09-04T17:47:00+03:00`

Effective window production:

`2026-09-03T03:58:49+03:00` → `2026-09-05T03:57:22+03:00`.

Оба реальных source instant находятся внутри окна. Оба ошибочных model-side converted instant находятся после cutoff. Следовательно, причина false rejection воспроизводится обычной deterministic datetime arithmetic без поискового backend.

## Treatment B: universal Primary temporal boundary guard

Treatment добавляет в каждый из 12 Primary prompts один и тот же контракт:

- source timestamp с timezone/offset сохраняется как доказанный instant;
- ручной календарный conversion модели не является final freshness authority;
- если иначе пригодный candidate найден, его нельзя выбросить только из-за сомнительного timezone rollover;
- final comparison остаётся за deterministic Source Freshness Proof;
- если timestamp неоднозначен, модель не должна придумывать converted datetime;
- downstream fail-closed policy не меняется.

Treatment **не меняет**:

- query text;
- число Primary directions;
- Primary search budget 12;
- Hybrid/Coverage/Agency budgets;
- significance thresholds;
- archive/semantic dedupe;
- Event Freshness / Source Freshness thresholds.

## Offline regression

Fixture:

`automation/fixtures/recall/primary-temporal-boundary-2026-09-05.json`

Test:

`automation/tests/test_primary_temporal_boundary_guard.py`

Тест проверяет:

1. source instant математически равен корректно converted instant;
2. оба source instant находятся внутри exact production window;
3. сохранённые ошибочные +1-day instant действительно лежат после cutoff;
4. guard присутствует во всех 12 Primary prompts;
5. business query treatment остаётся неизменным и появляется ровно один раз;
6. Primary budget остаётся 12;
7. diagnostics фиксируют `query_changed=false`, `additional_search_operations=0`, `downstream_freshness_fail_closed=true`.

## Verdict по temporal defect

**GO.**

Это локализованный false-negative дефект, доказанный exact production artifact и deterministic timestamp arithmetic. Для него не нужен Terra A/B, потому что treatment не меняет search query/ranking и не делает новых поисковых операций.

Риск лечения ниже риска сохранения дефекта: downstream Source Freshness остаётся строгим deterministic gate и всё равно отвергнет реально outside-window candidate.

## Накопительный retrieval sample: 2026-09-03 → 2026-09-05

### 3 сентября

Подтверждены source/ranking misses и source-resolution seams, включая Broadcom/Reuters, Enflame и OpenAI automated-shutdown disclosure. Узкий business query treatment был отдельно проверен и принят; blanket rewrite всех queries был отклонён.

### 4 сентября

Подтверждены сильные misses:

- OpenAI Daybreak;
- Figure × Nscale;
- MBZUAI K2 Horizon;
- Microsoft MAI-Transcribe-2.

Pipeline использовал 24/25 operations, поэтому возникла гипотеза seventh-slot short-digest reserve. Она была оставлена NO-GO без Terra-equivalent A/B и at-most-once/priority replay.

### 5 сентября

Pipeline использовал уже полный ceiling 25/25, но независимый контроль всё равно нашёл сильные in-window misses:

- ByteDance $29.6B financing / AI infrastructure;
- US-China dedicated AI-safety talks;
- Gimlet Labs $300M / $3B valuation;
- Reuters material disclosure про rogue OpenAI agents;
- повторно Figure × Nscale;
- повторно MBZUAI K2 Horizon.

Daybreak на этот раз был обнаружен, но не прошёл Source Freshness из-за Axios HTTP 403, то есть тот же сюжет переместился из pure discovery miss в source-resolution bottleneck.

Figure × Nscale и K2 Horizon пропущены второй production-день подряд, несмотря на 24-hour healing overlap, который специально существует для восстановления сильных пропусков предыдущего выпуска.

## Что уже доказано накопленным sample

**Да, retrieval/search layer требует дальнейшего изменения.** Доказательств уже достаточно не потому, что один день короткий, а потому что повторяются разные наблюдаемые механизмы false-negative:

1. provider/ranking source-pool misses сильных событий;
2. `major_agencies` raw-zero при independently verified fresh Reuters events;
3. source-resolution failures после успешного discovery;
4. repeated cross-day misses, не вылеченные healing overlap;
5. model-side temporal false rejection;
6. полный 25/25 budget сам по себе не устраняет factual recall gaps.

## Что пока НЕ доказано

Не доказано, что системным лечением является:

- ещё один daily search slot;
- увеличение общего ceiling выше 25;
- blanket rewrite broad queries;
- ослабление weak-source/freshness rules;
- превращение Reuters или любого списка компаний в whitelist.

Sep 5 специально опровергает простую версию «нам не хватает одного search»: свободного operation не было, а strong misses остались.

## Следующий приоритет экспериментов

1. **Agency/provider routing experiment**: измерить, почему `major_agencies` и rescue получают raw-zero/zero-addition при существующих Reuters Must Include controls. Цель — улучшить source-pool access/ranking в пределах существующего slot, а не ослабить downstream acceptance.
2. **High-signal source resolution experiment**: для уже обнаруженного события доказанно находить официальный/agency origin внутри существующих navigation/search semantics. Daybreak Sep 5 — прямой fixture.
3. **Query wording A/B** только после появления доступного Terra-equivalent инструмента, потому что production query fixes по проектному контракту должны проверяться на Terra. Ordinary assistant web search нельзя выдавать за Terra.

## Query-change verdict

**NO-GO для изменения query wording в этом PR.**

В текущей сессии отдельного Terra tool нет. Assistant-side web search достаточно для независимой factual проверки misses, но недостаточно для production query A/B по контракту проекта.

## Итоговое решение

- Temporal boundary guard: **GO / implement now**.
- Broad/business/model query rewrite: **NO-GO now**.
- Seventh-slot short-digest reserve как системное решение: **NO-GO**.
- Следующий bounded target: **agency/provider routing + source resolution внутри текущих budget/quality invariants**.
