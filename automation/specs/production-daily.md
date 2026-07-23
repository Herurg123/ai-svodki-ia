# Production daily workflow

## Зафиксированные договорённости

- Постоянный RSS: `https://rybalka.one/posts/rss.xml`.
- Принятые Дзеном статьи в `/posts/dzen-test/` остаются на месте навсегда.
- Новые выпуски публикуются в `/posts/YYYY-MM-DD/`.
- Новые изображения публикуются в `/posts/images/`.
- Первый автоматический выпуск: 24 июля 2026 года.
- Расписание: около 06:07 по Москве, GitHub cron `7 3 * * *`.
- Тип материалов для Дзена: статья.
- В RSS у каждого item сохраняются категории `Статья` и `native-yes`.
- Production workflow не использует FTP secrets. После commit в `main` он отправляет
  `workflow_dispatch` существующему `Deploy posts to rybalka.one`, который выполняет FTP отдельно.
- До API workflow проверяет, что последний item RSS относится к предыдущему дню.
  Это защищает от пропуска архива и повторения уже вышедших новостей.

## Сегодняшняя подготовка

1. Бесплатный `Production daily readiness`.
2. Проверка принятого RSS, десяти legacy-item и workflow-контракта.
3. Unit-тесты даты, stale RSS и защиты от дубля.
4. После зелёного результата production workflow переносится в `main`.
5. Поскольку cron 03:00 UTC сегодня уже прошёл, первый schedule будет завтра.

## Legacy images

Перед первой production-сборкой десять принятых обложек копируются из
`posts/dzen-test/images/` в канонический `posts/images/`. Старые файлы не удаляются.
Это необходимо, потому что общий builder ожидает изображения RSS в `posts/images/`.
