# Artifact-only release candidate

## Назначение

Stage 6 закрепляет принятый редакционный и графический результат как golden fixture и проверяет полный release candidate без изменения production.

Golden fixture от 2026-07-11 служит регрессионным образцом. Он всегда имеет:

- `release_kind: golden_fixture`;
- `production_eligible: false`;
- запрет на FTP, commit в `posts/` и рабочий RSS;
- ручную визуальную проверку принятого `cover.png`;
- SHA-256 исходного редакционного artifact, изображения и собранного сайта.

## Release candidate

Бесплатный workflow выполняет:

1. Проверку хешей сохранённого editorial artifact.
2. Наложение принятого `cover.png`.
3. Проверку полного digest artifact.
4. Проверку PNG-контракта.
5. Сборку изолированных HTML, индекса и RSS.
6. Проверку сайта и RSS для Дзена.
7. Создание `release-manifest.json`.
8. Повторную проверку manifest и файлов.
9. Загрузку только GitHub artifact.

## Production gate

Production gate считается готовым только при одновременном выполнении условий:

- `production_enabled: true`;
- ветка `main`;
- событие `workflow_dispatch`;
- подтверждённое ручное одобрение;
- `release_kind: production`;
- `production_eligible: true`;
- свежесть кандидата в пределах `max_candidate_age_hours`;
- успешные editorial, cover, visual, site и Dzen-проверки;
- чистые safety flags.

Текущая конфигурация содержит `production_enabled: false`. Workflow не имеет write permissions, не получает FTP secrets и не публикует файлы даже при успешной проверке.
