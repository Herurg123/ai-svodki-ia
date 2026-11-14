# Инцидент 14.11.2026: нормализатор менял уже подтверждённый editorial RAW

## Подтверждённая цепочка

- [run 43544298749](https://github.com/Herurg123/ai-svodki-ia/actions/runs/43544298749), `workflow_dispatch`, 2026-11-14 02:05–02:16 UTC: Research/Editorial PASS, Coverage PASS (6/6); ошибка на `Normalize and validate digest artifact`; Image, commit, FTP не начинались.
- Артефакты: `daily-production-2026-11-14`, `daily-production-checkpoint-research-2026-11-14-attempt-1`, `daily-production-checkpoint-coverage-2026-11-14-attempt-1`; исходный checkpoint Coverage артефакт ID `14093258159`, финальный failed ZIP ID `14093303071`.
- [run 43549846157](https://github.com/Herurg123/ai-svodki-ia/actions/runs/43549846157) и [run 43550459751](https://github.com/Herurg123/ai-svodki-ia/actions/runs/43550459751): восстановили тот же Coverage-checkpoint; fresh Research пропущен; снова та же ошибка. Платного повторного полного поиска не было.

## Независимая проверка на сохранённых файлах

До шага нормализации (из оригинального checkpoint), SHA-256 canonical JSON:
- `editorial-repair-2026-11-14.response.json.response.output_text`: `c32cdf30b67dc23ff4f57fb410b8b22ca8dcae0d48dfad6dc8d5b368d128e343`.
- `2026-11-14/editorial-output-raw.json`: **тот же SHA-256**, равенство полное, journal `state=validated`.

После ошибочного шага:
- `2026-11-14/artifact-normalization.json` записал изменение `editorial-output-raw.json` в `$.digest.image_prompt`, добавив `без водяных знаков` и `без узнаваемых лиц`.
- Длина raw image_prompt с 1444 увеличилась до 1497 символов.
- `editorial-output-raw.json` canonical SHA-256 стал `d2ef5092a396a67cd9d3c2829c848868caab9f3d8e9904b90aa52fbeecf9f7af`.
- Все остальные поля raw совпадали с проверенным ответом; единственное различие — эти две добавленные presentation-only фразы.
- Базовый `validate_digest_artifact` выдал `Errors: 0; warnings: 0`; затем `editorial_repair_guard.publication_safe` корректно отказал: `validated repair no longer matches final editorial artifact`.

Независимый офлайн policy-equivalence replay на assistant-owned Python прочитал оба исходных ZIP и проверил корректирующую модель **skip raw, normalize only derived**. Raw JSON и journal seal остаются равными, `digest.json` и `editorial-output.json` уже удовлетворяли требованиям обложки, search/API не потребовались. Это не запуск Terra и не платный live production.

## Fix / отказ от опасных обходов

- `normalize_digest_artifact.JSON_FILES` и `META_SERVICE_JSON_FILES` больше не включают `editorial-output-raw.json`.
- `validate_digest_artifact_base` продолжает блокировать `Meta*` в производных служебных полях, но больше не применяет presentation-marker контракт к неизменяемому raw ответу.
- `editorial_repair_guard`, signed journal/response, `publication_safe`, дополнительные security/prompt проверки производных данных, лимиты Search/Hybrid/Coverage и платные модели неизменны.
- Offline tests: нормализация с реальными типами файлов и seal-bound `publication_safe`, Meta* в raw и исправление derived, idempotent second pass, intentional tamper (must block).

## Операционное восстановление после merge

1. Получить явное разрешение владельца на merge подготовленного PR, проверить `PR Gate` и `main` CI.
2. Использовать сохранённые **same-day paid checkpoints**, не запускать `force_fresh_research`.
3. Продолжить к изображению только после успешной normalizer + publication guard, соблюдая image API budget и общее разрешение владельца на production.
4. Проверить `stories.json`, `article.html`, RSS, Git commit, FTP deploy; успешный CI не является подтверждением опубликованной страницы.

**Никакого повторного независимого paid Research/Editorial запуска для проверки этой гипотезы не производилось.**
