# Независимый аудит выпуска 2026-09-03

## Итог

Publication/recovery path после исправлений #142, #144, #145 и #146 прошёл успешно: recovery run `33720878043` восстановил artifact `33719317861`, не запускал fresh Primary research, повторно провалидировал text artifact, сгенерировал cover, опубликовал commit `ce9f81b03c93ffb55e7397eae2c28110b639494b`; deploy и Main CI завершились успешно.

Отдельный retrieval-аудит выполнен по оригинальному fresh production artifact run `33702310841`, чтобы recovery не скрывал качество исходного discovery.

## Архитектурные инварианты

Проверены зависимости Primary → Source/Event Freshness → Source Pulse → Agency Rescue → Hybrid → Coverage → Editorial/validators → recovery/publication.

Изменение не должно:

- увеличивать Primary выше 12 search operations;
- увеличивать normal pipeline выше 24 или double-regional-gap выше 25;
- превращать Source Pulse в paid/Web Search слой;
- закрывать Search-derived Russia/China-Asia gap Pulse-only candidate;
- принимать `weak_source` без verified evidence;
- ослаблять freshness, publisher/organization diversity, provenance или recovery fail-closed.

Предлагаемый treatment не меняет ни один из этих контрактов.

## Что показал оригинальный run

Effective research window:

`2026-09-01T04:01:28+03:00` → `2026-09-03T04:07:02+03:00`.

Primary завершил 12/12 search operations. Реальные queries:

1. `global_breaking`: `latest major AI news models products business infrastructure`
2. `major_agencies`: `latest AI models research chips infrastructure financing earnings business deals policy security`
3. `models_products_agents`: `latest major AI models products agents research launches`
4. `infrastructure_chips_cloud`: `latest AI chips cloud data centers infrastructure energy Nvidia AMD hyperscalers`
5. `business_investment_partnerships`: `latest AI investment financing acquisitions partnerships enterprise deals`
6. `china_asia_models`: `latest China AI models releases Tencent Hunyuan Qwen DeepSeek GLM open source`
7. `china_asia_integrations`: `latest China Asia AI business earnings revenue strategy cloud partnerships deployments`
8. `russia`: `последние новости ИИ Россия Яндекс Сбер VK МТС продукты регулирование авторское право данные обучение моделей`
9. `developer_tools`: `latest coding agents developer tools Claude Code Cursor Copilot CLI updates`
10. `security_safety`: `latest AI security safety incidents prompt injection sandbox escape breach red teaming`
11. `legal_regulation`: `latest AI legal regulation copyright court decisions policy`
12. `independent_missing_events`: `latest major artificial intelligence news missing events`

Accepted counts: global 3, major agencies 0, models/products 4, infrastructure 0, business 0, China models 0, China integrations 0, Russia 0, developer tools 3, security 0, legal 1, independent sweep 3.

Оба regional health gap были открыты: China/Asia и Russia. Это подтверждает, что conditional fifth Hybrid search был архитектурно оправдан; его старый clean-process crash был отдельным runtime bug и уже исправлен #142.

## Хорошо

- Primary действительно расходует 12 независимых слотов, а не маскирует один широкий запрос под completeness.
- `major_agencies` уже содержит earnings, поэтому добавлять ещё один Reuters slot ради business treatment не требуется.
- Event/Source Freshness и weak-source rejection сработали fail-closed.
- Broadcom был замечен как потенциально крупное событие и не прошёл на одном HuggingNews: это правильное решение качества источника.
- Recovery не исказил аудит: оригинальный paid artifact сохранён и доступен для offline replay.

## Плохо / остаточные seam

- Business lane дал 0 accepted и не покрывал revenue/monetization/ads/earnings явным query contract.
- Broadcom: stronger Reuters evidence существовал в effective window, но после weak-source hit не был найден/resolved.
- Enflame IPO и OpenAI shutdown control отсутствовали в artifact.
- Snowflake AI/cloud-driven revenue forecast отсутствовал, хотя independent treatment query поднимает его.
- Поэтому 7 опубликованных сюжетов нельзя использовать как доказательство полного retrieval health.

## A/B решение

Подробности: `automation/audits/experiments/2026-09-03-business-query-ab.md`.

Control:

`latest AI investment financing acquisitions partnerships enterprise deals`

Treatment:

`latest AI investment financing acquisitions partnerships enterprise deals revenue monetization ads earnings`

Treatment сохраняет deal/funding surface и добавляет material AI-driven earnings/revenue recall. Наблюдаемый прямой выигрыш effective window: Snowflake Reuters. Цена — больше market/software noise.

Решение: **узкий GO только для business lane**, с deterministic exact-query overlay и явным требованием, чтобы AI был материальным драйвером события. Дополнительных search operations: 0.

## Source Pulse

OpenAI / Anthropic / European Commission registry expansion остаётся **NO-GO**. Существующий controlled fixture доказывает незакрытые first-party fetch/date/listing contracts. Production registry не меняется.

## Weak-source resolution

Broadcom показывает реальную архитектурную дыру, но автоматическое повышение `weak_source` до unresolved/verified не является безопасным исправлением. Текущий downstream не имеет отдельного bounded resolver для такого сигнала; добавление нового search slot нарушило бы бюджет, а простая смена статуса ослабила бы fail-closed.

Решение: **NO-GO в этом PR**. Нужен отдельный эксперимент по source-routing/resolution внутри существующих слотов или доказанный zero-paid resolver.

## Изменение

Public Primary wrapper фиксирует treatment-query только для `business_investment_partnerships` и сохраняет его в diagnostics как `business_query_treatment` с `additional_search_operations = 0`.

Добавлен regression, который проверяет:

- treatment только в business lane;
- отсутствие утечки в другие Primary directions;
- date-free / relative-freshness query discipline;
- сохранение investment/financing/acquisitions/partnerships/enterprise/deals;
- добавление revenue/monetization/ads/earnings;
- неизменный Primary budget 12.

## Документация

`README.md`, `automation/ARCHITECTURE.md` и `AGENTS.md` проверены. Они описывают budgets, слои и fail-closed контракты на архитектурном уровне и не фиксируют конкретный текст business query, поэтому обязательного изменения этих файлов для узкого query treatment нет. Детали решения сохраняются в этом аудите и experiment report, а runtime diagnostic делает treatment наблюдаемым в artifact.

## Экспериментальная стоимость

Production API/Web Search budget пользователя не использовался. Assistant-side независимый web A/B выполнен вне production. Terra как отдельный assistant tool в текущей сессии недоступна, поэтому результаты не маркируются как Terra experiment.
