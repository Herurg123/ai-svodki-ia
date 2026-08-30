# Нативная загрузка видео в Дзен через локальный Яндекс.Браузер

Этот документ описывает канонический browser-upload алгоритм локального
NotebookLM-video downstream. Штатный путь запускается через
`run-worker.cmd -> full-worker.js -> scheduled-worker.js`; ручные
`run-dzen-publish.cmd` и `run-dzen-dry-run.cmd` остаются операторскими и
диагностическими entrypoint.

Все Dzen-пути используют один защищённый профиль Яндекс.Браузера и общий CDP
bootstrap. Профиль, cookies и сессии нельзя удалять или пересоздавать автоматикой.
Native Dzen upload является штатной локальной scheduled-фазой, но остаётся
отдельным downstream относительно nightly GitHub production и не меняет RSS.

## Канонический live-flow

Перед любым новым upload выполняется fail-closed duplicate guard:

```text
Studio -> Публикации -> Видео
  -> input[type="radio"][aria-label="Видео"]
  -> checked=true
  -> искать title prefix до " | "
```

Если ожидаемый prefix найден, лог содержит `ВИДЕО УЖЕ ЕСТЬ`, а новый draft, MP4
upload и publish click не выполняются.

Если видео отсутствует, разрешён один fresh-upload child:

```text
новый video upload
 -> MP4
 -> videoEditorPublicationId только для диагностики
 -> title/description один раз
 -> PNG cover один раз
 -> ровно 5 tag-chip
 -> metadata/cover/tags больше не трогать
 -> ждать «Загрузили и обработали видео»
 -> ждать «Готово: можно публиковать и смотреть»
 -> comments = «Все пользователи»
 -> один клик «Опубликовать»/«Отправить»
 -> optional post-click anti-bot wait
 -> scheduled post-click verification через Публикации -> Видео
 -> PUBLISHED
```

Inter-run resume старых drafts, повторное заполнение metadata, повторный live child
и второй publish click запрещены.

## At-most-once state machine

Scheduled orchestration сохраняет `PUBLISH_ARMED` **до** запуска live child.
Дальнейшая схема:

```text
PENDING / RETRYABLE_PRE_CLICK
 -> PUBLISH_ARMED
 -> один live child
 -> CLICKED_UNVERIFIED
 -> verification
 -> PUBLISHED

PUBLISH_ARMED / CLICKED_UNVERIFIED / BLOCKED_AMBIGUOUS
 -> только verification
 -> новый upload запрещён
 -> второй publish click запрещён
```

Fresh retry допустим только если предыдущий child явно доказал
`publishClicked=false`. Любой неоднозначный исход после клика остаётся
verification-only.

## Редкая post-click антибот-проверка

30.08.2026 на целевой Dzen-среде зафиксирован нерегулярный interstitial, который
может появиться **после** единственного клика публикации. Наблюдаемый текст:

```text
Подтвердите,
что вы не робот
Я не робот
```

Окно встречается в светлой и тёмной теме. Ручное включение checkbox `Я не робот`
закрывает проверку, после чего публикация обычно продолжает работу через 1–2
секунды.

Это human-only anti-bot control. Production-контракт намеренно **не** пытается
автоматически нажать checkbox, имитировать человека или обходить challenge.
`dzen-browser-runner.js` делает только следующее:

1. после успешного direct child в течение 4 секунд проверяет, появился ли точный
   challenge-текст;
2. если challenge отсутствует, сразу продолжает штатный post-click путь;
3. если challenge появился, восстанавливает свёрнутое окно Яндекс.Браузера и
   выводит страницу с challenge на передний план;
4. пока challenge видим, не выполняет никаких UI-click;
5. ждёт до 120 секунд, пока оператор вручную поставит флажок `Я не робот`;
6. после исчезновения challenge ждёт ещё 2 секунды и продолжает обычную
   verification;
7. если challenge не исчез за лимит, завершает попытку как post-click
   неопределённость. Publish click уже считается выполненным, поэтому новый upload
   и второй click запрещены.

Таким образом редкое окно не создаёт второй publish attempt и не превращается в
автоматический CAPTCHA solver.

## Browser bootstrap

`dzen-browser-runner.js` использует `browser-session.js` и тот же защищённый
профиль, что NotebookLM worker. До Dzen-фазы NotebookLM browser/CDP должен быть
закрыт. Dzen bootstrap не удаляет и не пересоздаёт профиль или session files.

Штатный browser может запускаться свёрнутым. Единственное исключение к этому
поведению: при обнаружении ручного post-click challenge runner best-effort
восстанавливает существующее окно через Windows API, чтобы оператор мог увидеть
проверку. Это не является взаимодействием с checkbox.

## Метаданные

Заголовок:

```text
ИИ-Сводка на <длинная русская дата> | Подпишись, чтоб получать свежее!
```

Описание формируется один раз. Ссылки после `Этот выпуск:` находятся на
отдельных bullet-строках. Whitespace-only изменения, внесённые Дзеном, не
запускают повторный `fill()`; изменение непробельного содержимого остаётся
ошибкой.

## Теги

Обязательны ровно пять отдельных tag-chip:

```text
ии
ai
полезныесоветы
будущее
лайфхак
```

После Enter DOM может перерисоваться, поэтому input при необходимости ищется
заново. Исчезновение input после пятого тега нормально только когда все пять
ожидаемых chip уже видимы.

## Готовность и комментарии

Раннее `Уже можно публиковать` не является финальной готовностью. Перед
единственным publish click одновременно требуются:

- `Загрузили и обработали видео`;
- `Готово: можно публиковать и смотреть`;
- активная точная кнопка `Опубликовать` или `Отправить`.

После этого выставляется `Кто может комментировать = Все пользователи`, кнопка
проверяется ещё раз и нажимается ровно один раз.

## Логирование

Основные markers:

```text
ВИДЕО УЖЕ ЕСТЬ
КЛИК ПУБЛИКАЦИИ ВЫПОЛНЕН ОДИН РАЗ
ПОСЛЕ PUBLISH ПОЯВИЛАСЬ АНТИБОТ-ПРОВЕРКА «Я НЕ РОБОТ»
Антибот-проверка исчезла
```

Blocking errors пишутся с `!!! DZEN:`. Если ручной challenge не снят за 120
секунд, ошибка обязана явно указывать, что publish click уже состоялся и
повторный click запрещён.

## Ручной запуск

```powershell
cd "C:\TRASH\NotebookLMBot"
.\run-dzen-publish.cmd --date=YYYY-MM-DD
```

`run-dzen-dry-run.cmd` не выполняет финальный publish click и не является
каноническим scheduled алгоритмом.

История практических live-наблюдений и закрытых гипотез хранится в
[`DZEN_VIDEO_EXPERIMENTS.md`](DZEN_VIDEO_EXPERIMENTS.md).
