# Однократное сравнение Terra 5.6 и Terra 6.1, 28 октября 2026

**Статус:** 28.10 штатный выпуск успешно опубликован резервным `workflow_dispatch` run 40618839186 до scheduled run 40619686839. Запланированный job Terra 6.1 был `skipped`. Результатов Terra 6.1 пока нет; нельзя заполнять их задним числом.

## Поправка 28.10: восстановительный ручной запуск

- Разово вводится `workflow_dispatch.shadow_terra61=true` в существующий `Daily production digest` при `publication_date=2026-10-28`, `publish=false`, `force_fresh_research=false`, пустом `recovery_run_id`. Production и redeploy гарантированно пропускаются, даже если источник RSS временно пропадёт. Для самого эксперимента требуется положительная проверка `should_run=false`, то есть выпуск уже в RSS.
- Job требует `github.run_attempt=1` и сквозной guard `always()` на штатно пропущенных зависимостях, checkout exact original paid run head `eabe4855b7d604c4947f5c9f47df694a76be7680` и получает оригинальный `daily-production-2026-10-28` исключительно из run 40618839186.
- GitHub API перед первым API-запросом подтверждает точный оригинальный run ID / source SHA / завершённый status; дополнительно проверяется отсутствие прежнего артефакта `terra61-shadow-2026-10-28` (сериальная concurrency не позволяет второму job пройти одновременно). Результат старого штатного запуска не повторяется.
- В оригинальном fallback-артефакте **нет первоначального baseline manifest**, поскольку step был предназначен только для `schedule`. Нельзя утверждать, что он существовал. Для сравнения будет явно сформирован новый `terra61-reconstructed-baseline.json` с признаком `reconstructed_after_release_from_verified_unchanged_source_commit`: SHA всех исходных файлов из исторического коммита после той же runtime patch/bootstrap; подлинные сохранённые Primary и run-info исходного выпуска останутся неизменными.
- Воспроизведение исходных временных границ и архивной истории подтверждается оригинальным сохранённым run-info и primary-report. Честное ограничение: retrospective baseline, не независимый оригинал снимка до paid вызова. Результаты сравниваются с этой оговоркой. После опыта обязательное сохранение ZIP и удаление всего временного кодового механизма отдельным PR.

**Статус:** инструментирование до ручного запуска; результаты Terra 6.1 отсутствуют. Нельзя подменять исходные файлы реконструкцией.

## Согласование

Пользователь согласовал **один** дополнительный платный текстовый shadow-прогон полного конвейера 28 октября 2026 года в дополнение к штатному production Terra 5.6. Shadow-обложка, публикация, изменения `main`, RSS или архива не разрешены. Новых расписаний нет; job добавлен в существующий штатный workflow, доступен только для scheduled run с `run_attempt == 1`, датой `2026-10-28` и успешным production + deploy.

## Контракт сравнимости

1. Штатный production остаётся `gpt-5.6-terra`; у него по-прежнему фиксированная model check в workflow, запрет на обход публикационных checks, обычный image API и публикация.
2. До первого оплачиваемого вызова Terra 5.6 для 28 октября сохраняется `terra-compare-baseline-2026-10-28.json`: точный `HEAD SHA`, SHA-256 `automation/archive/index.json`, `site.json`, `editorial.json`, production config и трёх системных поисковых/редакторских промптов (после штатного локального patch `publication_hour=6`). На scheduled recovery без нового paid Research manifest не создаётся.
3. После фактического завершения production + deploy экспериментальная job checkout'ит ровно этот предрелизный SHA, скачивает final artifact Terra 5.6 **только для чтения контрольных полей**, сверяет baseline manifest по SHA-256, сравнивает id модели и 12/12 Primary. Кандидаты и редакторский JSON Terra 5.6 в Terra 6.1 **не передаются**.
4. Экспериментальная env `AI_DIGEST_TERRA61_SHADOW=2026-10-28` разрешает лишь модели `gpt-6.1-terra` использовать frozen `Primary search_window.end_at` и отдельно frozen редакторский `research_cutoff_at` из исходного final artifact Terra 5.6. В ordinary production env отсутствует. Текст редакторского ввода (включая cache boundary) идентичен, параметры reasoning medium, `store=False`, schema, limits — те же.
5. Запускаются `run_digest_preview.py --allow-provisional-editorial` (12 обязательных Primary, conditional agency rescue/Hybrid) и `ensure_story_coverage.py` (до 7 Coverage) с моделью Terra 6.1 и обычной цепью проверки. При потере одного mandatory search запуск fail-closed, без доплаты на иной модели; при аварии raw state сохраняется.
6. Shadow без image API, без `promote`, без `push_protected_main.sh`, без деплоя и любых git write permissions. Работа происходит исключительно в рабочей копии из checkout, результаты хранятся в `terra61-shadow-2026-10-28` через `actions/upload-artifact` (30 дней). `finish` записывает SHA-256 текстовых результатов, raw ingress, saved temporal boundaries, названия моделей и диагностику даже при неуспешном pipeline.
7. Один эксперимент не доказывает вероятностного превосходства; возможные отличия поздних Conditional Hybrid/Coverage обусловлены решениями модели, это измеряемый outcome. Поисковый сервис живой, поэтому выдача в разные часы может отличаться. Прямое сопоставление ведётся по frozen initial inputs, не по равным SERP снапшотам.

## Независимая офлайн-проверка и regression scope

Критерии тестов: staged baseline доступен только в `schedule`/attempt 1; изменённый архив запрещает shadow ещё до первого paid call; unexpected source SHA и незавершённые 12 Primary блокируют; frozen cutoffs пишутся как только проверены; `finish` не сообщает успех, если нет Coverage; повторный запуск отклоняется; workflow содержит один canonical cron; shadow не имеет доступа на push, не вызывает image API; clear production barriers сохранены. Проверка `test_terra61_shadow_once.py` + общие >900 offline CI tests. **Ни одного экспериментального API-запроса при подготовке не было**.

## Результат, который нужно сохранить после завтрашнего запуска

Сначала сохранить исходный ZIP `terra61-shadow-2026-10-28` **без изменения**; проверить SHA-256 GitHub Actions artifact и внутренний `terra61-shadow-manifest.json`; отдельно сохранить идентификатор исходного production run / artifact Terra 5.6, которыми он подтверждает свою frozen baseline. Слепое сравнение проводить позже, проверяя единицы событий, важность, даты и источники, стоимость (не включать обложку Terra 5.6 в сравнение text cost), поисковые операции и различие model misses vs validator rejects. ZIP хранится в Actions 30 дней, поэтому требуется скачать оригинал вне Actions до истечения срока.

После подтверждённого сохранения оригинального ZIP открыть cleanup PR, который удалит весь разовый shadow-job, добавленный baseline step, `terra61_shadow_once.py`, `test_terra61_shadow_once.py`, env overrides в `primary_recall_search_v2.py`, `generate_digest_preview.py`, экспериментальное расширение `prompt_context.py`, а также временные текстовые пометки. Сохранить этот `PLAN.md` и итоговый отчёт с SHA-256 как историческое evidence. Cleanup **не выполняется до получения оригинального ZIP**; иначе можно уничтожить ещё нужные данные.

## Ограничения

- Если штатный выпуск 28 октября был выпущен через recovery, а не fresh scheduled run, нет честной frozen baseline и платный shadow **не запускается**.
- Если native GitHub schedule не сработает и production пройдёт только через внешний `workflow_dispatch` backup, дата-гейтированный shadow в этой версии не запускается. Задача не должна автоматически создавать второй paid trigger.
- Исходные ответы Terra 5.6 сохраняются существующей production log/artifact политикой (14 дней); сохранение обоих оригиналов для исследования важно выполнить до retention.
- Shadow не создаёт cover, поэтому его результаты могут быть пригодны к экспертному сравнению даже без отдельного публикационного cover validator; валидность текстового контракта проверяется отдельно.
