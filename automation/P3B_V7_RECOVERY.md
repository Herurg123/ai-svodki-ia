# P3b v7 recovery preflight and rollback

Этот runbook относится только к stale-positive P3b recovery remediation. Он не меняет binder semantics, durable optional-slot request identity, query/routing или search budgets.

## Что делает v7

Active public `automation/scripts/ensure_story_coverage.py` загружает `ensure_story_coverage_p3b_v7.py`. V7 сохраняет весь active v6 exact-binding runtime как preserved layer: binder остаётся `weak_source_exact_binding_v4.py`, durable request contract остаётся `VERSION=2`, current semantic positive proof остаётся `EVIDENCE_VERSION=6`.

До вызова historical Coverage main v7 проверяет durable processed optional-slot evidence. Если positive processed proof имеет evidence version ниже 6 и exact provenance-bound stale P3b candidate всё ещё присутствует в current `candidates.json`, durable `coverage-audit-merged-candidates-<DATE>.json`, reusable Coverage report или complete `stories.json`, preflight выполняет только deterministic local mutation:

- optional-slot journal не переписывается;
- stale candidate удаляется только по тому же exact signal-bound provenance predicate, который использует v6;
- unrelated candidates сохраняются;
- current research, persisted merged research и reusable Coverage report очищаются до того, как recovery/`prior_complete` сможет вернуть stale row;
- если stale provenance затрагивает current research или complete story snapshot, `stories.json` сохраняется в quarantine backup и удаляется из publishable artifact до historical complete shortcut;
- до invalidating mutation атомарно записывается marker `coverage-p3b-v7-revocation-<DATE>.json` со state `pending` и `publication_snapshot_invalidated=true`;
- preflight сам не выполняет provider call, Web Search, retry или authoritative-page refetch.

Если stale provenance находится только внутри non-publishable recovery inputs (`coverage-audit.json` и/или persisted merged research), они очищаются offline без инвалидирования заведомо чистого complete digest. Такой pending marker явно имеет `publication_snapshot_invalidated=false`, поэтому crash/restart продолжает sanitation, но не карантинит чистый `stories.json` только из-за незавершённой записи recovery input.

### Ownership stale-revocation predicate через compatibility chain

Historical v1 admission существовал до позднего `p3b_authoritative_page_proof`, поэтому active v7 stale-revocation predicate является remediation-owned compatibility invariant, а не локальным helper только preflight. Один и тот же predicate обязан оставаться установленным и в reviewed v7-base namespace, и в preserved v6 seam на всём production path `active v7 -> reviewed base -> v6`.

Preserved base перед child execution выполняет собственный compatibility sync. Этот nested sync не имеет права вернуть pre-v7 `_without_stale_p3b_candidates` в v6: иначе genuine v1 row, уже удалённый preflight, может быть повторно принят historical migration/replay path. Permanent regression должен проходить именно через active `execute_audit_plan()`, nested base sync и preserved-v6 child, а не только напрямую вызывать `recovery_preflight`.

### Fail-closed deterministic processed snapshot

Optional-slot journal, который отсутствует, и journal, который присутствует в `state=processed`, но не содержит проверяемого deterministic result, являются разными состояниями. Для любого processed optional-slot owner recovery требует сохранённый полный Coverage plan:

- `processed_snapshot` является JSON object;
- `processed_snapshot.candidates` является list;
- `processed_snapshot.search_budget` является object и содержит `maximum_calls`, `completed_calls`, `remaining_calls`.

Missing/list/scalar/empty или structurally inconsistent processed snapshot является durable corruption и даёт fail-closed `CoverageSlotError` до `existing_full_digest`, `prior_complete` и других complete/reusable shortcuts. Validator намеренно не требует P3b-only diagnostic: legacy `unverified` owner использует тот же durable optional slot и валидный generic processed Coverage plan должен оставаться reusable.

## Durable marker

Основной state file:

`automation/preview/production-daily/coverage-p3b-v7-revocation-<DATE>.json`

Состояния:

- `pending` — remediation начата; если `publication_snapshot_invalidated=true`, complete reuse запрещён до clean rebuild;
- `blocked` — child runtime вернул success, но postflight всё ещё нашёл stale provenance либо не получил новый `stories.json`; publication должна оставаться заблокированной;
- `completed` — affected current/persisted research, Coverage report и `stories.json` прошли требуемую sanitation/postflight проверку.

Marker записывается до mutation. При crash следующий запуск считает publication-invalidating `pending` и `blocked` активной recovery obligation даже если optional-slot journal впоследствии отсутствует. Original SHA fields и первые backups не перезаписываются повторным запуском.

`completed` marker намеренно supersede'ит старый processed journal для recovery-readiness решения: journal не переписывается и не «повышается» до evidence v6, но после доказанного clean rebuild сам факт существования historical stale journal больше не должен бесконечно понижать каждый recovered artifact в `partial_editorial`.

## Quarantine backups

Рядом с marker сохраняются первые оригинальные snapshots, если соответствующий input существовал:

- `coverage-p3b-v7-revocation-<DATE>.candidates.original.json`;
- `coverage-p3b-v7-revocation-<DATE>.merged-research.original.json`;
- `coverage-p3b-v7-revocation-<DATE>.coverage-report.original.json`;
- `coverage-p3b-v7-revocation-<DATE>.stories.original.json`.

Эти файлы являются forensic/rollback evidence, а не publishable recovery inputs. Runtime не должен автоматически копировать их обратно в artifact/research paths.

## Same-bundle recovery через GitHub Actions artifact

`daily-production.yml` загружает в recovery bundle как dated artifact, так и sibling `production-daily/`. Поэтому `recover_digest_artifact.py` обязан сохранять bundle identity:

1. P0 выбирает dated source и фиксирует exact sibling evidence root.
2. Optional-slot journal, persisted merged research, Coverage report и v7 marker/backups можно восстанавливать только из этого же selected evidence root.
3. Если selected **full** bundle ещё pre-v7, но его processed journal содержит stale positive evidence-v1..v5, recovery mode понижается до `partial_editorial`. Это readiness-only решение: оно не делает search и не удаляет candidate, а гарантирует наличие pinned text runtime до того, как active v7 потребует sanitized rebuild.
4. Если marker имеет `pending|blocked` и `publication_snapshot_invalidated=true` (или поле отсутствует у раннего marker), full recovery также понижается до `partial_editorial`.
5. `completed` marker не понижает full recovery только из-за оставшегося historical journal.
6. Marker и forensic backups копируются в current `production-daily` только из exact selected bundle. Конфликт с уже существующим отличающимся state fail-closed; смешивать два artifact bundle запрещено.

Эта интеграция не повторяет retrieval, не открывает optional slot и не меняет search budgets.

## Проверка перед публикацией

Для выпуска, чей publishable snapshot был invalidated, publication-safe состояние требует одновременно:

1. marker имеет `state=completed`;
2. current `candidates.json` больше не содержит exact stale P3b provenance;
3. current durable `coverage-audit-merged-candidates-<DATE>.json`, если существует, больше не содержит exact stale provenance;
4. current reusable Coverage report больше не содержит exact stale P3b provenance;
5. новый `stories.json` существует и не ссылается на revoked candidate id/title/source URL;
6. optional-slot journal сохранил исходный consumption/ambiguity state и не был «refund» или переписан preflight;
7. обычные Coverage и whole-pipeline ceilings остаются 7 и 24/25 соответственно.

## Permanent controls

Помимо существующих v7 recovery/crash/bundle controls, `automation/tests/test_p3b_v7_external_review_regressions.py` закрепляет два composition-level invariants, которые не были доказаны isolated helper tests:

- nested active-v7/base/v6 compatibility sync не может восстановить old v6 stale predicate и resurrect genuine historical v1 provenance;
- corrupt/missing deterministic `processed_snapshot` fail-closed, при этом валидный generic/legacy processed Coverage plan остаётся reusable.

## Rollback

### Code rollback после `completed`

Если v7 нужно откатить после успешного clean rebuild, можно вернуть public shim на preserved v6 и удалить v7 code/tests отдельным PR. Current clean artifact, sanitized persisted merged research и sanitized report сохраняются. Original quarantine backups не восстанавливаются в publishable/recovery input paths.

### Code rollback при `pending` или `blocked`

Не восстанавливать `.original.json` в artifact directory или durable merged-research path. Перед переключением runtime назад убедиться, что current `candidates.json`, persisted merged research и reusable Coverage report уже sanitized, а old `stories.json` остаётся вне publishable path. Preserved v6 может продолжить normal partial/editorial recovery из очищенного research, но старый complete snapshot нельзя возвращать: именно его reuse был исходным defect.

Если оператору требуется остановить automated recovery, безопаснее оставить `stories.json` отсутствующим и job красным, чем восстановить stale complete artifact ради зелёного статуса.

### Data rollback только для расследования

Original backups можно копировать только в отдельный forensic directory. Возврат stale candidate/story в production artifact допустим лишь после независимой повторной валидации этого exact event по current binder evidence contract. Простое наличие старого positive processed snapshot таким доказательством не является.

## Нельзя делать при rollback

- удалять или обнулять optional-slot journal ради освобождения seventh slot;
- переводить old evidence-v1..v5 positive snapshot в current evidence version вручную;
- повторять protected provider search из `request_started`, `response_saved` или `processed` только из-за rollback;
- восстанавливать quarantined `stories.json` как fallback после editorial failure;
- восстанавливать `.merged-research.original.json` в active durable recovery path без новой current proof;
- смешивать marker/backups/report/research из разных selected artifact bundle;
- увеличивать Coverage выше 7 или whole-pipeline ceiling выше 24/25.

Rollback кода и rollback данных являются разными операциями. Первый может быть безопасным при сохранённом quarantine state; второй без новой current proof снова открывает исходную stale-publication дыру.
