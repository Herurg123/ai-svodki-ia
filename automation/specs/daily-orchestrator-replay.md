# Artifact-only daily orchestrator replay

## Назначение

Этот слой связывает четыре уже проверенные стадии в один детерминированный запуск:

1. сохранённый research fixture;
2. принятый editorial artifact;
3. принятый Image API artifact и ручная визуальная проверка;
4. artifact-only release candidate с заблокированным production gate.

Replay предназначен только для regression-тестов. Он не является свежим выпуском и не может публиковаться.

## Режим

Единственный разрешённый режим:

`recorded_fixture_replay`

Исторические fixtures были созданы с использованием OpenAI API. Текущий replay только читает зафиксированные файлы и обязан сообщать:

- network_used=false;
- openai_used=false;
- responses_api_calls=0;
- image_api_calls=0;
- web_search_calls=0;
- ftp_used=false;
- repository_write_used=false;
- production_paths_changed=false.

## Зафиксированная линия происхождения

- дата: 2026-07-11;
- research: сохранённый очищенный fixture, 6 кандидатов;
- editorial: editorial-resume-004;
- image: image-preview-2026-07-11-002;
- модель изображения: gpt-image-2;
- SHA-256 принятой обложки:
  `a9d944ff7cba1d13083649e1954c339f142a00ff9f684d9163498c182aa4861b`.

Все входные файлы фиксируются в `replay-source.json` с SHA-256. Любое изменение fixture без явного обновления manifest блокирует replay.

## Выход

Workflow формирует только каталог:

`automation/preview/daily-orchestrator/2026-07-11/`

и GitHub artifact. Внутри сохраняются:

- research stage;
- editorial stage;
- image stage;
- release source;
- собранный HTML, индекс и RSS;
- все validation reports;
- production gate report со статусом blocked;
- `daily-run-manifest.json`;
- `daily-run-validation.json`.

## Запреты

Replay workflow не должен содержать:

- schedule;
- OpenAI secret;
- сетевые запросы;
- FTP secrets или FTP action;
- contents: write;
- repository mutation;
- запись в production `posts/`;
- изменение request-файлов.
