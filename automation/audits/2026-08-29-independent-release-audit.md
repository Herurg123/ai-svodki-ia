# Независимый аудит выпуска ИИ-Сводки за 2026-08-29

## Статус

**Вердикт: FAIL по freshness и completeness; PASS по механике публикации, лимитам и at-most-once recovery.**

Этот аудит относится к успешно опубликованному выпуску 2026-08-29 и не меняет production-поведение. Он фиксирует результаты post-production проверки и формулирует отдельные bounded experiments для следующих изменений.

## Объект проверки

- Production workflow run: `33231413963` (`Daily production digest`, `workflow_dispatch`, success).
- Код production-run: `ccacc65ee24a2a1159985c9a26b45bdb08002f6f`.
- Recovery source run: `33228526922`.
- Успешный artifact: `daily-production-2026-08-29`, artifact ID `9708618496`.
- Digest artifact SHA-256: `b44c096424badb504e9e04be83db589f98cd80699ad4125cbedc051f0b6fe4e0`.
- Publish commit: `bacaa0fb37742dd189e226fa6e64db83b4a679a5`.
- Effective research window: `2026-08-27T04:43:51+03:00` → `2026-08-29T05:16:40+03:00`.
- Последний предыдущий research cutoff: `2026-08-28T04:43:51+03:00`.

Успешный run переиспользовал paid artifact предыдущего падения. `Run full research and editorial` был skipped; Coverage quality была завершена путём детерминированной переклассификации сохранённого результата. Сравнение response IDs всех семи Coverage attempts между failed artifact и successful artifact показывает полное совпадение, то есть новые Coverage Web Search operations при recovery не выполнялись.

## Метод независимого сравнения

Проверка выполнена без production API пользователя. Использованы:

1. сохранённые artifacts run `33228526922` и `33231413963`;
2. код на production SHA и publish commit через GitHub API;
3. обычный assistant web search по независимым первоисточникам и крупным СМИ;
4. отдельная сверка event date с source publication date для каждого опубликованного сюжета.

Standalone Terra в текущей среде чата не предоставлена, поэтому независимое сравнение ниже является assistant web comparison, а не Terra A/B. Production API пользователя не расходовался.

## Итог выпуска

Editorial выбрала 6 сюжетов из 8 кандидатов:

| ID | Сюжет | Machine geography | Production freshness |
|---|---|---:|---|
| `cand-001` | Salesforce + Anthropic / Claudeforce | world | `new_event` |
| `cand-004` | Суд отменил supply-chain risk designation Anthropic | world | `new_event` |
| `cand-005` | Anthropic Automated Alignment Researcher | world | `new_event` |
| `cand-006` | Lambda привлекла $1 млрд долга под Nvidia GPU / Microsoft | world | `new_event` |
| `cand-008` | Gemini Enterprise for Legal / Financial Services | world | `new_event` |
| `cand-003` | Z.ai GLM-5.3-Flash | world | `new_event` |

Все шесть stories машинно классифицированы как `world`; отдельной geography `china` в финальном stories нет. Поэтому текущая региональная observability уже на выходе не умеет прямо ответить на вопрос «сколько китайских сюжетов реально попало в выпуск».

## Freshness: опубликованный source ≠ новое событие

Source Freshness Proof v1 подтвердил timestamp выбранной публикации, но как минимум в трёх случаях свежая вторичная страница описывала более старое событие. Это позволяет старому событию получить `freshness_status=new_event`.

### 1. GLM-5.3-Flash — FAIL, outside window

Production:
- primary source: ChinaAPI timeline;
- `published_date=2026-08-28`;
- `freshness_status=new_event`;
- в production verification релиз отнесён к 27 августа.

Независимая проверка:
- официальный Z.ai release датирован **2026-08-26**;
- независимые публикации также связывают формальный релиз с 26–27 августа, при этом официальный model post остаётся датирован 26 августа.

Sources:
- https://z.ai/blog/glm-5.3-flash
- https://www.scmp.com/tech/big-tech/article/3365433/zhipu-ai-shares-jump-viral-ox-alpha-model-revealed-glm-53-flash-chinese-chips

Effective window начинается только 27 августа в 04:43:51 МСК. Событие GLM-5.3-Flash произошло до окна. **Опубликованный единственный китайский сюжет не является валидным in-window China event.**

### 2. Gemini Enterprise for Legal / Financial Services — FAIL, old reprint

Production:
- primary source: TechRadar, опубликован 27 августа 23:25 UTC;
- `freshness_status=new_event`.

Независимые первоисточники Google Cloud:
- Legal launch: **2026-08-25**;
- Financial Services launch: **2026-08-25**.

Sources:
- https://cloud.google.com/blog/products/ai-machine-learning/introducing-gemini-enterprise-for-legal
- https://cloud.google.com/blog/products/ai-machine-learning/introducing-gemini-enterprise-for-financial-services

Это событие более чем на сутки старше начала effective window. TechRadar оказался свежей вторичной публикацией старого запуска.

### 3. Claudeforce — FAIL, event before window

Production:
- primary source: TechRadar, `2026-08-27T08:57:33Z`;
- `freshness_status=new_event`.

Независимая проверка:
- Salesforce/Business Wire объявили Claudeforce 26 августа;
- Nasdaq/Business Wire фиксирует timestamp **2026-08-26 16:21 EDT = 20:21 UTC**;
- Effective window начинается **2026-08-27 01:43:51 UTC**.

Sources:
- https://www.salesforce.com/news/press-releases/2026/08/26/salesforce-and-anthropic-announce-claudeforce/
- https://www.nasdaq.com/press-release/salesforce-and-anthropic-announce-claudeforce-1-ai-meets-1-ai-crm-2026-08-26

Событие произошло примерно за 5 ч 23 мин до effective window. Это ещё один случай, когда свежесть вторичной статьи была ошибочно приравнена к свежести события.

### Freshness verdict

Три остальных выбранных сюжета имеют независимое событие внутри окна:
- Anthropic court ruling — 27/28 августа;
- Anthropic alignment research — официальный материал 28 августа;
- Lambda debt — публикация 28 августа.

Следовательно, на независимой event-level проверке:
- **source-page freshness: production считает 6/6 PASS;**
- **event freshness: 3/6 PASS, 3/6 FAIL.**

Это отдельный structural defect: Source Freshness Proof сейчас надёжнее доказывает «страница опубликована в окне», чем «самостоятельное событие произошло в окне».

## Независимые свежие контроли, которых нет в выпуске

### Россия, strict control 1: Яндекс Сим

Официальный Яндекс, 28 августа:
- анонсирован виртуальный мобильный оператор «Яндекс Сим»;
- ИИ встроен в саму связь: расшифровка разговоров, создание напоминаний/событий/контактов, антифрод;
- CNews даёт точный timestamp `28.08.2026 10:35`.

Sources:
- https://yandex.ru/company/news/28-08-2026-01
- https://www.cnews.ru/news/line/2026-08-28_ii-pomoshchnik_yandeksa_vstroitsya

**Классификация: strict Must Include / Россия / AI product + telecom + security.**

Production anatomy:
- Primary `russia`: raw=0, accepted=0;
- Source Pulse **нашёл ровно этот lead**, но promotion отверг его с `source_freshness_no_publication_date`;
- Hybrid Russia adaptive pass: 0;
- Coverage: не восстановил.

Это не чистый discovery miss: Pulse discovery сработал, но доказательство свежести не смогло извлечь дату с Yandex IR URL, несмотря на то что официальный Yandex company-news surface явно содержит дату 28 августа.

### Россия, strict control 2: предложение Альянса в сфере ИИ по copyright/training data

28 августа российские разработчики, включая Сбер, Яндекс, VK, МТС и других участников Альянса в сфере ИИ, публично вынесли новую позицию по правилам обучения моделей на открытых или законно полученных произведениях. Письмо датировано 27 августа и направлено в Госдуму.

Sources:
- https://frankmedia.ru/301951
- https://pravo.ru/news/265552/
- https://mfd.ru/news/view/?companyId=6&id=2783493

**Классификация: strict Must Include / Россия / AI policy + copyright + training data.**

Production anatomy:
- Primary Russia не нашёл;
- Source Pulse не дал lead;
- Hybrid Russia query прямо содержит `регулирование`, но вернул 0;
- Coverage legal/copyright использовал англоязычный global query и также не нашёл событие.

### Китай, strict control: Tencent Hy4 preview

28 августа Tencent официально выпустила и открыла Hy4 preview:
- 770B total / 49B active parameters;
- context >1M;
- coding, office work, scientific research;
- open-source weights;
- Reuters опубликовал материал 28 августа.

Sources:
- https://www.tencent.com/tencent-releases-and-open-sources-tencent-hy4-preview/
- https://www.reuters.com/world/asia-pacific/chinas-tencent-releases-new-open-source-ai-model-coding-research-tasks-2026-08-28/

**Классификация: strict Must Include / China / model release.**

Production anatomy:
- Primary `china_asia_models` query: `latest China Asia AI model releases agents open source`;
- этот exact-purpose route нашёл GLM и Qwen, но не Hy4;
- `major_agencies` не нашёл свежий Reuters;
- Hybrid broad model search не восстановил;
- отдельный China/Asia adaptive Hybrid pass **не запускался**, потому что Primary уже имел 2 accepted Asia candidates;
- Coverage `security_asia` является security-route, а не общим China model recall, поэтому тоже не восстановил.

С учётом того, что GLM оказался outside-window, финальный выпуск фактически имеет **0 валидных in-window China events**, хотя визуально содержит один китайский сюжет.

### Global recovery control: a16z Machine Age $1.1B — найден, но потерян при recovery

Coverage `general_coverage_gaps` уже в failed artifact нашёл:
- a16z Machine Age Fund;
- $1.1 млрд;
- `recommendation=include`;
- `verification_status=verified`;
- `freshness_status=new_event`;
- `candidate_count=1`.

Независимые sources:
- https://a16z.com/the-machine-age-fund/
- https://techcrunch.com/2026/08/28/a16z-creates-a-1-1b-machine-age-fund-to-accelerate-the-physical-buildout-of-ai/

Однако успешный recovery report имеет:
- `audit_added_candidates=0`;
- `accepted_candidates=[]`;
- `editorial_rerun_required=false`;
- candidate pool до/после = 6;
- финальный digest остаётся из 6 сюжетов.

Это **не retrieval miss**. Это deterministic recovery candidate-replay defect.

Код подтверждает механизм:
1. v8 `execute_audit_plan()` умеет восстанавливать top-level `candidates` из сохранённых checked direction records.
2. текущий Retrieval Quality wrapper в `_prepare_prior_for_quality()` успешно переклассифицирует сохранённый seventh-slot result.
3. после этого `execute_audit_plan()` возвращает `prepared` немедленно, если quality уже complete.
4. исходный failed top-level report не содержит top-level `candidates`, хотя candidate лежит внутри `attempts/directions`.
5. policy main получает `audit_plan.get("candidates", [])`, получает пустой массив и не запускает merge/editorial rerun.

Дополнительное подтверждение: response IDs всех 7 Coverage attempts в failed и successful artifact идентичны, значит recovery корректно не тратил новый поиск, но не восстановил уже найденный кандидат.

## Почему Россия снова пустая

### Primary

`russia`:
- query: `последние новости ИИ Яндекс Сбер VK МТС российский рынок`;
- raw=0;
- accepted=0;
- выдача была заполнена главным образом старыми/агрегаторными страницами;
- Яндекс Сим и письмо Альянса не попали в retrieval result.

### Source Pulse v1.2

Механически слой работает:
- 13 configured sources;
- 10 `ok`;
- 3 unavailable;
- 10 leads;
- 9 eligible new leads;
- 0 OpenAI calls / 0 Web Search.

Для России он действительно улучшил discovery:
- Yandex IR был опрошен;
- lead «28 августа 2026 ИИ-помощник Яндекса встроится в мобильную связь» найден.

Но promotion fail-closed отверг **все восемь Yandex leads** как `source_freshness_no_publication_date`.

При этом snapshot имеет отдельный parser anomaly: заголовки явно содержат даты 18/20/21/24/26/28 августа, но snapshot присвоил всем `published_date=2026-08-28`. Promotion не доверился этой сомнительной дате и повторно проверил direct page, что безопасно для precision, но привело к false-negative настоящего события 28 августа.

TASS AI source в этом run был unavailable, CNews остаётся Tier-B lead-only.

**Вывод: Pulse не бесполезен. Он нашёл нужный российский сюжет, но не смог провести его через freshness proof.**

### Hybrid

Russia health был красным после Primary, поэтому Hybrid запустил отдельный adaptive pass:

`последние новости ИИ Россия модели продукты агенты инвестиции облако инфраструктура кибербезопасность регулирование`

Результат: 0 candidates. Механика сработала, practical recovery — нет.

### Coverage

Coverage выполнил 7/7 search operations, но его региональные направления не являются общим региональным safety net:
- Russia route = **security Russia**;
- Asia route = **security Asia**;
- legal/copyright route = global English query;
- general route = global broad.

Поэтому отсутствие любой российской product/policy/business новости не гарантирует дополнительный специально российский Coverage search.

### Россия: targeted recall

На двух высокоуверенных независимых in-window controls:
- Яндекс Сим: MISS;
- AI Alliance copyright/training policy: MISS.

**Targeted Russia recall = 0/2.**

Это диагностическая контрольная выборка, не оценка полного множества всех российских ИИ-новостей.

## Почему по Китаю финально одна новость, а фактически валидных ноль

Primary regional health является **binary upstream health**, а не контролем итогового состава:
- `china_asia_models` + `china_asia_integrations` дали 2 accepted candidates;
- поэтому `asia.health_check_needed=false`;
- один кандидат затем был исключён;
- второй (GLM) прошёл редактуру, но независимый event-date audit показывает, что он outside window.

Hybrid запускает отдельный regional query только для регионов, у которых Primary дал **zero**. Он не пересчитывает Asia health после Source Freshness/selection и не знает, что final eligible China pool фактически схлопнулся.

Conditional fifth Hybrid call запускается только когда **одновременно** открыты Russia и Asia zero-gaps. В этом run открыт был только Russia gap, поэтому:
- Hybrid = 4/4;
- fifth call не использован;
- dedicated China adaptive query не было.

Одновременно Source Pulse China имел слабую доступность:
- `baidu_ir` unavailable;
- `xpeng_ir` unavailable;
- несколько China sources помечены degraded;
- полезного China lead для Hy4 не возникло.

И наконец Primary `major_agencies` и Reuters-only rescue снова не спасли ситуацию:
- `major_agencies` вместо свежего Reuters вернул старые Bloomberg/AP pages;
- Reuters-only rescue v4: `consulted_sources=[]`, raw=0, accepted=0;
- при этом свежий Reuters Tencent Hy4 объективно существовал внутри окна.

**China verdict: practical regional recall FAIL.**

## Второй слой проверок: помогает ли он

Короткий ответ: **частично помогает, но сегодня доказанно недостаточен.**

Это не один fallback, а несколько независимых слоёв:

| Слой | Запустился | Что сделал | Почему не спас |
|---|---:|---|---|
| Source Pulse | да | нашёл Яндекс Сим | freshness promotion false-negative |
| Agency rescue | да, сохранённый | Reuters-only search | `consulted_sources=[]` |
| Hybrid Russia | да | отдельный широкий Russia query | 0 candidates |
| Hybrid China | нет | не требовался по binary health | 2 upstream Asia candidates закрыли gap |
| Coverage | да, 7/7 | нашёл a16z и проверил обязательные beats | regional breadth ограничен; a16z потерян при recovery replay |

То есть «второй слой не работает» было бы слишком грубо. Он **работает механически**, но сегодня обнаружены сразу четыре независимых practical failure modes:
1. источник найден, но freshness extractor блокирует его;
2. search route выполняется, но retrieval/source pool не даёт существующий материал;
3. regional health закрывается слишком рано по upstream candidate count;
4. saved Coverage candidate теряется при recovery.

## Agency/source routing

Recurring symptom снова подтверждён out-of-sample:
- Primary `major_agencies` разрешал Reuters/AP/Bloomberg/FT;
- фактически получил старые Bloomberg/AP материалы;
- свежих Reuters/FT control pages не дал;
- Reuters-only rescue v4 выполнил one-search contract с `search_context_size=high`, но получил `consulted_sources=[]`.

Tencent Hy4 даёт свежий независимый Reuters control ровно на этот день. Поэтому это уже нельзя объяснить отсутствием новостей или только wording query. **Provider/source-pool routing остаётся практическим blind spot.**

## Search budget / recovery / publication mechanics

PASS:
- Primary: 12/12;
- agency discovery rescue: 1 saved operation;
- Hybrid: 4/4;
- Coverage: 7/7;
- Source Pulse: 0 paid calls / 0 Web Search;
- lineage total = 24 Web Search operations;
- conditional fifth Hybrid call не использован;
- recovery не повторил сохранённые paid retrieval operations;
- cover был создан один раз после успешного Coverage;
- публикация, commit и deploy завершились успешно.

At-most-once recovery после PR #113 выдержан. Новый найденный defect относится не к повторному расходу, а к **неполной материализации сохранённого Coverage candidate**.

## Консервативные метрики этого аудита

Это targeted diagnostic sample, а не полный census новостей.

- Published story event freshness: **3/6 = 50% PASS**.
- Hard stale/old-event selected stories: **3/6 = 50% FAIL**.
- Russia strict controls: **0/2**.
- China strict in-window control Tencent Hy4: **0/1**.
- Saved Coverage candidate replay: **0/1 promoted**.
- Paid search/recovery budget integrity: **PASS**.

Near-cutoff Reuters OpenAI/Cursor report от 29 августа 02:01 UTC также находится внутри formal cutoff `02:16:40 UTC`, но отделён от cutoff только примерно 16 минутами. Он фиксируется как **latency-sensitive control**, а не используется для обвинения архитектуры в обычном recall miss.

## Приоритеты следующих bounded experiments

Этот аудит **не вносит production patch автоматически**.

### P0 — Coverage recovery candidate replay

Нужен deterministic offline regression на реальном artifact `33228526922`:
- saved mandatory attempt содержит fresh verified candidate;
- saved quality resolution reclassified without search;
- candidate должен быть reconstructed из `directions/attempts`;
- merge/editorial rerun должен произойти ровно один раз;
- Web Search operations после recovery = 0;
- negative control: no candidate stays no-op.

Это отдельный correctness bug, не tuning search.

### P1 — event-age freshness, не только source-page freshness

Контролы:
- negative: GLM-5.3-Flash, Google Gemini Legal/Finance, Claudeforce;
- positive: Anthropic alignment, Lambda, Anthropic court ruling;
- boundary negatives/positives вокруг exact cutoff.

Цель: свежая перепечатка не должна превращать старый event в `new_event`. Ослаблять current fail-closed proof нельзя; нужен отдельный event-origin check.

### P1 — Yandex IR / Source Pulse date extraction

Контролы:
- 18/20/21/24/26/28 августа на одной Yandex IR listing;
- direct Yandex company-news page;
- Яндекс Сим как positive;
- старые 18–26 августа как negatives.

Цель: не присваивать всем sibling items одну page-wide дату и при этом уметь доказать direct publication date для настоящего 28 августа.

### P1 — provider/source-routing health

Повторяемый pattern:
`fresh Reuters strict control exists → major_agencies misses → Reuters-only rescue consulted_sources=[]`.

Следующий experiment должен исследовать provider/source routing/health, а не ещё раз менять wording или context-size.

### P2 — regional health после фильтрации

Текущий health-check строится по accepted Primary candidates и не пересчитывается после:
- freshness rejection;
- selection;
- independent event-age invalidation.

Нужен offline state-machine experiment: regional health должен опираться на **surviving eligible regional pool**, но не превращаться в publication quota.

### P2 — региональная breadth Coverage

Сегодняшние mandatory regional Coverage beats проверяют security, а не общий Russia/China recall. Любой дополнительный paid regional Coverage search меняет budget contract и требует отдельного experiment/разрешения; автоматически не добавлять.

## Финальный verdict

**FAIL.**

Успешная публикация доказала, что recovery после PR #113 больше не падает на bounded-unverified resolution и не повторяет paid retrieval. Но содержательно сегодняшний выпуск выявил три более глубоких дефекта:

1. **event freshness regression:** 3 из 6 выбранных сюжетов относятся к событиям до effective window;
2. **regional recall failure:** два сильных российских события и Tencent Hy4 не дошли до выпуска;
3. **Coverage recovery replay bug:** свежий verified a16z candidate был найден и сохранён, но потерян при recovery.

По вопросу второго слоя ответ однозначный: его наличие полезно и уже даёт диагностические сигналы, но **он пока не является надёжной страховкой полноты**. Сегодня Pulse нашёл один нужный российский сюжет, Hybrid честно проверил Russia gap, Coverage честно выполнил 7/7 и даже нашёл дополнительную новость, однако downstream contracts не позволили этим усилиям превратиться в более полный и более свежий выпуск.
