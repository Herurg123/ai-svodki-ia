# Историческая независимая приёмка 8 сентября

Это сохранённый FAIL checkpoint. По новой команде владельца 9 сентября
ошибки исправлены и автономный diagnostic module прошёл повторную приёмку:
[`2026-09-09-step05-acceptance/README.md`](2026-09-09-step05-acceptance/README.md).
Исходные результаты ниже сохранены для воспроизведения.

8 сентября Terra выявила 4 проблемных контрольных сценария (подробности:
[сохранённая проверка](2026-09-08-step05-independent/README.md)). 66 локальных
тестов не заменяют независимую приёмку. После FAIL реализация остановлена.
Не подключённый к production `source_value_period.py` сохранён как непроверенный
черновик: необходимые observation IDs ещё не реализованы в producer.

9 сентября по команде пользователя начато отдельное исправление production run
34298397080. Пункт 5 приостановлен; его DOCX ещё не завершён, PR/merge не было.
Исторические состояния ниже сохранены для продолжения, не являются текущим PASS.

---

# Пункт 5 — сохранённый промежуточный результат, 8 сентября 2026

Статус: **частично подготовлен, НЕ принят**. База `54d07e84bcc2ceb0c63f54122183d3cb5641e183`.

## Третий checkpoint: подтверждение публикации в репозитории

Второй checkpoint сохранён коммитом `e109e92e863852bdd44cda77eb0adf9c1572fd4d`.
Добавлен `source_value_publication.py`: по явным repo/full SHA он читает только
committed canonical artifacts и страницу. SHA должен быть ancestor локального
`origin/main`, Pulse input совпадает побайтно, страница содержит заголовки и
точные source URLs всех stories. Draft worktree, unmerged commit, чужая/пустая
страница, другой Pulse input не могут подтверждать `repository_published`.
`published`/FTP delivery остаётся unknown; сетевых запросов этот reader не делает.

Реальный replay NVIDIA 2 сентября по main commit `54d07e8`: promoted=1,
post_freshness=1, editorial_selected=1, assembled_stories=1,
repository_published=1. FTP данным опытом не проверялся. Добавлены 5 offline Git/
page-provenance tests, включая hidden script text. Вместе с Pulse suite — 66 tests.

До приёмки остаются multi-release/recovery aggregation, явная политика отсутствия
данных и нулей, независимая оценка реализации, полный архитектурный/regression
gate. Поисковой runtime не менялся; пункт 5 ещё НЕ принят.

## Второй checkpoint: связка с редакционным отбором

Добавлен optional `--release-dir` и консервативный `source_pulse_trace.py`.
Проверяются дата выпуска, уникальность кандидатов, Pulse title/URL/provenance,
полный partition selected/excluded IDs и совпадение selected stories по ID,
источнику и полям события. Конфликты, отсутствующие artifacts и недостаточные
freshness states сохраняют unknown. Assembled stories не объявляются опубликованными.

Реальные положительный и отрицательный случаи сохранены независимо от retention
в `fixtures/recall/source-value-trace-2026-09.json`: NVIDIA 2 сентября — один Pulse
кандидат отобран; Yandex 6 сентября — кандидат добавлен, но не отобран. Fixture
явно сокращён, SHA256 оригиналов сохранены. Есть проверки recycled ID, same URL
different event, неполного partition, missing stories, unknown promotion и
отсутствия мутаций входных данных. Прошёл набор из 61 Source Pulse tests.

Следующее: доказательство publication отдельно от assembly, сравнение выпусков и
дедупликация recovery, затем независимая приёмка и полная проверка зависимостей.
Старые разделы ниже описывают первый checkpoint; его downstream-null ограничение
частично закрыто новым optional trace. Пункт 5 целиком по-прежнему НЕ принят.
Ветка `architecture/step05-source-value-20260907`. Пункт 4 отложен по команде
пользователя и сохранён отдельно в `architecture/step04-evidence-20260907`.
Изменения пункта 4 сюда не переносились. Пункт 6 не начат.

## Сделано

Автономный `source_pulse_value.py` читает один сохранённый JSON и разделяет:
source health, parsed/window items, accepted leads, promotion reasons и exact-URL
подтверждение merge acceptance. Он не оценивает полезность одним баллом и не
отключает источники. Недоступный источник не трактуется как отсутствие новостей.
Неизвестные downstream результаты остаются `null`.

Проверен текущий контракт v1.2/v1.3: `promoted` определяется совпадением исходного
`record.url` с принятыми URLs. Поэтому fetch `final_url`, общий host, название
компании и похожий заголовок не подменяют кандидатную идентичность.

На сохранённом запуске 34175843146: 13 источников, 10 со статусом `ok`,
3 `source_unavailable`, 0 promoted. Yandex: 30 parsed, 2 window/accepted leads,
2 отказа (неподтверждённая дата и AI relevance). Отбор/публикация данным CLI пока
не анализируются. Это один наблюдаемый выпуск, не оценка полезности за период.

Fixture `fixtures/recall/source-value-2026-09-08.json` — явно сокращённая копия
полей исходного Pulse report; provenance содержит ссылку на запуск и SHA256
исходного файла. Полный артефакт запуска имеет SHA256
`333cffb852c0e3eb1dc47887a5cb978190f375f720f3ad2a24428e2981b25089`.

## Проверки и пределы

Локальные проверки: stage separation, missing evidence, duplicate source IDs,
input immutability, same-host different-article collision и redirect identity.
Прогон CLI на настоящем сохранённом Pulse report выполнен без сети.
Независимая приёмка и полный regression gate **ещё не выполнялись**.
Поисковые запросы не менялись; поисковой Terra A/B для этого checkpoint не было.
Production не вызывает новый CLI. Платные API не запускались.

## Следующий шаг

1. Довести exact-event provenance через merged candidates, Event/Source Freshness,
   окончательный editorial selection и publication; неоднозначные связи — unknown.
2. Добавить корректное сравнение нескольких выпусков с различением отсутствующих
   данных и фактических нулей, recovery и повторных копий snapshot.
3. Проверить положительные случаи попадания Pulse-сюжета в публикацию и отказы на
   каждом этапе; подтвердить, что same-company/different-event не приписывается
   источнику. Оценить побочные зависимости по архитектуре проекта целиком.
4. Независимая приёмка, необходимый regression gate, DOCX. Только после успеха —
   PR и разрешённое пользователем слияние с проверкой main. Этот checkpoint не
   является завершением пункта 5 и не даёт права отключать источники.

## Статистика текущего окна

Возобновление пункта 5: 2026-09-08 06:34:22 МСК, 30% по сообщению пользователя.
До этого пользователь сообщил 41%; последние 11 п.п. относились к проверке
расходов и ответу, а не к реализации пункта 5. Живой счётчик ассистенту недоступен.
Отображаемый API spend 8 сентября: $0.25 по скриншоту; тарифная оценка $2.6769533
не подменяет этот показатель. Расхождение биллинга остаётся не сверенным.
