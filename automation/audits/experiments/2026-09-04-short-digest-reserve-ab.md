# Short-digest reserve sweep A/B — 2026-09-04

## Цель

Проверить, есть ли доказательство для использования уже существующего седьмого Coverage slot как второго independent source-neutral sample, когда:

- выпуск после первого editorial короче usual target;
- шесть mandatory Coverage passes завершены;
- seventh slot не занят targeted unresolved resolution, agency corroboration или zero-pool sentinel;
- технического partial/error нет;
- общий Coverage cap остаётся 7.

Новый paid slot не предлагается. Проверяется только возможное использование уже разрешённого budget.

## Production control

Оригинальный run: `33823919741`.

Effective window:

`2026-09-02T04:07:02+03:00` → `2026-09-04T03:58:49+03:00`.

Шестой mandatory Coverage query:

`latest major AI news products business infrastructure regulation research`

Он добавил WeatherNext 3, но финальный выпуск остался коротким: 4 stories.

Search spend составил 24 при double-gap ceiling 25. Coverage использовал 6/7 slots.

## Assistant-side A/B

Тест не использовал production OpenAI/API/Web Search budget.

Отдельный Terra-инструмент в текущей assistant session недоступен. Поэтому результаты ниже являются обычным assistant-side web A/B и не считаются provider-equivalent Terra validation.

### A — production broad control

`latest major AI news products business infrastructure regulation research`

Повторный current sample поднимает, среди прочего:

- OpenAI Daybreak / critical-infrastructure cyber initiative;
- OpenAI Astra;
- крупные infrastructure/business материалы.

Это важно: Daybreak был пропущен production run, хотя тот же broad wording способен находить его сейчас. Следовательно, miss нельзя честно объяснить только плохим query text. Здесь есть ranking/index/provider timing component.

### B — event-shape treatment

Проверены source-neutral формулировки без publisher/company/date whitelist, в том числе:

`latest AI model releases compute partnerships investment cybersecurity products`

и

`artificial intelligence new model launch strategic partnership compute funding cyber defense`

Treatment sample дополнительно поднял события, которых нет в production artifact:

- Figure × Nscale: до 100 000 NVIDIA Vera Rubin GPUs, initial $3.5B compute commitment, strategic investment;
- GDIT × OpenAI Select Partner для федеральных AI deployments;
- текущие cybersecurity partnership/model events.

Таким образом, второй event-shape sample способен дать incremental recall относительно одного broad ranking draw.

## Независимые strong controls

В saved artifact отсутствуют:

1. OpenAI Daybreak for Frontline Defenders, $1B commitment, official OpenAI, 2026-09-03.
2. Figure × Nscale, up to 100k Rubin GPUs / $3.5B initial commitment, official Figure, 2026-09-03.
3. MBZUAI K2 Horizon, six fully-open models 0.9B–375B, official MBZUAI, 2026-09-03.
4. Microsoft MAI-Transcribe-2, Microsoft News, 2026-09-03.

Для Figure/Nscale production business lane имел сохранённую source metadata (21 consulted source), но Figure/Nscale source в pool отсутствовал. Это provider/ranking source-pool miss, а не model rejection после retrieval.

## Почему treatment пока не отправлен в runtime

A/B показывает потенциал, но ещё не доказывает безопасный production win.

### 1. Нет Terra-equivalent validation

Project contract требует проверять search-query изменения на Terra, поскольку production использует Terra. Отдельного Terra tool в assistant session нет. Подмена обычным web search была бы удобной, но методологически неверной.

### 2. Candidate volume != final story volume

В 2026-09-04 final candidate pool было 9 candidates, 8 из них `include|consider`; editorial выбрал 4. Поэтому ещё один broad retrieval pass может добавить кандидатов, но не доказано, что добавит сопоставимо сильный publishable story.

### 3. Seventh slot уже имеет priority semantics

Седьмой Coverage slot сейчас может использоваться для:

- high-confidence unresolved resolution;
- fresh-agency corroboration;
- zero-pool high-signal recall sentinel.

Short-digest reserve не должен вытеснять ни один из этих более конкретных rescue paths.

### 4. Recovery должен оставаться at-most-once

Новый supplemental attempt обязан иметь persisted/reused semantics, чтобы same-day recovery не повторял уже потраченный search. Это требует dedicated regression replay, а не просто дополнительного `if remaining_calls`.

## Безопасный design contract для будущего implementation

Если hypothesis будет реализована, reserve должен запускаться только после всех существующих high-priority seventh-slot consumers и только когда slot всё ещё свободен.

Обязательные инварианты:

- Coverage maximum остаётся 7;
- normal whole-pipeline maximum остаётся 24;
- double-regional-gap maximum остаётся 25;
- no domain/publisher/company whitelist;
- query без календарных дат;
- include/consider только при `verification_status=verified` и `freshness_status=new_event|material_update`;
- никакого padding ради числа 7;
- technical partial/error не превращается в usable result;
- same-day recovery не повторяет spent reserve;
- unresolved/agency/sentinel имеют приоритет над reserve.

## Решение

**Runtime: NO-GO сейчас.**

**Hypothesis: GO для отдельного bounded implementation/replay.**

Причина NO-GO не в отсутствии сигнала. Incremental recall наблюдается. Причина в том, что без Terra-equivalent A/B и exact recovery/priority regression невозможно доказать, что изменение улучшит production, а не просто потратит последний slot на ещё один изменчивый ranking draw.

## Стоимость

- production OpenAI/API calls: 0;
- production Web Search operations: 0;
- production workflow runs: 0;
- assistant-side web A/B only.
