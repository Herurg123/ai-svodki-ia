# Исправление остановки выпуска 9 сентября

**Независимая офлайн-проверка: PASS.** Исходный запуск:
https://github.com/Herurg123/ai-svodki-ia/actions/runs/34298397080

Production base: `d3ed784ec8a9f3450d723e2565b3ab1509d0facf`.
Проверенный SHA256 `generate_digest_preview.py`:
`c93893b9cbd07c4f1f6b43681e9307965d1c06da91b9651664faa80169193830`.

Редактор подготовил семь мировых сюжетов и исключил cand-008: карточка Яндекса
содержала заголовок и общее описание сайта вместо достаточных деталей продукта.
Старый validator объявлял любой российский include/consider со score ≥ 3
обязательным для отбора. Это противоречило действующей политике без квот.
`git blame` относит это условие к `6803faac` от 12 июля; изменения пунктов 1–3
его не добавляли и не меняли. Отложенные пункты 4–5 не входят в production base.

Исправление превращает только региональную блокировку в предупреждение с ID.
Оно не выбирает новости вместо редактора и не достраивает факты слабого lead.

## Доказательства

- Точный сохранённый editorial/research с полной archive базы: baseline даёт
  единственную ошибку, candidate — ноль ошибок и семь тех же сюжетов.
- Digest SHA256 совпадает, входные JSON не меняются.
- 10 новых штатных tests; полный suite — 624 tests; 6 validators — PASS.
- Terra независимо выполнила replay и 52 целевых теста, включая ранее
  существующие recovery/editorial regressions. Это не 52 новых теста.
- Соседние cases: selected/excluded/weak regional, stale/exclude, all-excluded,
  неизвестный ID, partition, diversity и подмена ссылки. Их действующие
  ограничения сохранились.
- Точный artifact восстанавливается офлайн как partial_editorial, включая
  сохранённые семь Coverage searches; обложка отсутствует.

Подробности: `independent-audit-report.md`, `independent-controls.json`.
Воспроизведение из корня полной git-копии:

```bash
python automation/audits/experiments/2026-09-09-editorial-regional-stop/run_independent_controls.py
python -m unittest discover -s automation/tests -p 'test_sep09_editorial_regional_stop.py' -v
```

Runner читает точную базу и полный архив через git show. Минимальный fixture
сохранён в `automation/fixtures/recall/2026-09-09-editorial-regional-stop.json`
с SHA256 исходных inputs; срок хранения Actions artifact не ограничивает replay.

## Границы и восстановление

Проверены границы поиска, Source/Event Freshness, публикации и recovery по
архитектуре и существующим regressions; новый case R7 внесён в общую матрицу.
Поисковая формулировка, бюджеты, source registry, freshness gates, workflow,
cover generation и recovery implementation не менялись.

Реальный production/recovery не запускался, новых API расходов пользователя нет.
Исправление кода само по себе не публикует сегодняшний выпуск. Его последующий
recovery должен использовать run 34298397080, а не повторять full research.
Partial editorial ещё не является завершённой стадией: существующий recovery
может потребовать новый редакционный вызов; отсутствующая обложка потребует
Image API. Этот PR не разрешает эти платные действия.

Отдельно сохранённый пункт 5 остаётся непринятым в своей ветке, checkpoint
`c9c151f25aeb2a8620222d36a5943befe9ae8a51`; к пункту 6 не переходили.
