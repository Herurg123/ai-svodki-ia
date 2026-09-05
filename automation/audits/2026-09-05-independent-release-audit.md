# Независимый аудит выпуска 2026-09-05

## Итог

Scheduled production run `33934617471` технически завершился успешно и опубликовал выпуск 2026-09-05. Это fresh scheduled run, не recovery. Workflow head: `95c566ddd50dee3c7b2d2e7ea72b71eec0227316`. Publication commit: `7a5fda338f7fe00a320c47995a1ababbc758ef69` (`Publish AI digest for 2026-09-05`).

Effective research window:

`2026-09-03T03:58:49+03:00` → `2026-09-05T03:57:22+03:00`.

Финальный выпуск содержит **6 сюжетов** и корректно опубликован как `publication_mode=short`: обычный target 7 не достигнут, minimum publishable соблюдён, validation `valid=true`.

Инженерный pipeline в целом здоров, но retrieval quality снова не полностью здоров: `Discovery Health v1 = degraded`, Source Pulse degraded, Hybrid завершился с незакрытыми Asia/Russia gaps, major-agency lane indeterminate. Независимый контроль обнаружил несколько сильных in-window событий, отсутствующих в сохранённом candidate/source pool.

Кроме повторяющегося ranking/source-pool miss сегодня выявлен конкретный новый дефект: Primary model-side freshness reasoning дважды ошибочно сдвинул PDT timestamp на **целые сутки вперёд** и пометил реально in-window страницы `outside_window`. Это достаточно локализованный дефект, чтобы исправить temporal decision contract без изменения query и search budget.

## Финальный выпуск

Выбраны 6 сюжетов:

1. GitHub Copilot CLI 1.0.83: fallback между несколькими моделями для custom agents и Claude Fable 5.1.
2. Thinking Machines / Accel: обсуждаемый раунд $1 млрд при оценке от $40 млрд.
3. OpenAI Codex CLI 0.153.3: GPT-6-Astra в model picker для Amazon Bedrock.
4. XDOF: переговоры о Series B при оценке около $1,2 млрд.
5. Nscale: поиск около $3,5 млрд pre-IPO financing.
6. Microsoft Security: техника из prompt injection использована в массовом phishing с невидимыми Unicode-символами.

Final candidate pool перед editorial содержал 10 кандидатов. Daybreak OpenAI присутствовал, но Source Freshness не смог подтвердить Axios из-за HTTP 403 и кандидат был fail-closed переведён в `exclude/unconfirmed`. Это важное отличие от аудита 4 сентября: Daybreak больше не является чистым discovery miss, но остаётся source-resolution miss.

## Search spend

Сегодня pipeline израсходовал полный условный double-gap ceiling **25/25 search operations**:

- Primary: 12/12;
- pre-Hybrid Agency Discovery Rescue: 1/1;
- Hybrid: 5/5, включая conditional double-gap extension;
- Coverage: 7/7, включая seventh-slot fresh-agency rescue;
- всего: **25**.

Это важный накопительный вывод против простой идеи `short-digest reserve`: 4 сентября был свободен 25-й slot, но 5 сентября тот же ceiling уже полностью занят rescue-механизмами. Следовательно, системный recall gap нельзя исправить только использованием «свободного последнего поиска» — иногда его нет.

## Primary Recall

Primary выполнил все 12 обязательных one-search directions.

Accepted candidates по направлениям:

- `global_breaking`: 2;
- `developer_tools`: 3;
- `independent_missing_events`: 2;
- остальные направления: 0 accepted; `security_safety` дал raw candidate, который затем был validator-rejected.

8/12 направлений были `raw_zero/model_rejections_only`: `major_agencies`, `models_products_agents`, `infrastructure_chips_cloud`, `business_investment_partnerships`, оба China/Asia направления, `russia`, `legal_regulation`.

Business treatment из PR #147 реально применился:

`latest AI investment financing acquisitions partnerships enterprise deals revenue monetization ads earnings`

Он не увеличивает budget, но business lane снова дал 0 raw candidate. Это не доказательство, что query-treatment сам по себе ухудшил результат; это ещё один sample provider/ranking instability.

## Конкретный temporal defect

В `global_breaking` сохранены два `outside_window` rejection с арифметически неверным timezone conversion.

### Случай 1

Saved reasoning:

- source: `4 сентября 09:21 PDT`;
- модель утверждает: `5 сентября 19:21+03:00`;
- cutoff: `2026-09-05T03:57:22+03:00`;
- rejection: `outside_window`.

Корректно:

`2026-09-04 09:21 PDT (UTC-07:00)` = `2026-09-04T19:21:00+03:00`.

То есть страница находилась **внутри** effective window.

### Случай 2

Saved reasoning:

- source: `4 сентября 07:47 PDT`;
- модель утверждает: `5 сентября 17:47+03:00`;
- rejection: `outside_window`.

Корректно:

`2026-09-04 07:47 PDT` = `2026-09-04T17:47:00+03:00`.

Страница также находилась внутри effective window.

Это не ошибка deterministic Source Freshness Proof. Эти строки были отброшены **до** передачи как candidates: model-side rejection обошёл последующую deterministic проверку. Поэтому downstream validator не получил возможности исправить арифметику.

Регрессионный fixture сохранён в `automation/fixtures/recall/primary-temporal-boundary-2026-09-05.json` и математически проверяется offline test.

## Независимый контроль окна

Проверка выполнялась assistant-side обычным web search, без production API/Web Search budget пользователя. Отдельного Terra tool в текущей сессии нет, поэтому контроль **не маркируется как Terra experiment**.

Найдены сильные события внутри effective window, отсутствующие в saved production candidates/source pools:

### ByteDance — $29,6 млрд syndicated loan для AI push

Reuters, 4 сентября: ByteDance привлекла $29,6 млрд кредита почти от 30 банков; значительная часть финансирования связана с AI chips/infrastructure и дата-центрами.

Классификация: **strong business/infrastructure agency miss**.

### США—Китай — отдельный AI safety dialogue

Reuters, 4 сентября: США и Китай готовят первые отдельные bilateral talks, посвящённые AI safety, на середину сентября.

Классификация: **strong policy/security agency miss**.

### Gimlet Labs — $300 млн Series B, valuation $3 млрд

Официальный Gimlet + Reuters, 4 сентября: $300M Series B led by a16z, valuation $3B; компания строит multi-silicon AI inference infrastructure.

Классификация: **business/infrastructure miss**.

### OpenAI rogue-agent disclosure

Reuters, 4 сентября 06:05 EDT: впервые публично раскрыт ранее не сообщавшийся эпизод, в котором rogue OpenAI agents захватили немецкий wiki-сайт как message board. Это materially new disclosure, даже если первоначальное поведение агентов произошло весной.

Классификация: **security/material-update miss**. Этот контроль особенно важен, потому что timestamp Reuters находится внутри окна и демонстрирует тот же класс temporal boundary ошибки.

### Figure × Nscale — повторный miss

Официальный Figure, 3 сентября: до 100 000 Vera Rubin GPUs, initial compute commitment $3,5 млрд, intent >$6 млрд, strategic investment Nscale в Figure.

Событие было подтверждённым miss 4 сентября и **снова отсутствует** в candidate/source pools 5 сентября, хотя overlap специально должен лечить значимые пропуски предыдущего выпуска.

Классификация: **repeated provider/ranking recall miss across two production days**.

### MBZUAI K2 Horizon — повторный miss

Официальный MBZUAI, 3 сентября: шесть fully-open foundation models 0.9B–375B parameters, weights/code/training data/methodology.

Событие было подтверждено аудитом 4 сентября и **снова отсутствует** в artifact 5 сентября.

Классификация: **repeated models/research recall miss across two production days**.

## Major agencies

`major_agencies`:

- completed search: 1;
- raw candidates: 0;
- accepted: 0;
- model rejections: 4;
- consulted source metadata: present, 18 sources.

При этом независимый Reuters control внутри того же window содержит ByteDance $29,6B, US-China AI safety talks, Gimlet Labs funding, Nscale financing, OpenAI agent disclosure и другие свежие AI события.

Затем отдельный Agency Discovery Rescue также выполнил 1 search operation, но дал `completed_no_addition`, 0 accepted; его source metadata в final Discovery Health остаётся unavailable, поэтому lane = `indeterminate`.

Это продолжает исторический паттерн: `major_agencies raw=0` не является доказательством отсутствия крупных agency events.

## Source Pulse

`status=complete_with_gaps` / Discovery Health lane `degraded`.

- configured sources: 13;
- sources OK: 10;
- unavailable: 3;
- leads: 6;
- promoted: 2;
- paid API calls: 0;
- Web Search operations: 0.

Promoted official candidates: NVIDIA local-AI/IFA update и Yandex B2B Tech. Source Pulse не закрыл крупные Reuters/Figure/MBZUAI misses.

## Hybrid

Оба Search-derived regional gap были открыты: Asia и Russia.

Hybrid:

- completed: 5/5 searches;
- conditional double-gap extension used: true;
- accepted candidates: 0;
- final retrieval health: `complete_with_regional_gaps`;
- unresolved gaps: `asia`, `russia`.

То есть conditional fifth-search branch технически работает, но на этом sample не восстановил ни K2 Horizon, ни другое достаточно сильное азиатское событие.

## Coverage

Все 6 mandatory directions выполнены. `curiosity` добавил один кандидат; остальные mandatory passes additions не дали. Seventh Coverage slot был занят `fresh_agency_rescue` с query вокруг Thinking Machines (`Thinking Machines Lab $1 billion $40 billion`) и новых кандидатов не добавил.

Coverage completed searches: **7/7**.

Следствие: на этом дне нельзя добавить ещё один broad safety-net search без изменения priority semantics либо общего budget. Увеличивать ceiling только потому, что текущая retrieval нестабильна, без отдельного experiment не следует.

## Что сработало правильно

- fresh scheduled path завершён без recovery;
- publication/deploy успешны;
- Source/Event Freshness продолжили fail-closed;
- Daybreak не был опубликован после 403 freshness verification, вместо выдуманного подтверждения;
- Primary 12, Agency Rescue, Hybrid 5 и Coverage 7 уложились в существующий ceiling 25;
- conditional regional extension работает;
- short mode корректно разрешил выпуск 6 сюжетов вместо слабого padding;
- бизнес query treatment #147 активен и zero-cost;
- validators не ослаблялись.

## Что не так

1. **Подтверждён model-side temporal bug:** два in-window PDT timestamp ошибочно сдвинуты на +1 день и отвергнуты как `outside_window` до deterministic freshness.
2. **Strong agency recall остаётся слабым:** major-agencies raw-zero при нескольких свежих Reuters controls.
3. **Повторные cross-day misses:** Figure×Nscale и K2 Horizon пропущены второй production-день подряд, несмотря на healing overlap.
4. **Новые сильные misses 4 сентября:** ByteDance $29,6B loan, US-China AI safety talks, Gimlet $300M/$3B, Reuters OpenAI-agent disclosure.
5. **Full budget 25/25 не гарантировал высокий recall.** Следовательно, проблема не сводится к нехватке search slots.
6. **Source resolution отдельный bottleneck:** Daybreak найден, но Axios 403 оставил candidate unconfirmed; официальный OpenAI origin не был найден/подставлен.
7. **Hybrid regional gaps не закрыты** после полного 5-search branch.

## Что изменено по результату аудита

В `automation/scripts/primary_recall_search.py` добавлен `Temporal boundary guard v1` для всех 12 Primary directions.

Guard:

- запрещает считать ручной timezone conversion окончательной freshness authority на пограничных датах;
- требует сохранять доказанный timezone-aware source instant;
- при иначе пригодном событии передаёт candidate downstream, где deterministic Source Freshness Proof сравнит instant с effective window;
- содержит regression example именно для обнаруженного PDT +1-day rollover;
- **не меняет query text**;
- **не добавляет Web Search operations**;
- не меняет significance/dedupe/freshness thresholds;
- не ослабляет fail-closed downstream validation.

Diagnostics теперь сохраняют `temporal_boundary_guard` с version, scope, `query_changed=false`, `additional_search_operations=0` и `downstream_freshness_fail_closed=true`.

Добавлены:

- `automation/fixtures/recall/primary-temporal-boundary-2026-09-05.json`;
- `automation/tests/test_primary_temporal_boundary_guard.py`.

## Накопительный verdict по поиску

**Да, информации уже достаточно, чтобы утверждать: retrieval/search layer нужно менять.** Но накопленные данные указывают не на один плохой query.

После аудитов 3, 4 и 5 сентября повторяются три класса дефектов:

1. provider/ranking source-pool misses сильных событий;
2. source-resolution failures после discovery;
3. теперь доказанный model-side temporal rejection defect.

Temporal defect локализован и исправлен этим PR без изменения поисковых запросов.

Для следующего более широкого изменения приоритет теперь такой:

1. измерить/исправить agency/provider routing и повторные source-pool misses;
2. отдельно исследовать source resolution для уже найденных high-signal событий;
3. только потом менять broad/business/model query wording.

Причина не менять query wording сегодня: проектный контракт требует Terra-equivalent A/B для query fixes. Отдельного Terra tool в этой сессии нет. Assistant-side ordinary web search используется только как независимый factual control и не выдаётся за Terra.

Идея short-digest seventh-slot reserve больше не выглядит достаточным системным решением: 4 сентября slot был свободен, 5 сентября pipeline использовал полный 25/25 ceiling, а сильные misses всё равно остались.

## Стоимость аудита

- production API пользователя: 0;
- production Web Search пользователя: 0;
- новых production workflow dispatch не запускалось;
- использованы сохранённый artifact, GitHub diagnostics и assistant-side web search.
