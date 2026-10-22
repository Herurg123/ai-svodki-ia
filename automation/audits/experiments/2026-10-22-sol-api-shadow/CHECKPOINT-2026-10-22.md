# Контрольная точка эксперимента Terra vs Sol — 22.10.2026

**Назначение:** сохранить точный набор доказательств и условия возобновления работы
23 октября. Это manifest/протокол, **не замена оригинальным ZIP-файлам**.

## GitHub источники

- Terra production: [Actions 39706110827](https://github.com/Herurg123/ai-svodki-ia/actions/runs/39706110827);
  исходный Primary: `automation/content/2026-10-22/primary-recall.json` в production SHA `af033f009635ba681979368245b1091f2cdc42a5`.
- Sol API, первая попытка: [Actions 39726774610](https://github.com/Herurg123/ai-svodki-ia/actions/runs/39726774610);
  artifact `12402559662`, name `sol-api-shadow-2026-10-22-attempt-1`,
  **expires_at `2026-11-05T05:17:58Z`**.
- Sol API, успешное завершение 7+5: [Actions 39748548566](https://github.com/Herurg123/ai-svodki-ia/actions/runs/39748548566);
  artifact `12412378520`, name `sol-primary-manual-2026-10-22-39748548566`,
  **expires_at `2026-11-05T08:39:41Z`**.
- Бесплатный replay исходного ZIP: [Actions 39743448183](https://github.com/Herurg123/ai-svodki-ia/actions/runs/39743448183).
- Итоговое сравнение: [RESULT.md](RESULT.md).
- Экспериментальный код: [run_shadow.py](run_shadow.py),
  [compare_primary.py](compare_primary.py); PR [#213](https://github.com/Herurg123/ai-svodki-ia/pull/213)
  остаётся **draft**, не merged.

## Контрольные суммы сохранённых архивов

Алгоритм: SHA-256 по **исходным скачанным байтам** ZIP, без изменений.

| Архив | Размер, байт | SHA-256 |
|---|---:|---|
| Сбой / первые семь | 23847 | `ada53d88eadb3aac9e2508d1a04a5e8b5eb7ed72d1e9aa391a87e336f92a3cc3` |
| Успех / 12 направлений | 54284 | `82585fff3216e5375e8333569e56276204185b0fd73d3af10905ada7fd9a50a6` |

### Содержимое первого архива

| Внутренний путь | Байты | SHA-256 |
|---|---:|---|
| `sol-shadow-2026-10-22/execution.json` | 4332 | `c8bac1db420f209cfb73b0134a6f4208d572a5da96f002e78edadf1099cf9685` |
| `production-daily/primary-recall-2026-10-22.json` | 133145 | `ed2d9364bf024e0ef5aacda920bf70356ed9a3a92597af7b39b4bcffacba4525` |
| `production-daily/research-error.json` | 328 | `75da2a2b07e8739bb6ea2cf191562a936645f2887b5d21f82570a610fdc358a5` |

### Содержимое завершённого архива

| Внутренний путь | Байты | SHA-256 |
|---|---:|---|
| `sol-shadow-2026-10-22/ab-review.csv` | 9463 | `a5c4c97ef40737b0dfdac3f7fc693f989f6ac8bd2fb72af372bcaa6e77215e38` |
| `sol-shadow-2026-10-22/ab-review.json` | 902 | `6bfbdb1bad3017a84da88511a98117f37ba549db7b9a2ec52e555a1064142c93` |
| `sol-shadow-2026-10-22/execution.json` | 4285 | `3394cd56980c94fc4ca7a0b2a49141ea04b36228938e3fe01e2ffc1c22002c8b` |
| `sol-shadow-2026-10-22/offline-verification.json` | 420 | `ef28c1269a4c6f53d60d11632809d141b5125e11a2d8e4bb311b740a179debf1` |
| `production-daily/primary-recall-2026-10-22.json` | 289978 | `414375e6db6ddad2e4c0a7b19483a030d5a40d9d6c60c054ac55ea7340f2ba4b` |

## Вывод и ограничения по результатам

- 12/12 Primary Terra, 12/12 Primary Sol; Terra 15 raw / 12 accepted, Sol 9 raw / 8 accepted.
- Sol нашла важный дополнительный сюжет PHP2Shell; Terra сохраняет ряд значимых тем, не поднятых Sol.
- DeepSeek `legal_scale` — общий дефект контрактов и валидатора, не надо выдавать его за поражение одной из моделей.
- Не проводились параллельный запуск на двух новых днях, Sol Editorial, Coverage и полная публикация.
- Индекс поиска в первом сравнении не идентичен по времени; окончательное решение о смене модели **ещё не принято**.
- Временный платный job уже **удалён из CI в экспериментальной ветке**; production `main` не менялся.
- Артефакты Actions имеют срок хранения. **Не удалять PR-ветку и не полагаться на Actions после 05.11.2026; для долгосрочного архива нужно отдельно сохранить оба оригинальных ZIP**.
- Не нажимать Re-run у старых запусков: это может снова оплатить API.

## Следующий этап: 23 октября (только по отдельному ручному разрешению)

1. После завершения штатного Terra выпуска 23.10 получить frozen pre-publication archive, начало/конец окна, metadata, production Primary и исследовательский пул.
2. Перед созданием нового Sol paid job зафиксировать модель/effort, те же редакционные правила и лимиты, критерии качества и идентичности событий. Sol не должна видеть результаты Terra.
3. Запустить однократный branch-only Sol shadow максимально близко по времени к Terra, но без публикации, Image, FTP или изменения production; сохранить полные raw/candidate/rejection/usage журналы и исходный Actions artifact.
4. Независимо оценить уникальные события, их подтверждения, дату события и значимость. Сравнить не сырые URL, а события, отдельно учитывая отказы валидатора.
5. При явном преимуществе одной модели принять решение; если результат неоднозначен, согласовать ещё один контрольный день. Не считать второй день автоматически одобренным или запланированным.

**На 22 октября никаких будущих платных задач/автоматических Sol-запусков не оставлено.**
