# P3b exact authoritative binding: permanent validation matrix

Этот документ является постоянным regression contract для active P3b поверх P3a weak-source signal retention. Он дополняет общую `search-change-validation-matrix.md` и не заменяет её.

## Scope и неизменяемые границы

P3a остаётся evidence-only: qualified `reason_code=weak_source` сохраняет source provenance и identity hints, но имеет `resolution_required=false`, `candidate_eligible=false` и сам не связывает событие с authoritative source.

Active P3b использует binder implementation `weak_source_exact_binding_v4.py` при сохранённом durable request-contract `VERSION=2`; public Coverage path идёт через v7 recovery-preflight → preserved v6 → v5 → v4 → v3 → v2 compatibility chain. Binder v4 отдельно маркирует semantic positive proof через `EVIDENCE_VERSION=6`, не разрывая durable request identity. Runtime v7 не повышает evidence marker: его изменение находится над binder и закрывает production reuse shortcuts, которые могли обойти v6 `execute_audit_plan` postcondition. Evidence v6 сохраняет все evidence-v5 fail-closed требования и дополнительно делает historical classification relation-local для самой lifecycle relation: unrelated old full date/background не может скрыть current negation или foreign attribution, historical cancellation/state не veto'ит отдельную current exact claim, а old year/date до или после lifecycle action остаётся historical только при чистой relation-bound связи. Unicode wrappers, включая `«…»`, `‹…›` и fullwidth `（…）`, не скрывают trailing `by` attribution. Positive processed snapshot с более старым evidence marker, включая evidence-v5, не переиспользуется как current proof. P3b может рассмотреть максимум один qualified P3a weak-source signal и использует только уже существующий optional seventh Coverage slot. Шесть mandatory Coverage directions не меняются. Required high-signal `unverified` resolution имеет приоритет. Если optional capacity занята, потрачена или неоднозначна, weak-source signal остаётся unresolved/deferred. Восьмой Coverage search запрещён. Обычный whole-pipeline ceiling остаётся 24 Web Search operations; существующий conditional double-regional-gap ceiling остаётся 25.

Положительное P3b admission требует runtime proof, а не утверждения модели: authoritative non-weak URL, реальную страницу, exact organization, все retained version/model anchors, совместимый lifecycle/action, deterministic Event/Source Freshness и archive/dedupe checks. Organization, все retained anchors и lifecycle/action должны доказываться одним local event claim; соседние title/paragraph claims нельзя склеивать в одно событие. Простого присутствия organization в том же claim тоже недостаточно: lifecycle assertion должна относиться к signal organization, а foreign named actor, passive attribution другому agent, foreign trailing agent после complete directed replacement span либо явная reporting/role attribution между organization и lifecycle/action делает identity недоказанной. Passive/trailing agent identity сравнивается по полному normalized agent surface, а не по prefix или fragment до первой запятой. Historical/background claim остаётся non-current evidence и не veto'ит отдельный current exact event только из-за собственной foreign attribution. Historical marker должен быть связан с lifecycle relation, а не просто присутствовать где-то в claim. Replacement direction выводится из retained signal claim, а не из порядка anchors. Negation, conditional/uncertain language, prefix/suffix planned/modal/cancelled/denied assertions и historical/background mentions не являются current-event proof. Взаимоисключающие active lifecycle claims для той же exact identity, включая GA в одной local claim и preview в соседней, fail closed. Provider terminal-negative labels не являются independent proof.

Production recovery добавляет отдельный invariant над этими semantic rules. Если durable `processed` journal доказывает stale positive evidence-v1..v5 и exact provenance-bound candidate всё ещё присутствует в current research, durable `coverage-audit-merged-candidates-<DATE>.json`, reusable prior Coverage report или complete story snapshot, v7 выполняет deterministic preflight до `existing_full_digest` и `prior_complete` shortcuts. Preflight не переписывает optional-slot journal, удаляет только тот же exact stale provenance, сохраняет unrelated candidates и санирует все recovery inputs. При затронутом publishable snapshot он атомарно записывает `coverage-p3b-v7-revocation-<DATE>.json` со state `pending` и `publication_snapshot_invalidated=true`, после чего убирает old `stories.json` из publishable artifact. Если stale provenance есть только в non-publishable report/persisted research, marker имеет `publication_snapshot_invalidated=false`: sanitation всё равно crash-safe, но заведомо чистый complete digest не инвалидируется. `pending`/`blocked` publication-invalidating marker переживает crash и не считается завершённым до clean rebuild; provider search, retry и page refetch preflight не открывает.

GitHub artifact recovery является частью того же invariant. V7 marker/backups, optional-slot state, persisted merged research и Coverage report можно продолжать только из exact artifact bundle, чей dated source выбрал recovery. Selected full pre-v7 bundle со stale positive evidence-v1..v5, а также full bundle с publication-invalidating `pending|blocked` marker, обязан быть понижен до `partial_editorial` до workflow runtime-readiness decision. Это не разрешает search: оно только делает pinned text runtime доступным для sanitized downstream rebuild. `completed` marker supersede'ит historical stale journal для этого readiness-решения, потому что journal намеренно не переписывается после успешной remediation.

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
- stale positive processed proof revokes только provenance-bound P3b candidate даже если current model/archive/request hash drift уже заставил preserved layer вернуть early deferred; cleanup остаётся v6 `execute_audit_plan` postcondition для direct path, а active v7 дополнительно применяет тот же revocation predicate до production complete/reuse shortcuts;
- complete recovered digest со stale evidence-v1..v5 не может пройти `existing_full_digest`: v7 должен записать durable pending marker, удалить stale provenance из research, вывести old `stories.json` из publishable path и потребовать clean rebuild;
- reusable prior Coverage report со stale evidence-v1..v5 должен быть санирован до `prior_complete` reuse; stale + independent candidates сохраняют только independent row;
- durable `coverage-audit-merged-candidates-<DATE>.json` является полноценным recovery input: stale provenance в нём санируется тем же exact predicate, unrelated rows сохраняются, первый original backup не перезаписывается и postflight не принимает повторно внесённый stale row;
- stale только в report/persisted merged research очищается offline без ненужного invalidation чистого complete digest; crash такого sanitation сохраняет marker scope `publication_snapshot_invalidated=false`;
- crash после publication-invalidating pending marker, включая ситуацию когда optional-slot journal позже отсутствует, не возвращает old complete snapshot; первый original SHA/backup metadata сохраняется;
- child failure оставляет marker `pending`; ложный child success, который вернул revoked story, stale persisted research либо не создал новый `stories.json`, переводит marker в `blocked` и возвращает non-zero;
- same-bundle recovery переносит v7 marker/forensic backups только из evidence root, выбранного для dated artifact; divergent current state не смешивается с recovery bundle и fail-closed;
- selected full pre-v7 artifact со stale positive journal и selected full artifact с publication-invalidating `pending|blocked` marker понижаются до `partial_editorial` до runtime-readiness decision, чтобы rebuild мог выполниться без повторного retrieval;
- valid `completed` marker не создаёт вечный `partial_editorial` только потому, что historical processed journal намеренно остался evidence-v1..v5;
- current evidence-v6 positive запускает обычный reuse только при доказанной durable processed lineage; pre-lineage evidence-v6 positive не считается current reusable proof и обрабатывается fail-closed без refund/retry;
- current processed writer сохраняет hash полного `processed_snapshot` и provenance exact request/response/pre-optional bundle; подмена `candidates[]` после записи provenance обязана fail-closed;
- production-shaped final research `candidates.json` не обязан содержать Coverage `attempts/checked_directions` и не используется для реконструкции pre-optional bundle identity;
- post-request `processed_snapshot` не обязан содержать top-level `search_window/publication_date` и не сравнивается через lifecycle-нестабильный `_P3A._bundle_identity(processed_snapshot)`;
- saved parsed result при `response_saved|processed` обязан точно воспроизводиться deterministic offline parse из hash-проверенного raw response; `raw A + parsed B` fail-closed без provider/search/page I/O;
- processed legacy `unverified_resolution` обязан совпадать с current full request contract, пересчитанным из current required signals/model/archive/search window; stable `signal_id` при query/prompt/model/content drift не разрешает early reuse;
- matching legacy request сам по себе не повышает pre-lineage `processed` journal до reusable: без proven processed lineage он fail-closed до `prior_complete`/`existing_full_digest`, slot остаётся spent и search не повторяется;
- historical `response_saved` с parsed snapshot без additive lineage обязан reparsed'иться из hash-проверенного raw response offline и получить current result lineage до `processed`; serialized raw replay обязан сохранять nested search action metadata и message output-text blocks;
- v7 preflight/recovery integration не выполняет ordinary/protected provider call, retry, Web Search или authoritative-page refetch и не меняет optional-slot journal bytes/search-budget consumption;
- `reserved` P3b intent не обходит higher-priority required `unverified`, а foreign/mismatched reservation не удаляется;
- proven unstarted P3b reservation может быть передан required `unverified` только атомарной заменой durable intent под тем же slot lock, который защищает request admission; между P3b и legacy не возникает состояния без reservation;
- crash сразу после atomic transfer оставляет полный legacy `reserved` journal, а crash после `request_started` оставляет consumed/ambiguous journal; recovery в обоих случаях не создаёт восьмой Coverage search;
- transfer не имеет права перезаписать уже `request_started`, response-bearing, consumed/ambiguous, foreign или concurrently changed P3b journal;
- explicit negation, suffix-negative lifecycle, conditional `if/unless/whether`, rumor/speculation, planned/cancelled/modal и historical exact-event mention не дают positive binding;
- uncertainty/action-state checks применяются независимо от позиции lifecycle token: `reportedly launched`, `launch expected`, `launch may|might|could happen`, `launch denied`, `GA planned|cancelled|may happen` fail closed;
- organization нельзя заимствовать из соседнего page claim: exact organization + retained anchors + lifecycle/action должны находиться в одном local event claim;
- same-claim foreign actor contamination fail-closed: `DeepSeek says OpenAI launches V4.1 Flash`, lowercase foreign actor, role-attribution, passive `... launched by OpenAI` и replacement `DeepSeek says V4 Pro was replaced by V4.1 Flash by OpenAI` не доказывают DeepSeek event, а корректная attribution к signal organization, включая `... by DeepSeek`, сохраняет positive control;
- replacement trailing attribution нельзя спрятать несколькими wrapper/separator tokens: `((by OpenAI))`, `: — by OpenAI`, `{by OpenAI}`, `"by OpenAI"`, `({by OpenAI})`, `«by OpenAI»`, `‹by OpenAI›`, `（by OpenAI）` и аналогичные bounded combinations должны fail closed;
- passive/replacement agent capture не обрезается на первой запятой: `by DeepSeek, OpenAI and Anthropic` является multi-agent surface и не считается exact `DeepSeek` attribution;
- current lifecycle contradiction нельзя маскировать unrelated historical marker: `launch cancelled today due to a 2025 incident` и `Today, ... did not launch ..., with a dispute dating to September 1, 2025` остаются current non-positive contradictions, а не historical background;
- historical cancellation/state, связанный с old relation (`launch cancelled on September 1, 2025`), не veto'ит отдельную current exact claim; historical-only cancellation остаётся non-positive;
- historical/background same-identity claim с foreign attribution, включая полную дату вроде `on September 1, 2025`, не veto'ит отдельную current exact claim; это относится и к passive launch/update, и к replacement; historical-only proof остаётся non-positive;
- historical year/date, непосредственно связанный с lifecycle relation, остаётся historical независимо от отдельного subsequent current predicate: `In 2025, ... launched` и `launched ... in 2025 and now discusses it` не становятся current proof;
- GA claim не может одновременно использовать active preview/beta/early-access assertion как positive proof; это относится и к конфликту внутри одной claim, и к нескольким local claims с той же exact organization/model identity;
- structured archive organization не может переназначить foreign headline actor на signal organization;
- replacement old/new roles не зависят от порядка `product_version_anchors`, а наличие обеих противоположных active replacement directions fail-closed;
- canonical `general_availability` совместим с GA, но negated/preview GA остаётся fail-closed;
- lowercase, numeric и punctuation continuations (`v2`, `experimental`, `/Pro`, `+`, dash-variant`) не считаются exact shorter anchor, кроме явно разрешённого обычного prose continuation; v4 может локально разрешать обычные predicate/linking words (`remain/remains/stay/stays/...`) без изменения historical v2/v3 compatibility vocabulary;
- mutable archive updates одной модели не dedupe'ятся по org+version+lifecycle; exact URL остаётся conclusive, а semantic duplicate требует exact normalized ordered event-detail fingerprint, включая single-digit direction (`8K→9K` не равно `9K→8K`);
- high-overlap distinct updates (`video input support` vs `video output support`) не являются одним событием;
- positive `processed` snapshot без current binder `EVIDENCE_VERSION=6`, включая evidence-v1/evidence-v2/evidence-v3/evidence-v4/evidence-v5 positives, не переиспользуется как current hardened proof;
- canonical 20-case executable matrix импортирует active `weak_source_exact_binding_v4`, проверяет public v7 ownership + preserved v6 layer и не закрепляет historical v2 binder как active semantic implementation;
- `test_p3b_astra_regressions.py` проходит standalone в чистом Python process, чтобы full-suite import order не мог маскировать compatibility defect.

## Permanent executable coverage

- `automation/tests/test_p3b_exact_authoritative_binding.py`;
- `automation/tests/test_p3b_regression_matrix.py`;
- `automation/tests/test_p3b_optional_slot_recovery.py`;
- `automation/tests/test_p3b_astra_regressions.py`;
- `automation/tests/test_p3b_astra_second_review.py`;
- `automation/tests/test_p3b_astra_third_review.py`;
- `automation/tests/test_p3b_astra_fourth_review.py`;
- `automation/tests/test_p3b_astra_fifth_review.py`;
- `automation/tests/test_p3b_astra_sixth_review.py`;
- `automation/tests/test_p3b_recovery_ownership_priority.py`;
- `automation/tests/test_p3b_negation_historical_binding.py`;
- `automation/tests/test_p3b_replacement_roles.py`;
- `automation/tests/test_p3b_replacement_passive_attribution_hotfix.py`;
- `automation/tests/test_p3b_archive_update_identity.py`;
- `automation/tests/test_p3b_lifecycle_alias_suffix.py`;
- `automation/tests/test_p3b_import_isolation.py`;
- `automation/tests/test_p3b_v7_recovery_preflight.py`;
- `automation/tests/test_p3b_v7_durable_recovery_inputs.py`;
- `automation/tests/test_p3b_v7_recovery_bundle.py`;
- `automation/tests/test_p3b_v7_durable_lineage.py`;
- `automation/tests/test_p3b_architecture_contract.py`.

## Durable optional-slot state machine

Переходы active P3b binder/slot layer остаются `reserved → request_started → response_saved → processed`; v7 preflight не добавляет переходов в этот journal и не переписывает его.

| Saved state | Допустимое действие | Новый provider search |
|---|---|---|
| no journal | Только если mandatory Coverage завершён, optional seventh slot реально свободен и нет higher-priority required resolution | максимум 1 |
| `reserved` + capacity свободна | Продолжить тот же exact P3b intent; перед wire call перейти в `request_started` под protected admission lock | максимум 1 |
| `reserved` + proven P3b intent + required `unverified` | Под shared slot lock атомарно заменить только unstarted P3b reservation на полный legacy durable reservation; затем исполнить required legacy resolution через P3a protected transport | максимум 1 |
| `reserved` + budget уже исчерпан | Defer; reservation не может восстановить потраченный seventh slot | 0 |
| `request_started` | Outcome неизвестен; сохранить indeterminate/consumed, transfer/retry запрещены | 0 |
| `response_saved` | До child reuse active v7 доказывает exact deterministic raw→parsed equivalence для saved result; затем preserved offline replay, без provider search/mutable-page refetch | 0 |
| `processed` | Reuse только current hardened result с `EVIDENCE_VERSION=6` **и** валидной durable processed lineage exact bytes → request/response/pre-optional bundle; pre-lineage/stale/foreign/mismatched result fail-closed без refund | 0 |
| invalid/foreign/mismatched journal | Fail closed; не переписывать чужой intent и не угадывать consumption | 0 |

Только current unstarted P3b reservation с доказанным exact request-contract identity может быть передан уже существующему required `unverified`. `coverage_slot_handoff.transfer_reserved_slot` под тем же межпоточным/межпроцессным slot lock проверяет `state=reserved`, отсутствие wire-attempt, response/snapshot/consumed evidence и exact expected source journal hash, после чего одним atomic replace записывает полный legacy request/bundle contract. Поэтому нет crash-window, где P3b уже снят, а legacy reservation ещё не существует. Handoff сохраняет publication-date context на время P3a durable resolution; crash после `request_started` не возвращает capacity и следующий запуск не выполняет восьмой search.

V7 имеет отдельный publication/recovery marker state machine `pending → completed` либо `pending → blocked`; это не optional-slot state и не разрешение на новый provider call. Marker дополнительно фиксирует `publication_snapshot_invalidated`, чтобы crash при sanitation только non-publishable recovery inputs не превращал чистый digest в ложную rebuild obligation.

## Exact identity / archive contract

Binding fail-closed, если отсутствует хотя бы одно обязательное доказательство:

- normalized organization соответствует exact signal identity;
- normalized organization, каждый retained product/version/model anchor и lifecycle/action присутствуют в одном local event claim; совпадения, разбросанные по соседним claims, не складываются;
- lifecycle/action в этом local claim атрибутирован signal organization; organization не может быть только speaker/context рядом с event другого actor, включая явную reporting/role attribution, passive attribution другому agent и separate foreign trailing agent после complete directed replacement span;
- каждый retained product/version/model anchor присутствует точно, без fuzzy prefix/version conflation и без неизвестного adjacent lexical/punctuation continuation;
- lifecycle/action совпадает, replacement направлен, negation/conditional/uncertain/history и prefix/suffix noncurrent/modal assertions не принимаются за current assertion;
- взаимоисключающие active lifecycle assertions для той же exact identity fail closed даже когда находятся в разных local claims; GA не может сосуществовать с active preview/beta/early-access proof;
- primary/final URL относится к разрешённому authoritative source class и не совпадает с weak-source host;
- fetched page independently содержит exact current-event surface;
- deterministic freshness подтверждает saved editorial window;
- archive/dedupe не доказывает уже опубликованный exact event.

Для mutable lifecycle exact archive URL является достаточным proof. При другом URL org+version+lifecycle недостаточно: normalized ordered event-detail fingerprint должен совпасть целиком и сохранять направление numeric/mutable change. Частичное lexical overlap не блокирует fresh candidate. Structured archive organization может дополнять headline только внутри той же story row и не может переопределять foreign actor в headline.

## Recovery / compatibility / budget proof

Public `ensure_story_coverage.py` обязан сохранять historical Coverage API и monkeypatch seams, но production CLI и direct `execute_audit_plan()` входят через active P3b v7 runtime. V7 добавляет только production recovery preflight/postflight; preserved v6 остаётся владельцем binder v4, atomic P3b→legacy slot transfer и direct `execute_audit_plan` stale-evidence migration. V5 сохраняет second-review orchestration compatibility, preserved v4/v3/v2/v1 layers остаются replay/regression boundaries. Compatibility sync не имеет права снять durable occupied-slot guard, заменить active binder v4 legacy matcher'ом или восстановить уже потраченную optional capacity.

Preserved `ensure_story_coverage_p3a.py` должен оставаться byte-identical pre-P3b public implementation. Historical binder v1/v2/v3 остаются forensic/compatibility assets; binder v4 наследует hardened v3 semantics, сохраняет durable `VERSION=2`/mode и отдельно использует `EVIDENCE_VERSION=6` для current positive processed proof. Evidence-v1/evidence-v2/evidence-v3/evidence-v4/evidence-v5 positive snapshots считаются stale и fail-closed без нового provider search/page refetch. Stale semantic-proof cleanup является v6 postcondition на direct execute path и v7 preflight invariant перед production complete/prior-report reuse: current request-hash/model/archive drift может запретить replay, но не может сохранить или повторно опубликовать candidate, admitted только obsolete proof.

Common `coverage_slot_guard.py` добавляет current snapshot lineage без изменения preserved P3a/P3b semantic layers: result/processed hashes связываются с immutable request-contract hash, saved-response hash и pre-optional bundle hash; current `processed` state дополнительно обязан ссылаться на exact `result_snapshot_sha256` и не создаётся без доказанного parsed-result lineage. Pre-optional bundle не реконструируется из post-request Coverage plan или final research artifact, потому что их lifecycle/schema намеренно различаются.

Persisted merged Coverage research является durable recovery source, а не временным scratch-файлом. Поэтому v7 санирует его до downstream reuse и включает в postflight. `recover_digest_artifact.py` восстанавливает v7 marker/backups только из exact selected artifact bundle и понижает full recovery до `partial_editorial` только когда selected bundle доказывает незавершённую publication-invalidating remediation либо является pre-v7 stale-positive bundle. Это readiness guard, не разрешение на retrieval. Valid `completed` marker прекращает такой downgrade, хотя historical journal остаётся byte-for-byte прежним.

V7 quarantine backups являются forensic/rollback evidence и не должны автоматически возвращаться в publishable или active durable recovery-input paths. Code rollback и data rollback различаются; canonical procedure описана в `automation/P3B_V7_RECOVERY.md`. Pending/blocked rollback не имеет права восстанавливать old `stories.json`/merged research ради зелёного статуса, refund optional-slot journal или вручную повышать evidence marker.

P3b не меняет Primary 12-search matrix, Agency Rescue route/health, Hybrid allocation, regional health, ranking, editorial policy, Source Pulse или Freshness policy. Search ceilings остаются 24/25.

## Validation evidence и external-search boundary

Whole-project architecture/recovery audit: `automation/audits/experiments/2026-09-12-p3b-exact-authoritative-binding/README.md`.

V6/atomic-handoff remediation evidence: `automation/audits/experiments/2026-09-14-p3b-astra-third-review/README.md`.

Fourth-review semantic/matrix remediation evidence: `automation/audits/experiments/2026-09-14-p3b-astra-fourth-review/README.md`.

Replacement passive-attribution hotfix evidence: `automation/audits/experiments/2026-09-14-p3b-replacement-passive-attribution-hotfix/README.md`.

Final PR #183 independent-review remediation evidence: `automation/audits/experiments/2026-09-15-p3b-astra-final-review-remediation/final-review-four-blockers-remediation.md`.

Fifth-review three-blocker remediation evidence: `automation/audits/experiments/2026-09-15-p3b-astra-final-review-remediation/fifth-review-three-blockers-remediation.md`.

Sixth-review three-group remediation evidence: `automation/audits/experiments/2026-09-15-p3b-astra-final-review-remediation/sixth-review-three-groups-remediation.md`.

V7 post-merge stale-positive reuse remediation is specified by `automation/P3B_V7_RECOVERY.md` and executable controls `automation/tests/test_p3b_v7_recovery_preflight.py`, `automation/tests/test_p3b_v7_durable_recovery_inputs.py` and `automation/tests/test_p3b_v7_recovery_bundle.py`; it changes orchestration/recovery placement, not search-side semantics.

В среде реализации Terra не был exposed. Поэтому search-side acceptance выполнен через deterministic fixtures, saved artifacts и offline replay без production API пользователя и без paid Web Search. V7 не меняет search query/routing, поэтому live substitute search не выполняется и production spend для этой remediation не требуется.

Перед merge final exact head обязан пройти полный PR Gate и отдельный независимый Astra review final diff. Regression tests с именем `astra` являются executable controls, а не заменой независимого reviewer verdict.