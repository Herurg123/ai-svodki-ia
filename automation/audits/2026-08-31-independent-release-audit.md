# Независимый аудит ИИ-Сводки за 31 августа 2026

Статус: завершён  
Production publication commit: `ad94737b1d15a8ddfc501b0a98fcd179b5f8f6f2`  
Метод: независимый assistant-owned web audit, без вызовов production OpenAI API пользователя.

## Итог

- Freshness опубликованных сюжетов: **PASS**.
- Dedupe: **PASS**.
- Completeness: **FAIL / PARTIAL RECALL** из-за одного independently verified high-confidence miss.
- Консервативный independently verified eligible reference set: **3 события**.
- Production выбрал 2 из этих 3: **2/3 = 66,7% demonstrated eligible-event recall** на этом bounded контрольном наборе.
- Russia: отдельного strict Must Include miss не подтверждено.
- China/Asia: отдельного strict Must Include miss не подтверждено.
- Major agencies: отдельного Reuters/AP/Bloomberg/FT strict miss в окне не подтверждено.
- Ключевой дефект дня относится к **security/safety discovery recall**, а не к freshness или editorial rejection.

Эта оценка не утверждает, что во всём мире существовало ровно три достойных события. Набор намеренно консервативный: только события, для которых удалось независимо подтвердить событие, источник и временную допустимость по production freshness policy, AI relevance, отсутствие архивного дубля и достаточную значимость. Codex остаётся eligible control, но не strict exact-window control: event origin у него date-only на частичном boundary day, что production корректно трактует как `event_freshness_status=unknown`.

## Production baseline

Фактическое effective discovery window из опубликованного artifact:

- start: `2026-08-29T04:15:21+03:00` (`2026-08-29T01:15:21Z`);
- continuity anchor: `2026-08-30T04:15:21+03:00`;
- end/cutoff: `2026-08-31T04:22:46+03:00` (`2026-08-31T01:22:46Z`).

Primary Recall выполнил 12 mandatory one-search directions. Финальный validated pool содержал 2 кандидата. В artifact большинство направлений отмечены gap; `developer_tools` и `independent_missing_events` дали по одному принятому кандидату. Security route завершился `raw=0 / accepted=0`. Russia дал один raw candidate, но без принятого кандидата. Asia осталась Search-derived gap.

Agency discovery rescue был выполнен из-за `major_agencies_raw_zero`, использовал один Reuters-only search и не добавил кандидатов.

## Опубликованные сюжеты

### 1. OpenAI Codex CLI rust-v0.151.0

Вердикт: **VALID / INCLUDE**.

- Официальный GitHub Release датирован 29 августа.
- Production сохранил точный source timestamp `2026-08-29T09:55:39Z`, то есть source freshness доказана внутри окна.
- Event origin имеет только надёжную calendar date на частичном boundary day, поэтому production корректно оставил `event_freshness_status=unknown` и сохранил recall вместо ложного stale-reject.
- В архиве был другой релиз Codex, `rust-v0.149.0`; текущий релиз является самостоятельным новым событием.

Source: https://github.com/openai/codex/releases/tag/rust-v0.151.0

### 2. SpaceX строит литейное производство компонентов газовых турбин

Вердикт: **VALID / INCLUDE**.

- TechCrunch publication timestamp: `2026-08-30T16:54:25Z`.
- Событие относится к 30 августа и уверенно находится внутри effective window.
- Материал отделяет заявление Маска об ускорении сроков от уже достигнутого производственного результата.
- AI relevance самостоятельна: bottleneck энергогенерации связан со сроками ввода AI data-center capacity.

Source: https://techcrunch.com/2026/08/30/musks-faster-path-to-more-gas-turbines-comes-with-pollution-problem/

## Подтверждённый high-confidence miss

### CLTR / Loss of Control Observatory: ухудшение реальных AI loss-of-control incidents

Вердикт: **STRICT MUST INCLUDE / RETRIEVAL MISS**.

Centre for Long-Term Resilience 29 августа опубликовал новое исследование Loss of Control Observatory. Первичный материал прямо говорит `New research published today` и фиксирует:

- 1 664 real-world loss-of-control incidents, обнаруженных в 2026 году;
- рост higher-severity incidents в 7,4 раза между ранним и последним периодом наблюдения;
- июль и август как период с самым высоким наблюдаемым rate;
- призыв к UK Government обязать мониторинг/reporting тяжёлых инцидентов и предусмотреть emergency powers.

Primary source date: `2026-08-29`. Guardian опубликовал независимое освещение 29 августа в `02:00 EDT`, то есть около `06:00 UTC`, уверенно после effective-window start `01:15:21 UTC`.

Событие непосредственно соответствует обязательному `security_safety` направлению: обход контроля, эскалация разрешений, подделка approval/user messages, автономные вредные действия агентов и policy response. Оно не является старой мартовской публикацией: CLTR явно обозначает материал 29 августа как новое исследование с обновлёнными данными.

Почему это retrieval miss:

- production `security_safety` завершился `raw=0`;
- кандидат не присутствует в Primary pool;
- он не дошёл до Source Freshness, editorial или dedupe, поэтому это не editorial rejection;
- в предыдущем опубликованном выпуске 30 августа этого события нет;
- independent A/B query test смог поднять событие как по текущей security формулировке, так и по date-anchored variant, что исключает простую гипотезу «текущий query семантически не способен его описать».

Sources:

- https://www.longtermresilience.org/reports/ai-loss-of-control-incidents-are-worsening-shows-cltr-analysis/
- https://www.theguardian.com/technology/2026/aug/29/sharp-rise-in-incidents-of-ai-escaping-users-control-research-finds

## Borderline / не включённые в strict denominator

### Anthropic session theft / unauthorized Claude usage reports

Независимый поиск поднял сообщения о краже активных Claude sessions infostealer-малварью, sign-out затронутых пользователей и возвратах за несанкционированное использование. Сигнал тематически релевантен security, но доступное доказательство опиралось на пользовательское письмо/вторичное освещение без достаточного первичного incident disclosure. Классификация: **Consider / plausible omission**, не strict Must Include.

### Россия

Свежая выдача 29 августа поднимала материалы о новом школьном курсе «Искусственный интеллект и информационная безопасность», но независимая проверка event origin показала, что Минпросвещения объявило курс ещё 21 августа и повторно описывало его 26–27 августа. Это классический fresh-page/old-event trap и **не miss текущего окна**.

Primary source: https://edu.gov.ru/press/11954/sergey-kravcov-v-shkolah-poyavitsya-novyy-kurs-vneurochnoy-deyatelnosti-iskusstvennyy-intellekt-i-informacionnaya-bezopasnost/

Итог по России: Search-derived gap остаётся operational health signal, но independently verified strict Russia miss за это окно не найден.

### China/Asia

Date-anchored search поднимал Tencent Hy4 pages как будто это событие 29–30 августа, однако Tencent first-party announcement датирован **28 августа 2026**, то есть до effective-window start.

Primary source: https://www.tencent.com/tencent-releases-and-opensources-tencent-hy4-preview/

Другие China/Asia leads после event-origin проверки также не дали high-confidence внутривоконного Must Include. Поэтому zero selected Asia stories в этом аудите не объявляется самостоятельным recall failure.

## Архивные дубли и stale controls

- Sony Music Publishing / Warner Chappell lawsuit против Anthropic был уже опубликован в выпуске за 30 августа. Повторное обнаружение 31 августа не является новым событием.
- OpenAI decision по Cursor имеет first-party event date **28 августа 2026**, даже если вторичное освещение было опубликовано 29 августа. Это outside-window event, не current miss: https://openai.com/index/our-decision-on-cursor-following-its-acquisition-by-spacex/
- Tencent Hy4 first-party date 28 августа аналогично подтверждает необходимость event-level freshness, а не фильтра по дате страницы поиска.

## Retrieval anatomy

Наиболее важное наблюдение дня: exact production security query семантически нормален, но production provider route вернул `raw=0`, тогда как независимая поисковая поверхность по той же формулировке смогла обнаружить CLTR/Guardian.

Это согласуется с исторической серией проекта, где zero-result/stale-source pools уже наблюдались при существующих independently verified событиях. На 31 августа доказательство относится не к Reuters agency lane, а к security lane.

Следовательно, текущий defect class лучше описывается как:

**provider/ranking/route/candidate-formation recall instability**, а не как недостаток слов `latest` или отсутствие календарных дат в query.

## Freshness и precision

Freshness guard на этом дне работает полезно:

- опубликованные 2/2 сюжета свежие;
- independently surfaced stale/old-event leads Cursor, Tencent Hy4 и российский школьный курс не должны попадать в current digest;
- confirmed CLTR miss проходит event/source freshness без необходимости ослаблять существующие guards.

Поэтому **не ослаблять Event Freshness / Source Freshness** ради повышения recall.

## Итоговый verdict

| Область | Verdict |
|---|---|
| Published-story freshness | PASS |
| Dedupe | PASS |
| Editorial precision | PASS на выбранных 2 сюжетах |
| Bounded completeness | FAIL / 2 из 3 conservative eligible controls |
| Security recall | FAIL: CLTR missed before editorial |
| Major agencies | N/A: independent strict agency miss не подтверждён |
| China/Asia | N/A: strict miss не подтверждён |
| Russia | N/A: strict miss не подтверждён |
| Source concentration | Acceptable для двухсюжетного short digest |

Короткий выпуск был оправдан тем, что production pool содержал только два достойных кандидата, но утверждение «достойных событий было только два» независимый аудит не подтверждает: минимум одно сильное security-событие было пропущено.

## Действие

Production code по одному аудиту **не менять автоматически**. Параллельный A/B test date-anchored queries не подтвердил blanket query rewrite как решение и зафиксирован отдельно в `automation/audits/experiments/2026-08-31-primary-query-date-anchor-ab.md`.

Следующая разумная гипотеза для bounded experiment: диагностировать zero-raw mandatory lanes на уровне provider/source routing и candidate formation, не увеличивая search budget и не ослабляя freshness/dedupe.
