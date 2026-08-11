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
календарные дни допустимы. Окно исследования начинается с фактического
`search_cutoff_at` последнего успешно опубликованного выпуска и заканчивается
фактическим pre-research cutoff текущего запуска; нормализованное `published_at`
06:00 МСК не создаёт слепую зону между запусками.

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
причиной `permanent_archive_branch`.

## Ежедневный производственный цикл

1. Gate проверяет RSS и живую страницу до любых платных API-вызовов.
2. Архив и временное окно проверяются относительно последнего успешного
   выпуска. Наличие его канонических файлов в GitHub остаётся жёстким gate;
   проверка статьи и обложки на живом сайте выполняется как диагностика и при
   временной сетевой/FTP/CDN-недоступности даёт warning, но не срывает новый
   независимый выпуск.
3. Свежий основной research выполняет **Primary Recall v2**. Жёсткий primary-
   бюджет по-прежнему равен **12 Web Search** operations, но теперь это не один
   агентный вызов, самостоятельно расходующий бюджет. Python-orchestrator
   запускает ровно двенадцать обязательных one-search проходов, каждый с
   `max_tool_calls=1`:
   `global_breaking`, `major_agencies`, `models_products_agents`,
   `infrastructure_chips_cloud`, `business_investment_partnerships`,
   `china_asia_models`, `china_asia_integrations`, `russia`, `developer_tools`,
   `security_safety`, `legal_regulation`, `independent_missing_events`.
4. Primary работает по принципу **discovery-first**. На retrieval-этапе лучше
   сохранить проверяемое потенциально важное событие как `consider`, чем
   потерять его до редакции. После каждого прохода кандидаты всё равно проходят
   существующие проверки окна, источников, freshness, дублей, legal/curiosity и
   значимости. Финальный `independent_missing_events` получает список уже
   найденного и ищет именно крупные события, отсутствующие в пуле.
5. Китай/Азия намеренно разделены на два прохода: модели/релизы и продуктовые
   интеграции/партнёрства. Исторический эксперимент на окне выпуска 2026-08-11
   показал, что одна широкая China/Asia-проверка подняла 5 из 6 контрольных
   событий, но пропустила интеграцию Apple/Qwen; отдельный integrations-pass
   поднял шестое событие без увеличения primary-бюджета. Regression fixture:
   `automation/fixtures/recall/2026-08-11.json`.
6. Все двенадцать primary-направлений обязательны. Технически незавершённый
   проход делает fresh primary красным и **не** может интерпретироваться как
   «новостей мало». Пустой результат нормально допустим только для успешно
   выполненного прохода. Диагностика сохраняет фактические запросы, источники,
   raw candidates, model rejections и validator rejections по каждому слоту.
7. Primary формирует обычный research artifact и передаёт его существующему
   editorial-generator через `--research-input`. Это позволяет не размножать
   editorial/validation-логику. Внешний `--research-input` по-прежнему означает
   recovery/editorial rerun и пропускает оплаченный fresh primary; внутренний
   research-input Primary Recall v2 считается свежим primary и получает ровно
   один нормальный hybrid-pass после него.
8. После свежего primary запускается отдельный `hybrid completeness` v1. Три
   фиксированных прохода получают по одному Web Search:
   models/products/agents/research, infrastructure/chips/business,
   safety/security/policy/major regional gaps. При полностью пустом тематическом
   кластере разрешён один adaptive gap search. Hard cap hybrid равен `4`, каждый
   запрос использует `max_tool_calls=1`; API domain filter намеренно отсутствует.
9. Hybrid-кандидаты проходят тот же `story_coverage` validator. Editorial
   повторяется только при реально принятом новом кандидате. Caller-supplied
   `--research-input` rerun и recovery не запускают hybrid рекурсивно. При
   технической ошибке hybrid baseline primary artifact сохраняется или
   восстанавливается.
10. Если после primary + hybrid достойных сюжетов меньше обычной цели,
    выполняется обязательный fallback coverage audit: шесть отдельных
    тематических Web Search-проходов и один резервный слот. Если обязательное
    направление технически не завершено, резерв расходуется на его повтор. Если
    все шесть завершены, но пригодный пул нулевой, седьмой слот становится
    `high_signal_recall_sentinel` версии 7.
11. `gpt-image-2` создаёт одну PNG-обложку 1536×864; валидатор проверяет её
    технический контракт. Legacy-staging исторических обложек остаётся
    best-effort слоем совместимости.
12. Кандидат сайта получает RSS, sitemap и Schema.org и проходит офлайн-
    валидацию. Только проверенное состояние записывается одним commit в `main`,
    после чего `deploy-posts.yml` разворачивает именно этот SHA.

Теоретический worst case retrieval не изменился: **12 primary + до 4 hybrid +
до 7 coverage = 23** завершённых `search` operations. Полный день не оплачивает
тяжёлый fallback audit после того, как primary + hybrid уже дали обычный выпуск.
Служебные `open_page` и `find_in_page` видны в диагностике, но не считаются
поисковыми операциями.

Шесть обязательных направлений fallback coverage audit:

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
high-signal recall sentinel v7. Его адресный запрос остаётся аварийным
regression-probe класса security-пропусков, а не заменой основного поиска.

Короткий выпуск допускается только после фактического завершения всех шести
fallback-направлений. Пустой результат отдельного направления нормален и даёт
`complete_with_gaps`; технически неполный audit блокирует Image API, commit и
deploy. Если после завершённого Primary Recall v2, hybrid completeness, полного
fallback audit и актуального zero-pool recall sentinel итоговый пул всё ещё
пуст, workflow создаёт переиспользуемую редакционную остановку без публикации.
Это штатный зелёный `no-publish`.

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
- путь или рубрика URL источника не определяют редакционную категорию;
- curiosity необязателен, должен быть проверяемым и может дать не более одного
  выбранного сюжета;
- URL, заголовок и издатель источника принадлежат исследовательскому пулу:
  редактор может выбрать и процитировать источник, но перед валидацией
  метаданные известного нормализованного URL программно восстанавливаются из
  `candidates.json`; неизвестный URL блокирует выпуск.

Канонический источник правил —
[`automation/specs/editorial-policy.md`](automation/specs/editorial-policy.md).

## Расписание, ручной запуск и recovery

Основной GitHub cron ежедневного workflow задан на `23:17 UTC` предыдущего
календарного дня — это `02:17 МСК` даты выпуска. Внешний резервный запуск через
cron-job.org сохраняет независимую страховку. GitHub Actions может фактически
запустить schedule позднее; cron является триггером, а не гарантией минуты.

- плановый запуск всегда публикует результат;
- ручной `workflow_dispatch`: `publish` — по умолчанию `false`;
- `publication_date` задаёт необязательную дату `YYYY-MM-DD`;
- `recovery_run_id` позволяет явно переиспользовать сохранённый artifact;
- без явного ID workflow автоматически ищет пригодный artifact той же даты,
  предпочитает наиболее полный результат: готовая обложка → готовый digest →
  research-only; свежесть используется как tie-break;
- уже оплаченные стадии повторно не запускаются без необходимости;
- fresh Primary Recall v2 вызывает hybrid completeness один раз; любой
  последующий caller-supplied `--research-input` rerun его пропускает;
- primary diagnostics сохраняются как `primary-recall-YYYY-MM-DD.json`, а
  подготовленный research — как `primary-recall-research-YYYY-MM-DD.json`;
- hybrid merge и диагностика сохраняются в соответствующих
  `hybrid-completeness*.json` artifacts;
- если recovery восстановил готовый выпуск и coverage/editorial/Image API не
  нужны, workflow не устанавливает OpenAI SDK и не требует `OPENAI_API_KEY`;
- завершённый нулевой primary-пул может продолжить hybrid и обязательный
  coverage только если все 12 primary Web Search действительно завершены;
- полный coverage audit и sentinel текущей версии переиспользуются без новых
  запросов; partial audit продолжает только незавершённые направления;
- повторный резервный запуск после готового выпуска завершается бесплатным
  no-op, а если commit уже есть, но живой URL недоступен, выполняется только
  FTP-redeploy.

Production-artifacts создаются с `retention-days: 14`, но repository hygiene
может удалить уже ненужные опубликованные artifacts раньше по безопасному окну.
Artifacts неопубликованной актуальной даты защищены для recovery.

## Модели и доступы

- секрет `OPENAI_API_KEY` нужен только production-этапу;
- `OPENAI_TEXT_MODEL` по умолчанию и текущему контракту — `gpt-5.6-terra`;
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
- перед commit проверяются RSS, даты, страницы, изображения, индексы и sitemap;
- плановый запуск применяет очистку автоматически, ручной по умолчанию dry-run;
- срок хранения нельзя уменьшить ниже 32 дней;
- после успешного commit FTP синхронизируется с точным созданным SHA.

## Правила инженерной уборки GitHub

`repository-hygiene.yml` отделён от очистки выпусков. Плановый запуск в 15:43
МСК применяет только доказуемо безопасные операции; ручной `workflow_dispatch`
по умолчанию audit-only и требует `apply=true` для destructive-фазы.

- `archive/search-baseline-pre-hybrid-2026-08-09` всегда защищена как
  `permanent_archive_branch`;
- `main`, protected branches, ветки открытых PR и ветки с активным Actions-run
  не удаляются;
- старые merged-ветки удаляются только при доказуемом совпадении HEAD с PR;
- Actions artifacts чистятся только по описанным безопасным retention-правилам;
- orphan workflow безопасно отключается только после canonical absence из
  текущего `main`; GitHub Pages platform-managed workflow остаётся диагностикой;
- completed runs старше 14 суток удаляются только для независимо доказанного
  `safe_disable` orphan workflow;
- source scanner report-only и никогда не меняет tracked-файлы;
- перед destructive-фазой повторно проверяется SHA `main`; при активном
  production-run Actions-уборка пропускается;
- tracked project files, releases, tags, published/editorial content и
  permanent archive branches этим workflow не изменяются.

Канонический алгоритм: `automation/scripts/repository_hygiene_policy.py`, GitHub
runtime: `automation/scripts/repository_hygiene.py`.

## Основные каталоги

- `automation/content/YYYY-MM-DD/` — структурированные материалы выпусков;
- `automation/archive/index.json` — архив для антидублей и обновлений;
- `automation/archive/search-baselines/` — manifests постоянных retrieval-
  baseline-точек;
- `automation/config/` — production-, editorial-, site- и image-конфигурация;
- `automation/prompts/` — primary recall, legacy research, editorial и
  coverage-audit промпты;
- `automation/fixtures/recall/` — исторические retrieval-regression окна;
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

Контракт версионируется. Recovery не переиспользует legacy research без текущей
версии temporal anchor, если локальная дата конца окна уже опережает UTC-дату.
Для такого кросс-полуночного legacy artifact research выполняется заново.
Coverage audit старой версии также не считается окончательной нулевой
остановкой. Это сознательно допускает повторную оплату только для доказанно
ненадёжного временного класса artifact, сохраняя обычный recovery для остальных
случаев.
