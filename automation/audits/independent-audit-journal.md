# Журнал независимых аудитов ИИ-Сводки

Последнее обновление: 2026-08-21  
Назначение: накопление независимых проверок полноты и свежести ежедневной ИИ-Сводки без расходования production API пользователя.

## Как использовать журнал

После каждого успешного ежедневного выпуска:
1. Определить фактическое effective news window по production artifact / archive.
2. Независимо проверить выпуск на собственных поисковых ресурсах (Terra/web), не используя production API пользователя.
3. Отдельно проверить:
   - свежесть опубликованных сюжетов;
   - значимые пропуски;
   - stale-новости;
   - слабые/сомнительные источники;
   - поведение retrieval по регионам и тематикам.
4. Добавить новую запись в этот файл.
5. Не менять архитектуру по одному наблюдению, если нет явного критического дефекта. Ищем повторяющиеся паттерны.

---

## 2026-08-17

### Production
- Выпуск опубликован успешно.
- Опубликовано 2 сюжета:
  1. Anthropic — компрометации инфраструктуры организаций во время кибероценок.
  2. Stripe / OpenRouter — предполагаемая сделка более чем на $7 млрд.
- Effective window:
  - start: 2026-08-15 08:59:33 +03:00
  - end: 2026-08-17 02:33:51 +03:00

### Независимый аудит
- Stripe / OpenRouter: свежая и корректная новость.
- Anthropic: stale. Основной материал AP был опубликован 2026-07-31, то есть примерно за 17 дней до окна.
- Значимый пропуск: Nvidia / SB Energy / OpenAI — свежий материал Reuters от 2026-08-15 о переговорах Nvidia по инвестиции до $3 млрд в SB Energy для проекта дата-центра OpenAI в Огайо.
- Других сопоставимых по значимости обязательных пропусков в точном окне независимо не найдено.

### Оценка
- Freshness precision опубликованных сюжетов: примерно 1/2 = 50%.
- Recall по ясно подтверждённому high-signal reference set: примерно 1/2 = 50%.
- Вердикт: FAIL по свежести и полноте.

### Диагноз
- Модель могла сама записать неверную дату публикации источника.
- Timezone-конверсия одного из timestamp также была ошибочной.
- Stale Anthropic ошибочно удовлетворила source-health.
- Новый механизм unresolved signals не помог, потому что свежий Nvidia-сигнал вообще не был обнаружен.

### Последствие
После этого наблюдения внедрён Source Freshness Proof v1:
- дата/время источника должны подтверждаться машинно;
- timestamp нормализуется кодом, а не LLM;
- stale или непроверяемый по дате сюжет не должен доходить до публикации.

---

## 2026-08-18

### Production
- Выпуск опубликован успешно.
- Опубликовано 6 сюжетов:
  1. Nvidia / SB Energy / OpenAI — инвестиция в площадку в Огайо.
  2. Gravis Robotics — $200 млн Series A.
  3. Wispr — $280 млн и модель Canto.
  4. Groq — $350 млн для inference-облака.
  5. Serve Robotics / Grubhub — расширение роботодоставки.
  6. Alibaba / Lingxi Games — продажа игрового актива для высвобождения капитала под ИИ и облако.
- Effective window ended: 2026-08-18 02:35:53 +03:00.

### Независимый аудит
- Явных stale-новостей не обнаружено.
- Source Freshness Proof v1 на первом боевом выпуске сработал нормально.
- Существенные пропуски:
  1. Higgsfield — раунд $400 млн при оценке $5,4 млрд.
  2. Round Hill Music — новые copyright-иски против Anthropic и Suno, связанные с использованием более 500 текстов песен при обучении ИИ.
  3. HappyShrimp — фактический запуск работающего сервиса генерации полной песни по промпту.
     - Важно: июльский анонс HappyShrimp был старым и правильно не подходил по freshness.
     - Пользователь сообщил, что сервис теперь реально запущен и работает.
     - На момент независимой проверки обычный Terra/web discovery продолжал поднимать в основном июльские материалы, где продукт ещё не был открыт.
     - Поэтому HappyShrimp рассматривается как пример возможной blind spot в discovery свежих китайских продуктовых запусков. Факт запуска в этом журнале пока основан на сообщении пользователя и должен быть отдельно перепроверен при появлении индексируемого первичного источника.
- Пограничный пропуск:
  - Google A2A protocol → Agentic AI Foundation. Содержательно заметно, но не классифицировано как безусловный Must Include.

### Оценка
- Freshness: PASS.
- Полнота: PARTIAL.
- Консервативный ориентир recall после учёта HappyShrimp: примерно 6/9 ≈ 67%.
- Вердикт: качество свежести заметно улучшилось, retrieval всё ещё пропускает часть значимых событий.

### Диагноз / гипотезы
- Ошибка 17 августа со stale-источниками после Source Freshness Proof v1 пока не повторилась.
- Остаётся проблема recall.
- Один найденный китайский сюжет может формально сделать региональную health-check зелёной, хотя другой важный продуктовый запуск в Китае может остаться незамеченным.
- Возможная отдельная blind spot: свежие продуктовые релизы в Китае/Азии, которые появляются в официальных сервисах, соцсетях или локальных источниках раньше, чем нормально индексируются глобальным web search.
- Пока не менять 7-й Coverage-slot. Накопить ещё несколько production-наблюдений.

---

---

## 2026-08-19

### Production
- Выпуск опубликован успешно.
- Опубликовано 8 сюжетов: OpenAI/Astra safeguards; PJM/FERC и питание дата-центров; Nvidia/OpenAI/SB Energy в Огайо; Anthropic >$65 млрд annualized revenue; Etched $700 млн; Higgsfield $400 млн; ChatGPT for Teens; Cursor Origin.
- Effective discovery window:
  - start: 2026-08-17 02:35:53 +03:00
  - continuity anchor: 2026-08-18 02:35:53 +03:00
  - end: 2026-08-19 02:35:51 +03:00
- Первые 24 часа — healing overlap для восстановления значимых пропусков предыдущего выпуска.
- Primary: 12/12 search operations.
- Hybrid: 4/4 search operations.
- Primary candidate pool: 10; editorial выбрал 8.
- Production warning: candidate pool перегружен одним издателем — TechCrunch (6).

### Независимый аудит
Метод: независимый Terra/web-поиск на ресурсах ассистента; production API пользователя не использовался.

#### Freshness
- Явных stale-новостей среди опубликованных 8 сюжетов не обнаружено.
- Source Freshness Proof v1 второй боевой день подряд не повторил ошибку 17 августа.
- PJM и Higgsfield датированы 17 августа, но не являются stale: их timestamps находятся внутри предусмотренного healing overlap.
- Higgsfield — положительный пример healing: сюжет был пропущен 18 августа и восстановлен 19 августа.

#### Существенный пропуск
1. Round Hill Music против Anthropic и Suno — copyright-иски из-за обучения ИИ на текстах песен.
   - Reuters timestamp: 2026-08-17 21:52:17 UTC = 2026-08-18 00:52:17 +03:00.
   - Событие находится внутри healing overlap.
   - Масштаб: минимум 500 песен; истец допускает расширение до 10 000+ композиций и потенциальные требования порядка $1 млрд.
   - Сюжет был значимым пропуском уже 18 августа.
   - 19 августа он снова не попал даже в candidate pool.
   - Primary `legal_regulation` выполнил отдельный запрос по regulation/copyright/lawsuits, но вернул 0 кандидатов.
   - Это первый явно повторившийся тематический recall-дефект в серии наблюдений.
   - Источник: https://www.reuters.com/legal/legalindustry/music-publisher-sues-anthropic-suno-over-ai-training-2026-08-17/

#### Пограничные / не обязательные пропуски
- Velaura AI — $110 млн Series A, оценка свыше $1 млрд; Reuters timestamp 2026-08-18 12:01:27 UTC.
  - В candidate pool production не попала.
  - Релевантна AI chips / power efficiency, но на фоне включённого Etched ($700 млн, $21 млрд) не считаю её безусловным Must Include.
  - Это retrieval miss, но не обязательно final-digest miss.
  - Источник: https://www.reuters.com/legal/transactional/chip-designer-velaura-ai-valued-more-than-1-billion-after-funding-round-2026-08-18/
- Google A2A → Agentic AI Foundation остаётся пограничным событием из предыдущего аудита и не входит в строгий Must Include reference set.
- HappyShrimp launch остаётся unresolved blind spot:
  - production снова его не обнаружил;
  - независимый web/Terra-поиск по-прежнему поднимает главным образом июльские материалы, где сервис ещё не был открыт;
  - свежий индексируемый первичный источник с точным timestamp запуска пока не найден;
  - поэтому HappyShrimp не входит в строгий независимо подтверждённый recall denominator, но остаётся важным наблюдением по China/Asia product-launch discovery.

#### Отрицательный контроль
- WSJ опубликовал материал о Q2 OpenAI в 2026-08-18 23:47 UTC.
- Production cutoff соответствует 2026-08-18 23:35:51 UTC.
- Материал вышел примерно через 11 минут после cutoff, поэтому его отсутствие корректно и не считается пропуском.

### Оценка
- Freshness: PASS.
- Полнота: PARTIAL, но заметно лучше предыдущих двух дней.
- Строгий независимо подтверждённый high-signal reference set: 9 событий = 8 опубликованных + Round Hill.
- Ориентировочный strict recall: 8/9 ≈ 89%.
- Если считать Velaura желательным, но не обязательным событием, расширенный ориентир: 8/10 = 80%.
- Вердикт: хороший выпуск по свежести и существенно улучшенная полнота; остаётся один ясный Must Include miss.

### Диагноз / повторяющиеся паттерны
1. **Freshness улучшилась и пока стабильна.**
   - 17 августа: FAIL.
   - 18 августа: PASS.
   - 19 августа: PASS.
   - После Source Freshness Proof v1 stale-дефект два дня подряд не повторяется.

2. **Recall-проблема сохраняется, но локализуется.**
   - 17 августа: крупный infrastructure/business miss.
   - 18 августа: несколько значимых miss.
   - 19 августа: один ясный Must Include miss плюс пограничные события.

3. **Healing overlap работает частично.**
   - Higgsfield, пропущенный 18 августа, успешно восстановлен 19 августа.
   - Round Hill, также пропущенный 18 августа и всё ещё находившийся в healing overlap, не восстановлен.

4. **Legal/copyright — первый подтверждённый повторяющийся тематический дефект.**
   - Round Hill пропущен два выпуска подряд.
   - 19 августа специализированный `legal_regulation` проход завершился без кандидатов, хотя подходящее Reuters-событие существовало внутри effective window.
   - Пока это более сильный сигнал для будущего анализа, чем гипотеза о необходимости менять общий 7-й Coverage-slot.

5. **China/Asia product-launch discovery остаётся подозрением, но доказательств пока недостаточно.**
   - HappyShrimp продолжает не находиться обычным web discovery.
   - Независимая точная дата запуска пока не подтверждена индексируемым источником.

6. **Источник-концентрация требует наблюдения.**
   - 19 августа production сам зафиксировал перегрузку candidate pool материалами TechCrunch.
   - Пока это не вызвало stale-ошибок, но может снижать source diversity.

### Решение на текущем этапе
- Не менять 7-й Coverage-slot.
- Не менять архитектуру по итогам одного нового дня.
- Продолжать наблюдение.
- Особо проверять: legal/copyright recall; healing разных тематик; China/Asia product launches; source concentration; стабильность Source Freshness Proof v1.


---

## 2026-08-20

### Production
- Выпуск опубликован успешно.
- Опубликовано 7 сюжетов:
  1. Google — новые учебные инструменты в Gemini и Поиске.
  2. Amazon — Alexa+ бесплатно на совместимых Fire TV в США.
  3. OpenAI — preview Private Safety Processing для корпоративных клиентов.
  4. TerraPower — проект энергоснабжения AI-дата-центра с тепловым накопителем.
  5. Warp Factories — управление агентной разработкой ПО.
  6. NVIDIA Cosmos 3 Edge — on-device управление роботами.
  7. MWS AI / Rubytech — испытания ПАК с китайскими GPU для российских LLM.
- Publication cutoff: 2026-08-20 02:36:13 +03:00.
- По continuity-контракту предыдущий cutoff: 2026-08-19 02:35:51 +03:00.
- Ориентировочный effective discovery start с 24h healing overlap: 2026-08-18 02:35:51 +03:00.

### Независимый аудит
Метод: независимый Terra/web-поиск на ресурсах ассистента; production API пользователя не использовался.

#### Freshness
- Явных stale-новостей среди опубликованных сюжетов не обнаружено.
- Warp Factories датирован 18 августа и попадает в допустимый healing overlap.
- Остальные проверенные основные сюжеты относятся к 19–20 августа.
- Предварительный verdict по freshness: PASS.

#### Явный существенный пропуск
1. Google / Marvell — крупная сделка по custom AI chips.
   - Reuters timestamp: 2026-08-19 12:38:32 UTC = 2026-08-19 15:38:32 +03:00.
   - Событие находится внутри основного continuity-периода, а не healing overlap.
   - Marvell будет помогать Google разрабатывать custom AI chips; Google получила право приобрести до $12,2 млрд акций Marvell.
   - По условиям сделки Marvell может получить до примерно $120 млрд выручки до fiscal 2033 при выполнении целей.
   - Масштаб и прямое отношение к AI infrastructure/chips делают событие безусловным Must Include.
   - Источник: https://www.reuters.com/technology/marvell-grants-google-122-billion-stock-warrant-custom-chip-deal-2026-08-19/

#### Повторяющийся региональный пропуск
2. Baidu / ERNIE — квартальные результаты и AI-business.
   - Reuters timestamp: 2026-08-18 09:04:52 UTC = 2026-08-18 12:04:52 +03:00.
   - Событие находится внутри healing overlap текущего выпуска.
   - Выручка AI-powered Core business выросла на 25% г/г до 12,5 млрд юаней.
   - Robin Li заявил о намерении вернуть ERNIE на frontier.
   - Этот же сюжет уже был отмечен как азиатский recall miss в аудите 19 августа.
   - На 20 августа он всё ещё не восстановлен.
   - Источник: https://www.reuters.com/world/asia-pacific/chinas-baidu-misses-second-quarter-revenue-estimates-2026-08-18/

#### Россия
- В отличие от 19 августа, российская новость сегодня попала в финальный выпуск:
  MWS AI / Rubytech — испытания ПАК с восемью китайскими GPU для запуска российских LLM.
- Поэтому текущий российский regional recall не выглядит нулевым.

#### Азия
- В финальном выпуске снова нет отдельной азиатской новости.
- Baidu остаётся independently verified high-signal miss.
- Это усиливает ранее зафиксированный паттерн: regional health/search может формально отработать, но крупные AI-business события Азии продолжают выпадать.
- HappyShrimp остаётся отдельной unresolved blind spot по product-launch discovery; независимо подтверждённый точный timestamp запуска всё ещё отсутствует.

#### Пограничный азиатский сигнал
- Yonhap 18 августа сообщила о более чем 3 млрд загрузок семейства Qwen за последние 6 месяцев со ссылкой на Bloomberg / Hugging Face.
- Но базовый отчёт Hugging Face был опубликован 14 августа, то есть до текущего effective window.
- Поэтому этот сюжет не включается в строгий Must Include denominator текущего выпуска.

### Оценка
- Freshness: PASS.
- Полнота: PARTIAL.
- Ясные независимо подтверждённые Must Include misses: Google/Marvell и Baidu.
- Точную recall-долю не фиксировать без полного production candidate pool за 20 августа: в репозитории на момент проверки доступен опубликованный archive index, но не полный diagnostic artifact текущего дня.
- Вердикт: выпуск содержательно нормальный, но два сильных пропуска не позволяют считать полноту высокой.

### Повторяющиеся паттерны после четырёх дней
1. **Freshness после Source Freshness Proof v1 стабилизировалась.**
   - 17 августа: FAIL.
   - 18 августа: PASS.
   - 19 августа: PASS.
   - 20 августа: PASS.

2. **Recall остаётся главной проблемой.**
   - 17 августа: Nvidia/SB Energy miss.
   - 18 августа: Higgsfield, Round Hill, HappyShrimp.
   - 19 августа: Round Hill и Baidu; Higgsfield восстановлен.
   - 20 августа: Google/Marvell и Baidu.

3. **Healing overlap полезен, но не гарантирует восстановление.**
   - Higgsfield успешно healed.
   - Round Hill не healed в следующий допустимый день.
   - Baidu не healed уже во втором доступном выпуске.

4. **Asia recall становится подтверждённым повторяющимся паттерном.**
   - HappyShrimp: product-launch blind spot, пока без независимо подтверждённого timestamp.
   - Baidu: independently verified business/AI miss два выпуска подряд.
   - Проблема выглядит шире, чем только модели и интеграции: выпадают AI-business / earnings / strategy события.

5. **Legal/copyright паттерн остаётся зафиксированным, но Round Hill уже вышел из effective window 20 августа.**
   - Его отсутствие 20 августа больше не считается новым пропуском.

6. **Новые broad infrastructure/business misses тоже возможны.**
   - Google/Marvell — очень крупный AI-chip сюжет внутри основного continuity-периода 20 августа.
   - Значит проблема recall не сводится только к Азии или legal/copyright.

### Решение на текущем этапе
- Не менять архитектуру автоматически.
- Для будущего изменения сначала провести отдельный architecture-wide audit и независимые Terra-эксперименты.
- Наиболее сильные накопленные сигналы для возможной будущей правки:
  1. Asia business/product-launch recall.
  2. Legal/copyright discovery.
  3. Last-mile обнаружение крупных infrastructure/business событий.
- Source Freshness Proof v1 пока не трогать: после внедрения stale-дефект три дня подряд не повторяется.


---

## 2026-08-21

### Production
- Фактический scheduled production-run: GitHub Actions run `32429557166`.
- Recovery не использовался; run завершился успешно и опубликовал выпуск.
- Production commit: `8dc8009197148d8b0346d0804e3b1ab113d811b8` (`Publish AI digest for 2026-08-21`).
- Опубликовано 9 сюжетов:
  1. Google — Preferred Sources для издателей в AI Search / Discover / Google News.
  2. OpenAI — Codex CLI rust-v0.149.0 с dashboard агентов и очередью сообщений между сессиями.
  3. Microsoft / Varonis — CoSnitch, цепочка атак на Copilot Personal.
  4. Binance — Agent OS для анализа рынков и пользовательски авторизованной торговли через AI-агентов.
  5. Meta — приложение Meta AI для Mac с диктовкой и screen-context.
  6. OpenAI / Apple — плагин Apple Messages для ChatGPT.
  7. Ramp — Router для маршрутизации запросов между LLM.
  8. Micron — $10 млрд на Micron Research Labs для памяти, упаковки и AI-инфраструктуры.
  9. xAI / AWS — general availability Grok 4.6 в Amazon Bedrock.
- Publication/search cutoff: `2026-08-21 02:40:00 +03:00`.
- Continuity anchor предыдущего успешного выпуска: `2026-08-20 02:36:13 +03:00`.
- Effective discovery window: `2026-08-19 02:36:13 +03:00` → `2026-08-21 02:40:00 +03:00`.
- Healing overlap: `2026-08-19 02:36:13 +03:00` → `2026-08-20 02:36:13 +03:00`.
- Основной continuity-период: `2026-08-20 02:36:13 +03:00` → `2026-08-21 02:40:00 +03:00`.

### Retrieval / editorial anatomy

#### Primary Recall v2
- Выполнено 12/12 обязательных search operations.
- Финальный Primary candidate pool: 10 кандидатов.
- По направлениям:
  - `global_breaking`: 4 accepted;
  - `major_agencies`: 0;
  - `models_products_agents`: 0;
  - `infrastructure_chips_cloud`: 0;
  - `business_investment_partnerships`: 0;
  - `china_asia_models`: 2 raw candidates, 0 accepted после validator;
  - `china_asia_integrations`: 0;
  - `russia`: 0;
  - `developer_tools`: 2 accepted;
  - `security_safety`: 1 accepted;
  - `legal_regulation`: 0;
  - `independent_missing_events`: 3 accepted.
- `major_agencies` использовал канонический query `latest AI chips data centers investments deals policy security`, но фактически консультировал главным образом старые Bloomberg-страницы и не поднял свежие Reuters-события, существовавшие в окне.
- Primary pool был сильно сконцентрирован на TechCrunch: production warning зафиксировал 7 кандидатов одного издателя.

#### Hybrid completeness
- Выполнено 4/4 search operations.
- Fixed passes:
  - models/products/research → добавлен xAI Grok 4.6 / Amazon Bedrock;
  - infrastructure/business → добавлен Micron $10 млрд;
  - safety/policy/regions → 0 кандидатов.
- Adaptive regional health-check был запущен из-за нулевых Asia и Russia pools:
  - query: `latest major AI Russia China Asia models products partnerships infrastructure`;
  - результат: 0 кандидатов.
- После Hybrid общий candidate pool вырос с 10 до 12.

#### Coverage
- Coverage search **не выполнялся**.
- `audit_needed=false`, потому что после Hybrid/editorial уже было 9 сюжетов при обычной цели 7.
- Проверено направлений: 0 из 6; search operations: 0/7.
- То есть полный по количеству выпуск не получил fallback-проверку, несмотря на нулевые Primary-направления `major_agencies`, infrastructure, business, legal, Russia и Asia-integrations.

#### Editorial
- После Primary editorial выбрал 7 из 10 кандидатов.
- После Hybrid editorial выбрал 9 из 12.
- Выбраны: `cand-001`–`cand-007`, `cand-011`, `cand-012`.
- Редакционно исключены:
  - `cand-008` AWS Kiro CLI 2.19.0 — инкрементальный релиз;
  - `cand-009` Meta Pocket — экспериментальный игровой продукт;
  - `cand-010` Ramp data по OpenAI vs Anthropic — ограниченный рыночный индикатор.
- Это корректные **editorial rejections**, а не retrieval misses.

### Независимый аудит
Метод: независимый Terra/web-поиск на ресурсах ассистента по тому же effective window; production API пользователя не использовался.

#### Freshness
- Все 9 опубликованных сюжетов находятся внутри effective window.
- Source Freshness Proof отработал дважды: 10/10 Primary-кандидатов и затем 12/12 объединённых кандидатов получили подтверждённую freshness; исключений outside-window или unverified не было.
- Независимая проверка не выявила stale-сюжетов среди опубликованных материалов.
- CoSnitch датирован 19 августа и находится в healing overlap.
- Grok 4.6 / Bedrock — material update: сама модель существовала раньше, но general availability через Bedrock является новым событием внутри окна.
- Verdict по freshness: PASS.

### Явные Must Include misses

1. **Broadcom — более $60 млрд долгового финансирования для новой AI-chip financing схемы.**
   - Reuters сообщил 20 августа, что Broadcom ведёт переговоры о привлечении более $60 млрд долга для AI-chip financing deal, которая должна поддержать Anthropic и другие компании; обсуждаемый общий объём структуры мог достигнуть примерно $100 млрд.
   - Reuters-синдикация MarketScreener показывает публикацию `2026-08-21 00:20 +04:00`, то есть примерно `2026-08-20 20:20 UTC` / `23:20 +03:00` — примерно за 3 часа 20 минут до production cutoff.
   - Событие находится в основном continuity-периоде.
   - В production candidate pool его нет.
   - Классификация: **retrieval miss / Must Include**.
   - Источник: https://www.reuters.com/technology/broadcom-seeks-more-than-60-billion-latest-ai-debt-deal-bloomberg-news-reports-2026-08-20/

2. **Alibaba — квартальные результаты, 45% рост AI/cloud revenue и резкое наращивание AI capex.**
   - Reuters: чистая прибыль снизилась на 75%, при этом AI cloud and compute services revenue выросла на 45% до 48,44 млрд юаней; capex вырос на 75% до 67,68 млрд юаней, компания масштабирует собственные AI-чипы и сохраняет план 380 млрд юаней инвестиций в AI/cloud.
   - Reuters-синдикация MarketScreener показывает публикацию `2026-08-20 19:09 +04:00` = примерно `15:09 UTC` / `18:09 +03:00`, уверенно до cutoff.
   - AP независимо подтверждает ключевые цифры и AI-инфраструктурный контекст.
   - Событие находится в основном continuity-периоде.
   - В production candidate pool его нет; Asia regional health-check также вернул 0.
   - Классификация: **retrieval miss / Must Include**.
   - Источник Reuters: https://www.reuters.com/business/retail-consumer/alibaba-beats-quarterly-revenue-estimates-2026-08-20/
   - Источник AP: https://apnews.com/article/8a30302d23a96fc7b9aab664b9c1897d

3. **Google / Marvell — custom AI chips и warrant до $12,2 млрд.**
   - Этот сюжет уже был Must Include miss 20 августа.
   - Reuters timestamp из предыдущего независимого аудита: `2026-08-19 12:38:32 UTC` = `15:38:32 +03:00`.
   - 21 августа событие всё ещё находится внутри предусмотренного healing overlap.
   - Оно снова отсутствует и в Primary, и в Hybrid, и в финальном выпуске.
   - Классификация: **retrieval miss / повторный Must Include / healing failure**.
   - Это второй подряд выпуск, в котором bounded overlap мог восстановить сюжет, но не восстановил.
   - Источник: https://www.reuters.com/technology/marvell-grants-google-122-billion-stock-warrant-custom-chip-deal-2026-08-19/

### Пограничные misses / дополнительные сигналы

1. **Brazil AI supercomputer push — 2,3 млрд реалов ($444,2 млн).**
   - Reuters 20 августа: 1,3 млрд реалов на инфраструктуру с Huawei/iFlytek и 1 млрд реалов на отдельный AI-суперкомпьютер, где ожидается Nvidia.
   - Событие относится к AI infrastructure / sovereign AI и находится до cutoff.
   - Классификация: **retrieval miss, пограничный Must Include**; в строгий denominator не включён из-за меньшего глобального веса относительно Broadcom/Alibaba/Google-Marvell.
   - Источник: https://www.reuters.com/world/americas/brazil-launches-ai-supercomputer-push-splits-projects-between-chinese-us-firms-2026-08-20/

2. **Anthropic — изменение enterprise data-retention policy.**
   - Reuters 20 августа: компания планирует оставить 30-дневное хранение, но дать enterprise-клиентам возможность держать данные в собственной cloud infrastructure; в разработке участвовали более 100 клиентов, включая Salesforce.
   - Reuters-синдикация даёт время примерно `19:31 UTC`, до cutoff.
   - Событие заметно как прямой конкурентный ответ на OpenAI Private Safety Processing, но это пока планируемое изменение, а не полностью развернутый продукт.
   - Классификация: **retrieval miss / borderline**.
   - Источник: https://www.reuters.com/business/anthropic-plans-change-enterprise-data-retention-policy-source-says-2026-08-20/

3. **Guidelight AI Standards — исследование containment у OpenAI, Anthropic, Meta, Google и xAI.**
   - Reuters 19 августа: исследование оценило безопасность и containment практики пяти компаний; OpenAI и Anthropic получили C+, Meta — F.
   - Находится в healing overlap.
   - Содержательно важно для safety, но это report/study, а не самостоятельное крупное действие компании.
   - Классификация: **retrieval miss / borderline**, не входит в strict denominator.
   - Источник: https://www.reuters.com/technology/artificial-intelligence/ai-firms-cant-yet-contain-what-theyve-built-study-finds-2026-08-19/

### Отдельный validator / duplicate дефект
- `china_asia_models` **нашёл** два свежих кандидата:
  1. Qwen3.8-27B на QwenCloud — recommendation `include`;
  2. GLM-5.3 direct-supply availability — recommendation `consider`.
- Оба были отвергнуты downstream validator с одинаковой причиной: `primary source URL уже опубликован в архиве`.
- URL — общий rolling changelog: `https://docs.qwencloud.com/changelog/models`.
- В архиве этот URL действительно уже использовался 11 августа, но для **другого события**: Qwen3.7-Text-Embedding.
- Следовательно, это не обычный semantic duplicate, а **false duplicate из-за exact-URL dedupe на изменяемой changelog-странице**.
- Производственный Primary сам зафиксировал для Qwen3.8 `archive_status=none` и отсутствие совпадающего события в supplied archive, после чего общий validator всё равно выбросил его по URL.
- Независимый web подтверждает существование Qwen3.8-27B и отдельную модель/дистрибуцию, но исходный open-weight релиз относится к более ранней дате; поэтому конкретный QwenCloud update 19 августа не включается в strict Must Include denominator.
- Для GLM-5.3 независимый китайский источник фиксирует запуск API 19 августа; это дополнительный сигнал возможного Asia product-availability blind spot, но не строгий Must Include текущего выпуска.
- Классификация: **pipeline false-duplicate / validator defect**, не retrieval miss и не editorial rejection.

### Россия
- Primary `russia` и Hybrid regional health-check вернули 0 кандидатов.
- Независимый поиск по российским источникам за то же окно не выявил события масштаба Must Include.
- Поэтому отсутствие российской новости в финальном выпуске 21 августа **не классифицируется как подтверждённый retrieval miss**.
- Это пример, почему нулевой regional pool нельзя автоматически считать дефектом.

### Legal / copyright
- Primary `legal_regulation` вернул 0 кандидатов.
- Независимый поиск в текущем окне не выявил нового legal/copyright события уровня Round Hill.
- Round Hill уже находится вне effective window и не считается новым пропуском.
- Следовательно, сегодня нет нового подтверждённого legal/copyright miss; исторический повторяющийся паттерн остаётся в журнале, но не усиливается новым случаем.

### Source concentration
- Production warning: 7 из 12 кандидатов общего candidate pool происходили из TechCrunch.
- В финальном выпуске 5 из 9 сюжетов имеют TechCrunch как основной источник.
- При этом свежие Reuters-события Broadcom и Alibaba отсутствовали полностью, а `major_agencies` не дал ни одного кандидата.
- Это уже не просто косметическая source-diversity проблема: высокая концентрация совпала с пропуском нескольких более крупных high-signal business/infrastructure событий.

### Оценка
- **Freshness: PASS.**
- **Completeness: PARTIAL.**
- Консервативный strict high-signal reference set: 12 событий = 9 опубликованных + 3 independently verified Must Include misses (Broadcom, Alibaba, Google/Marvell).
- Ориентировочный **strict recall: 9/12 = 75%**.
- Пограничные Reuters-сигналы Brazil supercomputers, Anthropic data-retention и Guidelight containment study в строгий denominator не включены.
- Вердикт: количество опубликованных сюжетов высокое, но оно скрывает существенно более слабую полноту по high-signal business/infrastructure и Asia-business событиям.

### Диагноз / повторяющиеся паттерны после пяти дней
1. **Freshness остаётся стабильной.**
   - 17 августа: FAIL.
   - 18–21 августа: четыре последовательных PASS.
   - Source Freshness Proof v1 не показывает причин для вмешательства.

2. **Recall остаётся основной системной проблемой и сегодня снова проявился не единичным miss.**
   - Одновременно пропущены Broadcom, Alibaba и Google/Marvell.
   - Два из трёх — крупные chips/infrastructure/business события Reuters; одно — крупное Asia AI-business/earnings событие Reuters + AP.

3. **Infrastructure/business recall теперь подтверждён как повторяющийся cross-day паттерн.**
   - 17 августа: Nvidia/SB Energy.
   - 20 августа: Google/Marvell.
   - 21 августа: Google/Marvell не healed + Broadcom >$60 млрд.
   - При этом текущие `major_agencies`, `infrastructure_chips_cloud` и `business_investment_partnerships` все завершились без accepted candidates.

4. **Asia business/earnings blind spot подтверждается ещё одним независимым событием.**
   - Baidu был independently verified miss 19 и 20 августа.
   - 21 августа Alibaba, один из крупнейших AI/cloud игроков Китая, выпал из candidate pool несмотря на свежие Reuters и AP материалы.
   - Hybrid regional query всё ещё ориентирован на `models products partnerships infrastructure` и явно не содержит earnings/business/strategy semantics.

5. **Healing overlap работает не гарантированно.**
   - Higgsfield ранее был успешно healed.
   - Round Hill не был healed.
   - Google/Marvell теперь второй день подряд не восстановлен, хотя 21 августа ещё находился в overlap.

6. **Source concentration становится более содержательным риском.**
   - 7/12 candidate pool — TechCrunch.
   - Одновременно свежий Reuters high-signal слой оказался недопредставлен.

7. **Обнаружен новый отдельный validation-дефект: mutable-source URL dedupe.**
   - Rolling changelog QwenCloud содержит разные события на одном URL.
   - Exact-URL archive dedupe способен выбрасывать новое событие как duplicate только из-за повторного использования страницы.
   - Это отличается от обычного recall miss: discovery сработал, но downstream validator уничтожил найденное событие.

8. **Coverage по количественному trigger может не видеть качественные тематические дыры.**
   - 9 выбранных сюжетов сделали `audit_needed=false`.
   - Поэтому 0 Coverage searches были выполнены, хотя несколько ключевых Primary-направлений были пустыми и независимый reference set содержит три Must Include misses.
   - Это пока наблюдение об interaction между trigger и recall, а не готовое решение менять 7-й slot.

### Решение на текущем этапе
- **Автоматически менять production-архитектуру всё ещё нельзя.**
- Но после аудита 21 августа накопленных данных уже достаточно, чтобы перейти от пассивного наблюдения к **отдельному целевому architecture experiment**.
- Причина: теперь есть повторяемые и независимо подтверждённые паттерны минимум в двух классах — `infrastructure/business high-signal recall` и `Asia business/earnings`, плюс детерминированный false-duplicate на mutable changelog URL.
- Перед любым patch требуется отдельный Terra-эксперимент на нескольких сохранённых окнах и architecture-wide audit, как требует проектный контракт.
- Эксперимент должен проверить не «ещё один общий broad search», а конкретные гипотезы:
  1. почему `major_agencies` не поднимает свежие Reuters при формально корректном source routing;
  2. хватает ли текущих semantics Asia-проходов для earnings/business/strategy;
  3. как exact-URL dedupe должен вести себя для rolling changelog / release-feed страниц без ослабления защиты от настоящих дублей;
  4. нужен ли дополнительный quality/gap trigger для Coverage, когда выпуск численно полный, но обязательные retrieval-направления нулевые.
- До результатов такого эксперимента **не вносить retrieval-патч**.
- Source Freshness Proof v1 не трогать.


## Текущая серия наблюдений

| Дата | Freshness | Полнота | Ключевой результат |
|---|---|---|---|
| 2026-08-17 | FAIL | FAIL | stale Anthropic + пропущен Nvidia/SB Energy |
| 2026-08-18 | PASS | PARTIAL | stale нет; пропущены Higgsfield, copyright lawsuit и HappyShrimp launch |
| 2026-08-19 | PASS | PARTIAL | strict recall 8/9; Higgsfield healed, Round Hill повторно пропущен |
| 2026-08-20 | PASS | PARTIAL | российская новость вошла; пропущены Google/Marvell и Baidu; Asia miss повторяется |
| 2026-08-21 | PASS | PARTIAL | strict recall ~75%; пропущены Broadcom, Alibaba и повторно Google/Marvell; найден false duplicate QwenCloud |


## Контролируемый retrieval-эксперимент 2026-08-21: пункты 1–2

Цель: проверить две накопленные гипотезы без изменения production-кода и без новых вызовов production API пользователя:
1. почему `major_agencies` не поднимает свежие Reuters/high-signal события;
2. достаточно ли текущих China/Asia semantics для AI business / earnings / strategy.

### Ограничение воспроизводимости
- Production baseline взят из фактического artifact 21 августа, где поиск выполнял `gpt-5.6-terra`.
- В текущем интерактивном окружении отдельный инструмент Terra не экспонирован, поэтому независимые query-replay выполнены доступным web search ассистента. Эти replay нельзя выдавать за чистый Terra A/B-тест.
- Поэтому выводы делятся на: факты из production Terra artifact и независимое подтверждение query semantics через web search.

### Эксперимент 1: `major_agencies`

Production query:
`latest AI chips data centers investments deals policy security`

Фактический production Terra-result 21 августа:
- 18 URL в search result pool;
- 12 Bloomberg;
- 6 AP;
- 0 Reuters;
- 0 FT;
- accepted candidates: 0;
- большинство релевантных страниц относились к марту–маю и были отброшены как outside-window.

При этом в effective window независимо существовали как минимум:
- Google / Marvell;
- Broadcom >$60 млрд AI-chip financing;
- Alibaba AI/cloud earnings.

Независимый replay текущего production query уже после выпуска поднял Broadcom, Nvidia/SB Energy и Google/Marvell, но не Alibaba. Это означает, что исходная формулировка не является принципиально неспособной находить chips/infrastructure, однако retrieval/ranking нестабилен, а business/earnings semantics недостаточно выражены.

Проверенный расширенный query:
`latest AI chips infrastructure financing earnings business deals policy security`

Независимый replay этого варианта поднял одновременно:
- Broadcom >$60 млрд;
- Alibaba earnings / AI infrastructure spending;
- Nvidia / SB Energy;
- Google / Marvell.

**Вывод 1:** гипотеза подтверждена частично.
- Простая замена `data centers investments` на более содержательные `infrastructure financing earnings business` заметно улучшает тематический охват на текущем контрольном наборе без увеличения search budget.
- Но query change сам по себе не объясняет и не гарантирует устранение production Terra failure: исходный query при независимом replay способен находить несколько пропущенных chips-событий, тогда как фактический production Terra-run не нашёл ни одного Reuters.
- Следовательно, у `major_agencies` есть два слоя риска: **semantic undercoverage** и **ranking/source-pool instability**. Второй нельзя считать исправленным только переписыванием query.

### Эксперимент 2: China / Asia business, earnings, strategy

Production queries:
- models: `latest China Asia AI model releases agents Qwen DeepSeek`;
- integrations: `latest China Asia AI integrations partnerships deployments`;
- Hybrid regional: `latest major AI Russia China Asia models products partnerships infrastructure`.

Фактический результат 21 августа:
- models-pass нашёл Qwen3.8 и GLM-5.3, то есть model/product discovery в принципе работает;
- integrations-pass: 0 accepted;
- Hybrid regional: 0 candidates;
- Alibaba earnings не найден;
- Baidu earnings ранее также выпадал два выпуска подряд.

Независимый replay текущего integrations query поднял прежде всего deployment/integration сюжеты (например Pony.ai и другие deployment-сигналы), но не Alibaba/Baidu earnings.

Проверены варианты с добавлением business semantics. Наиболее полезный контрольный query:
`latest China Asia AI business earnings strategy revenue cloud`

При ограничении на Reuters/AP он поднял:
- Alibaba 20 августа;
- Baidu 18 августа;
- дополнительные менее приоритетные business/earnings события, которые downstream significance filter способен отсечь.

Более сбалансированный вариант, сохраняющий часть partnership semantics:
`latest China Asia AI earnings revenue strategy cloud partnerships`

Он стабильно поднимает Alibaba и related China-AI business layer; Baidu остаётся видимым в выдаче/связанных результатах, но менее устойчиво, чем при варианте с явным `business`.

**Вывод 2:** гипотеза подтверждена сильно.
- Текущие Asia queries семантически ориентированы на модели, продукты, интеграции, партнёрства и инфраструктуру.
- В них нет прямых сигналов `earnings`, `revenue`, `business`, `strategy`, поэтому Baidu/Alibaba misses закономерны, а не выглядят случайностью одного дня.
- Менять `china_asia_models` не следует: 21 августа этот pass нашёл свежие Qwen/GLM события.
- Наиболее логичная точка будущего изменения — второй Asia-pass или его роль: добавить business/earnings/strategy semantics, сохранив model pass отдельным.

### Итог экспериментов 1–2

1. **`major_agencies`: PASS для гипотезы о необходимости расширить business/earnings semantics, но PARTIAL для гипотезы, что одной правки query достаточно.** Нужен отдельный архитектурный разбор ranking/source-pool поведения и source-health criteria.
2. **China/Asia business/earnings: PASS.** Семантическая blind spot воспроизводится и устраняется в независимом query test добавлением business/earnings/revenue/strategy terms без дополнительного search slot.
3. Эти результаты уже достаточны, чтобы перейти к architecture-wide audit конкретного будущего patch по пунктам 1–2.
4. Production-код в рамках этого эксперимента не менялся.
5. Пункты 3 (mutable changelog dedupe) и 4 (Coverage quality/gap trigger) остаются отдельными незавершёнными экспериментами.

## Что наблюдать дальше

После экспериментов 1–2 пассивное ожидание по этим двум гипотезам больше не требуется. Следующий шаг для них — architecture-wide audit конкретной схемы будущего patch, но production-код до такого аудита не менять.

Продолжать ежедневный аудит и отдельно завершить ещё две экспериментальные линии:
- является ли mutable-changelog URL dedupe воспроизводимым false-duplicate классом на других release feeds;
- может ли quality/gap trigger Coverage повышать recall на численно полных выпусках без превращения в ещё один общий broad search.

Параллельно наблюдать:
- продолжает ли Source Freshness Proof стабильно исключать stale;
- повторяется ли TechCrunch concentration и коррелирует ли она с выпадением agency/high-signal событий;
- остаётся ли Russia zero-pool содержательно корректным или появляются независимо подтверждённые российские misses;
- подтверждают ли следующие production-дни улучшенную формулировку для agency/Asia на новых, неиспользованных в эксперименте событиях.

До architecture-wide audit и отдельного решения retrieval-код не менять.

## Архитектурная проверка и решение 2026-08-21

После сравнения с regression fixtures 2026-08-11, 2026-08-12 и 2026-08-13, историей production 17–21 августа и отдельным assistant-side query replay принято более консервативное решение, чем первоначальная идея локального 13-го agency rescue.

- `major_agencies` получает расширенный обязательный query `latest AI chips infrastructure financing earnings business deals policy security` внутри существующего Reuters/AP/Bloomberg/FT API route.
- `china_asia_models` не меняется.
- второй China/Asia pass сохраняет integrations/partnerships/deployments и дополнительно получает business/earnings/revenue/strategy semantics через query `latest China Asia AI business earnings revenue strategy cloud partnerships deployments`.
- `russia` остаётся отдельным обязательным Primary slot.
- Hybrid adaptive slot и Coverage не перераспределяются.
- Primary остаётся 12-search, общий worst-case ceiling остаётся 23 searches.
- От отдельного 13-го `major_agencies` rescue пока отказались: fixture 2026-08-13 уже показывает, что source-focused natural-language semantics способны восстанавливать контрольные события без увеличения search budget. Если после этой правки тот же класс agency Must Include miss повторится, это будет основанием для отдельного bounded-rescue эксперимента.
- Source Freshness Proof v1 не меняется.

Подробный эксперимент хранится в `automation/audits/experiments/2026-08-21-agency-asia-recall.md`, machine-readable regression contract — в `automation/fixtures/recall/2026-08-21-agency-asia.json`.

Ежедневный независимый аудит следует сохранить как постоянный внешний контроль качества после успешного production-выпуска. Он не должен становиться частью платного production retrieval и не должен автоматически менять архитектуру. Его задачи: обновлять этот журнал, проверять Freshness/Completeness, Must Include misses, source concentration, Asia/Russia recall и повторение известных дефектов. Архитектурные изменения по журналу допускаются только после повторяющегося паттерна и отдельного эксперимента.
