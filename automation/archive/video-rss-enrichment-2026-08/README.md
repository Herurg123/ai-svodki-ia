# Архив эксперимента Video RSS enrichment, август 2026

Этот каталог сохраняет исходную реализацию закрытого эксперимента Video → RSS для выпуска 2026-08-27.

## Что сохранено

Здесь находятся точные копии бывших production-файлов:

- `video-rss-enrichment.workflow.yml`, бывший `.github/workflows/video-rss-enrichment.yml`;
- `video_rss_enrichment.py`, бывший `automation/scripts/video_rss_enrichment.py`;
- `test_video_rss_enrichment.py`, его offline regression test;
- `repository_hygiene_video_rss_runs.py`, специальная retention-политика Actions runs этого workflow;
- `test_repository_hygiene_video_rss_runs.py`, её regression test.

Исходная ветка разработки: PR #93 `chore/video-rss-publish`. Git history дополнительно сохраняет все исходные commits и точные предыдущие пути.

## Почему архивировано

Media RSS enrichment технически добавлял MP4/PNG в `posts/rss.xml`, но этот путь не дал нужной нативной публикации видео в Дзене. Рабочим направлением стала отдельная операторская загрузка видео через Студию Дзена в локальном NotebookLM-video downstream.

Поэтому Video → RSS больше не является production-механизмом проекта.

## Статус

Этот каталог является **reference-only archive**:

- файлы отсюда не импортируются active runtime;
- здесь нет GitHub Actions workflow path;
- файлы не входят в `automation/scripts/`;
- тесты архива не входят в обычный `unittest discover`;
- никакой scheduled или automatic activation из этого каталога не допускается.

Если к подходу потребуется вернуться, сначала создаётся новый изолированный experiment/PR с отдельным обоснованием и проверкой актуального поведения платформы. Архив нельзя просто переносить обратно в production paths без нового review.

## Текущий инвариант

Видео может существовать как отдельный MP4/PNG asset и публиковаться через независимый video downstream, но `posts/rss.xml` не должен содержать локальные video payloads: `/posts/video/`, `medium="video"` или `type="video/*"`.
