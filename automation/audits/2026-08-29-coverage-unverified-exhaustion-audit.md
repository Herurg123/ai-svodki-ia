# Независимый аудит hotfix Coverage от 2026-08-29

## Инцидент

Production run `33228526922` завершил Primary, Source Pulse, Hybrid и все шесть mandatory Coverage directions. Седьмой Retrieval Quality search `Hugging Face Nvidia billion latest` также технически завершился, но три дублирующих high-signal сигнала остались `unverified`. Runtime ошибочно превратил содержательно завершённый bounded check в `audit_status=partial`, хотя слух не был принят кандидатом.

## Узкая граница исправления

`unverified` не становится `verified` и не попадает в publication. Quality считается исчерпанным без кандидата только если один source-neutral resolution search завершён, сохранён ровно один query, domain filter отсутствует и каждый required signal имеет не менее трёх matching `unverified` rejection с трёх разных source hosts. Один/два host, same-host repetition, unrelated evidence, domain-filtered resolution, multiple search operations и technical/API ambiguity остаются fail-closed.

## Независимый replay

Проверка выполнена на скачанном artifact run `33228526922`, без production API пользователя. Фактические rejected URLs относятся к TechCrunch, TechRadar и Fortune и матчятся ко всем трём дублирующим Nvidia/Hugging Face signals. Контроли one-report, two-host, same-host, unrelated, domain-filtered, multiple-search и technical-failure не закрывают quality obligation.

Terra отдельно не запускалась: дефект находится после уже сохранённого retrieval и воспроизводится детерминированно на production JSON. Повторять платный поиск для доказательства классификационной ошибки не требуется.

## Recovery и budget

Saved completed resolution переклассифицируется детерминированно до удаления supplemental attempt. Recovery возвращает `completed_usable/complete_with_gaps`, сохраняет `completed_calls=7`, `remaining_calls=0` и не вызывает V8/search повторно. Primary=12, agency rescue<=1, Hybrid<=4/conditional5, Coverage<=7 и whole-pipeline ceilings 24/25 не меняются. Source Freshness, candidate verification, editorial, image/publication gates и regional policy не ослабляются.

## Вердикт

PASS для узкого hotfix при условии полного Main CI на точном PR head. Изменение исправляет ложный production failure после уже выполненного evidence-rich resolution и одновременно сохраняет запрет публиковать неподтверждённый сюжет.
