# Business recall query A/B — 2026-09-03

## Цель

Проверить запланированную гипотезу из аудита 2026-09-02: можно ли улучшить recall бизнес-событий, не добавляя новый paid/Web Search slot и не переписывая остальные Primary-направления.

## База

Оригинальный fresh production run: `33702310841`.

Effective window исходного research:

- `2026-09-01T04:01:28+03:00`
- `2026-09-03T04:07:02+03:00`

Primary выполнил ровно 12/12 search operations. Фактический business query был:

`latest AI investment financing acquisitions partnerships enterprise deals`

Business-pass завершился с `accepted_count = 0`.

## A/B

### A — production control

`latest AI investment financing acquisitions partnerships enterprise deals`

Наблюдавшийся независимый search sample сохранял хорошие deal/funding hits, включая Anthropic infrastructure commitments и Wonderful funding. При этом в sample не поднялся свежий Snowflake earnings/outlook event, который был заметным AI-driven business событием effective window.

### B — treatment

`latest AI investment financing acquisitions partnerships enterprise deals revenue monetization ads earnings`

Treatment сохранил financing/deals results и дополнительно поднял:

- Snowflake: повышение annual revenue forecast на фоне cloud/AI demand; Reuters, 2026-09-02;
- OpenAI Ads: $1B annualized revenue run rate; Axios, 2026-08-31, то есть полезный контроль предыдущего healing-overlap паттерна, но не основание обходить freshness;
- SB Energy IPO / AI-infrastructure business context; Reuters, 2026-09-01.

Treatment также добавил шум: обычные software/private-equity/market results, где AI не является материальным драйвером события. Поэтому query расширение безопасно только вместе с существующим editorial/freshness contract и явным запретом превращать lane в общий financial-market sweep.

## Независимые контрольные события 2026-09-03

Дополнительная assistant-side проверка обнаружила сильные in-window события, которые показывают границы treatment:

- Broadcom: Reuters, сильный AI-chip revenue outlook. В production Primary событие было замечено только через HuggingNews и отклонено как `weak_source`; Reuters-версия затем не была поднята.
- Enflame: Reuters, Tencent-backed AI-chip IPO с экстремальным спросом; в сохранённом artifact отсутствует.
- OpenAI automated shutdown capabilities после security incident: в сохранённом artifact отсутствует.
- Snowflake: Reuters, AI/cloud-driven annual revenue forecast; в сохранённом artifact отсутствует и является прямым выигрышем business treatment.

Следовательно, wording treatment лечит только часть проблемы. Broadcom/Enflame/OpenAI shutdown остаются source/ranking/resolution seam, а не доказательством необходимости blanket query rewrite.

## Решение

**GO:** узко зафиксировать treatment B только для существующего `business_investment_partnerships` Primary slot.

**NO-GO:**

- не менять остальные 11 Primary queries;
- не добавлять новый search slot;
- не ослаблять Source/Event Freshness;
- не принимать `weak_source` как verified evidence;
- не добавлять отдельный resolver без нового bounded experiment.

Search ceilings остаются: Primary 12, normal pipeline 24, double-regional-gap 25.

## Source Pulse companion experiment

Запланированное zero-paid расширение Source Pulse на OpenAI / Anthropic / European Commission повторно рассмотрено по уже committed controlled fixture `automation/fixtures/recall/source-pulse-official-newsrooms-2026-09-02.json` и regression `test_source_pulse_official_newsroom_experiment.py`.

Результат остаётся **NO-GO**:

- OpenAI: first-party fetch path был нестабилен/403;
- Anthropic: недостаточно надёжный generic machine-readable publication-date contract;
- European Commission: не доказан стабильный targeted listing/pagination contract.

Добавление этих URL в production registry сейчас ухудшило бы fail-closed freshness semantics, поэтому registry не меняется.

## Стоимость эксперимента

- Production OpenAI/API calls: `0`
- Production Web Search operations: `0`
- Assistant-side web search использован только как независимый A/B/control sample.
- Отдельный assistant Terra-инструмент в этой сессии недоступен; обычный web search намеренно не выдаётся за Terra.
