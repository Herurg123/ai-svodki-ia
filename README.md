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

## Локальный подпроект NotebookLM-видео

`automation/notebooklm-video/` хранит отдельный Windows-подпроект downstream-
автоматизации. После уже опубликованной ИИ-Сводки он читает RSS, создаёт
видеоповествование в NotebookLM, скачивает MP4, делает PNG-превью первого кадра
и при включённой настройке доставляет медиа в изолированный FTP-каталог `video`.

Подпроект находится в том же репозитории, чтобы схема выпуска, исходники и
инструкции оставались доступны в одном месте, но он **не входит** в основной
ночной retrieval/editorial GitHub Actions production. Его содержимое
обслуживается отдельными задачами подпроекта. Обычные изменения поиска,
редакционной логики, сайта, RSS, основного FTP-deploy, очистки и аудитов не
должны попутно менять `automation/notebooklm-video/`.

В Git попадают только переносимые исходники, безопасные шаблоны и инструкции.
Реальные локальные конфиги, доступы, state, журналы, скачанные медиа и
защищённый браузерный профиль не коммитятся. Подробности работы и переноса на
другую Windows-машину описаны в
[`automation/notebooklm-video/README.md`](automation/notebooklm-video/README.md)
и
[`automation/notebooklm-video/DEPLOYMENT.md`](automation/notebooklm-video/DEPLOYMENT.md).

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
сюжетов. Search queries остаются date-free и используют relative-freshness cues;
точные timestamps effective window применяются только после retrieval. Так
overlap лечит старые пропуски, не превращаясь в календарный ranking-фильтр.

| Workflow | Назначение |
|---|---|
| `.github/workflows/ci.yml` | Бесплатные офлайн-проверки pull request и `main`: компиляция, unit-тесты, редакционный и production-контракты, архив, RSS, sitemap и Schema.org. |
| `.github/workflows/daily-production.yml` | Gate, Primary Recall v2, bounded agency discovery rescue при подтверждённом gap, независимый hybrid completeness, editorial, ограниченный coverage audit, обложка, сборка сайта, commit в `main` и вызов FTP-деплоя. |
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
   Для `major_agencies` production использует query `latest AI chips infrastructure financing earnings business deals policy security`; publisher routing задаётся Reuters/AP/Bloomberg/FT API domain filter и не увеличивает 12-search Primary budget.
7. Китай/Азия намеренно разделены на два прохода. Исторический эксперимент на
   окне выпуска 2026-08-11 показал, что одна широкая China/Asia-проверка
   обнаружила 5 из 6 контрольных событий, но пропустила продуктовую интеграцию
   Apple/Qwen; отдельный второй проход поднял шестое событие без увеличения
   12-search primary-бюджета. `china_asia_models` по-прежнему отвечает за модели,
   релизы и product/model discovery. Второй слот сохраняет id
   `china_asia_integrations`, но дополнительно к integrations/partnerships/
   deployments покрывает AI business, earnings, revenue и strategy запросом
   `latest China Asia AI business earnings revenue strategy cloud partnerships deployments`.
   Это независимый путь в candidate pool, а не региональная квота на публикацию.
   Regression fixtures: `automation/fixtures/recall/2026-08-11.json` и
   `automation/fixtures/recall/2026-08-21-agency-asia.json`.
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
14. После сохранённого Primary/provisional-editorial checkpoint, но **до Hybrid**,
    выполняется bounded `agency_discovery_rescue` v3 только если обязательный
    `major_agencies` технически завершился и дал `raw_count=0` либо
    `accepted_count=0`. Trigger не зависит от общего числа candidates или stories:
    даже полный пул не маскирует подтверждённый gap dedicated agency route.
    Rescue получает максимум **одну** дополнительную Web Search operation,
    использует publisher-neutral date-free query
    `latest AI chips infrastructure financing earnings business deals policy security`
    и отдельный provider-level `allowed_domains=["reuters.com"]`. В v3
    `search_context_size=high`; downstream принимаются только прямые Reuters
    primary URL. Rescue остаётся missing-event discovery, а не подтверждением уже
    известного события и не Reuters quota.
15. Rescue-candidate проходит обычный `story_coverage` validator, archive check,
    same-event guard (`organization + event_type + published_date`), затем штатный
    Source Freshness Proof и editorial. Reuters не даёт бонуса к significance и
    ничего не публикует автоматически. Zero-result, stale, weak, duplicate или
    техническая ошибка rescue не блокируют ранее пригодный выпуск. Состояние
    `agency-discovery-rescue.json` пишется до поиска и после ответа: recovery
    никогда не повторяет `search_started`, а `search_completed`/`merge_failed`
    может завершить merge без второго поиска. Если Hybrid ломается уже после
    успешного rescue, сохранённый rescue pool всё равно проходит Source Freshness
    Proof/editorial через существующий trusted runtime path.
16. После **свежего** primary/rescue запускается отдельный `hybrid completeness`
    v1. Он не заменяет primary, а остаётся независимой страховкой. Три
    фиксированных прохода получают ровно по одному search operation: (1)
    models/products/agents/research, (2) infrastructure/chips/business, (3)
    safety/security/policy/major regional gaps. После них детерминированно
    считаются три тематических кластера; если хотя бы один полностью пуст в
    объединённом primary + rescue + completeness пуле, разрешается **один**
    adaptive gap search. Жёсткий потолок слоя — 4 search operations, обычный
    расход — 3. Hybrid не имеет API domain filter и тоже может использовать
    ограниченную навигацию после своего единственного search каждого прохода.
17. Hybrid-кандидаты проходят тот же строгий `story_coverage` validator,
    дедупликацию по URL/событию и лимит пула. Editorial повторяется только если
    принят хотя бы один новый кандидат. Объединённый research для rerun также
    проходит через доверенный `.runtime` ingress. Caller-supplied
    `--research-input` recovery не запускает completeness рекурсивно. Если сам
    completeness или его editorial-rerun технически ломается, baseline primary
    artifact сохраняется или восстанавливается; уже добавленный agency rescue
    candidate при этом не теряется.
18. Если после primary + rescue + hybrid достойных сюжетов всё ещё меньше обычной
    цели, выполняется прежний обязательный coverage audit: шесть отдельных
    тематических Web Search-проходов и один резервный слот. Production targeted
    passes получают одну search operation и небольшой navigation allowance для
    проверки страниц. Coverage query discipline совпадает с Primary/Hybrid:
    relative-freshness ranking остаётся date-free, а full effective window
    используется для eligibility. Если обязательное направление технически не
    завершено, резерв тратится на его повтор. Если все шесть завершены, но
    итоговый пригодный пул всё ещё нулевой, тот же седьмой search становится
    `high_signal_recall_sentinel` версии 8; при ненулевом пуле он может остаться
    существующим same-event `fresh_agency_rescue` или unresolved-resolution
    quality slot по текущей Coverage policy.
19. `gpt-image-2` создаёт одну PNG-обложку 1536×864; валидатор проверяет её
    технический контракт.
20. Legacy-staging исторических обложек работает как best-effort слой
    совместимости: его предупреждение само по себе не блокирует выпуск.
    Канонический build и последующие валидаторы всё равно обязаны подтвердить,
    что все реально используемые страницы и изображения присутствуют.
21. Кандидат сайта получает RSS, sitemap и Schema.org и проходит офлайн-
    валидацию.
22. Только проверенное состояние записывается одним commit в `main`, после чего
    `deploy-posts.yml` разворачивает именно этот SHA.

Primary Recall v2 имеет hard cap `12`, bounded agency discovery rescue — `1`
только при подтверждённом `major_agencies` gap, hybrid completeness — hard cap
`4`, а fallback coverage — до `7`. Теоретический worst case теперь равен
**24 завершённым `search` operations: 12 + 1 + 4 + 7**. Rescue не является 13-м
обязательным Primary pass и в нормальном случае вообще не выполняется. Служебные
`open_page` и `find_in_page` видны в диагностике и увеличивают общее число hosted
tool calls, но не считаются поисковыми операциями.

Шесть обязательных направлений fallback coverage audit не меняются:

1. `security_world`
2. `security_russia`
3. `security_asia`
4. `legal_copyright_scraping`
5. `curiosity`
6. `general_coverage_gaps` — авторитетный last-mile sweep первоисточников,
   агентств, судов и регуляторов с доменным фильтром API.

Седьмой Web Search сначала резервируется для повтора первой незавершённой
обязательной проверки. При полном mandatory plan тот же слот используется только
одной из взаимоисключающих quality-семантик текущей Coverage policy: unresolved
high-signal resolution, same-event `fresh_agency_rescue` либо source-neutral
zero-pool sentinel. Новый pre-Hybrid `agency_discovery_rescue` в этот слот не
встраивается и учитывается отдельно в потолке 24.

Короткий выпуск допускается только после фактического завершения всех шести
fallback-направлений. Пустой результат отдельного направления нормален и даёт
`complete_with_gaps`; технические `partial`, `budget_exhausted` и `error`
сохраняются в artifact и останавливают Image API, commit и deploy. Если после
завершённого Primary Recall v2, bounded rescue при его trigger, hybrid
completeness, полного fallback audit и актуального zero-pool recall sentinel
итоговый пул всё ещё пуст, workflow создаёт переиспользуемую редакционную
остановку без публикации.

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
- `force_fresh_research` по умолчанию `false`. Только для ручного
  `workflow_dispatch` значение `true` отключает **автоматический** выбор artifact
  той же даты и тем самым разрешает fresh research на текущем `main`; это нужно,
  например, для проверки retrieval-hotfix после уже завершённого zero-pool
  `editorial_stop`. `force_fresh_research=true` и явный `recovery_run_id`
  взаимоисключающие и завершают run ошибкой до платных API. На scheduled runs
  новый флаг не меняет recovery semantics. `publish` остаётся независимым:
  `false` сохраняет dry-run, `true` после успешного fresh research идёт обычным
  publish path;
- без явного ID и без `force_fresh_research=true` workflow автоматически ищет
  пригодный artifact той же даты, предпочитает наиболее полный результат
  (готовая обложка → готовый digest → research-only), а свежесть использует как
  tie-break; уже оплаченные стадии повторно не запускаются без необходимости;
- artifact, который уже имеет `artifact-normalization.json.status=error` или
  `artifact-validation.json.status=error`, не может быть выбран recovery;
  сохранённый `primary-recall.json` дополнительно обязан повторно пройти
  текущий source-health gate даже для `full` artifact;
- modern full artifact с `major_agencies` gap, но без завершённого
  `agency-discovery-rescue` contract, понижается до `partial_editorial`, чтобы
  recovery имел text runtime для единственного допустимого первого rescue
  attempt. `search_started` никогда не повторяется; `search_completed` или
  `merge_failed` ремонтируются из сохранённого response без второго Web Search;
- fresh Primary Recall v2 вызывает bounded rescue/Hybrid только один раз;
  caller-supplied `--research-input` editorial rerun их не запускает рекурсивно,
  а recovery использует сохранённые candidates и stage diagnostics;
- свежий primary research сохраняется как диагностический
  `automation/preview/production-daily/primary-recall-research-YYYY-MM-DD.json`
  и как ignored trusted runtime input
  `automation/fixtures/research/.runtime/primary-recall-research-YYYY-MM-DD.json`;
  полная траектория двенадцати слотов сохраняется как
  `primary-recall-YYYY-MM-DD.json` и внутри artifact выпуска;
- agency rescue сохраняет `agency-discovery-rescue.json` внутри artifact и
  `agency-discovery-rescue-YYYY-MM-DD.json` в production diagnostics; при
  добавлении кандидата отдельная `.runtime` merged-копия гарантирует прохождение
  Source Freshness Proof/editorial даже если Hybrid затем падает;
- если hybrid нашёл пригодные NEW-only кандидаты, диагностическая объединённая
  копия сохраняется как `hybrid-completeness-merged-YYYY-MM-DD.json`, а рабочая
  runtime-копия для editorial rerun проходит через тот же `.runtime` ingress;
- если recovery восстановил полностью готовый выпуск и ни quality/text stage,
  ни Image API больше не нужны, workflow не устанавливает OpenAI SDK и не
  требует `OPENAI_API_KEY`; pending first agency rescue или сохранённый response,
  которому ещё нужны merge/freshness/editorial, переводит recovery в text-needed;
- завершённый Primary Recall v2 с нулевым пулом остаётся пригодным для
  продолжения только если диагностика подтверждает все 12 обязательных search
  operations; затем bounded rescue срабатывает по собственному agency trigger,
  Hybrid получает независимый шанс дополнить пул, после чего при необходимости
  запускается обязательный coverage audit;
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
- `automation/audits/` — канонический независимый журнал качества и сохранённые
  retrieval-эксперименты;
- `automation/config/` — production-, editorial-, site- и image-конфигурация;
- `automation/prompts/` — Primary Recall v2, legacy research, editorial и
  coverage-audit промпты;
- `automation/fixtures/recall/` — исторические retrieval-regression окна и
  machine-readable контракты экспериментов;
- `automation/fixtures/research/.runtime/` — ignored доверенный временный ingress
  fresh primary/rescue/hybrid research в существующий generator; содержимое не
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
временем задачи для Primary Recall v2, bounded agency rescue, hybrid
completeness, всех coverage-проходов и recall sentinel. Модель обязана считать
всё до этой отметки не будущим независимо от собственной системной даты или
UTC-даты API-запуска.

Канонический continuity anchor остаётся `search_cutoff_at` последнего успешного
выпуска. Fresh Primary Recall строит effective discovery start не более чем на
24 часа раньше anchor, чтобы восстановить существенные пропуски предыдущего
дня. Exact archive URL отсекаются до merge, а обычная semantic/archive
дедупликация остаётся обязательной.

Для query planning это окно делится на две роли. Первые 24 часа от effective
start до continuity anchor являются healing overlap. Основной continuity-период
начинается после них и продолжается до `search_window.end_at`. Но календарные
границы не кодируются в поисковую строку: Primary, rescue, Hybrid и Coverage
используют короткие date-free relative-freshness queries, а полное effective
window остаётся авторитетной границей post-retrieval валидации.

Контракт версионируется. Recovery не переиспользует legacy research без текущей
версии temporal anchor, если локальная дата конца окна уже опережает UTC-дату.
Для такого кросс-полуночного legacy artifact основной research выполняется
заново. Coverage audit старого temporal contract также не считается
окончательной нулевой остановкой.

## Обновление retrieval после экспериментов 2026-08-13, 2026-08-14 и 2026-08-21–24

Production run `31652757802` за 13 августа дал ровно четыре raw candidates,
editorial выбрал все четыре и все четыре были опубликованы. Значит крупные
пропуски этого выпуска возникли до editorial. Regression fixture
`automation/fixtures/recall/2026-08-13.json` закрепляет пять high-signal controls:
Pixel 11/Gemini (AP), Nebius, River AI, IBM/Together AI и Nvidia Nemotron
(Reuters). Source-focused natural-language searches по тому же effective window
в совокупности восстановили все пять controls без увеличения бюджета.

Следующий свежий production 14 августа показал новую деградацию: Primary,
Hybrid и Coverage технически завершили свои search operations, но календарное
кодирование расширенного effective window ухудшало ranking. После live
`gpt-5.6-terra` эксперимента retrieval перешёл на короткие date-free
relative-freshness queries, сохранив exact effective window для валидации.

Аудиты 17–21 августа выявили новый повторяющийся слой: крупные
infrastructure/business события Nvidia/SB Energy, Google/Marvell и Broadcom, а
также China/Asia AI-business события Baidu и Alibaba могли выпадать до
candidate pool. Эксперимент 21 августа сначала сохранил общий потолок 23 и
усилил semantics внутри существующих 12 Primary routes.

Out-of-sample наблюдения 22–23 августа показали, что одной semantic-правки
недостаточно: `major_agencies` продолжил давать 0/0, Broadcom повторно выпадал,
а 23 августа был пропущен свежий Reuters-сигнал Nvidia server price hikes.
Контролируемый bounded experiment 22 августа подтвердил source-pool/ranking
instability и добавил отдельный one-search missing-event rescue после Primary
checkpoint и до Hybrid.

Production run `32674034063` за 24 августа дал следующий независимый контроль:
все 24 search operations завершились, но candidate pool остался нулевым, хотя
в effective window находилось Reuters-событие Alibaba о размещении примерно на
$10.2 млрд с направлением net proceeds на full-stack AI. Обязательный
`major_agencies` с Reuters/AP/Bloomberg/FT provider filter ранжировал в основном
старые Bloomberg/FT материалы; source-open discovery rescue получил
агрегаторы/syndication и тоже не поднял свежий прямой Reuters. Source Freshness
Proof не отклонял Alibaba: ни один кандидат до него не дошёл. Независимый
source-focused replay подтвердил, что один Reuters-only provider route с
publisher-neutral query устойчивее восстанавливает контрольный Reuters-слой,
не требуя второго search. Это привело к v2: Reuters-only route с
`search_context_size=medium`.

Fresh production run `32691255059` затем дал более точный контроль уже для v2.
Старый artifact не переиспользовался, Reuters-only rescue действительно выполнил
один search с тем же нейтральным query и `medium`, но вернул
`consulted_sources=[]` и `raw_count=0`; Alibaba снова не дошёл ни до freshness,
ни до editorial. Поэтому v3 меняет только `search_context_size` на `high`.
Изолированный assistant-side Terra `medium/high` A/B по-прежнему недоступен, так
что это минимальная production-supported reliability-гипотеза, а не доказанный
универсальный optimum. Query, Reuters-only filter, один search, direct-Reuters
acceptance, freshness/significance/dedupe и global ceiling 24 не меняются.

Текущий high-signal routing:

- `global_breaking`: source-neutral broad current-AI catch-all;
- `major_agencies`: обязательный Reuters/AP/Bloomberg/FT API route с query
  `latest AI chips infrastructure financing earnings business deals policy security`;
- `agency_discovery_rescue`: условный one-search missing-event route с тем же
  publisher-neutral query, отдельным `allowed_domains=["reuters.com"]`,
  `search_context_size=high` и downstream direct-Reuters acceptance;
- `independent_missing_events`: source-neutral broad missing-events sweep;
- `china_asia_models`: отдельный model/product/release route;
- `china_asia_integrations`: integrations/partnerships/deployments +
  business/earnings/revenue/strategy;
- `russia`: отдельный обязательный Primary route без изменений.

Общий worst-case ceiling остаётся **24 operations: 12 Primary + 1 conditional
agency discovery rescue + до 4 Hybrid + до 7 Coverage**.

Эксперименты и regression contracts сохранены в:

- `automation/audits/experiments/2026-08-21-agency-asia-recall.md`;
- `automation/fixtures/recall/2026-08-21-agency-asia.json`;
- `automation/fixtures/recall/2026-08-22-agency-discovery-rescue.json`;
- `automation/fixtures/recall/2026-08-24-agency-recovery.json`;
- `automation/audits/experiments/2026-08-24-agency-context-high.md`.

## Независимый ежедневный аудит качества

Канонический журнал находится в
`automation/audits/independent-audit-journal.md`. После каждого успешного
production-выпуска его следует обновлять независимой проверкой, не расходуя
production API: определить точное effective window, разобрать Primary/rescue/
Hybrid/Coverage и editorial, независимо проверить Freshness/Completeness, Must
Include misses, stale, source concentration, Asia/Russia и повторение известных
паттернов.

Этот monitoring является внешним quality-control слоем, а не ещё одной стадией
платного production retrieval. Нулевой региональный результат сам по себе не
ошибка и не создаёт story quota. Один miss также не меняет архитектуру
автоматически: повторяющиеся паттерны сначала фиксируются в том же журнале,
затем проходят отдельный эксперимент и architecture-wide audit.

## Hygiene search diagnostics

Перед сохранением Primary, rescue, Hybrid и Coverage diagnostics URL,
возвращённые search provider, очищаются от временных credential/token/signature
query-параметров, включая AWS signed URL. Домен, путь и несекретные параметры
сохраняются. Artifact secret-scanner остаётся fail-closed и не получает
исключений для подписанных URL.

### Проверенный relative-freshness retrieval

Эксперимент 2026-08-14 на production-модели `gpt-5.6-terra` показал: явные
календарные даты в Web Search query ухудшают ranking и могут приводить к
false-zero. Поэтому Primary, bounded rescue, Hybrid, Coverage и финальный
zero-pool sentinel используют date-free `latest`/`recent`/`current`/`breaking`
запросы. Это только ranking hint: фактическая дата/timestamp источника
по-прежнему строго проверяется против полного effective window.

Source-health проверяет свежую Reuters/AP/Bloomberg/FT evidence по всей 12-pass
Primary matrix. `major_agencies` всё равно обязан завершить свою search operation
и иметь хотя бы один consulted source, а общий anti-junk gate не ослабляется.
Новый discovery rescue не заменяет mandatory route и не исправляет его
технические ошибки: он разрешён только после технически завершённого gap.

## Возобновляемые платные стадии

Production рассматривает успешно провалидированный текст выпуска как отдельный
checkpoint. Если после него ломается обложка, сборка сайта, commit или FTP,
следующий recovery-run переиспользует готовый artifact и не оплачивает заново
Primary Recall, уже завершённый agency rescue, Hybrid, Coverage и редактуру.
Успешная обложка является следующим checkpoint, а уже закоммиченный выпуск при
проблеме FTP только redeploy-ится.

Для обложки обязательным идентификатором является отдельный `image_request_id`.
Исходный `source_editorial_request_id` хранится только как provenance и может
отсутствовать у корректного recovery-артефакта; его отсутствие не должно
останавливать Image API. Обычная генерация обложки остаётся one-shot без
автоматического retry.

## Fresh-agency rescue после Coverage

Coverage `fresh_agency_rescue` остаётся отдельной **corroboration**-механикой.
Если после Primary, conditional discovery rescue, Hybrid и шести обязательных
Coverage-направлений в ненулевом validated pool всё ещё нет свежего
Reuters/AP/Bloomberg/FT primary source, свободный седьмой Coverage search может
подтвердить **уже найденное** сильное событие. Для нулевого пула тот же слот
остаётся source-neutral `high_signal_recall_sentinel`; режимы взаимоисключающие.

Same-event rescue делает ровно один Web Search. Acceptance fail-closed: нужен
прямой Reuters/AP/Bloomberg/FT источник внутри effective window и точное
совпадение `organization`, `event_type` и `published_date` с target. Успешное
подтверждение не создаёт новый сюжет: agency source становится primary
существующего candidate. Это принципиально отличается от pre-Hybrid
`agency_discovery_rescue`, который ищет отсутствующее событие.

Coverage по-прежнему ограничен максимум семью search operations, но общий
pipeline ceiling с отдельным conditional discovery slot равен **24**.

## Exact cutoff для fresh-agency evidence

Fresh-agency source-health использует сохранённый точный `search_window.end_at`, а
не только календарную дату. Если у agency evidence есть timezone-aware
`published_at`, он обязан лежать внутри exact effective window. Date-only
evidence на календарном дне cutoff не считается достаточным доказательством
свежести. Эти правила одинаково применяются к discovery-rescue candidate через
Source Freshness Proof и к downstream corroboration evidence.

### Source-health при недетерминированной agency-выдаче

Обязательный `major_agencies` Primary pass остаётся fail-closed по техническому
контракту. Если он технически завершён, но даёт raw/accepted zero, bounded
missing-event discovery получает один независимый Reuters-only шанс; его
zero-result или слабый/устаревший candidate сам по себе не превращает пригодный
выпуск в аварию. Downstream same-event corroboration сохраняет прежний контракт.
Общий максимум остаётся 12 Primary + 1 conditional discovery rescue + до 4 Hybrid
+ до 7 Coverage = 24 searches.

## Retrieval Quality v1: unresolved-сигналы и региональная полнота

С 2026-08-16 production сохраняет важный `unverified` след из Primary Recall как
отдельный `unresolved_signal`, вместо того чтобы безвозвратно оставлять его в
обычных rejections. Targeted resolution обязателен только для strict high-signal
evidence; слабый `unverified` остаётся диагностикой и сам по себе не блокирует
выпуск.

`entities`, `anchors` и `source_hint` являются только evidence для построения
короткого запроса. Это **не** company whitelist, не обязательный AND-набор и не
publisher whitelist. Resolution выполняет один source-neutral Web Search без
API domain filter и может подтвердить событие любым авторитетным источником.

Если Primary Recall технически завершил China/Asia- или Russia-направление с
нулём принятых кандидатов, существующий optional 4-й Hybrid slot может стать
региональным recall-health check. Ноль после такой проверки допустим: это
контроль достаточности поиска, **не квота на публикацию**.

Adaptive-приоритет Coverage сохраняется: mandatory retry имеет приоритет над
unresolved resolution; при отсутствии unresolved-сигнала действуют прежние
same-event fresh-agency rescue / zero-pool sentinel. Сам Coverage остаётся
максимум 7 searches; общий pipeline maximum с conditional agency discovery
равен **24**.

`retrieval_quality_contract_version=1` участвует в recovery. Modern full artifact
без завершённого Retrieval Quality v1 понижается до partial editorial recovery.
Agency discovery имеет независимый recovery contract: pending first attempt или
сохранённый response, которому нужны merge/freshness/editorial, также делает
full artifact partial; неопределённый `search_started` не повторяется.

## Source Freshness Proof v1

С 2026-08-17 модельные `published_at` и `published_date` больше не являются
достаточным доказательством свежести trusted production candidate. Перед каждым
editorial-проходом внутреннего Primary/rescue/Hybrid/Coverage runtime
`automation/scripts/source_freshness.py` бесплатно, без OpenAI и Web Search,
открывает только уже процитированные source URL и извлекает машинно-читаемое
время публикации (`article:published_time`, JSON-LD `datePublished` и
эквиваленты). `dateModified` не используется как дата публикации.

Сравнение с сохранённым effective `search_window` и перевод timezone делает
Python. Точный timestamp обязан попадать в окно; date-only evidence на
календарном дне cutoff недостаточно и fail-closed. Если primary source не отдаёт
пригодную дату, но уже цитируемый supporting source подтверждает свежесть,
supporting может стать primary. Нового поиска для этого нет.

Источник с подтверждённой датой вне окна исключает candidate как `old_reprint`.
Если ни один уже цитируемый источник не позволяет независимо доказать дату
публикации, candidate становится `unconfirmed` и не может быть опубликован.
Recovery freshness-error удаляет supplemental rescue rows из candidate pool,
чтобы непроверенный rescue не загрязнял ранее пригодный artifact.

Source Freshness Proof сам по себе не добавляет Search/OpenAI вызовов. Изменение
общего потолка 23 → 24 связано только с отдельным conditional
`agency_discovery_rescue`, а не с freshness-проверкой.

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
