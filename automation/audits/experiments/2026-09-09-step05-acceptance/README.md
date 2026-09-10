# Пункт 5 Учёт вклада источников

**Независимая приёмка автономного диагностического модуля пройдена.**
Проверенный runtime checkpoint: `b328d4169d719f3367b1c0e15daafe3d58175329`.
База main: `8c50ca04068d23cef20917598bfa78f4f1da6536`. Рабочая ветка:
`architecture/step05-source-value-20260907`. Production integration не добавлена.

## Результат

Source Value разделяет наблюдение источника, найденные leads, добавленных
кандидатов, сохранённую freshness, редакционный отбор, сборку stories и наличие
stories в committed main page. Каждый переход требует своего доказательства.
FTP delivery остаётся неизвестной. Это инструмент проверки вклада Source Pulse,
а не оценка полноты всего Search и не основание автоматически отключать sources.

Четыре дефекта предыдущей приёмки закрыты: malformed rows и duplicate ledger
entries больше не дают false zero/positive; null identity не связывает события;
headline/source URL проверяются внутри собственного story block. Source/trace
IDs вычисляются по содержимому. Копии и recovery metadata не повышают totals,
conflicting observations одного дня дают null. Суммы сопровождаются отдельными
observed/unknown denominators; отсутствие наблюдений не маскируется нулём.

## Подтверждение

| Проверка | Результат |
| --- | --- |
| Четыре исходных контрпримера Terra | Исправлены, исходный FAIL сохранён |
| Новая независимая Terra-проверка | 16 controls PASS |
| Полный штатный offline suite | 675 tests PASS |
| Штатные validators | Все 6 PASS |
| Полные saved releases и отдельный Pulse | 6 наблюдений PASS |
| Exact copy и recovery copy в historical replay | Итоги не изменились |

Независимый отчёт: `ACCEPTANCE.md`. Проверенные runtime SHA256 перечислены там.
Его `independent_controls.py` перенесён с изменением только ROOT и output path;
все assertions сохранены, JSON после переноса побайтно совпал с исходным
`independent_controls_result.json`. Название одного сохранённого контроля
содержит Sep6, но его no-promotion input относится к Sep8; фактическая дата видна
из fixture path в runner. Это подпись контроля, не перенос наблюдения между днями.

`historical_replay.py` читает полные immutable main artifacts для 27 и 29 августа,
2, 6 и 7 сентября. Отдельный полный Pulse 8 сентября сохранён в fixture без
изменения байтов, чтобы результат не зависел от срока хранения Actions artifact.
Суммарно подаются 8 reports на 6 дат: шесть оригиналов, одна точная копия и одна
копия с recovery metadata. Последние две не увеличивают вклад.

| Дата | Проверяемый результат |
| --- | --- |
| 27 августа | Legacy report без promotion, вклад остаётся unknown |
| 29 августа | Подтверждённое отсутствие добавленных Pulse candidates |
| 2 сентября | NVIDIA promoted 1, freshness survivor 1, selected 1, repository published 1 |
| 6 сентября | Yandex promoted 1, freshness unknown, selected 0, repository published 0 |
| 7 сентября | Подтверждённое отсутствие добавленных Pulse candidates |
| 8 сентября | Подтверждённое отсутствие promotion; downstream неизвестен |

`historical-results.json` содержит hashes входов и страниц; `period-results.json`
содержит сами сравнения. Набор дат выбран по наличию сохранённых inputs; это не
сплошной мониторинг периода и не статистическая оценка всех источников.

## Воспроизведение

Из полной git-копии с локальным origin/main, содержащим baseline commit:

```bash
python automation/audits/experiments/2026-09-09-step05-acceptance/historical_replay.py
python automation/audits/experiments/2026-09-09-step05-acceptance/independent_controls.py
python -m unittest discover -s automation/tests -v
```

Оба runners по умолчанию пишут только в ignored `automation/preview/`.
Сеть, API и повторный опрос источников не используются. Шесть validators
перечислены в `validators.json`; полный CI запускает их стандартными командами.

## Архитектурное заключение

Внешние зависимости новых CLI ограничены saved JSON/HTML, Python stdlib и
read-only Git object access. В `.github/workflows` и существующем production
orchestration нет импортов этих модулей. Retrieval prompts/registry, candidate
cap, Source/Event Freshness, editorial policy, archive dedupe, search ceilings
24/25, paid-stage recovery, cover admission, commit/deploy и video downstream
не меняются. Совместимость historical source artifacts сохранена через unknown;
старые выходные отчёты v1/v2 нужно пересоздать офлайн для period reducer.

PR #159–162 из текущего main сохранены. Пункт 4 не переносился из отложенной
ветки, пункт 6 не начат. Реальные API вызовы и production recovery не выполнялись.
Следующий GitHub шаг после успешного PR CI — отдельная команда владельца на merge
с точным проверенным head SHA, как требует AGENTS.md.
