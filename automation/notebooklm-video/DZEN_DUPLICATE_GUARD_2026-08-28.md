# Dzen duplicate guard: live verification 2026-08-28

Этот файл дополняет `DZEN_VIDEO_EXPERIMENTS.md` фактическим результатом локального
MVP2 до следующей консолидации журнала экспериментов.

## Контрольный запуск

Дата запуска: **28.08.2026, 06:13:59–06:14:06 Europe/Moscow**.
Контрольный выпуск: **27.08.2026**. Видео уже существовало во вкладке `Видео`.

Фактический лог:

```text
DZEN-MVP2: до upload проверяю существующее Видео по prefix: «ИИ-Сводка на 27 августа 2026».
DZEN-MVP2: открываю список публикаций: https://dzen.ru/profile/editor/rybv/publications
DZEN-MVP2: нашёл radio-фильтр «Видео»; переключаю его напрямую, без клика по текстовому div.
DZEN-MVP2: фильтр «Видео» подтверждён: checked=true. Проверяю видимые заголовки.
DZEN-MVP2: ВИДЕО УЖЕ ЕСТЬ: найден заголовок «ИИ-Сводка на 27 августа 2026 | Подпишись, чтоб получать свежее!».
DZEN-MVP2: новый upload, draft и publish click не выполняю.
DZEN-MVP2: === END MVP2 SKIP existing-video=true date=2026-08-27 ===
```

## Предыдущая ошибка selector-а

Первая версия MVP2 пыталась нажать визуальный текст `Видео`. Dzen UI содержит
отдельный radio-input:

```html
<input type="radio" aria-label="Видео">
```

Он перехватывал pointer events. Playwright повторял `scrollIntoView` / click до
30-секундного timeout. Исправленный MVP2 активировал сам radio-input через DOM
click и отдельно подтвердил `checked=true`.

## Вывод

Pre-upload duplicate guard считается подтверждённым на целевой Windows/Dzen
среде. Канонический live runner может выполнять эту проверку до запуска
`dzen-publish-direct.js`:

- сравнивать только title prefix до ` | `;
- искать только после подтверждённого фильтра `Видео`;
- при совпадении завершать run без child/upload/draft/publish click;
- при невозможности надёжно подтвердить фильтр падать до upload;
- если совпадения нет, запускать ровно один существующий fresh-upload live child.

Этот guard не является post-click verification и не возвращает inter-run draft
resume. Он только предотвращает новый upload уже видимого опубликованного видео.
