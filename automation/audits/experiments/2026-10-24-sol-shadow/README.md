# Финальный контрольный Sol API 24 октября 2026 года

**Итог:** ручной Sol завершил **12/12 Responses и 12/12 Web Search** в [run 40062804057](https://github.com/Herurg123/ai-svodki-ia/actions/runs/40062804057). Общий run отмечен failure из-за устаревшей даты 23 октября в бесплатном компараторе; оригинальный [artifact 12548745112](https://github.com/Herurg123/ai-svodki-ia/actions/runs/40062804057/artifacts/12548745112) сохранён. **Повторять платный job или Re-run запрещено.** Полные результаты, контрольные суммы и решение: [RESULT.md](RESULT.md).

## Исходные свидетельства Terra

- Ночной [production run 40050398793](https://github.com/Herurg123/ai-svodki-ia/actions/runs/40050398793), дата 24.10.2026;
  [исходный Research artifact 12542274622](https://github.com/Herurg123/ai-svodki-ia/actions/runs/40050398793/artifacts/12542274622)
  (до Editorial и публикации).
- Оригинальный ZIP SHA-256
  `219151cbb68c6b846dab2d0f789261eb5f52af310af1597d8d6a60679c7a316f`.
  Внутренний оригинальный
  `production-daily/primary-recall-2026-10-24.json` SHA-256
  `5240a7a12c9759ce0bd48e260e80faddb17d5e9dff9fb90ec3608729788f56fe`.
- Terra Search: **12/12 completed**, **7 raw и 7 accepted Primary**.
- Pre-publication repository commit `14a62d313dfb153174f410450d023186f8f8ac75`.
  Sol берёт архив через immutable `git show <sha>:automation/archive/index.json`
  и не читает новостные материалы выпуска 24-го.
- Одинаковое историческое окно:
  **2026-10-22T04:31:19+03:00 — 2026-10-24T04:35:28+03:00**;
  latest archive: `2026-10-23T04:31:19+03:00`.

## Исторический протокол уже выполненного ручного запуска (не повторять)

1. Перейти [GitHub Actions → Main CI](https://github.com/Herurg123/ai-svodki-ia/actions/workflows/ci.yml).
2. **Run workflow** → **Use workflow from** = `experiment/sol-shadow-2026-10-24`.
3. Нажать зелёную кнопку **ровно один раз** и передать ссылку на новый run.
4. **Не нажимать Re-run jobs**, включая случай failure; сохранённые partial JSON могут
   иметь неочевидную оплачиваемую часть.

Запускается только branch-pinned `workflow_dispatch`, один раз,
после `validate`; PR/push и scheduled job не выполняют paid requests.
Модель `gpt-6.1-sol` `medium`, максимум **12 новых API Responses**
и 12 completed Web Searches (один на направление), SDK retries 0.
Клиентский денежный ограничитель снят **по явному разрешению владельца
на 23 и 24 октября**. Но запросы, исходные responses/IDs, search
actions, usage, service tier, Standard/tier cost estimates сохраняются
после каждого ответа и при остановке. Оценки не являются invoice.
Секрет `OPENAI_API_KEY` не раскрывается; read-only GitHub token.

Sol не получает Terra candidates или результаты до завершения своего
Primary. В конце job скачивается оригинальный Terra Research с GitHub
Actions, SHA-проверяется и строится comparison CSV/JSON. URL совпадения
не заменяют ручную event-level проверку источника, точной даты и значимости.
Поскольку поиск Sol происходит позже, search index не полностью
синхронизирован. Sol Editorial/Hybrid/Coverage/Image и публикация
отключены. Никакого FTP, коммитов или изменений production/main.

После одного запуска временный оплачиваемый job должен быть удалён
из PR; исходные доказательства остаются в архиве GitHub Actions,
обязательно записать SHA-256. Исходный Terra artifact истекает
**7 ноября 2026 года**.
