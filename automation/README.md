# Автоматизация ИИ-Сводок

Каталог содержит производственный конвейер ежедневной публикации ИИ-Сводок.

## Владение файлами

GitHub Actions управляет:

- `posts/index.html`;
- `posts/rss.xml`;
- `posts/sitemap.xml`;
- `posts/YYYY-MM-DD/index.html`;
- `posts/images/ai-svodka-YYYY-MM-DD.png`.

Исторический пакет `posts/dzen-test/**` сохраняется без переписывания URL.

Главная страница сайта `/index.html` не входит в производственный контур ИИ-Сводок.

## Каталоги данных

### `content/YYYY-MM-DD/`

Структурированные материалы выпуска. Для архива без повторной публикации достаточно:

- `meta.json`;
- `stories.json`.

Полный производственный выпуск дополнительно содержит статью, источники, digest и обложку.

### `archive/index.json`

Собирается скриптом `bootstrap_archive.py` из рабочего RSS и всех датированных каталогов `content/`. Архивные content-only записи включаются даже тогда, когда соответствующей статьи нет в RSS. Этот файл используется для поиска повторов и определения обновлений ранее опубликованных сюжетов.

### `preview/`

Временные результаты dry-run и отчёты CI. Содержимое не хранится в Git, кроме `.gitkeep`.

## Workflow

В репозитории остаются три понятных точки входа:

- `ci.yml` — единая офлайн-проверка `main`: Python, unit-тесты, архив, production-контракт, RSS, sitemap и Schema.org;
- `daily-production.yml` — ежедневное исследование, редактура, обложка, сборка и публикация;
- `deploy-posts.yml` — единственный FTP-деплой каталога `posts/`.

Экспериментальные preview, fixture, recovery и pre-production workflow удалены. Их полезные проверки остаются в `automation/tests/` и выполняются единым CI.

## Архив и дедупликация

Перед production-запуском:

```bash
python automation/scripts/bootstrap_archive.py
python automation/scripts/validate_archive.py
```

Архив хранит заголовки, организации, темы, типы событий, краткие описания, ключевые слова и URL источников. Сравнение нового исследования выполняется не только по заголовку, поэтому содержание `stories.json` важнее наличия копии старой HTML-страницы.

## Локальная проверка

```bash
python -m unittest discover -s automation/tests -v
python automation/scripts/validate_archive.py
```
