# P3b exact authoritative binding: permanent validation matrix

Этот документ является постоянным regression contract для active P3b поверх P3a
weak-source signal retention. Он дополняет общую
`search-change-validation-matrix.md` и не заменяет её.

## Scope и неизменяемые границы

P3a остаётся evidence-only: qualified `reason_code=weak_source` сохраняет source
provenance и identity hints, но имеет `resolution_required=false`,
`candidate_eligible=false` и сам не связывает событие с authoritative source.

P3b может рассмотреть максимум один qualified P3a weak-source signal и использует
только уже существующий optional seventh Coverage slot. Шесть mandatory Coverage
directions не меняются. Required high-signal `unverified` resolution имеет
приоритет над P3b. Если optional capacity занята, потрачена или неоднозначна,
weak-source signal остаётся unresolved/deferred. Восьмой Coverage search запрещён.
Обычный whole-pipeline ceiling остаётся 24 Web Search operations; существующий
conditional double-regional-gap ceiling остаётся 25.

Положительное P3b admission требует runtime proof, а не утверждения модели:
authoritative non-weak URL, реальную страницу, exact organization, все retained
version/model anchors, совместимый lifecycle/action, deterministic Event/Source
Freshness и archive/dedupe checks. Legacy fuzzy same-company matching не является
proof.

## Обязательная 20-case matrix

| # | Контроль | Ожидаемый результат |
|---:|---|---|
| 1 | Exact positive | Exact fresh authoritative same-event page допускает один bound candidate. |
| 2 | Same company, different product | Reject; совпадение организации не связывает другое product/model событие. |
| 3 | Similar version | Reject; `V4`, `V4.1`, `V4.1 Flash` и аналогичные соседние версии не взаимозаменяемы. |
| 4 | Old release | Reject через deterministic freshness; свежий search result не омолаживает старое событие. |
| 5 | Preview vs GA | Reject lifecycle mismatch; preview и general availability являются разными событиями. |
| 6 | Benchmark vs release | Reject lifecycle/action mismatch; benchmark/current comparison не доказывает новый release/replacement. |
| 7 | Duplicate/reprint | Exact independently proven duplicate является terminal non-positive disposition; не создаёт candidate. |
| 8 | False alias | Reject; неявный/ложный alias не заменяет exact retained identity anchors. |
| 9 | Missing authoritative source | Reject/defer; weak/non-authoritative URL не может доказать binding. |
| 10 | Wrong event/date official page | Reject; официальный домен сам по себе не достаточен, page identity и freshness обязаны совпасть. |
| 11 | Independently valid candidate, not binding | Candidate может быть валидной новостью, но reject для данного signal, если это другое событие. |
| 12 | Result-order permutation | Deterministic result не зависит от provider ordering; при нескольких exact positives действует стабильный source/url/title ordering. |
| 13 | Optional seventh occupied | P3b не стартует; signal остаётся deferred, восьмой search не появляется. |
| 14 | Seventh already spent before recovery | Потраченная capacity не «возвращается» пересчётом шести mandatory attempts; новый provider call запрещён. |
| 15 | Interrupted/ambiguous transport | `request_started` считается consumed/ambiguous и никогда автоматически не ретраится. |
| 16 | Saved completed resolution replay | `response_saved` replay и `processed` reuse выполняются offline без нового provider search; mutable page не refetch'ится для replay. |
| 17 | Stale authoritative page | Reject через deterministic Source Freshness. |
| 18 | Archive duplicate | Reject/no promotion; exact URL или independently exact same-event archive proof закрывает admission. |
| 19 | Candidate fails Freshness | Reject даже при положительном model label; runtime freshness имеет приоритет. |
| 20 | Same company + version, different lifecycle | Reject; совпадение entity/version без exact lifecycle/action недостаточно. |

Permanent executable coverage:

- `automation/tests/test_p3b_exact_authoritative_binding.py`;
- `automation/tests/test_p3b_regression_matrix.py`;
- `automation/tests/test_p3b_optional_slot_recovery.py`;
- `automation/tests/test_p3b_astra_regressions.py`.

## Durable optional-slot state machine

| Saved state | Допустимое действие | Новый provider search |
|---|---|---|
| no journal | Только если после mandatory Coverage действительно свободен optional seventh slot и нет higher-priority required resolution | максимум 1 |
| `reserved` + capacity свободна | Продолжить тот же exact intent; перед wire call перейти в `request_started` | максимум 1 |
| `reserved` + budget уже исчерпан | Defer; reservation не может восстановить потраченный seventh slot | 0 |
| `request_started` | Outcome неизвестен; сохранить indeterminate/consumed | 0 |
| `response_saved` | Replay сохранённого response/result offline | 0 |
| `processed` | Reuse сохранённого hardened result | 0 |
| invalid/foreign/mismatched journal | Fail closed; не переписывать чужой intent и не угадывать consumption | 0 |

Переходы active P3b: `reserved → request_started → response_saved → processed`.
Запись reservation должна быть durable до transport. Raw response/result snapshot
сохраняются до последующей semantic processing, чтобы same-day recovery не
повторял оплаченный search. Temporary six-call routing clamp не имеет права
стирать доказательство, что optional seventh operation уже была consumed другим
Coverage path.

## Exact identity / source / freshness contract

Binding fail-closed, если отсутствует хотя бы одно обязательное доказательство:

- normalized organization соответствует exact signal identity;
- каждый retained product/version/model anchor присутствует как exact ordered
  token sequence, без fuzzy prefix/version conflation;
- lifecycle/action совпадает направленно: replacement не benchmark, preview не GA,
  historical mention не превращается в current event;
- primary URL относится к разрешённому authoritative source class и не совпадает
  с weak-source host;
- fetched page independently содержит exact current-event surface;
- deterministic freshness подтверждает saved editorial window;
- archive/dedupe не доказывает уже опубликованный exact event.

Provider fields `verification_status`, `freshness_status`, rejection reason и
terminal label являются только входными claims. Они не заменяют real-page proof.
`unverified` model rejection никогда автоматически не закрывает weak-source
signal. Terminal negative допустим только при independent exact same-event proof.
Противоречивые exact positive/negative evidence остаются fail-closed.

## Recovery / compatibility / budget proof

Public `ensure_story_coverage.py` обязан сохранять historical Coverage API и
monkeypatch seams, включая late private hooks и identity-sensitive compatibility,
но production CLI и direct `execute_audit_plan()` должны идти через один и тот же
hardened P3b runtime. Compatibility sync не имеет права снять reserved-budget
guard, заменить hardened binder legacy fuzzy binder'ом или восстановить уже
потраченную optional capacity.

P3b не меняет Primary 12-search matrix, Agency Rescue route/health, Hybrid
allocation, regional health, ranking, editorial policy, Source Pulse или
Freshness policy. Search ceilings остаются 24/25.

## Validation evidence и external-search boundary

Whole-project architecture/recovery audit:
`automation/audits/experiments/2026-09-12-p3b-exact-authoritative-binding/README.md`.

В среде реализации Terra не был exposed. Поэтому search-side acceptance выполнен
через deterministic fixtures, saved artifacts и offline replay без production API
пользователя и без paid Web Search. Это ограничение должно быть явно сохранено в
аудите; отсутствие Terra не является поводом запускать production workflow.

Перед merge final exact head обязан пройти полный PR Gate и отдельный независимый
Astra audit/review final diff. Astra review не заменяется тем, что regression tests
называются `astra`: executable controls проверяют требования, но не являются
независимым reviewer verdict.
