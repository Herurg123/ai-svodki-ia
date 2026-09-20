# Dzen article-video stage

## Назначение

После того как нативное видео текущего выпуска уже опубликовано в Дзен и обе
same-day публикации подтверждённо добавлены в свои подборки, локальный Windows
downstream добавляет это видео в уже опубликованную статью того же дня.

Канонический runtime: `dzen-article-video.js`.

Scheduled ordering:

```text
NotebookLM/MP4/PNG/FTP
  -> native Dzen video publication
  -> Dzen collections
  -> Dzen article-video
```

Четвёртая фаза разрешена только при:

- `job.dzenAutomation.status=PUBLISHED`;
- `job.dzenCollections.status=COMPLETE`;
- отсутствии terminal `dzenArticleVideo=COMPLETE|SKIPPED_EXISTING|ERROR`.

## Универсальный same-day flow

Дата не зашита в коде. Scheduled worker передаёт `--date=YYYY-MM-DD` выбранного
job; ручной запуск без `--date` использует текущую дату в configured timezone.

Для выбранной даты runtime:

1. Studio -> `Публикации` -> `Статьи` и находит exact заголовок
   `ИИ-Сводка на <дата>`.
2. Через `Скопировать ссылку` получает public article URL.
3. Studio -> `Видео` и находит exact заголовок
   `ИИ-Сводка на <дата> | Подпишись, чтоб получать свежее!`.
4. Через `Скопировать ссылку` получает public video URL.
5. Синхронизирует article URL в `downloads/_ИИ-Сводка.txt` только когда в блоке
   `Этот выпуск:` второй bullet всё ещё является exact placeholder
   `- https://` (или configured `descriptionSecondUrlPlaceholder`).
6. Открывает статью в редакторе.
7. Перед exact anchor H2 `Мировые лидеры ИИ` создаёт обычную строку
   `Видеосводка`.
8. На следующей строке вставляет video URL реальным `Ctrl+V`, сохраняя и затем
   восстанавливая исходный Windows clipboard.
9. Ждёт реальный Dzen video preview/embed и исчезновение plain URL.
10. Выделяет exact `Видеосводка`, находит H2 в floating toolbar по semantic/UI
    сигналам, делает один physical click и проверяет применённый heading.
11. Ждёт одновременно `Сохранено ...` + `Есть неопубликованные правки` и
    минимум 8 секунд стабильности без `Идёт сохранение`.
12. Сохраняет `phase=PUBLISH_ARMED` до первого click `Опубликовать`.
13. Ждёт modal `Публикация`, выбирает единственный native `BUTTON`
    `Сохранить изменения`, сохраняет `phase=CONFIRMATION_ARMED` до final click
    и нажимает его ровно один раз.
14. Navigation после final Save Changes считается ожидаемым success-path, а не
    ошибкой Playwright.
15. Публично проверяет строгий порядок:
    H2 `Видеосводка` -> Dzen video preview -> H2 `Мировые лидеры ИИ`.
16. Только после этого сохраняет `status=COMPLETE; phase=VERIFIED`.

## Защита ручной ссылки в _ИИ-Сводка.txt

Это часть существующего project contract, а не новая эвристика.

Если exact placeholder второй ссылки отсутствует, файл **не изменяется**. Это
означает, что оператор мог уже вручную заполнить ссылку. Runtime не пытается
«исправить», нормализовать или заменить такую строку.

Когда placeholder присутствует, первая ссылка блока `Этот выпуск:` дополнительно
обязана совпасть с `job.publicationUrl`. Несовпадение блокирует этап до любого
редактирования статьи.

## State и at-most-once

`job.dzenArticleVideo.status`:

- `PENDING`
- `COMPLETE`
- `SKIPPED_EXISTING`
- `ERROR`

Основные phases:

- `PENDING`
- `LINKS_RESOLVED`
- `EDITING`
- `PUBLISH_ARMED`
- `CONFIRMATION_ARMED`
- `CLICKED_UNVERIFIED`
- `VERIFIED`
- `EXISTING_DETECTED`
- `ERROR`

`PUBLISH_ARMED`, `CONFIRMATION_ARMED` и `CLICKED_UNVERIFIED` являются
verification-only. После неопределённого результата автоматизация не возвращается
в editor и не делает второй publish/final-save click.

Если exact H2 `Видеосводка` уже существует до изменений, runtime ничего не
меняет и фиксирует `SKIPPED_EXISTING`.

`ERROR` terminal и не разрешает автоматический retry. Recovery конкретного
инцидента сначала обязан доказать, что повторная mutation безопасна.

## Live acceptance 2026-09-20

Финальный clean retest на реальной статье прошёл полный путь за один запуск:

- article/video URL resolved;
- video preview подтверждён;
- H2 применён;
- autosave прошёл `Идёт сохранение` и затем оставался stable 8 секунд;
- `Опубликовать` и final `Сохранить изменения` были нажаты ровно по одному разу;
- ожидаемая navigation после final click была корректно пережита;
- public verification подтвердила требуемый порядок;
- state завершился `COMPLETE/VERIFIED`.

Incident-only recovery/reset/retest entrypoints, использованные при разработке,
не входят в production source и не должны переноситься в обычный runtime.

## Ручные entrypoints

Dry-run без mutations:

```bat
run-dzen-article-video-dry-run.cmd --date=YYYY-MM-DD
```

Apply:

```bat
run-dzen-article-video-apply.cmd --date=YYYY-MM-DD
```

Normal Task Scheduler запускает только `run-worker.cmd`; отдельная scheduled
задача для article-video не нужна.
