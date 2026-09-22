# Контракт изображения ИИ-Сводки

## Назначение

Этот контракт описывает два реально используемых режима image pipeline:
бесплатную детерминированную техническую проверку и текущую production-генерацию
обложки через OpenAI Images API.

Офлайн-режим не вызывает OpenAI, не обращается к сети, не меняет `posts/` и не
публикует RSS. Он создаёт fixture-обложку и проверяет технический image contract
без расходования API.

Production image stage запускается только после успешных upstream
editorial/Coverage gates. Она создаёт runtime Image API request, генерирует одну
обложку, валидирует полученный artifact и только после этого передаёт его в
дальнейшую сборку и validation candidate site.

## Технический контракт

- production Image API model: `gpt-image-2`;
- artifact-файл: `cover.png`;
- publish filename берётся из нормализованного `digest.cover_filename`;
- формат: PNG;
- размер: ровно 1536×864;
- соотношение: ровно 16:9;
- quality API-запроса: `high`;
- PNG должен иметь корректные chunks и CRC;
- разрешены RGB и RGBA с bit depth 8;
- interlace запрещён;
- текстовые PNG chunks `tEXt`, `zTXt`, `iTXt` запрещены;
- после `IEND` не должно быть лишних байтов;
- SHA-256, размер и метаданные фиксируются в `image-manifest.json`.

Канонические технические значения принадлежат
`automation/config/image.json`. Production workflow дополнительно фиксирует
`OPENAI_IMAGE_MODEL=gpt-image-2` как текущий допустимый runtime model.

## Prompt

`image_prompt` проверяется на четыре блока в точном порядке:

1. `Изображение 16:9:`;
2. `Главные визуальные темы:`;
3. `Композиция:`;
4. `Стиль:`.

Prompt должен содержать точный нормализованный заголовок выпуска. Обязательные
prompt constraints из `automation/config/image.json` проверяются как ошибки, а
рекомендованные constraints выводятся как предупреждения.

## Границы автоматической проверки

`validate_cover_contract.py` является техническим offline validator. Он проверяет
PNG container, dimensions, hashes, request/manifest metadata и prompt contract,
но намеренно не заявляет semantic visual inspection или OCR заголовка.

Поэтому и для fixture, и для реального Image API artifact сохраняются:

```json
{
  "visual_semantics_validated": false,
  "rendered_title_validated": false
}
```

Эти значения не означают ошибку production stage. Они означают только, что
автоматический validator не подтверждает фактическое отсутствие визуального
текста, логотипов, узнаваемых лиц или водяных знаков и не подтверждает
читаемость отрисованного заголовка. Ограничения на такие элементы остаются частью
prompt contract, а не автоматической semantic/OCR-гарантией.

## Режимы

### `offline_fixture`

- `network_used=false`;
- `openai_used=false`;
- используется для бесплатной технической CI/regression-проверки image contract;
- не является результатом генеративной модели и не подтверждает visual semantics.

### `image_api_preview`

Историческое имя режима сохранено как machine-readable compatibility contract,
но именно этот mode используется текущей production Image API stage.

- `network_used=true`;
- `openai_used=true`;
- runtime request создаётся `create_production_image_request.py` только для
  валидированного digest artifact и содержит `mode=image_api_preview`;
- генерация выполняется `generate_image_preview.py` одним Images API request;
- production model должна быть `gpt-image-2`;
- результат сохраняется в image artifact directory вместе с request/response и
  `image-manifest.json`;
- `validate_cover_contract.py` обязан успешно проверить artifact до дальнейшей
  сборки candidate site;
- отдельное пользовательское approval между editorial/Coverage gates и Image API
  current production workflow не требует.

Успешная Image API генерация сама по себе не является публикацией: после image
validation pipeline продолжает отдельную сборку и validation candidate site, а
commit/deploy остаются downstream publication stages.

## Recovery

Same-day recovery должен переиспользовать уже оплаченный пригодный cover, если
такой artifact был сохранён и восстановлен как `image_recovered=true`.

В этом случае production workflow:

1. не создаёт новый Image API request и не выполняет повторную генерацию;
2. восстанавливает существующий image artifact;
3. повторно запускает `validate_cover_contract.py` через шаг
   `Revalidate recovered production cover`;
4. допускает artifact дальше только после успешной текущей validation.

Таким образом, recovery сохраняет at-most-once semantics платной image stage для
пригодного сохранённого cover и не ослабляет текущий технический контракт.

## Источники истины

- `automation/config/image.json` — технические параметры image contract;
- `automation/scripts/create_production_image_request.py` — production runtime
  request и machine-readable mode;
- `automation/scripts/generate_image_preview.py` — Images API execution и image
  artifacts;
- `automation/scripts/validate_cover_contract.py` — offline technical validation
  и явные границы visual/OCR assertions;
- `automation/scripts/recover_digest_artifact.py` — image recovery handoff;
- `.github/workflows/daily-production.yml` — production orchestration, ordering,
  recovery skip/revalidation и downstream publication path.
