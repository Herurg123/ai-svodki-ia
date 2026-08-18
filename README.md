# ИИ-Сводки

Репозиторий production-конвейера ежедневных аналитических выпусков об
искусственном интеллекте. GitHub хранит редакционный архив и публикуемый
статический сайт; успешный выпуск собирается, проверяется, фиксируется в
`main` и только затем синхронизируется на FTP.

Публичные адреса:

- [Дзен](https://dzen.ru/rybv)
- [сайт выпусков](https://rybalka.one/posts/)
- [RSS для Дзена](https://rybalka.one/posts/rss.xml)
- [sitemap](https://rybalka.one/posts/sitemap.xml)

## Текущее состояние production

Production работает только из ветки `main`, использует часовой пояс
`Europe/Moscow` и нормализует время выпуска к 06:00 МСК. Пропущенные
календарные дни допустимы. Каноническая continuity-точка исследования остаётся
`search_cutoff_at` последнего успешно опубликованного выпуска, а правой границей
служит cutoff, зафиксированный непосредственно перед текущим research.
Нормализованное `published_at` 06:00 МСК не создаёт слепую зону между
запусками.

Чтобы крупный материал, пропущенный предыдущим выпуском, не исчезал навсегда,
fresh Primary Recall v2 использует **effective discovery window** с ограниченным
24-часовым overlap перед continuity anchor. Сам архивный `search_cutoff_at` назад
не двигается. Уже опубликованные URL и события отсекаются антидублями; overlap
не является неограниченным backfill и не разрешает повторную публикацию старых
сюжетов. При этом search query теперь **continuity-first**: первые 24 часа
расширенного effective window остаются допустимым healing overlap, но даты
поисковой строки и ranking в первую очередь ориентируются на основной период от
continuity anchor до текущего cutoff. Так overlap лечит старые пропуски, не
вытесняя свежие события нового выпуска.

| Workflow | Назначение |
|---|---|
| `.github/workflows/ci.yml` | Бесплатные офлайн-проверки pull request и `main`: компиляция, unit-тесты, редакционный и production-контракты, архив, RSS, sitemap и Schema.org. |
| `.github/workflows/daily-production.yml` | Gate, Primary Recall v2, независимый hybrid completeness, editorial, ограниченный coverage audit, обложка, сборка сайта, commit в `main` и вызов FTP-деплоя. |
| `.github/workflows/repository-cleanup.yml` | Ежедневная очистка в 01:43 МСК: компактация архива и удаление публичных выпусков старше 32 дней. |
| `.github/workflows/repository-hygiene.yml` | Отдельная инженерная уборка GitHub в 15:43 МСК: старые merged-ветки, безопасно классифицированные Actions artifacts и orphaned workflows; исходники и старые runs только диагностируются. |
| `.github/workflows/deploy-posts.yml` | Синхронизация точного состояния `posts/` выбранного commit на FTP, включая контролируемое удаление исчезнувших файлов. |

Число unit-тестов может расти; источником точного набора проверок остаётся
[`ci.yml`](.github/workflows/ci.yml).

## Постоянный baseline старого поиска

Полный production-репозиторий непосредственно **до** включения hybrid
completeness сохранён навсегда как аналитическая и rollback-точка:

- branch: `archive/search-baseline-pre-hybrid-2026-08-09`;
- commit: `d926a3abf8b9443f58f303d984ef79fdc289fc3e`;
- manifest: `automation/archive/search-baselines/2026-08-09-pre-hybrid.md`.

Commit SHA является канонической content-addressed идентичностью старой
механики, а archive-ветка — постоянным человекочитаемым указателем. Ветка не
используется для разработки, не двигается на новые commits и не удаляется
repository hygiene: в policy она отдельно классифицируется как `protected` с
причиной `permanent_archive_branch`. По этой точке можно анализировать старые
выпуски, воспроизводить логику поиска и сравнивать будущие retrieval-изменения.

## Ежедневный производственный цикл

1. Gate проверяет RSS и живую страницу до любых платных API-вызовов.
2. Архив и временное окно проверяются относительно последнего успешного
   выпуска. Наличие его канонических файлов в GitHub остаётся жёстким gate;
   проверка статьи и обложки на живом сайте выполняется как диагностика и при
   временной сетевой/FTP/CDN-недоступности даёт warning, но не срывает сборку
   нового независимого выпуска. Каноническая continuity-точка сохраняется как
   предыдущий `search_cutoff_at`; fresh Primary может смотреть максимум на 24
   часа раньше неё только для healing пропусков.
3. Свежий основной research выполняет **Primary Recall v2**. Жёсткий primary-
   бюджет остаётся равен **12 Web Search search operations**, но расходуется
   детерминированно: Python-orchestrator запускает ровно двенадцать обязательных
   Responses-вызовов с ролями `global_breaking`, `major_agencies`,
   `models_products_agents`, `infrastructure_chips_cloud`,
   `business_investment_partnerships`, `china_asia_models`,
   `china_asia_integrations`, `russia`, `developer_tools`, `security_safety`,
   `legal_regulation`, `independent_missing_events`.
4. Каждый primary-pass обязан сделать ровно **один `action.type=search` и один
   логический search query**. Это не то же самое, что `max_tool_calls=1`:
   `open_page` и `find_in_page` тоже являются hosted tool calls. Поэтому после
   единственного поиска pass может использовать до трёх навигационных действий
   для проверки даты и фактов источника. Диагностика считает search operations,
   logical queries, total tool items и navigation items раздельно. Второй search
   или batched multi-query считается нарушением контракта.
   Responses-output ceiling одного Primary pass — 6000 tokens; это headroom для reasoning/JSON после уже выполненного поиска и не увеличивает 12-search budget.
5. Primary работает по принципу **discovery-first**. На retrieval-этапе
   проверяемое потенциально важное событие можно сохранить как `consider`, если
   окончательная редакционная значимость ещё не очевидна. После каждого
   прохода кандидаты проходят существующий `story_coverage` validator:
   effective window, freshness, verification, legal/curiosity и URL/semantic
   dedupe. Финальный `independent_missing_events` получает компактный список уже
   найденного и ищет именно крупные отсутствующие события.
6. Broad safety nets `global_breaking` и `independent_missing_events` работают
   без API domain filter. `major_agencies` остаётся дополнительным high-signal
   проходом по Reuters, AP, Bloomberg и FT. Фактический query во всех
   Primary-направлениях должен быть короткой date-free natural-language фразой
   с relative-freshness cue (`latest`/`recent`/`current`/`breaking`). Календарные
   даты, годы, названия месяцев, `after:`/`before:`, длинные Boolean `OR`-цепочки,
   скобки и огромные списки компаний в query запрещены. Полное effective window
   остаётся строгой post-retrieval границей допустимости кандидата; `latest` сам
   по себе не считается доказательством свежести.
   Для `major_agencies` production использует Terra-проверенный короткий query `latest AI chips data centers investments deals policy security`; publisher routing задаётся API domain filter и не увеличивает 12-search budget.
7. Китай/Азия намеренно разделены на два прохода. Исторический эксперимент на
   окне выпуска 2026-08-11 показал, что одна широкая China/Asia-проверка
   обнаружила 5 из 6 контрольных событий, но пропустила продуктовую интеграцию
   Apple/Qwen; отдельный `china_asia_integrations` поднял шестое событие без
   увеличения 12-search primary-бюджета. Regression fixture хранится в
   `automation/fixtures/recall/2026-08-11.json`.
8. Инцидент 2026-08-12 хранится отдельным regression fixture
   `automation/fixtures/recall/2026-08-12.json`: scheduled run `31548550639`
   завершил все 12 search operations, получил ложный нулевой pool и затем упал
   на несовместимом runtime `research_input`. Fixture закрепляет свежие Reuters-
   контроли IBM/Together AI/Nvidia, Nvidia Nemotron/NeMo и CoreWeave, а также
   bounded backfill-контроль Meta Muse Glimmer.
9. Live run `31566813147` выявил следующий класс проблемы: Primary Recall,
   editorial и coverage завершились, но `major_agencies` не имел ни одного
   consulted source, а candidate pool был практически целиком собран из
   Wikipedia/Reddit/arXiv. Перед публикацией действует минимальный fail-closed
   **source-health gate**: `major_agencies` обязан иметь хотя бы один consulted
   source, а суммарные diagnostics двенадцати pass должны содержать минимум два
   consulted URL вне Wikipedia, Reddit и arXiv. Это не общий whitelist и не
   квота на кандидатов; это защита от очевидно деградировавшего retrieval.
10. Тот же live run обнаружил metadata-seam: внутренний trusted
    `--research-input` свежего Primary Recall legacy generator помечал как
    `editorial_from_saved_research`, хотя diagnostics корректно содержали 12
    свежих searches. Перед artifact validation normalizer канонизирует
    доказанный fresh Primary в `pipeline=primary_recall_v2_then_editorial` и
    `research.settings.source=trusted_runtime_primary_recall`. Caller-supplied
    recovery/editorial input такого rewrite не получает.
11. Все двенадцать primary-направлений обязательны. Технический сбой или
    отсутствие ровно одного завершённого search operation в любом слоте делает
    fresh primary красным и **не** может быть переинтерпретировано как «новостей
    мало». Успешно выполненный pass вправе вернуть ноль кандидатов. Диагностика
    сохраняет фактические queries, consulted sources, raw candidates, model
    rejections и validator rejections каждого направления.
12. Обычный `maximum_candidates` применяется **только после завершения всех 12
    обязательных проходов**. До этого валидные уникальные события собираются во
    временный расширенный discovery-pool. Финальный cap сначала сохраняет
    сильнейший уникальный вклад каждого направления, а оставшиеся места заполняет
    общим ранжированием. Поэтому ранние broad-поиски не могут занять все места до
    China/Asia, Russia, security, legal или missing-events. Это fairness
    candidate-пула, а не квота на опубликованные сюжеты; diagnostics отдельно
    показывают полный validated pool и события, отброшенные только финальным cap.
13. Primary сохраняет диагностический research artifact в preview, а рабочую
    копию для существующего generator/editorial передаёт через доверенный
    ignored runtime ingress `automation/fixtures/research/.runtime/`. Это
    сохраняет старый security guard `--research-input`: произвольные preview-
    пути не разрешены. Только внутренний `.runtime` input может сохранить
    effective overlap-window при sanitation/editorial validation. Caller-supplied
    `--research-input` по-прежнему означает recovery/editorial rerun и не
    оплачивает fresh primary.
14. После **свежего** primary запускается отдельный `hybrid completeness` v1.
    Он не заменяет primary, а остаётся независимой страховкой. Три фиксированных
    прохода получают ровно по одному search operation: (1)
    models/products/agents/research, (2) infrastructure/chips/business, (3)
    safety/security/policy/major regional gaps. После них детерминированно
    считаются три тематических кластера; если хотя бы один полностью пуст в
    объединённом primary + completeness пуле, разрешается **один** adaptive gap
    search. Жёсткий потолок слоя — 4 search operations, обычный расход — 3.
    Hybrid не имеет API domain filter и тоже может использовать ограниченную
    навигацию после своего единственного search каждого прохода. Его query
    discipline теперь также continuity-first: даты берутся от начала основного
    периода после 24-часового healing overlap до текущего cutoff, при этом
    обнаруженный overlap-кандидат всё ещё может пройти обычную проверку.
15. Hybrid-кандидаты проходят тот же строгий `story_coverage` validator,
    дедупликацию по URL/событию и лимит пула. Editorial повторяется только если
    принят хотя бы один новый кандидат. Объединённый research для rerun также
    проходит через доверенный `.runtime` ingress. Caller-supplied
    `--research-input` recovery не запускает completeness рекурсивно. Если сам
    completeness или его editorial-rerun технически ломается, baseline primary
    artifact сохраняется или восстанавливается.
16. Если после primary + hybrid достойных сюжетов всё ещё меньше обычной цели,
    выполняется прежний обязательный coverage audit: шесть отдельных
    тематических Web Search-проходов и один резервный слот. Production targeted
    passes получают одну search operation и небольшой navigation allowance для
    проверки страниц. Исторические multi-search callers сохраняют прежний hard
    tool-call cap. Coverage query discipline совпадает с Primary/Hybrid:
    основной continuity-период имеет поисковый приоритет, первые 24 часа
    effective window остаются только healing overlap. Если обязательное
    направление технически не завершено, резерв тратится на его повтор. Если
    все шесть завершены, но итоговый пригодный пул всё ещё нулевой, тот же
    седьмой search становится `high_signal_recall_sentinel` версии 7.
17. `gpt-image-2` создаёт одну PNG-обложку 1536×864; валидатор проверяет её
    технический контракт.
18. Legacy-staging исторических обложек работает как best-effort слой
    совместимости: его предупреждение само по себе не блокирует выпуск.
    Канонический build и последующие валидаторы всё равно обязаны подтвердить,
    что все реально используемые страницы и изображения присутствуют.
19. Кандидат сайта получает RSS, sitemap и Schema.org и проходит офлайн-
    валидацию.
20. Только проверенное состояние записывается одним commit в `main`, после чего
    `deploy-posts.yml` разворачивает именно этот SHA.

Primary Recall v2 имеет hard cap `12`, hybrid completeness — hard cap `4`, а
fallback coverage — до `7` только для всё ещё короткого/нулевого пула. Поэтому
теоретический worst case остаётся **23 завершённых `search` operations**. Полный
день не оплачивает тяжёлый six-direction audit после того, как primary + hybrid
уже дали обычный выпуск. Служебные `open_page` и `find_in_page` видны в
диагностике и увеличивают общее число hosted tool calls, но **не** считаются
поисковыми операциями и не повышают потолок 23 searches.

Шесть обязательных направлений fallback coverage audit не меняются:

1. `security_world`
2. `security_russia`
3. `security_asia`
4. `legal_copyright_scraping`
5. `curiosity`
6. `general_coverage_gaps` — авторитетный last-mile sweep первоисточников,
   агентств, судов и регуляторов с доменным фильтром API.

Седьмой Web Search сначала резервируется для повтора первой незавершённой
обязательной проверки. Если повтор не нужен и после всех шести направлений
пригодный пул равен нулю, седьмой вызов используется как source-agnostic
high-signal recall sentinel v7. Его адресный запрос `OpenAI cybersecurity <UTC
 date>` сохранён как аварийный regression-probe подтверждённого класса security-
пропусков. Для sentinel API-доменный фильтр не используется; пригоден любой
надёжный первичный источник, крупное агентство либо авторитетное
технологическое/деловое СМИ при соблюдении обычных правил окна, верификации,
значимости и дедупликации.

Короткий выпуск допускается только после фактического завершения всех шести
fallback-направлений. Пустой результат отдельного направления нормален и даёт
`complete_with_gaps`; технические `partial`, `budget_exhausted` и `error`
сохраняются в artifact и останавливают Image API, commit и deploy. Если после
завершённого Primary Recall v2, hybrid completeness, полного fallback audit и
актуального zero-pool recall sentinel итоговый пул всё ещё пуст, workflow создаёт
переиспользуемую редакционную остановку без публикации. Такая остановка является
штатным успешным `no-publish`: production остаётся зелёным, Image API, commit и
deploy не запускаются; красный статус сохраняется только для технически
неполного или ошибочного обязательного audit.

## Редакционный контракт

- обычная цель — 7–12 сюжетов, но для публикации достаточно одного достойного;
- числовых квот для китайских и российских новостей нет;
- пустые китайский и российский разделы не выводятся;
- выпуск из 1–6 сюжетов получает курсивную пометку
  «Новостей сегодня меньше, чем обычно» сразу под обложкой;
- если не найдено ни одного достаточно подтверждённого сюжета после полного
  обязательного поиска и актуального zero-pool recall sentinel, публикация не
  создаётся;
- legal-кандидат принимается только при масштабе `major`, оценке не ниже 4 и
  надёжном источнике;
- путь или рубрика URL источника не определяют редакционную категорию: для
  sentinel у любого `category != legal` поля `legal_scale` и
  `legal_scale_reason` детерминированно нормализуются к `not_applicable` и
  пустой строке;
- curiosity необязателен, должен быть проверяемым и может дать не более одного
  выбранного сюжета;
- URL, заголовок и издатель источника принадлежат исследовательскому пулу:
  редактор может выбрать и процитировать источник, но перед валидацией
  метаданные известного нормализованного URL программно восстанавливаются из
  `candidates.json`; неизвестный URL по-прежнему блокирует выпуск.

Канонический источник правил —
[`automation/specs/editorial-policy.md`](automation/specs/editorial-policy.md).

## Расписание, ручной запуск и recovery

Основной GitHub cron ежедневного workflow задан на `23:17 UTC` предыдущего
календарного дня — это `02:17 МСК` даты выпуска. Внешний резервный запуск через
cron-job.org сохраняет независимую страховку, поэтому дополнительные GitHub
cron-окна больше не дублируют один и тот же gate. GitHub Actions может
фактически запустить schedule позднее; cron является триггером, а не гарантией
точной минуты старта.

- плановый запуск всегда публикует результат;
- ручной `workflow_dispatch` по умолчанию работает как dry-run (`publish=false`);
- `publication_date` задаёт необязательную дату `YYYY-MM-DD`;
- `recovery_run_id` позволяет явно переиспользовать сохранённый artifact;
- без явного ID workflow автоматически ищет пригодный artifact той же даты,
  предпочитает наиболее полный результат (готовая обложка → готовый digest →
  research-only), а свежесть использует как tie-break; уже оплаченные стадии
  повторно не запускаются без необходимости;
- artifact, который уже имеет `artifact-normalization.json.status=error` или
  `artifact-validation.json.status=error`, не может быть выбран recovery;
  сохранённый `primary-recall.json` дополнительно обязан повторно пройти
  текущий source-health gate даже для `full` artifact;
- fresh Primary Recall v2 вызывает hybrid completeness только один раз;
  caller-supplied `--research-input` editorial rerun его пропускает, а recovery
  использует сохранённые `candidates.json`, `primary-recall.json` и
  `hybrid-completeness.json` вместо повторной оплаты независимого поиска;
- свежий primary research сохраняется как диагностический
  `automation/preview/production-daily/primary-recall-research-YYYY-MM-DD.json`
  и как ignored trusted runtime input
  `automation/fixtures/research/.runtime/primary-recall-research-YYYY-MM-DD.json`;
  полная траектория двенадцати слотов сохраняется как
  `primary-recall-YYYY-MM-DD.json` и внутри artifact выпуска;
- если hybrid нашёл пригодные NEW-only кандидаты, диагностическая объединённая
  копия сохраняется как `hybrid-completeness-merged-YYYY-MM-DD.json`, а рабочая
  runtime-копия для editorial rerun проходит через тот же `.runtime` ingress;
  подробная траектория запросов, источников, кластеров и бюджета хранится в
  `hybrid-completeness-YYYY-MM-DD.json` и artifact выпуска;
- если recovery восстановил полностью готовый выпуск и ни coverage/editorial,
  ни Image API больше не нужны, workflow не устанавливает OpenAI SDK и не
  требует `OPENAI_API_KEY`; если восстановлен готовый текст, но нужна только
  новая обложка, текстовый SDK также не устанавливается, а проверяются только
  ключ и image-модель, действительно нужные Image API;
- завершённый Primary Recall v2 с нулевым пулом остаётся пригодным для
  продолжения только если диагностика подтверждает все 12 обязательных search
  operations; затем hybrid completeness получает независимый шанс дополнить
  пул, после чего при необходимости запускается обязательный coverage audit;
- полный coverage audit и завершённый sentinel текущей версии переиспользуются
  без новых запросов; partial audit продолжает только незавершённые направления;
- повторный резервный запуск после готового выпуска завершается бесплатным
  no-op, а если commit уже есть, но живой URL недоступен, выполняется только
  FTP-redeploy.

Production-artifacts создаются с `retention-days: 14`, но инженерный hygiene
может удалить уже ненужные опубликованные artifacts раньше по безопасному
окну выпусков, описанному ниже. Artifacts неопубликованной актуальной даты
остаются защищены для recovery.

## Модели и доступы

- секрет `OPENAI_API_KEY` нужен только production-этапу;
- `OPENAI_TEXT_MODEL` по умолчанию и по текущему контракту —
  `gpt-5.6-terra`;
- `OPENAI_IMAGE_MODEL` — `gpt-image-2`;
- `FTP_SERVER`, `FTP_USERNAME` и `FTP_PASSWORD` используются только
  изолированным workflow `deploy-posts.yml`;
- Main CI не вызывает OpenAI, Image API или платный Web Search.

## Правила очистки контента

Единый ночной workflow применяет одну и ту же границу хранения к GitHub,
публичному сайту и связанным файлам:

- удаляются только выпуски, дата которых **строго раньше** даты
  `сегодня − 32 дня`; сама граничная дата и всё более новое сохраняются;
- старые `automation/content/YYYY-MM-DD/` компактируются: удаляются статья,
  обложка, промпты, сырые ответы API и другие производственные файлы, но
  `meta.json` и `stories.json` остаются для редакционной дедупликации;
- из `posts/` удаляются просроченные страницы и связанные изображения,
  включая исторический пакет `dzen-test`;
- из одного набора актуальных выпусков пересобираются `posts/rss.xml`,
  `posts/dzen-test/rss.xml`, оба `index.html` и `posts/sitemap.xml`;
- перед commit проверяются RSS, даты, страницы, изображения, индексы и
  sitemap; расхождение или попытка затронуть свежий выпуск останавливает
  workflow без изменения `main`;
- плановый запуск применяет очистку автоматически, ручной по умолчанию
  работает как dry-run, а срок хранения нельзя уменьшить ниже 32 дней;
- после успешного commit FTP синхронизируется с точным созданным SHA.

Эта 32-дневная механика не используется для инженерной уборки GitHub и не
изменяется `repository-hygiene.yml`.

## Правила инженерной уборки GitHub

`repository-hygiene.yml` работает отдельно от очистки выпусков. Плановый запуск
в 15:43 МСК применяет только доказуемо безопасные операции; ручной
`workflow_dispatch` по умолчанию является audit-only и требует `apply=true`
для destructive-фазы.

Результат каждого этапа выводится в понятный GitHub Actions Summary. Смотреть:
`Actions → Repository hygiene → последний запуск → Summary`. Там показываются
счётчики защищённых, удаляемых и требующих внимания объектов, фактически
удалённые ветки/artifacts, отключённые workflows и причины безопасных пропусков.
Полный JSON каждого этапа прикладывается к запуску как Actions artifact с
`retention: 2 дня`, после чего GitHub удаляет его автоматически.

- `archive/search-baseline-pre-hybrid-2026-08-09` является отдельным постоянным
  исключением из branch lifecycle и всегда `protected` как
  `permanent_archive_branch`;
- защитное окно остальных веток ограничено одновременно пятью последними PR,
  реально смёрженными в `main` по `merged_at`, и семью сутками после merge.
  `main`, protected branches, ветки открытых PR и ветки с активным Actions-run
  никогда не удаляются. Старая merged-ветка удаляется только если её текущий
  HEAD всё ещё совпадает с `head.sha` смёрженного PR. Closed-unmerged ветка
  после 14 суток без открытого PR может перейти в `safe_delete`, но только при
  точном совпадении текущего HEAD с `head.sha` закрытого PR; ветки без PR и
  изменённые после merge/закрытия остаются `review_only`.
- CI-artifact `main-ci-<sha>` сохраняется для текущего `main`, head SHA пяти
  последних merged PR, их merge SHA и текущих head SHA открытых PR. Остальные
  однозначно superseded CI-artifacts удаляются; artifacts неоднозначных веток
  остаются `review_only`.
- Для production-artifacts полностью сохраняется цепочка двух последних
  опубликованных дат. Для опубликованных дат №3–5 сохраняется только artifact
  run, где успешно завершился `Commit production release`; остальные варианты
  этой даты удаляются. Artifacts более старых опубликованных дат удаляются.
  Актуальная/будущая неопубликованная дата защищена, а историческая
  неопубликованная дата остаётся `review_only`, чтобы не потерять оплаченный
  recovery.
- Workflow, которого больше нет среди файлов `.github/workflows/` в `main`,
  и не имеет живого run, безопасно отключается по правилам canonical absence.
  Динамический GitHub Pages workflow является платформенным объектом и при
  `has_pages=false` остаётся диагностическим `github_pages_platform_managed`.
- Завершённые runs workflow, уже доказанно классифицированного как orphan
  (`safe_disable`), хранятся ещё 14 суток, после чего ежедневная hygiene удаляет
  их с повторной проверкой workflow, статуса и возраста. Runs canonical,
  protected и review-only workflows не затрагиваются; stale queued runs остаются
  report-only. Source scanner начинает watchlist после пяти merge и отмечает
  `suspected_orphan` после десяти, но никогда не меняет tracked-файлы.
- Перед destructive-фазой строится новый план, а `main` повторно проверяется
  перед удалениями. Если SHA `main` изменился, запуск завершает cleanup
  безопасной ошибкой. При активном production-run вся Actions-уборка
  пропускается.
- Права разделены по jobs: audit имеет только read-доступ, branch-pruner не
  получает `actions: write`, а Actions-pruner не получает `contents: write`.
  Releases, tags, permanent archive branches, published/editorial content и
  tracked-файлы этим workflow не изменяются.

Канонический алгоритм классификации находится в
`automation/scripts/repository_hygiene_policy.py`, GitHub runtime — в
`automation/scripts/repository_hygiene.py`.

## Основные каталоги

- `automation/content/YYYY-MM-DD/` — структурированные материалы выпусков;
- `automation/archive/index.json` — архив для антидублей и обновлений;
- `automation/archive/search-baselines/` — manifests постоянных retrieval-
  baseline-точек;
- `automation/config/` — production-, editorial-, site- и image-конфигурация;
- `automation/prompts/` — Primary Recall v2, legacy research, editorial и
  coverage-audit промпты;
- `automation/fixtures/recall/` — исторические retrieval-regression окна;
- `automation/fixtures/research/.runtime/` — ignored доверенный временный ingress
  fresh primary/hybrid research в существующий generator; содержимое не
  коммитится и не является пользовательским fixture;
- `automation/specs/` — канонические редакционные, image- и Schema.org
  контракты;
- `automation/scripts/` — retrieval-orchestrators, генераторы, recovery,
  сборщики и валидаторы;
- `automation/tests/` — офлайн-регрессии;
- `posts/` — публикуемый статический сайт, RSS, sitemap и обложки.

Команды локальной проверки и подробности артефактов описаны в
[`automation/README.md`](automation/README.md).

## Временной контракт research и recovery

Ночные запуски происходят около 02:17 МСК, когда в UTC ещё может быть предыдущий
календарный день. Поэтому `search_window.end_at` является авторитетным текущим
временем задачи для Primary Recall v2, hybrid completeness, всех coverage-
проходов и recall sentinel. Модель обязана считать всё до этой отметки не
будущим независимо от собственной системной даты или UTC-даты API-запуска.

Канонический continuity anchor остаётся `search_cutoff_at` последнего успешного
выпуска. Fresh Primary Recall строит effective discovery start не более чем на
24 часа раньше anchor, чтобы восстановить существенные пропуски предыдущего
дня. Exact archive URL отсекаются до merge, а обычная semantic/archive
дедупликация остаётся обязательной. Например, старый пропуск внутри 24 часов
может вернуться, но событие за пределами overlap не воскресает бесконечно.

Для query planning это окно теперь делится на две роли. Первые 24 часа от
effective start до continuity anchor являются healing overlap. Основной
continuity-период начинается после них и продолжается до `search_window.end_at`;
именно его календарные даты обязаны иметь приоритет в Primary, Hybrid и
Coverage search queries. Полное effective window остаётся авторитетной границей
валидации кандидатов, поэтому сильный пропуск из overlap по-прежнему может быть
восстановлен.

Контракт версионируется. Recovery не переиспользует legacy research без текущей
версии temporal anchor, если локальная дата конца окна уже опережает UTC-дату.
Для такого кросс-полуночного legacy artifact основной research выполняется
заново. Coverage audit версии до temporal anchor также не считается
окончательной нулевой остановкой в таком окне; обязательные проходы выполняются
заново, а recall sentinel использует текущую версию 7. Это сознательно допускает
повторную оплату только для доказанно ненадёжного временного класса artifact,
сохраняя обычный recovery для остальных случаев.

## Обновление retrieval после экспериментов 2026-08-13 и production 2026-08-14

Production run `31652757802` за 13 августа дал ровно четыре raw candidates,
editorial выбрал все четыре и все четыре были опубликованы. Значит крупные
пропуски этого выпуска возникли до editorial. Regression fixture
`automation/fixtures/recall/2026-08-13.json` закрепляет пять high-signal controls:
Pixel 11/Gemini (AP), Nebius, River AI, IBM/Together AI и Nvidia Nemotron
(Reuters). Source-focused natural-language searches по тому же effective window
в совокупности восстановили все пять controls без увеличения бюджета.

Следующий свежий production 14 августа показал новую деградацию: Primary,
Hybrid и Coverage технически завершили свои search operations, но поисковые
строки в основном использовали даты всего расширенного effective window вместе
с healing overlap. В результате ranking систематически поднимал старые материалы,
а несколько свежих high-signal событий continuity-периода не попали в candidate
pool. Одновременно два broad Primary slots были Reuters-focused, то есть
source-routing оказался недостаточно независимым даже при формально разных
темах.

После этого search budget не увеличивается, но query discipline уточнена.
Primary, Hybrid и Coverage по-прежнему принимают кандидатов из полного effective
window, однако поисковая строка в первую очередь использует календарные даты
основного continuity-периода, начинающегося ровно через 24 часа после effective
start. Healing overlap остаётся вторичной областью восстановления и не должен
вытеснять свежие новости нового выпуска.

High-signal routing Primary также разделён без новых search slots:
`global_breaking` остаётся Reuters-focused для funding/acquisition/M&A/major
business; `major_agencies` становится source-neutral внутри существующего
Reuters/AP/Bloomberg/FT API filter и проверяет major AI news по моделям,
продуктам, чипам, инфраструктуре и бизнесу; `independent_missing_events`
остаётся независимым Associated Press-focused consumer-AI / major technology /
policy sweep. Это routing поискового ranking, а не whitelist кандидатов.
Остальные Primary directions остаются широкими и могут использовать официальные
первоисточники, авторитетные технологические/деловые/отраслевые СМИ,
регуляторов и исследовательские источники согласно обычным правилам качества.

Во всех трёх retrieval-слоях поисковые строки остаются короткими
natural-language queries, ориентир 6–18 значимых слов. `after:`, `before:`,
`site:`, длинные `OR`-цепочки, скобки и огромные перечни доменов/компаний
запрещены. `general_coverage_gaps` использует свой API domain filter вместо
ручной `site:foo OR site:bar ...` конструкции.

Source-health для modern `primary-recall.json` с `search_window` требует хотя бы
одно свежее Reuters/AP/Bloomberg/FT evidence внутри effective window среди broad
source-anchor passes. Dated Reuters/Bloomberg/FT URL либо verified in-window
agency raw candidate считается evidence; stale author, newsletter, event и
старые document pages не считаются. Это fail-closed health check, а не квота на
агентские сюжеты. Worst-case search ceiling остаётся 23 operations: 12 Primary +
до 4 Hybrid + до 7 Coverage.


## Hygiene search diagnostics

Перед сохранением Primary, Hybrid и Coverage diagnostics URL, возвращённые search provider, очищаются от временных credential/token/signature query-параметров, включая AWS signed URL. Домен, путь и несекретные параметры сохраняются. Artifact secret-scanner остаётся fail-closed и не получает исключений для подписанных URL.


### Проверенный relative-freshness retrieval

Эксперимент 2026-08-14 на production-модели `gpt-5.6-terra` показал: явные
календарные даты в Web Search query ухудшают ranking и могут приводить к
false-zero. Поэтому Primary, Hybrid, Coverage и финальный zero-pool sentinel
используют date-free `latest`/`recent`/`current`/`breaking` запросы. Это только
ranking hint: фактическая дата/timestamp источника по-прежнему строго проверяется
против полного effective window. Broad safety nets не привязаны к одному
издателю. Если Hybrid добавил валидный candidate, но immediate editorial rerun
упал, объединённый pool всё равно передаётся Coverage.


Source-health после перехода на source-neutral routing проверяет свежую Reuters/AP/Bloomberg/FT evidence по **всей 12-pass Primary matrix**, а не только в `global_breaking`/`major_agencies`/`independent_missing_events`: тематический pass вправе первым обнаружить сильный agency-материал. При этом `major_agencies` всё равно обязан завершить свою search operation и иметь хотя бы один consulted source, а общий anti-junk gate по источникам не ослабляется.

## Возобновляемые платные стадии

Production рассматривает успешно провалидированный текст выпуска как отдельный
checkpoint. Если после него ломается обложка, сборка сайта, commit или FTP,
следующий recovery-run переиспользует готовый artifact и не оплачивает заново
Primary Recall, Hybrid, Coverage и редактуру. Успешная обложка является следующим
checkpoint, а уже закоммиченный выпуск при проблеме FTP только redeploy-ится.

Для обложки обязательным идентификатором является отдельный `image_request_id`.
Исходный `source_editorial_request_id` хранится только как provenance и может
отсутствовать у корректного recovery-артефакта; его отсутствие не должно
останавливать Image API. Диагностика различает локальный image-preflight,
сетевой/HTTP сбой Images API и некорректный API response, а при доступности
сохраняет `x-request-id`. Обычная генерация обложки остаётся one-shot без
автоматического retry.

## Fresh-agency rescue после Coverage

Для modern production с ненулевым candidate pool source-health не считается
здоровым только по количеству сюжетов. Если после Primary, Hybrid и шести
обязательных Coverage-направлений в validated pool всё ещё нет свежего
Reuters/AP/Bloomberg/FT primary source, свободный **седьмой** Coverage search
operation используется как bounded `fresh_agency_rescue` версии 7 для
подтверждения уже найденного сильного события. Для нулевого пула этот же слот
остаётся source-neutral `high_signal_recall_sentinel` версии 8; режимы
взаимоисключающие.

Rescue делает ровно один Web Search. Для денежных событий query строится из
отличительных фактических anchors (`organization + сумма + valuation`) без
календарной даты, publisher-hint и API domain filter. Acceptance остаётся
fail-closed: нужен прямой URL Reuters/AP/Bloomberg/FT внутри effective window и
точное совпадение `organization`, `event_type` и `published_date` с target.
Успешное подтверждение не создаёт новый сюжет: agency source становится primary
существующего candidate, прежний primary переносится в supporting sources, после
чего editorial rerun обновляет ссылки.

Recovery старого ненулевого Coverage report версионируется по source-health
contract: уже оплаченные шесть обязательных проходов переиспользуются, а при
необходимости расходуется только новый rescue search. Worst-case search budget
не меняется: **12 Primary + до 4 Hybrid + до 7 Coverage = максимум 23 search
operations**. Live-наличие конкретной статьи во внешнем поисковом индексе не
является детерминированным CI-gate; production acceptance при отсутствии
валидного agency corroboration остаётся закрытым.

## Exact cutoff для fresh-agency evidence

Fresh-agency source-health использует сохранённый точный `search_window.end_at`, а
не только календарную дату. Если у Reuters/AP/Bloomberg/FT evidence есть
timezone-aware `published_at`, он обязан лежать внутри точного effective window.
Date-only evidence на календарном дне cutoff не считается достаточным
доказательством свежести: поздний same-day recovery уже может видеть статью,
опубликованную после исходного cutoff. Date-only evidence на стартовом дне
сохраняет совместимость с bounded healing overlap; точный timestamp, если он
есть, всегда проверяется строго.


### Source-health при недетерминированной agency-выдаче

Обязательный `major_agencies` Primary pass и bounded same-event agency rescue остаются частью fail-closed поискового контура и не увеличивают бюджет: максимум по-прежнему 12 Primary + до 4 Hybrid + до 7 Coverage searches. Технически незавершённый обязательный маршрут, отсутствие search operation или деградация общего source-health по-прежнему блокируют выпуск. Если же обязательные маршруты корректно завершились, но Terra не вернула подтверждённый свежий Reuters/AP/Bloomberg/FT материал, сам нулевой ranking-result больше не считается достаточной причиной аварии: normalization сохраняет явное `source-health warning`, а остальные editorial/validation gates продолжают работать. Любой найденный agency-материал всё так же обязан пройти точную проверку effective window.

## Retrieval Quality v1: unresolved-сигналы и региональная полнота

С 2026-08-16 production сохраняет важный `unverified` след из Primary Recall как отдельный `unresolved_signal`, вместо того чтобы безвозвратно оставлять его в обычных rejections. Targeted resolution обязателен только для strict high-signal evidence; слабый `unverified` остаётся диагностикой и сам по себе не блокирует выпуск.

`entities`, `anchors` и `source_hint` являются только evidence для построения короткого запроса. Это **не** company whitelist, не обязательный AND-набор и не publisher whitelist. Resolution выполняет один source-neutral Web Search без API domain filter и может подтвердить событие любым авторитетным первичным или вторичным источником. Reuters остаётся одним из возможных источников, а не центром поисковой архитектуры.

Если Primary Recall технически завершил China/Asia- или Russia-направление с нулём принятых кандидатов, существующий optional 4-й Hybrid slot может стать региональным recall-health check. Ноль после такой проверки допустим: это контроль достаточности поиска, **не квота на публикацию** и не требование искусственно добавлять российскую или азиатскую историю.

Adaptive-приоритет сохраняет стоимость: mandatory Coverage retry имеет приоритет над unresolved resolution; при отсутствии unresolved-сигнала действуют прежние fresh-agency rescue / zero-pool sentinel. Максимум не меняется: **12 Primary + до 4 Hybrid + до 7 Coverage = 23 Web Search operations на выпуск**.

`retrieval_quality_contract_version=1` участвует в recovery. Modern full artifact без завершённого Retrieval Quality v1 понижается до partial editorial recovery: уже оплаченные валидные mandatory-проходы переиспользуются, а свободный quality-slot выполняется по новой семантике. Legacy zero-pool terminal artifact старого контракта не используется между разными датами выпуска, потому что recovery выбирается строго по `daily-production-YYYY-MM-DD`. Live Terra smoke остаётся диагностической pre-release проверкой; наличие конкретной Reuters URL не является детерминированным CI-gate из-за недетерминированного ранжирования поиска.

## Source Freshness Proof v1

С 2026-08-17 модельные `published_at` и `published_date` больше не являются достаточным доказательством свежести trusted production candidate. Перед каждым editorial-проходом внутреннего Primary/Hybrid/Coverage runtime `automation/scripts/source_freshness.py` бесплатно, без OpenAI и Web Search, открывает только уже процитированные source URL и извлекает машинно-читаемое время публикации (`article:published_time`, JSON-LD `datePublished` и эквиваленты). `dateModified` не используется как дата публикации.

Сравнение с сохранённым effective `search_window` и перевод timezone делает Python. Точный timestamp обязан попадать в окно; date-only evidence на календарном дне cutoff недостаточно и fail-closed. Если primary source не отдаёт пригодную дату, но уже цитируемый supporting source подтверждает свежесть, supporting может стать primary. Нового поиска для этого нет.

Источник с подтверждённой датой вне окна исключает candidate как `old_reprint`. Если ни один уже цитируемый источник не позволяет независимо доказать дату публикации, candidate становится `unconfirmed` и не может быть опубликован. Caller-supplied fixtures остаются offline.

Контрольная регрессия: AP/Anthropic в выпуске 2026-08-17 был ошибочно размечен как 2026-08-16 при фактическом `datePublished=2026-07-31`; новый gate его отсекает. Свежий timestamp вроде TechCrunch `2026-08-16T13:57:00-07:00` корректно остаётся внутри окна благодаря Python timezone arithmetic.

Механика поиска не меняется: новые Search/OpenAI вызовы не добавлены, 7-й Coverage slot не менялся, потолок остаётся **12 Primary + до 4 Hybrid + до 7 Coverage = 23 search operations**.

## Устойчивость механизмов очистки

После инцидентов 17–18 августа 2026 года обе очистки имеют отдельные границы
устойчивости. Публичная 32-дневная очистка по-прежнему требует основной каталог
`posts/images/`, но допускает отсутствие исторического
`posts/dzen-test/images/`, если legacy-публикаций больше нет: Git не хранит
пустые каталоги. Если хотя бы один legacy-выпуск остаётся в RSS, его страница,
legacy-изображение и зеркало в основном каталоге изображений всё ещё обязательны
и проверяются fail-closed.

Клиент `repository_hygiene_github.py` повторяет только идемпотентные GitHub API
`GET` при временных `500/502/503/504` и transport `URLError`: максимум две
повторные попытки после исходной с коротким backoff. Автоматического retry для
`DELETE` и `PUT` нет, чтобы неопределённый результат destructive-запроса не
превратился в повторное изменение состояния. Эти случаи закреплены отдельными
offline regression tests.
