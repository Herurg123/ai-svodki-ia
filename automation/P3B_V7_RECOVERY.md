# P3b v7 recovery preflight and rollback

Этот runbook относится только к stale-positive P3b recovery remediation. Он не меняет binder semantics, durable optional-slot request identity, query/routing или search budgets.

## Что делает v7

Active public `automation/scripts/ensure_story_coverage.py` загружает `ensure_story_coverage_p3b_v7.py`. V7 сохраняет весь active v6 exact-binding runtime как preserved layer: binder остаётся `weak_source_exact_binding_v4.py`, durable request contract остаётся `VERSION=2`, current semantic positive proof остаётся `EVIDENCE_VERSION=6`.

До вызова historical Coverage main v7 проверяет durable processed optional-slot evidence. Если positive processed proof имеет evidence version ниже 6 и exact provenance-bound stale P3b candidate всё ещё присутствует в current `candidates.json`, reusable Coverage report или complete `stories.json`, preflight выполняет только deterministic local mutation:

- optional-slot journal не переписывается;
- stale candidate удаляется только по тому же exact signal-bound provenance predicate, который использует v6;
- unrelated candidates сохраняются;
- reusable Coverage report очищается до того, как historical `prior_complete` branch сможет его переиспользовать;
- если stale provenance затрагивает current research или complete story snapshot, `stories.json` переносится в quarantine backup и удаляется из publishable artifact до historical complete shortcut;
- до mutation атомарно записывается marker `coverage-p3b-v7-revocation-<DATE>.json` со state `pending`;
- preflight сам не выполняет provider call, Web Search, retry или authoritative-page refetch.

Если stale provenance находится только внутри reusable report, report очищается offline без инвалидирования заведомо чистого complete digest. Marker сразу получает `completed` с reason `stale_positive_p3b_prior_report_sanitized`.

## Durable marker

Основной state file:

`automation/preview/production-daily/coverage-p3b-v7-revocation-<DATE>.json`

Состояния:

- `pending` — stale publication snapshot был обнаружен; complete reuse запрещён, clean rebuild ещё не подтверждён;
- `blocked` — child runtime вернул success, но postflight всё ещё нашёл stale provenance либо не получил новый `stories.json`; publication должна оставаться заблокированной;
- `completed` — rebuilt `candidates.json`, Coverage report и `stories.json` прошли postflight и не содержат revoked provenance.

Marker записывается до quarantine mutation. При crash следующий запуск считает `pending` и `blocked` активной recovery obligation даже если optional-slot journal впоследствии отсутствует. Original SHA fields и первые backups не перезаписываются повторным запуском.

## Quarantine backups

Рядом с marker сохраняются первые оригинальные snapshots:

- `coverage-p3b-v7-revocation-<DATE>.candidates.original.json`;
- `coverage-p3b-v7-revocation-<DATE>.coverage-report.original.json`;
- `coverage-p3b-v7-revocation-<DATE>.stories.original.json`.

Эти файлы являются forensic/rollback evidence, а не publishable recovery inputs. Runtime не должен автоматически копировать их обратно.

## Проверка перед публикацией

Для затронутого выпуска publication-safe состояние требует одновременно:

1. marker имеет `state=completed`;
2. current `candidates.json` больше не содержит exact stale P3b provenance;
3. current reusable Coverage report больше не содержит exact stale P3b provenance;
4. новый `stories.json` существует и не ссылается на revoked candidate id/title/source URL;
5. optional-slot journal сохранил исходный consumption/ambiguity state и не был «refund» или переписан preflight;
6. обычные Coverage и whole-pipeline ceilings остаются 7 и 24/25 соответственно.

## Rollback

### Code rollback после `completed`

Если v7 нужно откатить после успешного clean rebuild, можно вернуть public shim на preserved v6 и удалить v7 code/tests отдельным PR. Current clean artifact и sanitized report сохраняются. Original quarantine backups не восстанавливаются в publishable paths.

### Code rollback при `pending` или `blocked`

Не восстанавливать `.original.json` в artifact directory. Перед переключением runtime назад убедиться, что current `candidates.json` и reusable Coverage report уже sanitized, а old `stories.json` остаётся вне publishable path. Preserved v6 может продолжить normal partial/editorial recovery из очищенного research, но старый complete snapshot нельзя возвращать: именно его reuse был исходным defect.

Если оператору требуется остановить automated recovery, безопаснее оставить `stories.json` отсутствующим и job красным, чем восстановить stale complete artifact ради зелёного статуса.

### Data rollback только для расследования

Original backups можно копировать только в отдельный forensic directory. Возврат stale candidate/story в production artifact допустим лишь после независимой повторной валидации этого exact event по current binder evidence contract. Простое наличие старого positive processed snapshot таким доказательством не является.

## Нельзя делать при rollback

- удалять или обнулять optional-slot journal ради освобождения seventh slot;
- переводить old evidence-v1..v5 positive snapshot в current evidence version вручную;
- повторять protected provider search из `request_started`, `response_saved` или `processed` только из-за rollback;
- восстанавливать quarantined `stories.json` как fallback после editorial failure;
- увеличивать Coverage выше 7 или whole-pipeline ceiling выше 24/25.

Rollback кода и rollback данных являются разными операциями. Первый может быть безопасным при сохранённом quarantine state; второй без новой current proof снова открывает исходную stale-publication дыру.
