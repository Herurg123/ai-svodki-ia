# Журнал независимых аудитов ИИ-Сводки

Последнее обновление: 2026-08-22  
Назначение: накопление независимых проверок полноты и свежести ежедневной ИИ-Сводки без расходования production API пользователя.

> 22 августа 2026 историческая часть журнала была аккуратно сжата: сохранены ежедневные verdict, подтверждённые misses, повторяющиеся паттерны и принятые архитектурные решения. Детальный контролируемый эксперимент 21 августа остаётся в `automation/audits/experiments/2026-08-21-agency-asia-recall.md` и не дублируется здесь целиком.

## Как использовать журнал

После каждого успешного ежедневного выпуска:
1. Определить фактическое effective news window по production artifact / archive.
2. Независимо проверить выпуск на собственных поисковых ресурсах, не используя production API пользователя.
3. Отдельно проверить freshness, completeness, Must Include misses, stale, source quality, major agencies, models/products/agents, infrastructure/chips/cloud, business/investment, legal/copyright, security, Russia и China/Asia.
4. Различать retrieval miss, editorial rejection, stale, duplicate, material update, after-cutoff и borderline.
5. Добавить запись в этот файл.
6. Не менять production-архитектуру автоматически. Повторяющийся дефект сначала должен получить отдельный контролируемый эксперимент.

---

## 2026-08-17

### Production / audit
- Опубликовано 2 сюжета: Anthropic security и Stripe/OpenRouter.
- Effective window: `2026-08-15 08:59:33 +03:00` → `2026-08-17 02:33:51 +03:00`.
- Stripe/OpenRouter был свежим.
- Anthropic оказался stale: основной AP-материал был опубликован 31 июля.
- Must Include retrieval miss: Nvidia / SB Energy / OpenAI — Reuters о переговорах по инвестиции до $3 млрд в AI-data-center проект в Огайо.

### Оценка
- Freshness: FAIL, примерно 1/2.
- Strict recall: примерно 1/2 = 50%.
- После инцидента внедрён Source Freshness Proof v1: source timestamp должен подтверждаться машинно, stale/unverified источник не должен доходить до публикации.

---

## 2026-08-18

### Production / audit
- Опубликовано 6 сюжетов: Nvidia/SB Energy/OpenAI; Gravis Robotics; Wispr; Groq; Serve Robotics/Grubhub; Alibaba/Lingxi Games.
- Freshness: PASS.
- Существенные misses: Higgsfield $400 млн; Round Hill copyright lawsuits против Anthropic/Suno; HappyShrimp launch как отдельная China product-launch blind spot, пока без независимо подтверждённого точного timestamp.
- Google A2A → Agentic AI Foundation: borderline.

### Оценка
- Completeness: PARTIAL.
- Ориентир recall: около 67% при включении HappyShrimp в расширенный reference set.
- Главная проблема смещается от freshness к recall.

---

## 2026-08-19

### Production
- Опубликовано 8 сюжетов.
- Effective window: `2026-08-17 02:35:53 +03:00` → `2026-08-19 02:35:51 +03:00`.
- Continuity anchor: `2026-08-18 02:35:53 +03:00`; первые 24 часа — healing overlap.
- Primary: 12/12; Hybrid: 4/4; Primary pool: 10; editorial выбрал 8.
- TechCrunch concentration: 6 кандидатов.

### Audit
- Freshness: PASS; Higgsfield успешно восстановлен через healing overlap.
- Must Include retrieval miss: Round Hill copyright lawsuits, второй выпуск подряд; `legal_regulation` дал 0 кандидатов.
- Velaura AI $110 млн: borderline retrieval miss.
- Google A2A: borderline.
- HappyShrimp: unresolved China product-launch blind spot.
- WSJ OpenAI Q2 вышел примерно через 11 минут после cutoff: корректный after-cutoff negative control.

### Оценка
- Completeness: PARTIAL.
- Strict recall: 8/9 ≈ 89%.
- Legal/copyright стал первым подтверждённым повторяющимся тематическим recall-дефектом.

---

## 2026-08-20

### Production / audit
- Опубликовано 7 сюжетов; Freshness: PASS.
- Cutoff: `2026-08-20 02:36:13 +03:00`.
- Must Include misses:
  - Google / Marvell — custom AI chips, warrant до $12,2 млрд, Reuters.
  - Baidu / ERNIE — AI-business earnings/strategy, Reuters; повторный Asia miss.
- Россия: MWS AI / Rubytech вошли в выпуск, zero-region проблемы нет.
- Asia: Baidu подтвердил, что blind spot шире models/integrations и включает business/earnings/strategy.

### Оценка
- Completeness: PARTIAL.
- Freshness после Source Freshness Proof v1: третий последовательный PASS.
- Healing overlap полезен, но не гарантирует recovery.

---

## 2026-08-21

### Production
- Scheduled run `32429557166`, production commit `8dc8009197148d8b0346d0804e3b1ab113d811b8`.
- Опубликовано 9 сюжетов.
- Effective window: `2026-08-19 02:36:13 +03:00` → `2026-08-21 02:40:00 +03:00`.
- Continuity anchor: `2026-08-20 02:36:13 +03:00`.
- Primary 12/12, Hybrid 4/4, общий pool после Hybrid 12, editorial выбрал 9.
- Coverage не выполнялся, потому что выпуск уже достиг количественной цели.
- TechCrunch: 7/12 pool и 5/9 final stories.

### Audit
- Freshness: PASS.
- Must Include retrieval misses:
  1. Broadcom — >$60 млрд AI-chip debt financing, Reuters.
  2. Alibaba — AI/cloud revenue +45%, AI capex +75%, Reuters/AP.
  3. Google / Marvell — повторный miss в healing overlap.
- Borderline: Brazil AI supercomputer push; Anthropic enterprise data-retention; Guidelight containment study.
- QwenCloud rolling changelog выявил pipeline false-duplicate: новый Qwen event был отброшен exact-URL dedupe из-за общего mutable changelog URL.
- Russia zero-pool независимо не подтвердился как miss.
- Нового strict legal/copyright miss в текущем окне не было.

### Оценка
- Completeness: PARTIAL.
- Strict recall: 9/12 = 75%.
- Главные повторяющиеся классы: infrastructure/business high-signal recall, Asia business/earnings, source concentration, healing failures и mutable-source exact-URL dedupe.

### Контролируемый experiment / архитектурное решение
Подробности: `automation/audits/experiments/2026-08-21-agency-asia-recall.md`.

- `major_agencies` query расширен внутри прежнего search budget до `latest AI chips infrastructure financing earnings business deals policy security`.
- `china_asia_models` оставлен без изменений.
- Второй China/Asia pass расширен до `latest China Asia AI business earnings revenue strategy cloud partnerships deployments`.
- Russia, Hybrid, Coverage и Source Freshness Proof v1 не менялись.
- От отдельного 13-го agency rescue отказались.
- Зафиксировано заранее: если после этой правки тот же класс agency Must Include miss повторится, это основание для отдельного bounded-rescue / source-ranking эксперимента.

---

## 2026-08-22

### Production
- Фактический scheduled production-run: GitHub Actions run `32537516584`, attempt 1, conclusion `success`.
- Run стартовал на commit `847f925dd33d059068d7f9ed39adcb961c9e63d1` — вчерашней правке agency/Asia recall routing.
- Production publish commit: `43f2a894e240ef3eac161aa1a0a128e21880d5d8` (`Publish AI digest for 2026-08-22`).
- Опубликованный выпуск: `ИИ-Сводка на 22 августа 2026`, `published_at=2026-08-22T06:00:00+03:00`.
- Editorial production-stage использовал уже сохранённый research artifact `automation/fixtures/research/.coverage-audit-2026-08-22.json`; новых research web-search calls в editorial-only стадии не было.
- Effective window:
  - start: `2026-08-20 02:40:00 +03:00`;
  - continuity anchor / latest archive: `2026-08-21 02:40:00 +03:00`;
  - cutoff/end: `2026-08-22 02:37:50 +03:00`;
  - healing overlap: `2026-08-20 02:40:00` → `2026-08-21 02:40:00 +03:00`;
  - main continuity: `2026-08-21 02:40:00` → `2026-08-22 02:37:50 +03:00`.

### Retrieval anatomy

#### Primary Recall v2
- Выполнены 12 фиксированных one-search проходов.
- Raw/final Primary candidate pool: 7 уникальных кандидатов.
- По обязательным направлениям persisted artifact показывает:
  - `global_breaking`: raw 3 / accepted 3;
  - `major_agencies`: 0 / 0 — GAP;
  - `models_products_agents`: 0 / 0 — GAP;
  - `infrastructure_chips_cloud`: 0 / 0 — GAP;
  - `business_investment_partnerships`: 0 / 0 — GAP;
  - `china_asia_models`: 0 / 0 — GAP;
  - `china_asia_integrations`: 1 / 1;
  - `russia`: 0 / 0 — GAP;
  - `developer_tools`: 1 / 1;
  - `security_safety`: 0 / 0 — GAP;
  - `legal_regulation`: 0 / 0 — GAP;
  - `independent_missing_events`: 2 / 2.
- Primary pool был заметно, но меньше предыдущего дня, сконцентрирован на TechCrunch: 4 из 7 кандидатов.

#### Hybrid completeness
- Отдельный Hybrid-only counter/pool не сохранён в финальном публикуемом artifact за 22 августа, поэтому число его search operations не восстанавливается предположением.
- Финальный research artifact уже является `.coverage-audit` результатом; между Primary pool и итоговым pool нет иных новых кандидатов, кроме одного явно помеченного targeted Coverage кандидата. Следовательно, Hybrid не добавил кандидата, дошедшего до финального merged pool.
- Это ограничение observability, а не основание объявлять Hybrid «не выполненным».

#### Targeted Coverage
- `research_notes` прямо фиксирует: `Targeted coverage audit добавил кандидатов: 1`.
- Добавленный кандидат — `cand-008` Tencent Zhuque Lab / DeepSeek Harness (`audit_direction=security_asia`).
- Итоговый merged pool: 8 кандидатов.

#### Editorial
Выбраны 7 из 8:
1. `cand-001` Nvidia / Cloverleaf — AI-data-center infrastructure investment.
2. `cand-003` GitHub Copilot — shared cloud-agent sessions в Teams/Slack.
3. `cand-004` NVIDIA AVO — заявленные 100% на public ARC-AGI-3.
4. `cand-005` Claude Opus 4.6 — воспроизводимый jailbreak guardrails.
5. `cand-006` Starcloud — $250 млн на orbital AI data centers.
6. `cand-002` Alibaba — AI Cloud +45%, AI capex +75%.
7. `cand-008` Tencent Zhuque Lab / DeepSeek Harness — indirect prompt-injection risk.

Редакционно исключён только `cand-007` Micro1: $500 млн gross run rate основан на анонимном источнике, компания цифру не подтвердила. Классификация: **editorial rejection**, не retrieval miss.

### Независимый аудит
Метод: assistant-side web/GitHub resources; production API пользователя не использовался.

#### Freshness
- Все 7 опубликованных сюжетов находятся внутри effective window.
- Явных stale-сюжетов не найдено.
- Claude Opus 4.6 jailbreak опубликован около `2026-08-22 02:07 +03:00`, то есть примерно за 30 минут до cutoff — корректный near-cutoff inclusion.
- Alibaba и DeepSeek Harness находятся в healing overlap и корректно не считаются stale.
- Verdict: **PASS**.
- Это пятый последовательный PASS после дефекта 17 августа (18–22 августа).

#### Положительный healing / Asia result
- Alibaba, бывшая Must Include retrieval miss 21 августа, сегодня восстановлена и опубликована.
- Независимые Reuters и AP подтверждают ключевые цифры: AI/cloud revenue +45%, capex +75%.
- Это сильный положительный сигнал после вчерашнего расширения China/Asia business/earnings semantics, хотя по persisted provenance нельзя приписать Alibaba конкретно второму Asia-pass: важно именно то, что событие дошло до итогового pool.
- В финальном выпуске также есть DeepSeek Harness security research.
- Поэтому финальный China/Asia coverage сегодня содержательно **PASS/PARTIAL**: крупный business/earnings сюжет recovered, отдельный China security сюжет включён, но `china_asia_models` route остаётся zero.

#### Явный Must Include miss
1. **Broadcom — более $60 млрд AI-chip debt financing.**
   - Reuters timestamp: `2026-08-20 20:38:49 UTC` = `23:38:49 +03:00`.
   - Событие находится внутри healing overlap.
   - Broadcom обсуждает >$60 млрд debt financing для AI-chip сделки; потенциальный общий объём структуры может доходить до ~$100 млрд, среди бенефициаров/контекста — Anthropic и другие AI-компании.
   - В production pool из 8 кандидатов события нет.
   - `major_agencies` после вчерашней query-правки снова дал raw=0/accepted=0.
   - Классификация: **retrieval miss / Must Include / healing failure / повторный agency-class defect после patch**.
   - Источник: `https://www.reuters.com/technology/broadcom-seeks-more-than-60-billion-latest-ai-debt-deal-bloomberg-news-reports-2026-08-20/`.

#### Borderline / дополнительные retrieval misses
- **Brazil AI supercomputer push**, Reuters 20 августа: 2,3 млрд реалов / $444,2 млн, Huawei/iFlytek + ожидаемая Nvidia. В healing overlap; retrieval miss, но не включён в strict denominator из-за меньшего глобального веса.
- **BIPA voice-data AI lawsuits**, Reuters 20 августа: девять крупных tech-компаний, включая Apple, Amazon, Meta, Microsoft, Nvidia и Samsung, спорят по искам о voice data для training. Это сильный legal/privacy сигнал внутри overlap, но материал представляет текущую фазу уже идущих дел, поэтому классификация **borderline retrieval miss**, а не новый strict Must Include filing.
- **US corporate AI debt surge**, Reuters 21 августа: AI-hyperscaler debt issuance достигла около $220 млрд в 2026 году; значимый business/infrastructure market analysis внутри main continuity. Классификация **borderline**, не дискретное company event.
- **Anthropic enterprise data-retention change** из окна 20 августа остаётся borderline retrieval miss, не strict denominator.
- Reuters material update о rogue AI-agent hacking attempt также находится в окне, но ядро инцидента раскрывалось раньше; классификация **material update / borderline**, не strict new event.

#### Stale / duplicate / after-cutoff controls
- Google/Marvell, Must Include miss прошлых выпусков, опубликован `2026-08-19 12:38:32 UTC`; для сегодняшнего effective start он уже **outside-window** и в denominator не входит.
- Round Hill copyright lawsuits также давно outside-window и не считаются сегодняшним miss.
- Нового false-duplicate класса mutable changelog сегодня не зафиксировано: `china_asia_models` не дал кандидатов, поэтому вчерашний QwenCloud validator defect сегодня не был повторно протестирован.
- Отдельного подтверждённого after-cutoff события, которое production ошибочно должен был включить, не обнаружено.

### Россия
- Production `russia`: raw=0 / accepted=0; региональный health-check остаётся нужен по контракту.
- Независимый поиск по текущему окну не выявил российского события уровня Must Include.
- Verdict: **zero-pool не подтверждён как retrieval defect**. Не вводить региональную quota ради самой quota.

### Major agencies
- Это главный отрицательный результат дня.
- После вчерашнего patch `major_agencies` снова завершился raw=0 / accepted=0.
- При этом в точном окне существовал Reuters Broadcom Must Include, а также несколько Reuters borderline событий.
- Следовательно, проблема уже не выглядит только как недостаток query semantics: сохраняется **source-pool/ranking/retrieval instability**.
- AP Alibaba всё же дошла до финального выпуска через общий pipeline, поэтому source diversity финального выпуска лучше вчерашней, но dedicated agency route остаётся функционально слабым.

### Source concentration
- Primary: TechCrunch 4/7 кандидатов.
- Final: TechCrunch 3/7 сюжетов.
- Это заметное улучшение относительно 21 августа (7/12 pool, 5/9 final), но концентрация всё ещё требует наблюдения.

### Оценка
- **Freshness: PASS.**
- **Completeness: PARTIAL.**
- Консервативный strict reference set: 8 событий = 7 опубликованных + 1 independently verified Must Include miss (Broadcom).
- Ориентировочный **strict recall: 7/8 = 87,5%**.
- Borderline Brazil/BIPA/AI-debt/Anthropic retention/security material-update в strict denominator не включены.
- По сравнению с 21 августа strict recall улучшился примерно с 75% до 87,5% главным образом потому, что Alibaba была восстановлена, а Google/Marvell вышел из текущего окна. Однако повторный Broadcom miss не позволяет считать recall проблему решённой.

### Повторяющиеся паттерны после шести дней
1. **Freshness стабилизирована.** Пять PASS подряд после 17 августа; Source Freshness Proof v1 не трогать.
2. **Infrastructure/business high-signal recall остаётся системным риском.** Broadcom пережил вчерашний semantic patch и не был healed.
3. **Major-agency route остаётся слабым.** Новый query сам по себе не устранил raw=0 в production.
4. **Asia business/earnings показывает улучшение.** Alibaba recovered; это позитивный сигнал для вчерашней правки, но нужно подтверждать следующими днями.
5. **Healing overlap работает выборочно.** Alibaba recovered, Broadcom — нет.
6. **Legal route zero остаётся наблюдаемым**, но сегодня новый строгий legal/copyright miss не доказан; BIPA — borderline.
7. **Security coverage содержательно хороша несмотря на zero dedicated route:** Claude jailbreak + DeepSeek Harness вошли через другие направления.
8. **Models/products/agents coverage также содержательно присутствует:** GitHub Copilot и NVIDIA AVO вошли, хотя dedicated route был zero. Нулевой отдельный pass не равен нулевой итоговой теме.
9. **Mutable changelog dedupe** остаётся известным отдельным validator defect, но сегодня новых данных по нему нет.

### Архитектурное решение
- **Да, основания для отдельного архитектурного эксперимента теперь есть и они стали сильнее.**
- Причина: вчерашний журнал заранее установил критерий — если после расширения `major_agencies` тот же agency-class Must Include miss повторится, запускать отдельный bounded-rescue/source-ranking experiment. Broadcom сегодня именно такой повтор.
- Эксперимент должен быть узким и не менять production автоматически:
  1. воспроизвести updated `major_agencies` route на сохранённых окнах 20–22 августа и проверить, почему Reuters Broadcom не попадает даже в raw pool;
  2. сравнить source-domain routing/ranking с bounded Reuters/AP rescue без увеличения общего информационного шума;
  3. проверить quality/gap trigger: должен ли raw=0 у major agencies запускать bounded rescue даже когда общий story count уже достаточный;
  4. отдельно не смешивать этот эксперимент с Asia semantics, потому что Alibaba сегодня recovered;
  5. Source Freshness Proof v1 не менять.
- Production retrieval-код в рамках ежедневного аудита **не изменён**.

## Текущая серия наблюдений

| Дата | Freshness | Completeness | Strict recall / ключевой результат |
|---|---|---|---|
| 2026-08-17 | FAIL | FAIL | ~50%; stale Anthropic + Nvidia/SB Energy miss |
| 2026-08-18 | PASS | PARTIAL | ~67% extended; Higgsfield/Round Hill/China blind spot |
| 2026-08-19 | PASS | PARTIAL | ~89%; Higgsfield healed, Round Hill repeated |
| 2026-08-20 | PASS | PARTIAL | Google/Marvell + Baidu misses |
| 2026-08-21 | PASS | PARTIAL | 75%; Broadcom + Alibaba + Google/Marvell; false duplicate QwenCloud |
| 2026-08-22 | PASS | PARTIAL | 87,5%; Alibaba healed, Broadcom repeated after agency patch |

## Что наблюдать дальше

- Broadcom/agency-class recovery и любые новые Reuters/AP high-signal events после query patch.
- Стабильность China/Asia business/earnings после восстановления Alibaba.
- Russia zero-pool: считать дефектом только при независимо подтверждённом Must Include miss.
- Legal/privacy: проверить, станет ли BIPA-подобный класс повторяющимся strict miss или останется borderline.
- Source concentration и корреляцию с agency misses.
- Mutable changelog dedupe отдельной экспериментальной линией.
- Source Freshness Proof v1 оставить без изменений, пока stale-дефект не повторится.
