# Независимый аудит выпуска 2026-09-10

> Исправленная версия после дополнительной сверки exact recovery artifact. Первоначальный PR #164 зафиксировал предварительный denominator `11` и `Coverage 6/7`. Это оказалось методологически неверно: три опубликованных/контрольных события относились к healing overlap до `latest_archive_at`, а финальный recovery artifact действительно завершил Coverage `7/7`. Ниже приведён исправленный event-identity audit.

## Итог

- **Publication mechanics:** PASS.
- **Recovery / paid stages at-most-once:** PASS.
- **Source/Event Freshness fail-closed:** PASS как контракт, но **Source Freshness proof coverage:** FAIL по практической полноте.
- **High-signal completeness:** FAIL.
- **Strict Must Include main-window publication recall:** **`2/8 = 25.0%`**.
- **Strict Must Include final candidate recall:** **`3/8 = 37.5%`**.
- **Strict Must Include reached editor input:** **`3/8 = 37.5%`**, но после Source Freshness пригодными к выбору остались только `2/8`.
- **Search spend:** `12 Primary + 1 Agency Rescue + 5 Hybrid + 7 Coverage = 25/25`.
- **Discovery Health v1:** `degraded`.
- **Ни одного strict Must Include не потерял сам editor после того, как событие осталось fresh + eligible.**

Ключевой вывод: проблема 10 сентября не сводится к одному ranking/editorial miss. Она раскладывается на три проверяемых слоя:

1. hard upstream discovery misses;
2. source-resolution/source-upgrade miss для уже замеченного события;
3. Source Freshness Proof miss для уже найденного, verified, high-signal кандидата.

Поэтому править editor/ranking первым сейчас неправильно: два score-4 кандидата, которые выглядели как «ошибочно excluded», в Primary первоначально были `include + verified`. Их eligibility разрушил поздний source-freshness слой.

## Production evidence и recovery

Исходный scheduled run `34423913431`:

- успешно выполнил full research + editorial;
- остановился на `Complete mandatory coverage audit for a short digest`;
- сохранил paid artifact `daily-production-2026-09-10`, artifact ID `10132209897`.

Recovery run `34428040410`:

- artifact ID `10133444947`;
- digest `sha256:61a6fec5664216697a264e144151134d2a02db39449db53b4b10a8ea7fc28185`;
- восстановил сохранённый paid artifact;
- `Run full research and editorial` был **skipped**;
- Coverage был завершён;
- normalize/validate, image, site build, promote, commit и FTP deploy завершились успешно;
- release commit: `ced45730a586a0a3e439214efb3b448f0abdca6e`.

Последующий dispatch `34432025380` увидел уже опубликованный выпуск и корректно завершился no-op.

**Вердикт:** recovery и at-most-once поведение здоровы. Downstream failure не вызвал повторный full research/editorial.

## Exact research window

Saved Primary artifact:

- effective start: `2026-09-08T04:15:13+03:00`;
- saved cutoff: `2026-09-10T04:04:18+03:00`;
- canonical continuity boundary `latest_archive_at`: `2026-09-09T04:15:13+03:00`.

Для strict main-window denominator используются только independently verified high-signal события после `latest_archive_at` и до saved cutoff. События 8 сентября могут быть корректно опубликованы благодаря healing overlap, но не считаются strict hits 10 сентября.

Именно это исправляет главный методологический дефект первоначального PR #164: Arm и Massachusetts являются нормальными сюжетами выпуска, но их core events относятся к 8 сентября. Они не должны улучшать strict main-window recall.

## Опубликованные 7 сюжетов

1. Arm Neoverse CSS N4.
2. Apple Watch Audio Intelligence / Live Rewind / Siri Recap.
3. Massachusetts clean-power requirements for large data centers.
4. Paul Christiano joins OpenAI Foundation Board / Safety & Security Committee.
5. Suno v6.
6. Cymphony funding / AI-agent identity security.
7. Runway + Kinetix.

Все семь прошли действующие publication validators. В final story sources четыре сюжета используют TechCrunch как publisher source; это диагностический signal концентрации, но не основание вводить publisher quota.

## Независимый B/reference control

Проверка выполнена assistant-owned ordinary web/reference search, без production API/Web Search бюджета владельца. Standalone assistant-side Terra в этой сессии не exposed, поэтому эта проверка **не называется Terra A/B**. Она является независимой Terra-emulation/reference проверкой по exact historical window.

Сравнение ведётся по event identity, а не по совпадению headline string.

### Strict Must Include set: 8 событий

| # | Event | Независимое время | Production path | Verdict |
|---|---|---|---|---|
| 1 | Google: €13B AI infrastructure в Финляндии | Reuters `2026-09-09 07:01:30 UTC` | замечен только weak-source model rejection (HuggingNews), authoritative source не повышен до candidate | **MISS: source resolution / source upgrade** |
| 2 | DeepSeek привлёк CITIC для подготовки IPO на STAR Market | Reuters `2026-09-09 06:11:50 UTC` | current event отсутствует в saved surface | **MISS: discovery** |
| 3 | Harvey: $550M при valuation $15.5B | Reuters `2026-09-09 16:56:08 UTC` | отсутствует в saved surface | **MISS: discovery** |
| 4 | OpenAI rogue agents: >10 дополнительных сайтов с unauthorized communications | Reuters `2026-09-09 16:03:28 UTC` | Coverage видел старые/смежные материалы, но этот material update не стал candidate | **MISS: discovery / coverage** |
| 5 | Anthropic: четвёртый real-system incident / alignment assessment | Reuters `2026-09-09 19:40:20 UTC`; first-party page датирована Sep 9 | Primary: `include`, `verified`, score 4; final candidate `exclude/unconfirmed` из-за отсутствия machine-verifiable source publication date | **MISS: Source Freshness Proof** |
| 6 | NVIDIA + Australian partners: до 2 GW AI capacity | Reuters `2026-09-10 00:22:02 UTC`, то есть примерно за 42 минуты до cutoff | отсутствует в saved surface | **MISS: discovery, late-window** |
| 7 | Apple Watch Audio Intelligence / Live Rewind / Siri Recap | Sep 9 | final candidate include, опубликовано | **HIT** |
| 8 | Suno v6 / licensed-data transition | Sep 9 | final candidate include, опубликовано | **HIT** |

Reference URLs:

- Google: https://www.reuters.com/business/media-telecom/google-invest-15-billion-ai-infrastructure-finland-2026-09-09/
- DeepSeek: https://www.reuters.com/world/chinas-deepseek-taps-citic-securities-domestic-ipo-sources-say-2026-09-09/
- Harvey: https://www.reuters.com/legal/government/legal-ai-startup-harvey-reaches-155-billion-valuation-new-funding-round-2026-09-09/
- OpenAI rogue agents: https://www.reuters.com/world/openais-rogue-agents-used-least-10-more-sites-unauthorized-comms-researchers-say-2026-09-09/
- Anthropic: https://www.reuters.com/legal/litigation/anthropic-reports-fourth-cybersecurity-incident-with-early-version-claude-2026-09-09/
- NVIDIA Australia: https://www.reuters.com/world/asia-pacific/nvidia-teams-up-with-australian-partners-build-ai-factory-capacity-2026-09-10/
- Apple: https://www.apple.com/newsroom/2026/09/apple-unveils-apple-watch-ultra-4/
- Suno: https://suno.com/blog/introducing-v6

### Strong Include / borderline, вне strict denominator

- Paul Christiano joins OpenAI Foundation Board / SSC: опубликован, но governance/personnel significance ниже strict set.
- OpenAI AI-policy push: материал Sep 9, Source Pulse его обнаружил, но это policy advocacy, а не enacted regulatory action; поэтому не раздувает denominator.
- Massachusetts data-center clean-power story: допустимый и сильный сюжет, но underlying executive-order event датирован Sep 8 и относится к healing overlap.
- Arm Neoverse CSS N4 и Runway/Kinetix: также overlap events.
- China response / U.S. distillation advisory (`cand-001`): сильный follow-up, но core U.S. advisory был Sep 8. Дополнительно сохранённый `event_date_evidence` ошибочно выводит «Tuesday → 2026-09-09», хотя 9 сентября 2026 года была среда. Этот кандидат не используется в strict denominator.

### Not Required для strict Sep10 denominator

- DeepSeek V4.1 Flash launch: Reuters publication вышла после saved cutoff.
- GPT-6 Astra launch: core release был Sep 3; более свежий RSS appearance не превращает его в новый Sep9 launch.
- прочие analysis/features без нового material event.

## A/B / recall по слоям

Strict denominator: **8 Must Include**.

- independently verified controls: `8/8`;
- production retrieval awareness, включая saved weak-source rejection: `4/8 = 50.0%` (`Google`, `Anthropic`, `Apple`, `Suno`);
- final production candidate surface: `3/8 = 37.5%` (`Anthropic`, `Apple`, `Suno`);
- reached editor input: `3/8 = 37.5%`;
- fresh + eligible к реальному editorial choice: `2/8 = 25.0%`;
- selected: `2/8 = 25.0%`;
- published: **`2/8 = 25.0%`**.

Loss accounting:

- **Google Finland:** source-resolution/source-upgrade before candidate;
- **DeepSeek IPO/CITIC:** discovery;
- **Harvey funding:** discovery;
- **OpenAI rogue agents:** discovery/coverage;
- **Anthropic incident:** Source Freshness Proof;
- **NVIDIA Australia:** discovery, с оговоркой late-window;
- **Apple:** HIT;
- **Suno:** HIT;
- **editor:** `0` strict losses после fresh+eligible;
- **validator/recovery/publication:** `0` strict losses после editorial selection.

Таким образом, preliminary hypothesis «ranking/editor выбросил сильные найденные новости» для strict Sep10 set **не подтверждается**. Видимый `exclude` у Anthropic возник после freshness, а не из-за editorial preference.

## Retrieval anatomy

### Primary

Primary выполнил `12/12` mandatory searches.

Raw-zero directions:

- `major_agencies`;
- `models_products_agents`;
- `china_asia_models`;
- `china_asia_integrations`;
- `russia`;
- `legal_regulation`.

`developer_tools` вернул raw candidates, но все были validator-rejected.

Сильный положительный сигнал: Anthropic был найден в `security_safety` и первоначально имел `include + verified + score 4`.

Сильный отрицательный сигнал: Google Finland был замечен в model rejection только через слабый агрегатор и остановлен `weak_source`, хотя exact-window Reuters и first-party material существовали. Это не оправдание для ослабления weak-source fail-closed. Наоборот, это доказательство необходимости bounded authoritative source upgrade для уже замеченного high-signal event.

### Agency Rescue

- trigger: `major_agencies_raw_zero`;
- executed: `true`;
- Reuters-only;
- `1/1` search operation;
- raw / validated / accepted / added: `0 / 0 / 0 / 0`;
- `consulted_sources=[]`;
- source metadata unavailable;
- final state `completed_no_addition`.

В exact main window Reuters имел Google, DeepSeek, Harvey, OpenAI rogue-agent follow-up, Anthropic и NVIDIA Australia. На Sep9 Reuters-only rescue уже показывал тот же паттерн `0 additions` при наличии релевантных Reuters controls.

**Вывод:** Agency/provider routing является recurring defect signal. Это уже не аргумент за «ещё один search», а за controlled repair текущего Reuters slot/routing/provider behavior.

### Hybrid

- `5/5`, включая conditional +1 при double Asia + Russia gap;
- additions: `0`;
- Asia и Russia остались unresolved.

### Coverage

Финальный recovery artifact, а не preliminary scheduled state:

- maximum `7`;
- completed calls: **`7/7`**;
- all six required directions checked;
- additions: `0`;
- final status `complete_with_gaps`.

Это исправляет вторую ошибку первоначального PR #164. Общий paid search contour действительно использовал полный conditional ceiling:

**`12 + 1 + 5 + 7 = 25/25`.**

При таком расходе пропуски нельзя объяснять недостатком количества запросов. Нужна лучшая gap-awareness/source-resolution внутри существующего бюджета.

## Source Freshness

Критический Sep10 case: Anthropic.

В Primary событие было:

- recommendation `include`;
- verification `verified`;
- significance `4`;
- event date Sep 9.

После Source Freshness Proof final candidate стал:

- recommendation `exclude`;
- verification `unconfirmed`;
- `source_published_at = null`;
- reason: ни один already-cited source URL не отдал independently verifiable publication date.

При этом independent check подтверждает first-party Anthropic page Sep 9 и Reuters timestamp `19:40:20 UTC`.

Это **не** основание разрешить unknown freshness. Fail-closed контракт правильный. Исправлять нужно extractor/evidence propagation так, чтобы реально существующая authoritative date могла быть доказана машинно.

`cand-001` (China response / U.S. distillation) показывает похожий technical pattern, но не используется как strict main-window MISS из-за Sep8 core event и сомнительного saved date reasoning.

## Source Pulse: live effect PR #162

Saved Source Pulse:

- configured sources: `16`;
- source status OK: `12`;
- unavailable: `4`;
- accepted leads: `15`;
- promoted candidates: `3`;
- paid OpenAI calls: `0`;
- Web Search operations: `0`.

Три новых route из PR #162:

### OpenAI RSS

- HTTP `200`;
- `parsed_items=16`;
- `window_items=8`;
- `accepted_leads=8`;
- RSS реально обнаружил `Introducing ChatGPT Images 2.5`, policy material, Paul Christiano и другие items;
- все `pulse_only` OpenAI leads при promotion получили `source_fetch_error` / HTTP `403` при direct-page freshness fetch;
- Paul Christiano имел `fusion_disposition=both_exact_url`, то есть уже был найден Primary и не доказывает новый contribution.

**Новых promoted candidates от нового OpenAI route: 0.**

Это важный частичный успех: discovery plane работает, но downstream freshness transport не позволяет реализовать ценность.

### Qualcomm newsroom

- index HTTP `200`;
- status `ok`;
- `parsed_items=0`;
- `window_items=0`;
- `accepted_leads=0`.

**Contribution: 0.**

Для newsroom, который заведомо содержит материалы, `HTTP 200 + parsed 0` является parser-health signal, даже если transport-level status формально `ok`.

### NSA AI route

- HTTP `403`;
- `source_unavailable`;
- `accepted_leads=0`.

**Contribution: 0.**

### Реальный production uplift #162

На Sep10 новые routes #162 дали **0 доказанных новых promoted candidates и 0 опубликованных stories**.

Следовательно, ответ на главный вопрос аудита:

**#162 не продемонстрировал реальный publication uplift на первом live production после merge.**

Но это не опровергает саму идею Source Pulse. OpenAI RSS доказал полезный discovery. Проблема сейчас в acceptance/transport/parser слоях, поэтому добавлять новые source rows вместо исправления существующих routes не следует.

PR #163 полезен именно здесь: offline trace contract отделяет source health, leads, promotion, candidate/editorial/story/publication и не позволяет считать сам факт RSS discovery публикационным вкладом.

## Publisher / organization diversity

В final seven-story digest четыре source blocks используют TechCrunch. Это высокая концентрация для одного publisher.

Однако вводить publisher quota нельзя. Независимые misses одновременно показывают доступные Reuters и first-party surfaces, поэтому правильное направление — улучшить source acquisition и resolution. Diversity должна улучшаться как следствие лучшего retrieval, а не административной квоты.

## Историческая серия

Из предыдущих независимых аудитов:

- Sep6: strict recall `1/2 = 50%`;
- Sep7: `0/1 = 0%`;
- Sep8: подтверждён hard upstream miss при полном/почти полном search budget;
- Sep9: `5/9 = 55.6%`;
- historical controlled fixture treatment после #162: `10/13 = 76.9%`;
- Sep10 live: **publication strict recall `2/8 = 25.0%`**.

Denominators между днями различаются, поэтому это не time-series KPI в статистическом смысле. Но направление достаточно ясное: fixture uplift #162 пока не подтвердился live.

## Что уже достаточно доказано для runtime work

### P0. Source-date proof extraction / propagation без ослабления freshness

**Почему доказательств достаточно**

- Anthropic был найден, verified и score 4, но потерян только потому, что current source-date proof не смог машинно подтвердить реально существующую Sep9 дату.
- OpenAI RSS нашёл 8 in-window leads, но все pulse-only items заблокированы direct-page HTTP 403 на freshness proof.

**Какой слой менять**

Source Freshness Proof / authoritative date evidence propagation. В частности, проверить bounded использование exact feed-entry publication timestamp для exact canonical first-party URL и улучшить generic machine-readable/visible-date extraction, не превращая произвольный body text в доказательство.

**Чего не менять**

- не разрешать `unknown`;
- не ослаблять freshness window;
- не обходить canonical URL checks;
- не добавлять provider-specific исключения без bounded evidence.

**Нужен ли controlled experiment**

Да. Offline A/B на saved artifacts/pages/feeds с stale boundary, redirect, canonical mismatch, conflicting-date и missing-date negative controls до production PR.

### P1. Agency/provider routing в существующем Reuters slot

**Почему доказательств достаточно**

Sep9 и Sep10 Reuters-only rescue возвращает zero additions при наличии нескольких independently verified Reuters events в exact windows. На Sep10 rescue даже не сохранил source metadata.

**Какой слой менять**

Agency Rescue provider/domain routing и diagnostics выполнения search slot. Цель — сделать существующую одну Reuters operation реально способной доставлять Reuters surface и доказуемо фиксировать provider/source metadata.

**Чего не менять**

- не увеличивать Agency budget > 1;
- не увеличивать общий search ceiling;
- не ослаблять source/freshness validation.

**Нужен ли controlled experiment**

Да. Historical replay/A-B на Sep6–Sep10 controls с тем же `1` Agency operation и тем же общим ceiling.

### P2. High-signal weak-source → authoritative source upgrade и gap-awareness

**Почему доказательств достаточно**

Google €13B был замечен, но умер как `weak_source`, хотя Reuters и first-party source существовали. Одновременно Coverage `7/7` и Hybrid `5/5` дали `0` additions, а несколько cross-lane Must Include событий отсутствовали полностью.

**Какой слой менять**

Source-neutral source-upgrade / gap-resolution logic внутри существующих Primary/Coverage passes. Weak source должен оставаться непубликуемым, но high-signal event identity может быть bounded seed для поиска authoritative proof.

**Чего не менять**

- не ослаблять weak-source fail-closed;
- не увеличивать число запросов;
- не вводить company whitelists или regional publication quotas.

**Нужен ли controlled experiment**

Да. Fixed-budget regression matrix: baseline vs treatment на historical hard misses и negative controls.

### P3. Source Pulse route health / live acceptance

**Почему доказательств достаточно**

- OpenAI RSS discovery работает, promotion path нет;
- Qualcomm `200 + parsed 0`;
- NSA `403`.

Три новых route #162 в реальном production дали нулевой new-candidate contribution.

**Какой слой менять**

Route health semantics, parser fixtures и bounded transport fallback только для доказуемых official surfaces.

**Чего не менять**

- не плодить новые registry rows вместо ремонта;
- не считать HTTP 200 достаточным health proof для HTML parser;
- не делать Pulse заменой Search или regional gap resolver.

**Нужен ли controlled experiment**

Да. Отдельный route-by-route acceptance test с saved/live-public fixtures без production paid API.

## Что пока не пора менять

### Editorial ranking / prompt

Sep10 не даёт чистого доказательства editorial ranking failure среди strict Must Include:

- Anthropic потерян freshness gate;
- Google не дошёл до candidate;
- четыре Must Include не найдены;
- Apple и Suno, которые были fresh+eligible, редактор выбрал.

Поэтому editor/ranking следует исследовать после upstream/freshness repairs. Сейчас изменение editorial prompt смешало бы причинность и могло бы ухудшить выбор без исправления recall.

### Search budget

Полный conditional ceiling `25/25` уже использован. Добавлять 26-й запрос без доказанного routing/gap-awareness treatment не обосновано.

### Freshness / weak-source contracts

Оба контракта правильно предотвратили публикацию недостаточно доказанных candidates. Нужна лучшая добыча доказательств, а не более слабые доказательства.

## Документация и scope

Этот audit correction не меняет runtime, workflow, retrieval, editorial, freshness, recovery, publication или repository structure.

Проверены:

- `README.md`;
- `automation/README.md`;
- `automation/ARCHITECTURE.md`;
- `AGENTS.md`.

Изменения этих файлов не требуются: PR исправляет только audit evidence и метрики.

## Финальный вердикт

Техническая публикация 10 сентября здорова, а completeness — нет.

**Главный показатель:** `2/8 = 25%` strict Must Include publication recall в main window.

**Главный root cause:** не editor. Основной ущерб приходит из сочетания hard discovery misses, неработающего Reuters rescue/source routing, неспособности повышать weak-source high-signal события до authoritative evidence и Source Freshness Proof, который не умеет использовать существующее доказательство даты в нескольких важных cases.

**#162:** live publication uplift на Sep10 не доказан; реализованный вклад новых routes равен нулю. OpenAI RSS при этом доказал, что сам discovery route полезен, поэтому следующий шаг — не отменять Source Pulse, а чинить его acceptance/freshness path и route health.

**Приоритет runtime work:** P0 Source Freshness proof → P1 Agency/provider routing → P2 source-upgrade/gap-awareness → P3 Source Pulse live acceptance.
