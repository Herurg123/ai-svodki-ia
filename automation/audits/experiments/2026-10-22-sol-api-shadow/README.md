# Sol API shadow 2026-10-22

Это **одноразовый** экспериментальный код для PR. Никакая часть не должна попадать в production.

- Фиксированный production baseline: run 39706110827, исходный SHA eb3c8840df022eaac4e12038709eaccf898de8c4.
- Окно: 2026-10-20T04:35:44+03:00 до 2026-10-22T04:32:02+03:00.
- Модель: gpt-6.1-sol, reasoning=medium, pinned SDK openai==2.45.0.
- Через штатные run_digest_preview.py + ensure_story_coverage.py в изолированном GitHub Actions runner.
- Без новой публикации, image API, коммитов в main, FTP, VK, NotebookLM.
- Тот же production cap: 12 Primary + условные Agency/Hybrid + максимум 7 Coverage; общее ограничение 25 Web Searches.
- Budget guard делает перед каждым API-вызовом резерв на один full-context вызов и блокирует после исчерпания лимита в 10 USD. SDK retries=0. Charge при неизвестном исходе считается неопределённым, попытка не повторяется.
- Наличие исходных ссылок в будущем состоянии поискового индекса может отличаться от настоящей ночной выдачи. Live Source Pulse — не byte-identical сохранённому feed snapshot.
- В PR нет права на merge. Открытие PR запускает только однократный независимый эксперимент, если GitHub Actions принимает новый workflow в PR-ветке.
- Исходные evidence/usage logs загружаются только как Actions artifact; нет действий публикации.
- Не считать один день доказательством превосходства модели. Сравнивать события по идентичности, их источникам и свежести.
