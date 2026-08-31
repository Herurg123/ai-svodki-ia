# A/B experiment: Primary Recall baseline queries vs date-anchored queries, 31 августа 2026

Статус: завершён  
Тип: assistant-owned retrieval experiment, research-only  
Production API пользователя: **не использовался**  
Production behavior: **не изменён**

## Вопрос

Может ли простое добавление дат к существующим 12 Primary Recall query заметно повысить event-level recall без ухудшения freshness/precision?

Гипотеза B была намеренно простой: сохранить текущие направления и сущности, но заменить неопределённое `latest` на явное указание `August 29 2026 August 30 2026` (для российского направления: `29 августа 2026 30 августа 2026`). Это охватывает два основных календарных дня окна, но не его короткий хвост раннего 31 августа; этот boundary trade-off учитывается в verdict и сам по себе является недостатком blanket calendar-date anchoring.

## Почему тест нужен

Production за 31 августа выполнил 12 mandatory Primary searches, но получил только 3 raw candidates и 2 validated unique candidates. В большинстве направлений `raw=0`. Независимый аудит при этом подтвердил пропущенное security-событие CLTR/Loss of Control Observatory.

Самое очевидное объяснение — broad query недостаточно привязан ко времени. Это дешёвая гипотеза, поэтому её полезно проверить до очередной правки production. Люди традиционно предпочитают сначала переписать строку, а потом выяснить, что проблема была этажом ниже; здесь порядок обратный.

## Контрольное окно

Использовано то же сохранённое production effective window:

- start: `2026-08-29T04:15:21+03:00`;
- end: `2026-08-31T04:22:46+03:00`;
- continuity anchor: `2026-08-30T04:15:21+03:00`.

После search discovery каждый lead проверялся на **event origin**, а не только на дату найденной страницы. Архивные дубли и события до окна не считались улучшением recall. B не объявляется точным кодированием всего timestamp window: календарные даты используются только как ranking/discovery intervention, а точная временная допустимость остаётся downstream criterion.

## Варианты

### A — текущий production query family

1. `latest major AI news models products business infrastructure`
2. `latest AI models research chips infrastructure financing earnings business deals policy security`
3. `latest major AI model agent product research releases`
4. `latest AI chips cloud data centers infrastructure Nvidia AMD hyperscalers energy`
5. `latest AI financing acquisitions partnerships enterprise deals business`
6. `latest China AI models releases Tencent Hunyuan Qwen DeepSeek GLM open source`
7. `latest China Asia AI business earnings revenue strategy cloud partnerships deployments`
8. `последние новости ИИ Россия Яндекс Сбер VK МТС продукты регулирование авторское право данные обучение моделей`
9. `latest coding agents developer tools Claude Code Cursor Copilot Codex CLI releases`
10. `latest AI security safety incidents prompt injection data breach agent vulnerabilities`
11. `latest major AI copyright court regulation policy decisions`
12. `latest major artificial intelligence news missing events`

### B — date-anchored family

Для каждого направления сохранена его тема, но добавлены календарные даты `August 29 2026 August 30 2026`; для российского направления — `29 августа 2026 30 августа 2026`.

Это deliberately narrow intervention: не менялись source allowlists, downstream significance, freshness, dedupe, число направлений или budget.

## Метод

A и B запускались на одной assistant-owned web-search поверхности. Это **не идентичный production provider и не causal Terra/provider A/B**, поэтому эксперимент отвечает на более узкий вопрос:

> повышает ли сама date anchoring настолько явно качество surfaced event leads, чтобы оправдать production rewrite?

Оценивался не raw URL count, а validated event-level outcome:

- fresh event inside exact window;
- AI relevance;
- significance;
- archive dedupe;
- primary/authoritative event-origin evidence, когда оно доступно;
- false-fresh leads считались precision cost, а не recall gain.

## Результат по направлениям

| Направление | A | B | Вывод |
|---|---|---|---|
| global_breaking | нового high-confidence control не добавил | нового high-confidence control не добавил; поднял secondary coverage Cursor | **B не лучше**, Cursor event origin = 28 августа |
| major_agencies | внутривоконного strict Reuters control не найдено | тоже; surfaced Cursor Reuters page | **B не лучше**, first-party event origin Cursor = 28 августа |
| models_products_agents | новых valid controls нет | новых valid controls нет | tie |
| infrastructure_chips_cloud | выбранный SpaceX story в top surfaced results не восстановлен | также не восстановлен | tie / direct-lane miss у обеих формулировок |
| business_investment_partnerships | новых valid controls нет | новых valid controls нет | tie |
| china_asia_models | surfaced Tencent Hy4 | surfaced Tencent Hy4 более настойчиво | **ложный uplift**: Tencent first-party date = 28 августа, до окна |
| china_asia_integrations | hard valid control не подтверждён | hard valid control не подтверждён | tie |
| russia | hard valid control не подтверждён | больше fresh-looking leads | **precision хуже**: заметные leads оказались повторными страницами про более старые события |
| developer_tools | top results A не показали Codex v0.151.0 | B surfaced Codex v0.151.0 через secondary release tracker | **B lead-recall +**, но production A всё равно нашёл official GitHub release |
| security_safety | surfaced CLTR/Guardian | surfaced CLTR/Guardian | **tie на главном hard miss** |
| legal_regulation | Sony/Warner lawsuit surfaced, но это archive duplicate; также старые legal events | то же | tie |
| independent_missing_events | hard CLTR не был главным surfaced result | B surfaced CLTR через news aggregation | B даёт дополнительный lead, но **не новый unique event**, потому что A security lane уже нашёл CLTR |

## Главный контроль: CLTR security miss

High-confidence miss независимого аудита:

- Centre for Long-Term Resilience, 29 августа 2026;
- новое исследование Loss of Control Observatory;
- 1 664 real-world incidents detected in 2026;
- higher-severity incidents выросли в 7,4 раза;
- Guardian publication 29 августа, 02:00 EDT, уверенно внутри exact window.

Sources:

- https://www.longtermresilience.org/reports/ai-loss-of-control-incidents-are-worsening-shows-cltr-analysis/
- https://www.theguardian.com/technology/2026/aug/29/sharp-rise-in-incidents-of-ai-escaping-users-control-research-finds

**И A, и B смогли обнаружить это событие через security query.**

Production при текущем A query в том же направлении сохранил `raw=0`.

Это важнее небольших различий ранжирования между A и B: сам текст A query способен описать и найти событие на независимой поверхности. Следовательно, production miss нельзя объяснить только отсутствием дат в строке.

## Fresh-page / old-event regressions варианта B

### Cursor

B чаще поднимал материалы 29 августа об OpenAI/Cursor. Однако first-party OpenAI announcement датирован **28 августа 2026**:

https://openai.com/index/our-decision-on-cursor-following-its-acquisition-by-spacex/

Следовательно, более свежая secondary page не превращает событие в внутривоконное.

### Tencent Hy4

Date-anchored China query поднимал Hy4 как сильный recent lead, но Tencent first-party page:

https://www.tencent.com/tencent-releases-and-open-sources-tencent-hy4-preview/

имеет дату **August 28, 2026**, то есть событие находится до effective-window start.

### Россия

B поднимал свежие страницы о школьном курсе «Искусственный интеллект и информационная безопасность». First-party Минпросвещения показывает исходное объявление **21 августа**, а последующие федеральные страницы 26–27 августа повторяют уже известное решение. Это также не current-window event.

Primary source:
https://edu.gov.ru/press/11954/sergey-kravcov-v-shkolah-poyavitsya-novyy-kurs-vneurochnoy-deyatelnosti-iskusstvennyy-intellekt-i-informacionnaya-bezopasnost/

Иными словами, B делает выдачу визуально «свежее», но часть этого эффекта получается ровно тем способом, от которого Event Freshness contract защищает production.

## Event-level score

На conservative eligible reference set независимого аудита присутствуют три high-confidence события:

1. Codex CLI rust-v0.151.0 — production selected; source freshness точная, event origin date-only boundary и потому `event_freshness_status=unknown`;
2. SpaceX gas-turbine component foundry — production selected;
3. CLTR loss-of-control report — production missed и классифицирован как strict Must Include.

Для задачи **recovery пропущенного hard event** A и B дают одинаковый результат: оба находят CLTR на security lane.

B дополнительно улучшает surfaced lead position для Codex и CLTR в некоторых других lanes, но не добавляет новый validated unique Must Include event к контрольному набору. Одновременно B повышает число false-fresh leads с old event origin и имеет calendar-boundary blind spot для раннего 31 августа.

Поэтому утверждать `B recall > A recall` на validated event-level данных нельзя.

## Verdict

**NO-GO для blanket replacement A → B.**

Причины:

1. Главный production miss CLTR восстанавливается и A, и B.
2. B не дал доказанного прироста unique validated Must Include events.
3. B создаёт дополнительный false-fresh pressure на Cursor, Tencent Hy4 и российские повторные страницы.
4. B как calendar-date encoding не совпадает с timestamp continuity window и создаёт дополнительный boundary trade-off.
5. Production уже имеет строгий downstream Event Freshness contract; перенос календарных дат в broad query не решает provider/ranking failure, а только меняет ranking surface.
6. Исторические аудиты уже показывали zero-result/stale source-pool failures при семантически подходящих query. Результат 31 августа согласуется с этой линией.

## Что этот A/B говорит о root cause

Наблюдение:

`independent search + exact A security query → CLTR surfaced`

при одновременно:

`production Primary + exact A security query → raw=0`.

Наиболее правдоподобный class проблемы:

**provider/source routing, ranking, retrieval nondeterminism или candidate extraction/formation**, а не query wording сам по себе.

Этот эксперимент не разделяет эти четыре подпричины причинно. Для этого нужен следующий bounded diagnostic experiment на сохранённом production contract.

## Следующая гипотеза для отдельного эксперимента

Не менять 12 query и не добавлять поисковые операции. Вместо этого исследовать zero-raw mandatory lanes:

- сохранять/сравнивать provider source metadata и result-source diversity, когда доступно;
- отдельно классифицировать `no useful result`, `no source metadata`, `stale-only source pool` и `candidate extraction produced zero`;
- использовать известные out-of-sample controls вроде CLTR только как diagnostic reference, а не как hardcoded target;
- проверить, можно ли безопасно использовать уже разрешённые Hybrid/Coverage slots более targetably при доказанном degraded lane, не увеличивая global ceiling;
- не позволять Source Pulse закрывать Search-derived gap и не ослаблять Event/Source Freshness.

Любое production изменение после такого эксперимента потребует отдельного architecture audit, offline regression и PR.

## Документация

README, `automation/README.md`, `automation/ARCHITECTURE.md` и `AGENTS.md` не менялись: этот файл только фиксирует исследование и не изменяет runtime contract.
