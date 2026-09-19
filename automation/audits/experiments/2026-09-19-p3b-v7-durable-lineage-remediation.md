# P3b v7 durable-lineage remediation audit — 2026-09-19

## Scope

PR #184 remediation после независимого final review exact head:

`9611000fe3b863a84dce8c1ed080cbde398d3bd4`

Задача остаётся recovery-only. Query/routing, число Coverage searches, binder
semantics, editorial ranking, Source/ Event Freshness и provider retry policy не
меняются. Реализация не выполняла production OpenAI/Web Search/page-fetch calls и
не расходовала пользовательский paid API budget.

Preserved semantic layers остаются compatibility assets:

- `automation/scripts/ensure_story_coverage_p3a.py` сохраняется exact blob
  `14f0e38f57b9285a949ec5083136999c12c81bc0`;
- preserved P3b v2 также не используется как место новой remediation semantics.

Новая durable lineage реализована в общем `coverage_slot_guard.py`, а
production recovery validation — в active P3b v7.

## Independent-review counterexamples

### 1. Reservation bundle identity не является processed-result identity

До optional request journal сохранял
`bundle_identity_sha256 = sha256(_P3A._bundle_identity(plan))`.

После request P3b добавляет optional attempt с
`direction_id=general_coverage_gaps`. Этот direction одновременно входит в
mandatory `AUDIT_DIRECTION_IDS`, поэтому вычисление
`_P3A._bundle_identity(processed_snapshot)` уже видит другой набор attempts.

Следствие: pre-request reservation hash и post-request processed hash различаются
даже для одного честного lifecycle.

Одновременно `_bundle_identity()` не включает `candidates[]`. Поэтому замена
candidate content при неизменной истории attempts не меняет этот identity.

Старый invariant одновременно давал false reject для честного lifecycle и не
доказывал exact processed-result bytes.

### 2. Final research artifact не является Coverage audit plan

Production `artifact/candidates.json` хранит research shape: publication date,
search window, coverage/research candidates, unresolved signals, regional health
и связанные поля. Он не обязан содержать Coverage
`checked_directions/attempts`, из которых был построен pre-optional bundle hash.

V7 на defective head пытался реконструировать pre-optional bundle identity из
этого final research artifact. Same-bundle GitHub recovery поэтому мог fail
closed на корректном собственном state до предусмотренного offline
`response_saved`/processed recovery.

Дополнительно defective validation требовала
`processed_snapshot.search_window`, хотя current optional-slot writer сохраняет
complete post-request Coverage result без такого обязательного top-level поля.

## Remediation contract

Outer reservation identity остаётся immutable и по-прежнему включает:

- publication date;
- owner;
- `search_window_sha256`;
- `request_contract_sha256`;
- pre-optional `bundle_identity_sha256`.

Writer теперь дополнительно сохраняет:

- `result_snapshot_sha256`;
- `result_snapshot_provenance`;
- `processed_snapshot_sha256`;
- `processed_snapshot_provenance`.

Snapshot provenance связывает exact snapshot bytes с теми же
`request_contract_sha256`, `response_sha256` и pre-optional
`bundle_identity_sha256`. Processed provenance при наличии parsed result также
ссылается на exact `result_snapshot_sha256`.

Current processed reuse через `CoverageSlotReservation.processed_snapshot()`
разрешён только для proven lineage. Historical journals без новых additive
lineage fields остаются читаемыми через journal APIs для deterministic
migration/sanitation, но не получают автоматическое повышение до current reusable
processed result.

Active v7 больше:

- не требует top-level `search_window` внутри post-request
  `processed_snapshot`;
- не сравнивает `_P3A._bundle_identity(processed_snapshot)` с pre-request
  reservation hash;
- не реконструирует Coverage bundle identity из final research
  `candidates.json`.

Если final research содержит `search_window`, его exact hash по-прежнему
сверяется с durable outer search-window identity.

Current evidence-v6 positive из historical pre-lineage journal также не
считается автоматически reusable: active v7 отправляет его в zero-I/O
quarantine/sanitation path. Consumed optional slot не refund/reopen'ится.

## Response-saved boundary

Эта remediation **не меняет** preserved response parsing/replay routing. Existing
`response_saved` offline semantics остаются compatibility behavior preserved
P3a/P3b layers.

Common writer теперь записывает hash/provenance parsed `result_snapshot`, когда
он сохраняется, но отдельный broader вопрос о том, должен ли recovery всегда
перепарсить raw response вместо использования saved parsed result, не заявляется
как исправленный этим PR.

## Regression coverage

Новый
`automation/tests/test_p3b_v7_durable_lineage.py` закрепляет:

1. current writer записывает result/processed snapshot hashes и lineage;
2. production-shaped final research без Coverage attempts не вызывает ложный
   bundle mismatch;
3. подмена `processed_snapshot.candidates` после durable write обнаруживается
   по exact processed hash с нулём provider/protected/page-fetch I/O.

`test_p3b_v7_processed_snapshot_identity.py` теперь моделирует persisted
snapshot mix-up после честной записи current provenance, а не подменяет вход
самому writer.

Existing stale-v1..v5 sanitation, crash marker, same-bundle restore,
P3b→legacy handoff, no-eighth-search и binder regressions остаются обязательными.

## Architecture and dependency audit

Изменение затрагивает только durable optional-slot identity/recovery:

- search query/routing: без изменений;
- Coverage maximum: 7;
- whole-pipeline ceilings: 24/25;
- provider retry/search admission: без изменений;
- P3a weak-source semantics: без изменений;
- P3b binder `EVIDENCE_VERSION=6`: без изменений;
- final editorial policy/ranking: без изменений;
- same-bundle recovery selection: без изменений;
- external network I/O remediation path: 0.

Документация синхронизирована в:

- `automation/ARCHITECTURE.md`;
- `automation/README.md`;
- root `README.md`;
- `automation/P3B_V7_RECOVERY.md`;
- `automation/specs/p3b-exact-authoritative-binding-matrix.md`.

## Validation boundary

Final acceptance требует нового PR Gate на exact remediation head и актуальном
synthetic merge ref после всех code/docs/audit commits. Более ранние Gate runs
не являются доказательством final head. Независимый final review должен
проверять exact final SHA, final diff, current merge ref и сам runtime, а не
названия regression tests или этот audit record.
