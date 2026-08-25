# Source Pulse v0 — недельный architecture/retrieval bake-off

Дата эксперимента: 2026-08-25  
Статус: research-only, production behavior не меняется  
Период эталона: 2026-08-19 → 2026-08-25  
Production API пользователя: **не использовался**

## Зачем этот эксперимент

Независимые аудиты последней недели показывают повторяющийся класс ошибок:
крупное и свежее событие существует, но Web Search route либо вообще не видит
его, либо получает stale/пустой source pool. Особенно болезненно это проявляется
в Китае/Азии, России, agency/business и infrastructure.

Цель этого bake-off — проверить не ещё одну формулировку Web Search query, а
другую архитектурную гипотезу: может ли отдельный **Source Pulse** из
фиксированных официальных newsroom/IR/release/index источников и нескольких
авторитетных региональных lead-only источников обнаруживать события, которые
текущий search-ranking пропускает.

Это не попытка заменить Primary Recall. Гипотеза именно о независимом втором
канале discovery.

## Важное ограничение метода

В текущем чате нет отдельного интерактивного Terra-инструмента с тем же
provider/runtime contract, что production. Поэтому эксперимент является
**assistant-side fixed-source / source-aware replay**, а не pure Terra A/B.
Production OpenAI API и бюджет пользователя не использовались.

Исторические verdict/recall из канонического журнала не пересчитываются задним
числом. Для сравнения берутся уже зафиксированные strict Must Include misses и
отдельно отмеченные high-signal/borderline controls.

## Architecture-wide audit до эксперимента

### Что в текущей архитектуре нельзя ломать

Текущий production contract сохраняет:

- 12 обязательных Primary Recall v2 Web Search operations;
- отдельные `china_asia_models`, `china_asia_integrations` и `russia` routes;
- bounded `agency_discovery_rescue`;
- Hybrid и Coverage;
- общий потолок **24 Web Search search operations**;
- effective discovery window с bounded healing overlap;
- Source Freshness Proof fail-closed;
- archive URL dedupe + semantic/same-event dedupe;
- отсутствие региональных квот;
- recovery без повторного оплаченного research.

Source Pulse безопасен только если является дополнительным sidecar и не
переписывает эти гарантии.

### Архитектурные риски второго канала

1. **Source outage / anti-bot.** Официальный feed может вернуть 403/5xx или
   исчезнуть. Pulse не должен делать весь выпуск красным.
2. **Mutable indexes/changelogs.** Один URL может постоянно меняться; URL-only
   dedupe недостаточен.
3. **Noise explosion.** Newsroom/IR могут выдавать десятки мелких PR. Нельзя
   проталкивать их напрямую в editorial.
4. **Regional quota by accident.** Сам факт наличия China/Russia lead не даёт
   права на публикацию.
5. **Freshness bypass.** Дата в RSS/index — lead evidence, но не должна отменять
   обычную Source Freshness Proof.
6. **Recovery drift.** Если recovery повторно опрашивает mutable page, результат
   может отличаться от исходного research run.
7. **Primary crowd-out.** Если сырые Pulse leads подмешать в каждый Primary pass,
   они могут занять per-pass candidate cap и ухудшить независимый Web Search.
8. **Hidden search-budget growth.** HTTP polling не является OpenAI Web Search и
   не должен маскировать увеличение Web Search ceiling сверх 24.
9. **Security/SSRF.** Source registry должен быть фиксированным HTTPS allowlist;
   fetched links обязаны проходить те же public-network safety checks.

### Безопасный production contour

Если гипотеза подтвердится, архитектурно безопасный вариант такой:

1. **Source Pulse fetch/snapshot** выполняется до или параллельно Primary и пока
   ничего не меняет в candidate pool.
2. Primary 12/12 работает без изменений.
3. `major_agencies` health и agency rescue trigger остаются независимыми от Pulse;
   Pulse не имеет права скрыть `major_agencies raw=0/accepted=0`.
4. После Primary/rescue Pulse leads дедуплицируются против уже найденных событий.
5. Только unmatched leads проходят отдельную bounded triage-стадию. Для будущего
   production допустим максимум один no-Web-Search model call на ограниченный
   набор leads; это отдельная стоимость и требует явного разрешения до включения.
6. Принятые candidates объединяются с обычным pool **до Hybrid**.
7. Далее без изменений: freshness proof → archive/semantic dedupe → editorial →
   Hybrid/Coverage/recovery.
8. Каждый источник fail-open: его недоступность записывается в diagnostics, но
   старый pipeline продолжает работать.
9. Snapshot `source-pulse.json` сохраняется в artifact и повторно используется
   при same-day recovery; mutable sources автоматически не перепрашиваются.

**Не рекомендовано:** raw injection Pulse leads внутрь 12 Primary passes. Это
смешивает причинность эксперимента и может ухудшить recall через per-pass caps.

## Source Pulse v0 — фиксированный набор источников

Это не production whitelist и не исчерпывающий каталог. Он нужен для
проверяемого bake-off.

### Tier A — official / newsroom / IR / release

- Baidu Investor Relations — `https://ir.baidu.com/`
- Alibaba Group HKEX / IR — `https://www.alibabagroup.com/en-US/ir-filings-hkex`
- Alibaba Cloud Blog — `https://www.alibabacloud.com/blog`
- Marvell Current Reports — `https://investor.marvell.com/sec-filings/current-reports`
- NVIDIA Recent News — `https://blogs.nvidia.com/recent-news/`
- Yandex IR press releases — `https://ir.yandex.ru/press-releases?year=2026`
- XPENG IR / RSS discovery — `https://ir.xiaopeng.com/rss-feeds`
- fabricaONE.AI investor/news pages
- DeepSeek official docs/changelog/model inventory where available

### Tier B — lead-only regional sources

- IT之家 / ITHome — China tech/product discovery
- CNews — Russia enterprise/AI discovery

Tier B даёт только **lead**. Он не повышает significance и не обязан быть
финальным primary source: событие затем должно получить обычное официальное или
авторитетное corroboration.

### Source-health findings уже на этапе bake-off

- XPENG публично advertises RSS, но прямой replay RSS endpoint вернул HTTP 403.
  Значит source registry обязан поддерживать HTML/index fallback и per-source
  health diagnostics; нельзя строить архитектуру на предположении «RSS всегда
  работает».
- DeepSeek changelog/index оказался неполным/запаздывающим для исторического
  Vision-control. Поэтому официальный changelog не может быть единственным
  источником discovery; региональный lead + official corroboration полезнее.

## Эталон: исторические miss-day instances

Для эксперимента используются только уже известные из канонического журнала
пропуски. Повтор одного события в healing overlap считается отдельным miss-day,
потому что это отдельный шанс архитектуры его восстановить.

| Дата | Canonical strict misses, используемые в bake-off |
|---|---|
| 19 авг | Round Hill copyright |
| 20 авг | Google/Marvell; Baidu/ERNIE AI-business |
| 21 авг | Broadcom >$60B AI debt; Alibaba AI/cloud earnings; повтор Google/Marvell |
| 22 авг | повтор Broadcom |
| 23 авг | Nvidia AI-server price hikes; DeepSeek V4-Flash-Vision-Exp |
| 24 авг | Alibaba HK$80B / $10.2B AI placement |
| 25 авг | Alibaba Wan3.0; XPENG robotics funding; NVIDIA Groq 3 LPX |

Итого: **13 strict miss-day instances**.

Baidu на 19 августа отдельно помечен как `high_signal_historical`: последующий
журнал говорит, что сюжет уже был отмечен как Asia miss, но исходная canonical
strict recall 8/9 за 19 августа его в denominator не включала. Мы не переписываем
эту старую метрику.

## Результат Source Pulse v0

### Strict miss-day recovery

Source Pulse v0 дал обнаружимый lead для **9 из 13** strict miss-day instances:

- Google/Marvell — hit;
- Baidu — hit;
- Alibaba earnings — hit;
- повтор Google/Marvell — hit;
- DeepSeek Vision — hit через regional lead;
- Alibaba placement — hit через official source;
- Wan3.0 — hit через regional/current product lead с material-update distinction;
- XPENG robotics financing — hit;
- NVIDIA Groq 3 LPX — hit.

Не восстановлены:

- Round Hill copyright lawsuit;
- Broadcom private debt financing (оба miss-day);
- Nvidia server price hikes.

Итого: **9/13 = 69.2%** strict miss-day recovery.

Если добавить Baidu Aug19 как отдельно сохранённый historical high-signal
control, получается **10/14 = 71.4%**.

По уникальным strict missed events: **8/11 = 72.7%**.

Это не новый общий recall проекта. Это доля уже известных исторических misses,
для которых второй fixed-source/source-aware канал дал lead.

## По дням: что изменилось бы

| День | Published | Что Source Pulse дополнительно обнаруживает | Что всё ещё не находит | Оценка относительно текущего retrieval |
|---|---:|---|---|---|
| 19 авг | 8 | Baidu как historical high-signal; дополнительно HappyShrimp beta, MWS AI cost, VK AI Space как Consider leads | Round Hill strict | **Лучше региональный lead coverage**, strict canonical miss не вылечен |
| 20 авг | 7 | Google/Marvell + Baidu — оба strict misses | — из strict набора дня | **Сильно лучше: 2/2 strict recovered as leads** |
| 21 авг | 9 | Alibaba earnings + повтор Google/Marvell; CNews/Yandex ecosystem Consider leads | Broadcom debt | **Лучше: 2/3 strict miss-day leads** |
| 22 авг | 7 | Нового strict recovery нет | Broadcom debt | **Нейтрально**; хороший negative control против искусственной региональной квоты |
| 23 авг | 4 | DeepSeek Vision; fabricaONE.AI как borderline Russia lead | Nvidia server pricing | **Лучше: 1/2 strict + полезный Russia borderline lead** |
| 24 авг | 1 | Alibaba $10.2B placement через official IR/HKEX | — из strict набора дня | **Сильно лучше: false-zero agency miss получает независимый lead** |
| 25 авг | 3 | Wan3.0 + XPENG robotics + NVIDIA Groq 3 LPX; Sber anti-phishing как Consider; Yandex official-source redundancy | — из 3 strict controls | **Сильно лучше: 3/3 strict controls recovered as leads** |

## Конкретные positive controls

### Baidu / ERNIE

Официальный Baidu IR подтверждает Q2 AI-business события: AI-powered Business
12.5 млрд юаней, +25% г/г; AI Cloud Infrastructure 7.3 млрд, +50%; GPU Cloud
+283%. Это именно тип Asia business/earnings/strategy, который broad route уже
пропускал.

### Google / Marvell

Marvell Current Reports / 8-K даёт прямой официальный lead по Google custom
semiconductor programs, включая AI inference accelerators и warrant на
58,970,907 акций. Это сильный пример того, что SEC/IR index способен дать lead
независимо от search ranking.

### Alibaba earnings / AI capex

Alibaba official materials содержат рост AI-related cloud demand, Cloud
Intelligence revenue и крупный AI/infrastructure capex. Это подтверждает, что
официальный investor/news channel лечит часть Asia business blind spot.

### Alibaba placement

Официальный Alibaba/HKEX source подтверждает HK$80 млрд placement и направление
100% net proceeds на full-stack AI, включая chips, infrastructure, model
training/deployment. Это out-of-band lead для того же события, которое Reuters
route в production не поднял.

### DeepSeek V4-Flash-Vision-Exp

Regional China-tech lead фиксирует релиз 21 августа и ведёт к официальному
DeepSeek context/model inventory. Важный guardrail: официальный changelog alone
оказался недостаточно надёжным как discovery index, поэтому Tier-B lead здесь
реально добавляет независимость.

### Wan3.0

Regional lead фиксирует full launch 24 августа, при этом более ранний August beta
позволяет классифицировать это как material new launch/update, а не спутать с
старой страницей. Это именно класс model/product discovery, который production
25 августа не поднял.

### XPENG robotics

Официальные XPENG materials и локальные China-tech источники поднимают первый
раунд >$900 млн для robotics/embodied AI. RSS endpoint оказался 403 в replay, но
HTML/IR fallback сохраняет discoverability. Это аргумент за multi-format source
adapter, а не за «RSS-only».

### NVIDIA Groq 3 LPX

NVIDIA Recent News ведёт к официальному full-production announcement и Nebius
adoption. Это прямой infrastructure lead для strict miss 25 августа.

## Что Source Pulse v0 не лечит

Три уникальных high-signal класса остаются:

1. Round Hill copyright lawsuit — legal/news-agency event без полезного
   participant newsroom pulse.
2. Broadcom private >$60B debt financing — private capital-markets transaction,
   плохо представлена в company newsroom/IR на момент discovery.
3. Nvidia server price hikes — supply-chain/pricing report, который обычно
   появляется именно у агентств/отраслевых СМИ, а не в официальном newsroom.

Это важный отрицательный результат: **Source Pulse не может заменить Web Search
или agency discovery**. Он является комплементарным каналом.

## Россия: что показал replay

Source-aware Russia layer заметно богаче одного broad Web Search route:

- MWS AI / enterprise-cost signal;
- VK AI Space / developer-platform updates;
- Yandex Alice AI commerce adoption;
- fabricaONE.AI bond financing;
- Yandex medical assistant;
- Sber multimodal anti-phishing.

Не все эти события Must Include. Это и не цель: Source Pulse должен обеспечить
candidate awareness, после чего editorial решает значимость. Главный выигрыш —
исчезает ситуация «движок не знает, что событие вообще существовало».

## Freshness: уточнение диагноза 25 августа

Первоначальная гипотеза «Source Freshness Proof режет date-only sources» слишком
грубая. Текущий `source_freshness.py` уже допускает date-only evidence внутри
window и fail-closed отклоняет date-only только на самой cutoff date, где нельзя
доказать, что страница существовала до cutoff.

Фактическая проблема Google/Verizon и Yandex 25 августа другая: уже цитируемые
URL не отдали freshness extractor'у независимо проверяемую machine-readable
publication date. При этом для Yandex существует альтернативный официальный IR
URL, который явно датирует тот же press release.

Поэтому безопасный следующий freshness experiment — **alternate-source
freshness corroboration / extractor coverage**, а не ослабление date-only rule.
Он должен быть отдельным от Source Pulse, чтобы не смешивать причинность.

## Diagnostics, которые нужны до production rollout

Будущий `source-pulse.json` должен сохранять минимум:

- source id / tier / URL;
- fetch status, HTTP status, final URL, elapsed time;
- item count before/after window filter;
- timestamp precision;
- `fresh_source_leads`;
- `stale_only_source`;
- `source_unavailable`;
- exact/event fingerprints;
- `pulse_found_search_missed`;
- `search_found_pulse_missed`;
- lead disposition: duplicate / stale / triage-reject / accepted;
- reason for every rejection;
- source snapshot hash/time for recovery.

Отдельно сохранять provider-health текущего search:
`empty_provider_pool`, `consulted_sources=[]`, stale-source age distribution.
Так можно будет видеть, какой канал именно сломался.

## Guardrails для Source Pulse v1

1. Fixed HTTPS source registry; никаких произвольных URL от feed без public-URL
   validation.
2. Bounded HTTP: timeout, retries, response-size cap, total source count.
3. Per-source fail-open; весь Pulse не должен блокировать старый production.
4. Maximum items per source и global lead cap.
5. Tier B — только lead, не final authority.
6. Exact + event-semantic dedupe до model triage.
7. Mutable changelog dedupe по event fingerprint, не только URL.
8. Same effective window; no unbounded lookback.
9. No regional publication quota.
10. No Source Freshness bypass.
11. Recovery reuses saved snapshot; no silent repoll.
12. Agency rescue health remains independent.
13. Web Search ceiling остаётся **24**.
14. Любой будущий no-Web-Search LLM triage — отдельная явно учтённая стоимость;
    production API не включать без разрешения владельца.

## Что стало лучше / хуже в эксперименте

### Лучше

- 69.2% исторических strict miss-day instances получили независимый lead.
- На 20, 24 и 25 августа второй канал существенно меняет completeness picture.
- China/Asia model + business + embodied-AI покрываются несколькими независимыми
  типами источников вместо одного ranking pool.
- Russia получает устойчивый локальный discovery path без publication quota.
- Official sources дают больше source diversity и уменьшают зависимость от
  TechCrunch/search ranking.
- HTTP discovery не расходует Web Search budget.

### Не стало хуже на replay

- Canonical Web Search результаты не заменяются и не урезаются.
- Search ceiling не увеличивается.
- Source Freshness Proof, significance и dedupe не ослабляются.
- Negative/quiet day 22 августа не превращается в искусственный «обязательный
  региональный сюжет».
- Pulse miss (Broadcom/price/legal) оставляет старые Web/agency пути доступными.

### Новые риски/стоимость

- Больше engineering complexity: adapters, source-health, snapshots.
- Возможны 403/HTML changes/mutable pages.
- Без hard cap возрастёт число lead records.
- Будущий semantic triage может добавить один model call (без Web Search), если
  мы решим его включить в production.

Эти риски управляемы guardrails выше и не требуют ослабления существующей
редакционной защиты.

## Итоговый architecture verdict

**GO для bounded fail-open Source Pulse sidecar prototype.**

**NO-GO** для следующих вариантов:

- заменить Primary/Web Search Source Pulse'ом;
- inject raw Pulse leads внутрь 12 Primary passes;
- вводить China/Russia publication quotas;
- поднимать Web Search ceiling выше 24;
- автоматически принимать Tier-B source как финальное подтверждение;
- ослаблять Source Freshness Proof;
- смешивать Source Pulse и freshness-extractor patch в одном causal experiment.

Эксперимент подтверждает основную гипотезу: существенная доля наших последних
misses связана не с editorial, а с тем, что единственный search-ranking channel
не доставляет событие в candidate pool. Независимый fixed-source/source-aware
канал закрывает большую часть этих blind spots, но оставляет агентские/legal/
private-market события за Web Search — то есть архитектурно каналы действительно
дополняют друг друга.

## Рекомендованный следующий шаг

Сделать **Source Pulse v1 prototype**, пока не включённый в publication behavior:

- source registry + adapters;
- deterministic snapshot + window filtering;
- event fingerprints + archive comparison;
- diagnostics/report;
- replay fixture на 19–25 августа;
- offline tests на 403, timeout, malformed XML/HTML, stale-only, mutable URL,
  duplicate и quiet window.

После того как prototype воспроизводимо подтверждает этот bake-off, отдельным
production PR можно интегрировать его sidecar между Primary/rescue и Hybrid.
Такой production PR обязан обновить README/automation README/AGENTS и пройти
полный offline CI. До этого research-only PR документацию production contract не
меняет.