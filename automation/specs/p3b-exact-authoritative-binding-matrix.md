# P3b exact authoritative binding: permanent validation matrix

Этот документ является постоянным regression contract для active P3b поверх P3a weak-source signal retention. Он дополняет общую `search-change-validation-matrix.md` и не заменяет её.

## Scope и неизменяемые границы

P3a остаётся evidence-only: qualified `reason_code=weak_source` сохраняет source provenance и identity hints, но имеет `resolution_required=false`, `candidate_eligible=false` и сам не связывает событие с authoritative source.

Active P3b использует binder implementation `weak_source_exact_binding_v4.py` при сохранённом durable request-contract `VERSION=2`; public Coverage path идёт через v6 → v5 → v4 → v3 → v2 compatibility chain. Binder v4 отдельно маркирует semantic positive proof через `EVIDENCE_VERSION=2`, не разрывая durable request identity. Evidence v2 дополнительно требует fail-closed обработки suffix/modal/uncertain lifecycle language и межclaim lifecycle-противоречий; positive processed snapshot с более старым evidence marker не переиспользуется как current proof. P3b может рассмотреть максимум один qualified P3a weak-source signal и использует только уже существующий optional seventh Coverage slot. Шесть mandatory Coverage directions не меняются. Required high-signal `unverified` resolution имеет приоритет. Если optional capacity занята, потрачена или неоднозначна, weak-source signal остаётся unresolved/deferred. Восьмой Coverage search запрещён. Обычный whole-pipeline ceiling остаётся 24 Web Search operations; существующий conditional double-regional-gap ceiling остаётся 25.

Положительное P3b admission требует runtime proof, а не утверждения модели: authoritative non-weak URL, реальную страницу, exact organization, все retained version/model anchors, совместимый lifecycle/action, deterministic Event/Source Freshness и archive/dedupe checks. Organization, все retained anchors и lifecycle/action должны доказываться одним local event claim; соседние title/paragraph claims нельзя склеивать в одно событие. Простого присутствия organization в том же claim тоже недостаточно: lifecycle assertion должна относиться к signal organization, а foreign named actor, passive attribution другому agent либо явная reporting/role attribution между organization и lifecycle/action делает identity недоказанной. Replacement direction выводится из retained signal claim, а не из порядка anchors. Negation, conditional/uncertain language, prefix/suffix planned/modal/cancelled/denied assertions и historical/background mentions не являются current-event proof. Взаимоисключающие active lifecycle claims для той же exact identity, включая GA в одной local claim и preview в соседней, fail closed. Provider terminal-negative labels не являются independent proof.

## Обязательная 20-case matrix

| # | Контроль | Ожидаемый результат |
|---:|---|---|
| 1 | Exact positive | Exact fresh authoritative same-event page допускает один bound candidate. |
| 2 | Same company, different product | Reject; совпадение организации не связывает другое product/model событие. |
| 3 | Similar version | Reject; соседняя версия или именованный/числовой/punctuation suffix не заменяет exact retained anchor. |
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

Постоянные regressions также обязаны доказывать исходные independent-review counterexamples и последующие exact-head self-audit counterexamples:

- changed model / missing signal / changed archive при уже занятом seventh slot не создают новый optional search;
- `reserved` P3b intent не обходит higher-priority required `unverified`, а foreign/mismatched reservation не удаляется;
- proven unstarted P3b reservation может быть передан required `unverified` только атомарной заменой durable intent под тем же slot lock, который защищает request admission; между P3b и legacy не возникает состояния без reservation;
- crash сразу после atomic transfer оставляет полный legacy `reserved` journal, а crash после `request_started` оставляет consumed/ambiguous journal; recovery в обоих случаях не создаёт восьмой Coverage search;
- transfer не имеет права перезаписать уже `request_started`, response-bearing, consumed/ambiguous, foreign или concurrently changed P3b journal;
- explicit negation, suffix-negative lifecycle, conditional `if/unless/whether`, rumor/speculation, planned/cancelled/modal и historical exact-event mention не дают positive binding;
- uncertainty/action-state checks применяются независимо от позиции lifecycle token: `reportedly launched`, `launch expected`, `launch may|might|could happen`, `launch denied`, `GA planned|cancelled|may happen` fail closed;
- organization нельзя заимствовать из соседнего page claim: exact organization + retained anchors + lifecycle/action должны находиться в одном local event claim;
- same-claim foreign actor contamination fail-closed: `DeepSeek says OpenAI launches V4.1 Flash`, lowercase foreign actor, role-attribution и passive `... launched by OpenAI` не доказывают DeepSeek event, а корректная attribution к signal organization сохраняет positive control;
- GA claim не может одновременно использовать active preview/beta/early-access assertion как positive proof; это относится и к конфликту внутри одной claim, и к нескольким local claims с той же exact organization/model identity;
- structured archive organization не может переназначить foreign headline actor на signal organization;
- replacement old/new roles не зависят от порядка `product_version_anchors`, а наличие обеих противоположных active replacement directions fail-closed;
- canonical `general_availability` совместим с GA, но negated/preview GA остаётся fail-closed;
- lowercase, numeric и punctuation continuations (`v2`, `experimental`, `/Pro`, `+`, dash-variant`) не считаются exact shorter anchor, кроме явно разрешённого обычного prose continuation; v4 может локально разрешать обычные predicate/linking words (`remain/remains/stay/stays/...`) без изменения historical v2/v3 compatibility vocabulary;
- mutable archive updates одной модели не dedupe'ятся по org+version+lifecycle; exact URL остаётся conclusive, а semantic duplicate требует exact normalized ordered event-detail fingerprint, включая single-digit direction (`8K→9K` не равно `9K→8K`);
- high-overlap distinct updates (`video input support` vs `video output support`) не являются одним событием;
- positive `processed` snapshot без current binder `EVIDENCE_VERSION=2`, включая ранее допустимый evidence-v1 positive, не переиспользуется как current hardened proof;
- canonical 20-case executable matrix импортирует active `weak_source_exact_binding_v4`, проверяет public v6 ownership и не закрепляет historical v2 binder как active semantic implementation;
- `test_p3b_astra_regressions.py` проходит standalone в чистом Python process, чтобы full-suite import order не мог маскировать compatibility defect.

## Permanent executable coverage

- `automation/tests/test_p3b_exact_authoritative_binding.py`;
- `automation/tests/test_p3b_regression_matrix.py`;
- `automation/tests/test_p3b_optional_slot_recovery.py`;
- `automation/tests/test_p3b_astra_regressions.py`;
- `automation/tests/test_p3b_astra_second_review.py`;
- `automation/tests/test_p3b_astra_third_review.py`;
- `automation/tests/test_p3b_astra_fourth_review.py`;
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
| `reserved` + capacity свободна | Продолжить тот же exact P3b intent; перед wire call перейти в `request_started` под protected admission lock | максимум 1 |
| `reserved` + proven P3b intent + required `unverified` | Под shared slot lock атомарно заменить только unstarted P3b reservation на полный legacy durable reservation; затем исполнить required legacy resolution через P3a protected transport | максимум 1 |
| `reserved` + budget уже исчерпан | Defer; reservation не может восстановить потраченный seventh slot | 0 |
| `request_started` | Outcome неизвестен; сохранить indeterminate/consumed, transfer/retry запрещены | 0 |
| `response_saved` | Replay сохранённого response/result offline; без mutable-page refetch | 0 |
| `processed` | Reuse только current hardened result с `EVIDENCE_VERSION=2`; stale positive evidence-version fail-closed | 0 |
| invalid/foreign/mismatched journal | Fail closed; не переписывать чужой intent и не угадывать consumption | 0 |

Только current unstarted P3b reservation с доказанным exact request-contract identity может быть передан уже существующему required `unverified`. `coverage_slot_handoff.transfer_reserved_slot` под тем же межпоточным/межпроцессным slot lock проверяет `state=reserved`, отсутствие wire-attempt, response/snapshot/consumed evidence и exact expected source journal hash, после чего одним atomic replace записывает полный legacy request/bundle contract. Поэтому нет crash-window, где P3b уже снят, а legacy reservation ещё не существует. Handoff сохраняет publication-date context на время P3a durable resolution; crash после `request_started` не возвращает capacity и следующий запуск не выполняет восьмой search.

## Exact identity / archive contract

Binding fail-closed, если отсутствует хотя бы одно обязательное доказательство:

- normalized organization соответствует exact signal identity;
- normalized organization, каждый retained product/version/model anchor и lifecycle/action присутствуют в одном local event claim; совпадения, разбросанные по соседним claims, не складываются;
- lifecycle/action в этом local claim атрибутирован signal organization; organization не может быть только speaker/context рядом с event другого actor, включая явную reporting/role attribution и passive attribution другому agent;
- каждый retained product/version/model anchor присутствует точно, без fuzzy prefix/version conflation и без неизвестного adjacent lexical/punctuation continuation;
- lifecycle/action совпадает, replacement направлен, negation/conditional/uncertain/history и prefix/suffix noncurrent/modal assertions не принимаются за current assertion;
- взаимоисключающие active lifecycle assertions для той же exact identity fail closed даже когда находятся в разных local claims; GA не может сосуществовать с active preview/beta/early-access proof;
- primary/final URL относится к разрешённому authoritative source class и не совпадает с weak-source host;
- fetched page independently содержит exact current-event surface;
- deterministic freshness подтверждает saved editorial window;
- archive/dedupe не доказывает уже опубликованный exact event.

Для mutable lifecycle exact archive URL является достаточным proof. При другом URL org+version+lifecycle недостаточно: normalized ordered event-detail fingerprint должен совпасть целиком и сохранять направление numeric/mutable change. Частичное lexical overlap не блокирует fresh candidate. Structured archive organization может дополнять headline только внутри той же story row и не может переопределять foreign actor в headline.

## Recovery / compatibility / budget proof

Public `ensure_story_coverage.py` обязан сохранять historical Coverage API и monkeypatch seams, но production CLI и direct `execute_audit_plan()` должны идти через один hardened P3b v6 runtime. V6 владеет atomic P3b→legacy slot transfer, v5 сохраняет second-review orchestration compatibility, preserved v4/v3/v2/v1 layers остаются replay/regression boundaries. Compatibility sync не имеет права снять durable occupied-slot guard, заменить active binder v4 legacy matcher'ом или восстановить уже потраченную optional capacity.

Preserved `ensure_story_coverage_p3a.py` должен оставаться byte-identical pre-P3b public implementation. Historical binder v1/v2/v3 остаются forensic/compatibility assets; binder v4 наследует hardened v3 semantics, сохраняет durable `VERSION=2`/mode и отдельно использует `EVIDENCE_VERSION=2` для current positive processed proof. Evidence-v1 positive snapshot считается stale и fail-closed без нового provider search/page refetch.

P3b не меняет Primary 12-search matrix, Agency Rescue route/health, Hybrid allocation, regional health, ranking, editorial policy, Source Pulse или Freshness policy. Search ceilings остаются 24/25.

## Validation evidence и external-search boundary

Whole-project architecture/recovery audit: `automation/audits/experiments/2026-09-12-p3b-exact-authoritative-binding/README.md`.

V6/atomic-handoff remediation evidence: `automation/audits/experiments/2026-09-14-p3b-astra-third-review/README.md`.

Fourth-review semantic/matrix remediation evidence: `automation/audits/experiments/2026-09-14-p3b-astra-fourth-review/README.md`.

В среде реализации Terra не был exposed. Поэтому search-side acceptance выполнен через deterministic fixtures, saved artifacts и offline replay без production API пользователя и без paid Web Search. Последние remediation rounds не меняют search query/routing, поэтому отсутствие Terra не компенсировалось production spend.

Перед merge final exact head обязан пройти полный PR Gate и отдельный независимый Astra review final diff. Regression tests с именем `astra` являются executable controls, а не заменой независимого reviewer verdict.
