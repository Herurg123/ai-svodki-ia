# Пункт 5 Возобновление проверки вклада источников

Статус: независимая приёмка автономного модуля пройдена. Финальные evidence:
[`2026-09-09-step05-acceptance/README.md`](2026-09-09-step05-acceptance/README.md).
Следующие разделы сохраняют условия и промежуточное состояние checkpoint b328d41.
Владелец 9 сентября явно вернул работу к основным пунктам после production
incident. Пункт 4 остаётся отложенным, пункт 6 не начат. Исторический FAIL Terra
сохранён без правки под `2026-09-08-step05-independent/`.

Рабочая ветка совмещена с main `8c50ca04068d23cef20917598bfa78f4f1da6536`.
Региональная блокировка, Meta display validation и новые official Pulse routes
из main сохраняются. Изменения пункта 5 ограничены автономными CLI, их tests,
fixtures и документацией; production entrypoints/workflows их не импортируют.

## Исправления по четырём замечаниям

1. Malformed disposition rows не отбрасываются как пустая наблюдаемая выборка.
   Повреждение записывается в gaps, подтверждённое promotion и downstream — null.
2. Повторяющиеся accepted URLs/dispositions не превращаются в молчаливый set.
   Дубли внутри входного журнала означают неоднозначность. Повторные полные копии
   одного observation в периодическом отчёте, напротив, учитываются один раз.
3. Candidate/story identity требует содержательных typed event fields и валидной
   source date; null published_at допустим только как date-only contract.
4. Repository proof связывает каждый headline со всеми его source URLs внутри
   своего видимого h3 блока. Cross-wiring, hidden content и footer отклоняются.

Producer v3 теперь выдаёт source/trace content identities. Period reducer
показывает суммы наблюдаемой части и явные знаменатели полноты. Конфликты одного
выпуска не разрешаются по времени, порядку файлов или большему числу кандидатов.
Известная repository publication имеет приоритет над локальным draft; FTP
по-прежнему неизвестен. Старые v1/v2 reports пересоздаются офлайн из saved inputs.

## Проверки и условия продолжения

Локально прошли 36 целевых unit tests: 28 source value/publication/period и
8 trace tests, включая исторические NVIDIA 2 сентября и Yandex 6 сентября.
Это промежуточные результаты, не независимая приёмка.

Далее: replay сохранённых четырёх controls; несколько полных historical releases;
независимая Terra-проверка кодовой и архитектурной корректности; полный штатный
offline gate. При успехе — итоговый DOCX и подготовленный PR. Production API,
source polling, recovery и публикация в этом продолжении не запускаются.

Все перечисленные проверки выполнены: 16 независимых controls PASS, 675 штатных
tests PASS, 6 validators PASS, 6 historical observations PASS. Runtime checkpoint
после приёмки не изменён. Подготовка итогового DOCX и PR завершает этот шаг;
слияние требует отдельной команды владельца по repository AGENTS.md.
