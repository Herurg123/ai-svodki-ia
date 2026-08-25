# Независимый аудит patch: terminal-negative unresolved resolution

Дата: 2026-08-25

## Объект проверки

Production run `32798613325` успешно завершил fresh research/editorial и все шесть обязательных Coverage-направлений, после чего седьмой Retrieval Quality slot перепроверил high-signal сигнал `Rillet Lands $100M to Scale AI ERP`.

Targeted resolution выполнил один search и установил, что исходный раунд Rillet был объявлен 19 августа, до effective window текущего выпуска. Внутри окна были только поздние перепечатки/пересказы без material update. Ответ корректно вернул `candidate_count=0` и rejection `reason_code=outside_window`.

Текущий Retrieval Quality v1 ошибочно определял успех только через наличие accepted candidate (`bool(accepted)`), поэтому корректное отрицательное доказательство переводило весь Coverage в `partial` и блокировало публикацию.

## Независимая проверка гипотезы

Проверка выполнена по сохранённому production artifact и текущему коду `main`, без production API пользователя. Terra/web retrieval не использовался: дефект находится после retrieval и воспроизводится детерминированно на сохранённом JSON.

Подтверждено:

1. Шесть mandatory Coverage directions в run завершены; `partial_directions=[]`, `unchecked_directions=[]`.
2. Седьмой search завершён технически и сохранил фактический query.
3. Rillet rejection является именно доказанным freshness-negative для того же события, а не техническим `unverified`.
4. Верхнеуровневые diagnostics после failure противоречивы: `audit_status=partial`, но `retrieval_quality.status=complete` с `required_signal_count=0`. Причина — policy main не переносит wrapper extension fields, а finalizer ошибочно подставляет no-signal annotation.
5. Такой ошибочный `retrieval_quality=complete` нельзя использовать как самостоятельное recovery-доказательство: reuse gate обязан также требовать общий завершённый usable Coverage.

## Граница безопасного исправления

Patch не делает любой пустой resolution успешным. Terminal-negative разрешением считаются только детерминированные rejection classes:

- `duplicate`;
- `outside_window`;
- `old_reprint`;
- `minor_legal_event`;
- `satire_or_fiction`;
- `not_ai_news`.

Rejection дополнительно обязан относиться к тому же unresolved signal: используется содержательное token/entity matching. Поэтому нерелевантный stale-результат не может закрыть сигнал.

Намеренно остаются fail-closed и **не** считаются terminal-negative:

- `unverified`;
- `weak_source`;
- `other`;
- `insufficient_significance`.

Последний код оставлен fail-closed специально: это более субъективное редакционное решение и не должно автоматически снимать strict high-signal obligation в рамках этого hotfix.

## Architecture-wide regression audit

Проверены зависимости и инварианты:

- Primary Recall: без изменений.
- Bounded agency discovery rescue: без изменений.
- Hybrid completeness: без изменений.
- Six mandatory Coverage passes: без изменений.
- Seventh-slot priority: без изменений; patch меняет только классификацию результата уже выполненного unresolved resolution.
- Existing same-event `fresh_agency_rescue`: без изменений.
- Zero-pool recall sentinel: без изменений.
- Source Freshness Proof: без изменений.
- Russia/Asia routing и отсутствие regional quotas: без изменений.
- Candidate validation, archive/semantic dedupe и editorial ranking: без изменений.
- Search query, provider routing, search_context_size и число search operations: без изменений.
- Coverage hard cap остаётся 7; whole-pipeline theoretical ceiling остаётся 24.
- Technical failures и неоднозначные evidence остаются fail-closed.
- Recovery: ложный top-level `retrieval_quality=complete` больше не может помешать повтору незавершённого quality slot, потому что reuse требует одновременно завершённый overall Coverage.
- Diagnostics: finalizer реконструирует actual required signal/resolution result вместо ложного `required_signal_count=0`.

## Offline regression controls

Добавлены тесты на:

1. реальный класс Rillet `outside_window` → quality COMPLETE, candidate не добавляется;
2. `unverified` → всё ещё `partial`;
3. `weak_source` → всё ещё `partial`;
4. `insufficient_significance` → всё ещё `partial`;
5. нерелевантный `outside_window` rejection → не закрывает signal;
6. второй независимый required signal → один negative result не закрывает весь quality contract;
7. recovery старого противоречивого artifact освобождает только один quality slot, сохраняя шесть mandatory searches;
8. final diagnostics восстанавливают реальный required signal и terminal-negative disposition.

## Вердикт

**PASS для узкого patch.** Исправление устраняет ложный fail-closed только там, где единственный targeted search доказал, что именно проверяемое событие не имеет права попасть в выпуск по уже существующим объективным правилам. Оно не ослабляет freshness/verification для кандидатов, не меняет routing, budget, regional policy или editorial и не превращает слабое/непроверенное evidence в успешное разрешение.

Повтор production до merge не нужен. После merge следует использовать explicit artifact recovery из run `32798613325`, а не `force_fresh_research`, чтобы не повторять Primary/Hybrid и шесть уже оплаченных Coverage searches. Исправленный quality slot может потребовать только один повторный targeted search.
