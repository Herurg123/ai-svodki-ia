# ИИ-Сводки

Репозиторий производственного конвейера ежедневных аналитических выпусков об искусственном интеллекте.

Публичные адреса:

- сайт выпусков: https://rybalka.one/posts/
- RSS для Дзена: https://rybalka.one/posts/rss.xml
- sitemap: https://rybalka.one/posts/sitemap.xml

## Производственный цикл

- `.github/workflows/ci.yml` проверяет изменения в `main` без платных API-вызовов;
- `.github/workflows/daily-production.yml` выполняет исследование, редакционную сборку, генерацию обложки и обновление `posts/`;
- `.github/workflows/deploy-posts.yml` загружает изменившийся `posts/` через изолированного FTP-пользователя.

## Основные каталоги

- `automation/content/YYYY-MM-DD/` — структурированный контент выпусков и архивные записи для поиска дублей;
- `automation/archive/index.json` — агрегированный архив редакционной дедупликации;
- `automation/config/` — производственная конфигурация;
- `automation/scripts/` — генераторы и валидаторы;
- `automation/tests/` — регрессионные тесты;
- `posts/` — публикуемый статический сайт, RSS, sitemap и обложки.

Технические детали находятся в `automation/README.md`.
