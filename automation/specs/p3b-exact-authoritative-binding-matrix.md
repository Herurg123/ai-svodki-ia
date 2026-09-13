# P3b exact authoritative binding: permanent validation matrix

Этот документ является постоянным regression contract для active P3b поверх P3a weak-source signal retention. Он дополняет общую `search-change-validation-matrix.md` и не заменяет её.

## Scope и неизменяемые границы

P3a остаётся evidence-only: qualified `reason_code=weak_source` сохраняет source provenance и identity hints, но имеет `resolution_required=false`, `candidate_eligible=false` и сам не связывает событие с authoritative source.

Active P3b использует binder v2 и public Coverage path через v4 → v3 → v2. Он может рассмотреть максимум один qualified P3a weak-source signal и использует только уже существующий optional seventh Coverage slot. Шесть mandatory Coverage directions не меняются. Required high-signal `unverified` resolution имеет
приоритет. Если optional capacity занята, потрачена или неоднозначна, weak-source signal остаётся unresolved/deferred. Восьмой Coverage search запрещён. Обычный whole-pipeline ceiling остаётся 24 Web Search operations; существующий conditional double-regional-gap ceiling остаётся 25.

Положительное P3b admission требует runtime proof, а не утверждения модели: authoritative non-weak URL, реальную страницу, exact organization, все retained version/model anchors, совместимый lifecycle/action, deterministic Event/Source Freshness и archive/dedupe checks. Organization, все retained anchors и lifecycle/action должны доказываться одним local event claim; соседние title/paragraph claims нельзя склеивать в одно событие. Простого присутствия organization в том же claim тоже недостаточно: lifecycle assertion должна относиться к signal organization, а явный foreign named actor между organization и lifecycle/action делает identity недоказанной. Replacement direction выводится из retained signal claim, а не из порядка anchors. Negation и historical/background mentions не являются current-event proof. Provider terminal-negative labels не являются independent proof.

## Обязательная 20-case matrix

| # | Контроль | Ожидаемый результат |
|---:|---|---|
| 1 | Exact positive | Exact fresh authoritative same-event page допускает один bound candidate. |
| 2 | Same company, different product | Reject; совпадение организации не связывает другое product/model событие. |
| 3 | Similar version | Reject; соседняя версия или именованный/числовой suffix не заменяет exact retained anchor. |
| 4 | Old release | Reject через deterministic freshness; свежая страница/результат не омолаживает старое событие. |
| 5 | Preview vs GA | Reject lifecycle mismatch; preview и `general_availability`/GA являются разными событиями. |
| 6 | Benchmark vs release | Reject lifecycle/action mismatch; benchmark/current comparison не доказывает новый release/replacement. |
| 7 | Duplicate/reprint | Model duplicate label не является proof; independent archive evidence может дать terminal non-positive disposition. |
| 8 | False alias | Reject; неявный/ложный alias не заменяет exact retained identity anchors. |
| 9 | Missing authoritative source | Reject/defer; weak/non-authoritative URL не может доказать binding. |
| 10 | Wrong event/date official page | Reject; официальный домен сам по себе недостаточен, page identity и freshness обязаны совпасть. |
| 11 | Independently valid candidate, not binding | Валидная другая новость не может закрыть данный signal. |
| 12 | Result-order permutation | Deterministic result не зависит от provider ordering. |
| 13 | Optional seventh occupied | P3b не стартует; signal deferred, восьмой search не появляется. |
| 14 | Seventh already spent before recovery | Потраченная capacity не возвращается пересчётом mandatory attempts. |
| 15 | Interrupted/ambiguous transport | `request_started` считается consumed/ambiguous и никогда автоматически не ретраится. |
| 16 | Saved completed resolution replay | `response_saved` replay и `processed` reuse выполняются offline без нового provider search; mutable page не refetch'ится. |
| 17 | Stale authoritative page | Reject через deterministic Source Freshness. |
| 18 | Archive duplicate | Exact URL или independently exact same-event archive proof блокирует promotion. |
| 19 | Candidate fails Freshness | Reject даже при положительном model label. |
| 20 | Same company + version, different lifecycle | Reject; entity/version без exact lifecycle/action недостаточно. |

## Astra remediation controls сверх 20 cases

Постоянные regressions также обязаны доказывать исходные independent-review counterexamples и финальные self-audit counterexamples:

- changed model / missing signal / changed archive при уже занятом seventh slot не создают новый optional search;
- `reserved` P3b intent не обходит higher-priority required `unverified`, а foreign/mismatched reservation не удаляется;
- explicit negation и historical exact-event mention не дают positive binding;
- organization нельзя заимствовать из соседнего page claim: exact organization + retained anchors + lifecycle/action должны находиться в одном local event claim;
- same-claim foreign actor contamination fail-closed: `DeepSeek says OpenAI launches V4.1 Flash` не доказывает DeepSeek event, а `OpenAI says DeepSeek launches V4.1 Flash` сохраняет корректную attribution;
- structured archive organization не может переназначить foreign headline actor на signal organization;
- replacement old/new roles не зависят от порядка `product_version_anchors`;
- canonical `general_availability` совместим с GA, но negated GA остаётся fail-closed;
- `V4.1 Flash Thinking`, numeric continuation и иные distinct variants не считаются `V4.1 Flash`;
- mutable archive updates одной модели не dedupe'ятся по org+version+lifecycle; exact URL остаётся conclusive, а semantic duplicate требует exact normalized event-detail fingerprint;
- high-overlap distinct updates (`video input support` vs `video output support`) не являются одним событием;
- active matrix использует binder v2/public v4 path, а не исторический v1;
- `test_p3b_astra_regressions.py` проходит standalone в чистом Python process, чтобы full-suite import order не мог маскировать compatibility defect.

## Permanent executable coverage

- `automation/tests/test_p3b_exact_authoritative_binding.py`;
- `automation/tests/test_p3b_regression_matrix.py`;
- `automation/tests/test_p3b_optional_slot_recovery.py`;
- `automation/tests/test_p3b_astra_regressions.py`;
- `automation/tests/test_p3b_recovery_ownership_priority.py`;
- `automation/tests/test_p3b_negation_historical_binding.py`;
- `automation/tests/test_p3b_replacement_roles.py`;
- `automation/tests/test_p3b_archive_update_identity.py`;
- `automation/tests/test_p3b_lifecycle_alias_suffix.py`;
- `automation/tests/test_p3b_import_isolation.py`.

## Durable optional-slot state machine

Переходы active P3b: `reserved → request_started → response_saved → processed`.

| Saved state | Допустимое действие | Новый provider search |
|---|---|---|
| no journal | Только если mandatory Coverage завершён, optional seventh slot реально свободен и нет higher-priority required resolution | максимум 1 |
| `reserved` + capacity свободна | Продолжить тот же exact intent; перед wire call перейти в `request_started` | максимум 1 |
| `reserved` + budget уже исчерпан | Defer; reservation не может восстановить потраченный seventh slot | 0 |
| `request_started` | Outcome неизвестен; сохранить indeterminate/consumed | 0 |
| `response_saved` | Replay сохранённого response/result offline; без mutable-page refetch | 0 |
| `processed` | Reuse сохранённого hardened result | 0 |
| invalid/foreign/mismatched journal | Fail closed; не переписывать чужой intent и не угадывать consumption | 0 |

Только current unstarted P3b reservation с доказанным request-contract identity может быть снят ради уже существующего required `unverified`, причём лишь при доказанном отсутствии wire-attempt/response/consumed evidence и concurrent journal mutation.

## Exact identity / archive contract

Binding fail-closed, если отсутствует хотя бы одно обязательное доказательство:

- normalized organization соответствует exact signal identity;
- normalized organization, каждый retained product/version/model anchor и lifecycle/action присутствуют в одном local event claim; совпадения, разбросанные по соседним claims, не складываются;
- lifecycle/action в этом local claim атрибутирован signal organization; organization не может быть только speaker/context рядом с event другого явно названного actor;
- каждый retained product/version/model anchor присутствует точно, без fuzzy prefix/version conflation;
- lifecycle/action совпадает, replacement направлен, negation/history не принимаются за current assertion;
- primary/final URL относится к разрешённому authoritative source class и не совпадает с weak-source host;
- fetched page independently содержит exact current-event surface;
- deterministic freshness подтверждает saved editorial window;
- archive/dedupe не доказывает уже опубликованный exact event.

Для mutable lifecycle exact archive URL является достаточным proof. При другом URL org+version+lifecycle недостаточно: normalized event-detail fingerprint должен совпасть целиком. Частичное lexical overlap не блокирует fresh candidate. Structured archive organization может дополнять headline только внутри той же story row и не может переопределять явно названного foreign actor в headline.

## Recovery / compatibility / budget proof

Public `ensure_story_coverage.py` обязан сохранять historical Coverage API и monkeypatch seams, но production CLI и direct `execute_audit_plan()` должны идти через один hardened P3b runtime. Compatibility sync не имеет права снять reserved-budget guard, заменить hardened binder legacy binder'ом или восстановить уже потраченную optional capacity.

Preserved `ensure_story_coverage_p3a.py` должен оставаться byte-identical pre-P3b public implementation. Historical P3b v1/binder v1 остаются forensic/compatibility assets и не должны становиться active semantics из-за import order.

P3b не меняет Primary 12-search matrix, Agency Rescue route/health, Hybrid allocation, regional health, ranking, editorial policy, Source Pulse или Freshness policy. Search ceilings остаются 24/25.

## Validation evidence и external-search boundary

Whole-project architecture/recovery audit: `automation/audits/experiments/2026-09-12-p3b-exact-authoritative-binding/README.md`.

В среде реализации Terra не был exposed. Поэтому search-side acceptance выполнен через deterministic fixtures, saved artifacts и offline replay без production API пользователя и без paid Web Search. P3b remediation не меняет search query/routing, поэтому отсутствие Terra не компенсировалось production spend.

Перед merge final exact head обязан пройти полный PR Gate и отдельный независимый Astra review final diff. Regression tests с именем `astra` являются executable controls, а не заменой независимого reviewer verdict.
