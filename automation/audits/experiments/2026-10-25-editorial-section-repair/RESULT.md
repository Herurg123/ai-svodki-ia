# 2026-10-25: локальная нормализация редакционных разделов

## Production incident и доказательства

- Scheduled run [40149481587](https://github.com/Herurg123/ai-svodki-ia/actions/runs/40149481587), SHA `de8ecea028e56630c0d1667800e806cd08c9c407`. Research завершён; обязательный Coverage завершил 6/6 search directions и дал один дополнительный кандидат. Protected Editorial response сохранён: `editorial-repair-2026-10-25.json: state=response_saved`. Run остановился **после** провайдерского ответа при проверке раздела h3[2].
- Прямая причина: `editorial_policy.py::expected_editorial_heading()` раньше делала substring-match `Moonshot AI` в любом месте `organization` или `title`. Исходный кандидат №002: `organization="CyberCartel; Anthropic; xAI; Moonshot AI; Straiker"`, `geography=world`. Редактор правильно поместил сюжет о киберпреступности в мировые новости, но checker ошибочно требовал китайский раздел.
- Повторные runs [40153101612](https://github.com/Herurg123/ai-svodki-ia/actions/runs/40153101612) и [40156963548](https://github.com/Herurg123/ai-svodki-ia/actions/runs/40156963548) переиспользовали saved responses, `response_attempts=0`, и остановились на той же проверке. Новый платный search/editorial не требовался.
- Original production artifact `daily-production-2026-10-25`, ID **12581862386**, ZIP SHA-256 `69c82048714ff2ddfdafd5a57a3edfeeaf7ee5ee81bfa7f1a76825bc56509adb` (сверен с GitHub Actions digest). Не изменён; завершается retention 2026-11-08.
- Контроль оригинальной сохранённой статьи: 7 selected candidates, 7 h3 stories; CyberCartel h3[2] находится под `Мировые лидеры ИИ`. Сравнение baseline vs proposed на оригинальных полях кандидата: `old=china`, `new=world`, `actual=world`. Это **отдельная независимая read-only проверка исходного артефакта**, не воспроизведение всего CLI-сценария.

## Изменение поведения

1. `expected_editorial_heading()` определяет China по *ведущему* участнику (`organization` до первого `;`) либо компании в начале заголовка. Russia остаётся по `geography=russia`; упоминания китайского вендора во второстепенной роли не переводят криминальный сюжет в China.
2. После source-link identity и event-duplication проверки, но **до** финального editorial validation, `normalize_article_html()` переносит **целый** story HTML block в нужный раздел. Содержание текста, URL и число stories не меняются. Если нужного непустого тематического раздела нет, он добавляется. Если старый заголовок остался пустым, удаляется. Порядок world/China/Russia становится каноническим.
3. После перемещения `selected_candidate_ids` вновь вычисляются только из однозначного source-link mapping; изменения фиксируются в `policy-normalization.json` и `editorial_notes`. Сохранённый provider response и repair journal не изменяются. Провайдер не вызывается второй раз.
4. Двусмысленная идентификация источника, несбалансированный HTML, некорректные события, archive/freshness и структурные ошибки **не** превращаются в допуски к публикации. Это изменение географической *рубрикации*, не ослабление редакционного качества.

## Независимая baseline/proposal-матрица

| Case | Baseline | Proposed | Применимость |
|---|---|---|---|
| E1: incident CyberCartel с упоминанием Moonshot как инструмента | ошибочное требование China, блокировка | world, без исправления контента; валидатор проходит | подтверждено на полях оригинального artifact + новый offline test |
| E2: Moonshot/MiniMax как главный субъект, но HTML в world | ошибка размещения, публикация остановлена | целый h3 блок переносится в China, URL неизменны | offline tests |
| E3: Russia candidate в world | ошибка размещения | целый блок переносится в Russia, число сюжетов сохраняется | offline tests |
| E4: Story source URL становится неоднозначным | identity validation blocks | **тот же блокирующий source check** до normalizer | имеющиеся source-binding tests |
| E5: Непарный HTML / контентная ошибка | strict publication gate | strict publication gate | offline test и существующие валидаторы |
| E6: 21 октября MiniMax semantic repeated event | strict event identity guard с approved hash-bound repair | guard остаётся на прежнем месте до section normalizer, без удаления новых событий | Oct 21 regression tests |
| E7: Freshness/search budgets/recovery | без изменения | без изменения: 0 дополнительных provider calls; saved response replay прежний | Main offline suite + workflow unchanged |

Результат [Required PR Gate](https://github.com/Herurg123/ai-svodki-ia/actions/runs/40168049766): **954 offline tests passed**, включая новые section tests и существующий Oct 21 semantic-event guard. Video CI не запускался для не-видео файлов (нормально).

## Архитектурные последствия и ограничения

- Поведение Primary, Source Pulse, agency rescue, Hybrid и Coverage (включая 24/25 search ceiling) не меняется; изменения только после Research в HTML normalization.
- No more paid retry for section error; P0 durable editorial completion всё ещё `response_saved` до корректной offline revalidation. Не изменены journal SHA, at-most-once, same-bundle recovery.
- Полный replay оригинального 25.10 release из GitHub Actions bundle в живом runner *не проводился*: он требовал бы отдельного recovery exercise с релизными правами. Зелёный CI плюс item-level offline proof не является доказательством состоявшейся публикации.
- Principal-actor heuristic основана на сохранённых строках; если главным действующим лицом окажется **не** первая организация и имя не указано в начале заголовка, требуется более богатая структурная attribution metadata. Это возможный false-world edge case. Нельзя исправлять его автоматическим внешним semantic LLM без отдельного бюджета/безопасной матрицы.
- Нельзя автоматически скрывать структурные ошибки (двусмысленные URL, дубли, несбалансированный HTML); «не блокировать из-за рубрики» не означает «публиковать непроверенные новости».

## Решение/rollout

Этот PR draft, main неизменен. Для rollout нужен отдельный approval merge. Для восстановления выпуска 25.10 после merge используйте **same-day** `recovery_run_id=40149481587` и saved artifact, без `force_fresh_research`, предварительно подтвердив release/rollback procedure. Нельзя повторно запускать полный paid research ради перекладывания HTML.
