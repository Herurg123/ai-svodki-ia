# Матрица независимой проверки изменений поиска и сбора новостей

Этот документ задаёт обязательный минимальный стенд для любых изменений, которые
могут изменить набор найденных новостей, их provenance, порядок, полноту,
региональное покрытие, freshness, dedupe/fusion, search budget или условия
запуска дополнительных retrieval-веток.

Матрица является минимальным baseline. Её разрешено и ожидается расширять, когда
новый инцидент, эксперимент или архитектурное изменение обнаруживает ранее не
учтённое состояние. Сокращать обязательное покрытие без отдельного явного
решения владельца проекта нельзя.

## 1. Когда матрица обязательна

Независимый прогон нужен до production use и до утверждения изменения, если PR
затрагивает хотя бы один из следующих аспектов:

- построение поисковых запросов, их число, порядок, provider/model или routing;
- Primary Recall, Agency Rescue, Hybrid, Coverage или другой search-derived
  discovery path;
- логику regional/agency health, которая открывает или закрывает search slot;
- объединение результатов разных проходов, dedupe, event identity или URL
  provenance;
- source ranking, candidate caps, promotion/suppression и правила, которые могут
  изменить candidate pool;
- Event/Source Freshness, если изменение способно повлиять на сохранение или
  исключение найденных кандидатов;
- recovery/replay поисковых стадий, если возможен повтор paid retrieval или
  другое поведение на сохранённом artifact;
- новый supplemental discovery-plane, если он способен влиять на editorial
  candidate pool.

Чистые refactor/documentation/test-only изменения без semantic effect на
retrieval не требуют нового полного прогона, но должны доказать отсутствие
semantic delta существующими regressions.

## 2. Правила выполнения

1. Сравниваются **текущая production baseline** и **предлагаемая версия** на
   одинаковых controlled inputs, saved artifacts или assistant-owned данных.
2. Нельзя проверять только один happy path. Для затронутых измерений выполняется
   pairwise coverage, а известные опасные трёхсторонние пересечения проверяются
   отдельными critical-combination cases.
3. Если production retrieval использует Terra и assistant-side Terra доступна,
   поисковые эксперименты выполняются через Terra. Если Terra в текущей среде не
   exposed, это явно фиксируется в отчёте; пользовательский production API budget
   для компенсации этого ограничения не расходуется без отдельного разрешения.
4. Paid stages не повторяются ради regression. Используются сохранённые
   production artifacts, assistant-owned resources и zero-paid deterministic
   replays.
5. Для каждого case заранее фиксируются ожидаемые invariants и допустимый semantic
   delta. Неожиданное расхождение baseline/proposed считается результатом
   эксперимента, а не автоматически «улучшением».
6. Обязательно проверяются search ceilings, fail-closed mandatory stages,
   continuity window, event/source freshness, archive dedupe и recovery
   at-most-once semantics.
7. Результат сохраняется под `automation/audits/experiments/`; reusable
   machine-readable случаи добавляются в `automation/fixtures/recall/` и/или
   offline tests.
8. Новый production incident, связанный с retrieval, обязан добавить в эту
   матрицу новый постоянный case или расширить существующий, чтобы тот же класс
   ошибки больше не оставался невидимым.

## 3. Минимальная матрица состояний

| ID | Измерение | Обязательный case | Что должно проверяться |
|---|---|---|---|
| V1 | Объём | 0 релевантных результатов | Normal no-publish не превращается в technical failure; mandatory stages завершены. |
| V2 | Объём | 1–3 достойных кандидата | Short digest не стимулирует фиктивное добирание слабых новостей. |
| V3 | Объём | 4–6 кандидатов | Короткий выпуск сохраняет качество, provenance и отсутствие региональных квот. |
| V4 | Объём | Нормальный пул 7–12 | Обычный editorial/retrieval контракт не меняется случайно. |
| V5 | Объём | Dense pool выше candidate cap | Ranking/cap не теряет high-signal события и не создаёт publisher/topic flood. |
| O1 | Пересечения | Один URL встречается у нескольких кандидатов | Shared source URL не ломает identity mapping и не маскирует cross-candidate contamination. |
| O2 | Пересечения | Один event представлен разными URL/издателями | Dedupe объединяет событие по смыслу, не по одному URL. |
| O3 | Пересечения | Несколько разных событий одной организации | Event dedupe не схлопывает самостоятельные релизы. |
| O4 | Пересечения | Один supporting source используется в нескольких кандидатах | Supporting evidence остаётся допустимой, но не подменяет identity другого кандидата. |
| O5 | Пересечения | Один event найден несколькими search passes | Cross-query/cross-stage duplicate не раздувает candidate pool. |
| O6 | Пересечения | Identity принадлежит невыбранному кандидату | Unselected candidate не может загрязнить provenance выбранного сюжета. |
| O7 | Пересечения | Один publisher/topic доминирует в dense pool | Source/ranking pressure не уничтожает независимые достойные события. |
| R1 | Регион | Russia healthy, China/Asia healthy | Дополнительные regional slots не открываются. |
| R2 | Регион | Только Russia gap | Сохраняется контракт 3 broad + 1 regional Hybrid. |
| R3 | Регион | Только China/Asia gap | Сохраняется контракт 3 broad + 1 regional Hybrid. |
| R4 | Регион | Одновременно Russia + China/Asia gaps | Разрешается только утверждённый double-gap path: 3 broad + 2 regional, максимум 5 Hybrid searches. |
| R5 | Регион | Регион был early healthy, но viable survivor исчез после filtering | P4 может только re-open gap по exact Primary provenance. |
| R6 | Регион | Pulse-only кандидат существует при Search-derived gap | Supplemental plane не закрывает Search gap. |
| A1 | Agency | Early accepted agency candidate остаётся viable | Reuters rescue не тратится. |
| A2 | Agency | Early agency accepted, но все exact survivors отфильтрованы | Открывается только существующий один rescue slot. |
| A3 | Agency | Agency provenance ambiguous/unmatched | Неоднозначность не разрешает новый paid search. |
| F1 | Freshness | Event точно внутри окна, source свежий | Кандидат сохраняется. |
| F2 | Freshness | Event точно вне окна, source свежий reprint | Fresh reprint не делает старое событие новым. |
| F3 | Freshness | Event origin unknown, source свежий | Recall сохраняется, Source Freshness остаётся независимым gate. |
| F4 | Freshness | Date-only event на partial boundary day | Неоднозначная граница остаётся unknown, а не ложно stale/fresh. |
| F5 | Freshness | Source page stale при свежем/unknown event | Source Freshness fail-closed не обходится. |
| F6 | Freshness | Material update старого event | Update не смешивается с old reprint и проходит archive/material-update contract. |
| D1 | Degradation | Mandatory search возвращает 0 | Ноль отличается от technical error и отражается в diagnostics. |
| D2 | Degradation | Mandatory search timeout/error | Fail-closed stage не маскируется пустым successful result. |
| D3 | Degradation | Partial provider/tool result | Partial/budget_exhausted/error не допускают ложный complete. |
| D4 | Degradation | Source/network/parser/anti-bot error | Degraded diagnostics остаются видимыми и не превращаются в healthy. |
| D5 | Degradation | Один discovery-plane degraded, другой даёт кандидатов | Второй plane не маскирует health первого. |
| B1 | Budget | Caller передал oversized Hybrid limit | Шестой Hybrid search не появляется. |
| B2 | Budget | Baseline Hybrid limit понижен | Conditional fifth slot не активируется тайно. |
| B3 | Budget | Double-gap + oversized caller limit | Whole-pipeline ceiling остаётся в утверждённых пределах. |
| C1 | Continuity | Exact start/end timestamps | Поиск не создаёт дыру и не перечитывает уже закрытое окно без причины. |
| C2 | Continuity | Пограничная дата без точного времени | Date-only evidence не подменяет exact continuity timestamp. |
| P1 | Recovery | Research-only saved artifact | Recovery не повторяет уже оплаченный search без необходимости. |
| P2 | Recovery | Partial editorial saved artifact | Search state переиспользуется, downstream может быть завершён отдельно. |
| P3 | Recovery | Coverage добавил кандидата | Rerun editorial использует merged research без повторения завершённых retrieval passes. |
| P4 | Recovery | Saved artifact старой совместимой версии | Compatibility adapter сохраняет provenance и paid at-most-once semantics. |
| P5 | Ordering | Порядок кандидатов/результатов provider изменён | Смысловой результат не зависит от случайного порядка, кроме явно ranking-зависимых мест. |
| P6 | Ordering | Duplicate результаты приходят в разном порядке | Dedupe/fusion остаются детерминированными. |

## 4. Обязательные critical combinations

Минимум следующие пересечения прогоняются как совместные состояния, а не как
изолированные строки таблицы:

- sparse pool + shared supporting source;
- dense pool + cross-query duplicates + publisher/topic flood;
- both regional gaps + degraded/empty regional search;
- stale event + fresh reprint/source publication;
- date-only boundary + recovery from saved artifact;
- unselected candidate identity + supporting-source contamination;
- provider ordering perturbation + multi-URL same-event duplicate;
- double regional gap + oversized caller budget;
- agency candidate lost after filtering + simultaneous regional gap;
- Search-derived regional gap + Pulse-only candidate;
- mandatory-stage partial/error + same-day recovery;
- short digest + one degraded discovery-plane.

Для изменения, которое одновременно затрагивает несколько перечисленных
измерений, matrix должна покрывать pairwise combinations всех релевантных
измерений. Полный декартов продукт не требуется, если он не несёт дополнительного
риска, но известный incident shape или plausible three-way interaction нельзя
выкидывать ради сокращения числа тестов.

## 5. Критерий допуска

Изменение поиска/сбора новостей считается проверенным только когда:

- baseline и proposed version прогнаны независимо по релевантной матрице;
- все инварианты и ожидаемые deltas зафиксированы;
- неожиданные потери recall, ложные duplicates, provenance contamination,
  freshness regressions и budget/recovery нарушения устранены либо отдельно
  одобрены владельцем проекта;
- reusable regressions добавлены в репозиторий;
- в PR перечислены реально выполненные cases, использованный provider/tooling и
  любые ограничения стенда.

Green CI без такой независимой матрицы не является достаточным доказательством
безопасности semantic retrieval/search architecture change.
