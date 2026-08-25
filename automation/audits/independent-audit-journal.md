# Журнал независимых аудитов ИИ-Сводки

Последнее обновление: 2026-08-25  
Назначение: накопление независимых проверок полноты и свежести ежедневной ИИ-Сводки без расходования production API пользователя.

> Историческая часть журнала периодически сжимается: сохраняются ежедневные verdict, подтверждённые misses, повторяющиеся паттерны и принятые архитектурные решения. Детальные эксперименты хранятся в `automation/audits/experiments/` и не дублируются здесь целиком.

## Как использовать журнал

После каждого production-дня:
1. Определить фактический scheduled run, production SHA и effective news window.
2. Независимо проверить окно на собственных поисковых ресурсах, не используя production API пользователя.
3. Разделять retrieval miss, editorial rejection, stale, duplicate, material update, after-cutoff, borderline и infrastructure/API failure.
4. Отдельно проверять major agencies, China/Asia, Russia, Source Freshness Proof, Hybrid/Coverage и source concentration.
5. Не менять production-архитектуру автоматически. Повторяющийся дефект сначала получает отдельный контролируемый experiment.
6. Infrastructure/API failure, случившийся до meaningful execution retrieval pipeline, фиксировать в журнале как operational incident, но не включать в recall/completeness статистику архитектуры поиска. Первый последующий полноценный run за ту же publication date должен дать отдельный substantive audit и именно он учитывается в post-patch sample.

---

## Историческая серия 17–23 августа 2026

| Дата | Freshness | Completeness | Strict recall / ключевой результат |
|---|---|---|---|
| 2026-08-17 | FAIL | FAIL | ~50%; stale Anthropic + Nvidia/SB Energy Reuters miss |
| 2026-08-18 | PASS | PARTIAL | ~67% extended; Higgsfield/Round Hill/China blind spot |
| 2026-08-19 | PASS | PARTIAL | ~89%; Higgsfield healed, Round Hill repeated |
| 2026-08-20 | PASS | PARTIAL | Google/Marvell + Baidu misses |
| 2026-08-21 | PASS | PARTIAL | 75%; Broadcom + Alibaba + Google/Marvell; QwenCloud false duplicate |
| 2026-08-22 | PASS | PARTIAL | 87,5%; Alibaba healed, Broadcom repeated after semantic patch |
| 2026-08-23 | PASS | PARTIAL | ~66,7% on small weekend denominator; Nvidia Reuters + DeepSeek model misses; Russia borderline fabricaONE.AI |

### Устойчивые выводы этой серии
- Source Freshness Proof v1 стабилизировал freshness после 17 августа; без нового stale-defect его не ослаблять.
- `major_agencies` несколько дней давал `raw=0 / accepted=0` при independently verified Reuters Must Include событиях.
- Повторные agency misses Google/Marvell, Broadcom и Nvidia server pricing подтвердили source-pool/ranking instability, а не только слабую формулировку broad query.
- Alibaba recovery показал улучшение China/Asia business/earnings semantics, но DeepSeek V4-Flash-Vision-Exp выявил отдельный model/product blind spot.
- Russia zero-pool нельзя автоматически считать дефектом без strict Must Include denominator; fabricaONE.AI 4,7 млрд руб. остаётся borderline control.
- Short digest сам по себе не является дефектом; конкретные independently verified misses учитываются полностью.
- Возможный Coverage observability/persistence gap 23 августа остаётся отдельной reliability-линей и не смешивается с agency retrieval.

---

## Контроль 24 августа 2026 — false-zero и переход v2 → v3

### Baseline false-zero
- Production run `32674034063` израсходовал полный theoretical pipeline budget 24 search operations и завершился zero-pool `editorial_stop`.
- Независимый контроль подтвердил как минимум Reuters Alibaba share placement примерно на $10,2 млрд с направлением proceeds на full-stack AI: chips, infrastructure и models.
- Dedicated `major_agencies` уже имел provider-level Reuters/AP/Bloomberg/FT routing, но пригодного candidate не дал; Source Freshness Proof не был причиной miss, потому что Alibaba до него не дошёл.
- Source-open agency discovery rescue получил polluted aggregator/syndication layer и также не восстановил событие.

### v2
- PR #76 ввёл `agency_discovery_rescue` v2: ровно один Reuters-only provider search, publisher-neutral date-free query, direct-Reuters acceptance, неизменные freshness/significance/dedupe и global ceiling 24.
- Fresh run `32691255059` проверил v2 в production без reuse старого zero-pool artifact.
- v2 действительно выполнил Reuters-only search с `search_context_size=medium`, но получил `consulted_sources=[]`, `raw_count=0`; Alibaba снова не дошёл до freshness/editorial.

### v3
- PR #77 изменил только `agency_discovery_rescue` version `2 → 3` и `search_context_size: medium → high`.
- Query, `allowed_domains=["reuters.com"]`, one-search hard cap, direct-Reuters downstream acceptance, Source Freshness Proof, significance, archive/semantic dedupe, regional routes, Hybrid/Coverage и global ceiling 24 остались неизменны.
- Эта правка является bounded production-supported reliability hypothesis, а не доказанным isolated Terra A/B.

---

## 2026-08-25 — infrastructure/API exclusion до полноценного post-patch аудита

### Production
- Scheduled GitHub Actions run: `32789961306`, conclusion `failure`.
- Run работал на `main` SHA `aed73e362b770e31914d5c4230f274c429a84872`.
- Publication date: `2026-08-25`.
- Предыдущий опубликованный выпуск `2026-08-24` успешно проверен в repository и live; article/image HTTP 200.
- Automatic recovery не нашёл reusable artifact для 25 августа; `force_fresh_research=false`, manual `recovery_run_id` отсутствовал.
- Continuity validator: `search_window_start_at=2026-08-24T09:07:30+03:00`, policy `from_last_successful_research_cutoff`.
- Первый свежий Primary direction `global_breaking` завершился transport/API failure до получения search result:
  `429 insufficient_quota / credit_balance_exhausted` — `You have no credits remaining`.
- Pipeline fail-closed остановил research. Primary не завершён; `major_agencies` не запускался; agency discovery rescue v3, Hybrid, Coverage, editorial, image и promotion не запускались.
- Выпуск 25 августа не опубликован.
- Artifact `daily-production-2026-08-25`, ID `9542780627`, сохранён, но он маленький preflight/failure artifact; полноценного Primary/rescue/editorial state в нём нет.

### Статистический статус инцидента
- **EXCLUDED FROM RETRIEVAL ARCHITECTURE STATISTICS.** Этот run не учитывается как плохой recall/completeness день и не ухудшает post-patch статистику поиска.
- Причина непубликации внешняя по отношению к retrieval semantics: исчерпанный OpenAI API balance остановил pipeline до первого завершённого Primary search.
- Формальное `0 published` и даже условное `0/1` нельзя использовать в сравнении качества v3 с предыдущими днями: поисковая архитектура не получила возможности исполниться.
- Этот incident также **не расходует meaningful day post-patch sample**. До успешного полноценного run размер post-patch выборки остаётся `0/7`.
- Если ручной fresh `Daily production digest` за `2026-08-25` успешно завершится после пополнения баланса, для архитектурной статистики именно его artifact/effective window и готовый выпуск должны быть проаудированы как первый meaningful post-patch день `1/7`; текущая quota-запись остаётся только operational incident.

### Фактический v3 contract на production SHA
По `automation/scripts/agency_discovery_rescue.py` на SHA run:
- `AGENCY_DISCOVERY_RESCUE_VERSION = 3`;
- query: `latest AI chips infrastructure financing earnings business deals policy security`;
- `allowed_domains = ("reuters.com",)`;
- `search_context_size = "high"`;
- rescue max Web Search operations = 1;
- theoretical pipeline ceiling = `12 Primary + 1 rescue + 4 Hybrid + 7 Coverage = 24`.

То есть run стартовал уже на ожидаемом v3 code contract. Однако сам v3 stage сегодня не был достигнут.

### Effective window / independent reference set
- Подтверждённый continuity start: `2026-08-24 09:07:30 +03:00` (`06:07:30 UTC`).
- Запуск упал около `2026-08-25 02:35:17 +03:00` (`2026-08-24 23:35:17 UTC`); это практический верхний предел сегодняшней независимой проверки, поскольку authoritative research `search_window.end_at` не был сохранён после успешного Primary.
- Внутри этого интервала независимо найден как минимум один сильный свежий AI event:
  - Reuters, `2026-08-24 08:15:19 UTC`: Alibaba официально запустила AI video model `Wan3.0` с улучшенными возможностями после крупного AI financing event. Это находится после continuity start и до failure time; классификация: **strict Must Include candidate / China-Asia model-product + agency control**.
- Reuters Nvidia/Perplexity investment report имеет timestamp `2026-08-24 03:18:37 UTC`, то есть находится **до** continuity start и не используется как strict control сегодняшнего main-continuity window.
- Reuters Alibaba share-placement market update около `01:32–01:51 UTC` также находится до continuity start; исходное financing event уже относится к предыдущему release/healing history и не считается новым strict event сегодняшнего main window.
- NVIDIA 24 августа объявила новые Vera Rubin/Groq 3 LPX platform/inference developments, но доступный official page даёт только calendar date без надёжного точного publication timestamp; сохраняется как **borderline / timestamp-unresolved**, а не в strict denominator.
- AWS 24 августа объявила доступность OpenAI GPT-5.6 Terra/Luna в AWS GovCloud, но доступный source также даёт дату без точного времени; **borderline / timestamp-unresolved** для exact-window denominator.

### Strict recall
- Production retrieval не завершил даже первый обязательный search. Условное `0/1` описывает только факт прерванного run, но **не является метрикой retrieval quality и не входит в статистический ряд архитектуры поиска**.
- Каноническая оценка для post-patch experiment: **strict recall = N/A / excluded**; отдельно зафиксировано, что в окне был минимум один strict event, поэтому день нельзя считать «тихим нулём».

### Primary / Rescue / Hybrid / Coverage anatomy
- Primary: started, `global_breaking` failed before completion with OpenAI 429; completed searches по artifact/log = 0.
- `major_agencies`: not executed; raw/accepted = N/A.
- `agency_discovery_rescue v3`: not triggered/not executed because mandatory Primary matrix did not reach completed `major_agencies`; search count contribution = 0.
- Hybrid: not executed.
- Coverage: not executed.
- Editorial: not executed.
- Published stories: 0.
- Полного budget burn не было: failure произошёл на первом fresh Primary request, а не после 24 searches.

### v3 rescue verdict
**INCONCLUSIVE / NOT TESTED / EXCLUDED FROM SAMPLE.**

Сегодняшний scheduled run не предоставляет evidence ни в пользу, ни против `search_context_size=high`: API quota failure случился на `global_breaking` до `major_agencies` и до самого rescue. Нельзя классифицировать этот день как повтор v2 false-zero и нельзя объявлять v3 сломанным или улучшившимся.

### Freshness / noise / duplicates
- Новых candidates и published stories нет, поэтому Source Freshness Proof, direct-Reuters acceptance, archive dedupe, semantic dedupe, source concentration и syndicated-source guards не получили runtime test.
- Никаких stale/noise/duplicate regressions patch сегодня не продемонстрировал.

### China / Asia
- Production Asia routes не запускались.
- Independently verified Reuters `Alibaba Wan3.0` внутри доступного окна даёт новый out-of-sample China/Asia model-product control.
- Поскольку production был остановлен до этих routes, это **не retrieval miss v3**, а **unobserved due infrastructure/API failure**.
- DeepSeek model/product line остаётся отдельной наблюдаемой проблемой из предыдущих дней; сегодняшний Wan3.0 повышает ценность следующего полноценного Asia route test, но сам по себе не оправдывает новый patch.

### Russia
- Production `russia` route и regional Hybrid не запускались.
- Независимый поиск не дал уверенного strict Must Include с подтверждённым timestamp внутри exact доступного интервала; Russia strict recall = **N/A**.
- Предыдущий borderline fabricaONE.AI остаётся историческим control, а не сегодняшним обязательным miss.

### Recovery / cost / observability
- Scheduled run корректно не использовал `force_fresh_research`; automatic recovery artifact для новой даты отсутствовал.
- Неожиданного повторного research не было.
- Ошибка хорошо видна в job log как `credit_balance_exhausted`, но финальный `pipeline-status.json`/русский summary классифицировал её как `Неопределённый этап`. Это был отдельный **observability defect**, не retrieval defect.
- После этого инцидента PR #79 добавил сохранение Primary API failure и явный русский Summary для `429 insufficient_quota / credit_balance_exhausted`; исправление диагностики не меняет retrieval architecture и не влияет на её статистику.

### Оценка дня
- Freshness: **N/A — excluded infrastructure/API incident**.
- Completeness: **N/A — excluded infrastructure/API incident**.
- Post-patch verdict относительно baseline 24 августа: **NEUTRAL / INCONCLUSIVE, вне статистической выборки**.
- Причина: v3 architecture сегодня не исполнялась. Нельзя назвать patch лучше или хуже по run, который умер до relevant stage из-за исчерпанного OpenAI API balance.
- Важное отличие от baseline false-zero: 24 августа pipeline технически выполнил searches и не нашёл известное событие; 25 августа search architecture не получила возможности работать вообще.
- Meaningful post-patch наблюдения: **0/7**. Следующий успешный полный production run — включая ручной fresh rerun за 25 августа — должен стать первым полноценным out-of-sample production test v3.

### Что делать по результату
- Production retrieval code не менять по этому quota incident.
- После пополнения API balance допустим ручной fresh `Daily production digest` за `2026-08-25`; его результат нужно проверить отдельным полноценным независимым аудитом completeness/freshness/retrieval anatomy.
- В таком аудите особенно проверить новый strict control class: fresh Reuters/agency и China model-product events, `major_agencies raw/accepted`, v3 trigger/execution и source pool.
- Quota-failure run оставить в журнале только как operational/reliability incident; не смешивать его с дальнейшим BETTER/NEUTRAL/WORSE анализом retrieval patch.

---

## Post-patch серия после PR #77

| Статус | Дата | Production | v3 meaningful test | Verdict | Ключевой результат |
|---|---|---|---|---|---|
| excluded, sample остаётся 0/7 | 2026-08-25 scheduled | FAIL до Primary completion | нет | N/A / operational incident | API 429 `credit_balance_exhausted`; retrieval architecture не исполнялась |

## Что наблюдать дальше

- Первый успешный production run после v3 — в том числе ручной rerun 25 августа: `major_agencies` source pool и agency discovery rescue `high` против нового out-of-sample Reuters control.
- Не повторяется ли defect `fresh Reuters Must Include exists → provider source pool empty/stale → zero candidate`.
- China/Asia model-product route после DeepSeek и нового Wan3.0 control отдельно от business/earnings.
- Russia business/financing без региональной квоты; strict defect только при independently verified Must Include.
- Coverage persistence для short digest и failure observability как отдельные reliability-линии.
- Source Freshness Proof v1 оставить без изменений, пока stale-defect не повторится.
