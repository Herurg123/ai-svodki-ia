# 2026-08-24: agency discovery rescue v3 context-size follow-up

## Решение

После production false-zero v2 меняется только одна retrieval-переменная:
`AGENCY_DISCOVERY_SEARCH_CONTEXT_SIZE = "medium"` → `"high"`.

Не меняются:

- trigger: только технически завершённый `major_agencies` с `raw_count == 0` или `accepted_count == 0`;
- search operations: максимум 1;
- query: `latest AI chips infrastructure financing earnings business deals policy security`;
- provider routing: `allowed_domains=["reuters.com"]`;
- downstream source acceptance: только прямой `reuters.com` primary URL;
- Source Freshness Proof, significance/editorial, archive и same-event dedupe;
- China/Asia и Russia routes;
- Hybrid и Coverage budgets;
- global theoretical ceiling: 24 search operations.

Rescue contract version повышается с 2 до 3, чтобы production artifact явно
показывал применённую конфигурацию.

## Production evidence

Fresh manual production run: `32691255059`.

Run выполнялся на merged recovery/retrieval patch `082c4aecac21790e169212993001f8314f0f8bd4`
и не переиспользовал старый same-day zero-pool artifact. Research и Coverage
технически завершились, но итог снова стал `editorial_stop`.

Сохранённый `agency-discovery-rescue.json` показывает:

- `version = 2`;
- `trigger_reason = major_agencies_raw_zero`;
- `state = completed_no_addition`;
- `query = latest AI chips infrastructure financing earnings business deals policy security`;
- `allowed_domains = ["reuters.com"]`;
- `search_context_size = medium`;
- `search_operation_limit = 1`;
- `search_operation_count_contribution = 1`;
- `api.web_search_calls_completed = 1`;
- `api.actual_queries` содержит ровно один ожидаемый query;
- `api.consulted_sources = []`;
- `raw_count = 0`;
- `accepted_count = 0`;
- `added_count = 0`.

Это локализует дефект до retrieval/provider ranking самого Reuters-only rescue:
ни один Reuters candidate не дошёл до validator, Source Freshness Proof или
editorial. Следовательно, downstream filtering не объясняет этот false-zero.

## Positive control

В effective window присутствовал high-signal Reuters event от 23 августа 2026:
Alibaba объявила Hong Kong share placement примерно на $10.2 млрд и заявила,
что net proceeds направляются на full-stack AI, включая chips, infrastructure,
model development и deployment.

Direct Reuters URL:
`https://www.reuters.com/business/retail-consumer/alibaba-proposes-hong-kong-share-placement-worth-10-billion-2026-08-23/`

Этот event остаётся clean positive control: material business/AI-infrastructure
событие, прямой Reuters source и timestamp внутри окна. Независимый
assistant-side Reuters-focused search с тем же publisher-neutral query может его
поднять, тогда как production v2 `medium` route вернул вообще ноль consulted
sources.

## Ограничение эксперимента

Текущая assistant environment не предоставляет standalone Terra/Web Search API
с явным переключателем `search_context_size=medium/high`. Поэтому нельзя честно
назвать это isolated assistant-side Terra A/B.

Также провалившийся mandatory Primary `major_agencies` уже использовал `high`, но
это не чистый контроль для rescue: Primary одновременно ранжировал Reuters, AP,
Bloomberg и FT, тогда как rescue имеет отдельный Reuters-only provider pool.

Поэтому v3 трактуется как **минимальная следующая production-supported
reliability-гипотеза**, а не как доказательство, что `high` универсально лучше
`medium`.

## Почему не меняется query одновременно

Одновременная замена context size и search query уничтожила бы возможность
понять, какая переменная повлияла на recall. Сначала проверяется только
`medium → high` при полностью неизменном query и routing.

Если следующий авторизованный fresh production run с v3 снова вернёт
`consulted_sources=[]` / `raw_count=0`, гипотеза context size считается
неподтверждённой. Следующим отдельным bounded experiment должен стать более
короткий publisher-neutral query, например тематический вариант класса
`AI chips infrastructure financing deals`, без увеличения search count и без
одновременного изменения freshness/editorial rules.

## Offline regression contract

`automation/tests/test_aug24_agency_recovery_contract.py` должен фиксировать:

- rescue version 3;
- Reuters-only provider routing;
- `search_context_size == "high"`;
- один search operation;
- global ceiling 24;
- прежний date-free publisher-neutral query;
- direct Reuters acceptance и отказ AP/syndication в этом rescue;
- сохранение positive/negative controls fixture;
- отсутствие ложного утверждения о завершённом isolated `medium/high` A/B.

## Production budget boundary

Подготовка patch, документация, regression tests и CI не используют
пользовательский production OpenAI API. Реальный `force_fresh_research=true`
run после merge является отдельным платным production действием и запускается
только после явного разрешения владельца.
