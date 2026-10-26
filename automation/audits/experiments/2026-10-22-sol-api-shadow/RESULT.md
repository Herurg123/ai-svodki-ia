# Sol vs Terra: Primary 12/12, 22 октября 2026

## Подтверждённые артефакты

- Terra production Actions run 39706110827, Primary artifact committed to automation/content/2026-10-22/primary-recall.json.
- Первый Sol API run 39726774610, artifact 12402559662: семь сохранённых API-ответов и один восьмой ответ, потерянный до сохранения usage.
- Успешное продолжение Sol Actions run 39748548566, artifact 12412378520.
- SHA-256 загруженного итогового ZIP: 82585fff3216e5375e8333569e56276204185b0fd73d3af10905ada7fd9a50a6.
- Модель Sol: gpt-6.1-sol, reasoning medium; 7 прежних ответов повторно не вызывались, 5 новых API-ответов сохранены.
- Окно обеих сторон: 2026-10-20 04:35:44 +03:00 — 2026-10-22 04:32:02 +03:00.
- Оценка пяти новых вызовов по Standard $0.587131; консервативная оценка $0.7056275, НЕ реальный счёт.

## Результат по Primary

| Показатель | Terra | Sol |
|---|---:|---:|
| Завершённые направления | 12 | 12 |
| Реальные поисковые операции | 12 | 12 (7 старых + 5 новых) |
| Сырые кандидаты | 15 | 9 |
| Принятые уникальные кандидаты Primary | 12 | 8 |

**Общие принятые темы (4):** OpenAI/Google Cloud; NVIDIA Berlin modular data-center; Recursive Flint; Claude Code 2.1.307.

**Принятые Sol, но не Terra Primary (4):**
- PHP2Shell, уязвимости PHP, обнаруженные с помощью ИИ (сильный важный пропуск Terra, подтверждён OpenAI и Wiz 21 октября).
- Tencent и необычная веб-активность ИИ-агентов (20 октября; событие требует отдельной редакционной оценки origin).
- Meta Muse: 10+ млн пользователей и новые показатели agent shopping (21 октября, новая информация с earnings call).
- Daytona $60 млн. НЕ эксклюзивная находка Sol: Terra видела событие в сыром Primary, но отбросила как дубликат при merge.

**Принятые Terra, но не Sol Primary (8):** Arda $232M; ASI $325M; Frenos industrial cybersecurity AI; OpenAI internal misalignment-monitoring incidents; Anthropic AI safety legislative proposal; Walmart Agent Gateway; GitHub Copilot CLI 1.0.102; Google Antigravity CLI 1.4.4.

Отдельный дефект общих правил: DeepSeek был отклонён из-за сочетания legal_scale и category=regulation, его нельзя считать самостоятельной потерей какой-то одной модели.

## Оценка

В этом ретроспективном тесте Terra покрыла больше важных подтверждённых тем, включая Anthropic, Walmart и внутреннюю безопасность агентов OpenAI. Sol нашла резонансную PHP2Shell новость, отсутствующую даже среди 20 кандидатов полного исследования Terra. Один такой выигрыш не перевешивает доказанные пропуски Sol.

Метрики числа сырых кандидатов и точного совпадения URL сами по себе не измеряют события; обязательна редакционная идентификация сюжетов. Поисковый индекс изменился между ночным Terra и поздним Sol, поэтому сравнение не полностью синхронно. Full Editorial, Coverage и публикация Sol не тестировались.

**Решение: Terra оставить production; Sol продолжать проверять как complementary recall или альтернативу.** Два синхронных теневых выпуска пока не проведены; для них нужны отдельные санкционированные запуски. Временный paid job для 22 октября удалён, main не менялся, PR #213 остаётся черновиком.

## Поддерживающие публичные подтверждения

- OpenAI PHP: https://openai.com/index/coordinated-disclosure-of-critical-vulnerabilities/
- Wiz PHP: https://www.wiz.io/blog/php2shell-php-rce
- Walmart: https://corporate.walmart.com/news/2026/10/Making-It-Possible-for-Agents-to-Shop-on-Behalf-of-Customers
- OpenAI misalignment: https://alignment.openai.com/misalignment-reports/suppressing-misalignment-monitoring-alerts-and-disabling-misalignment-monitoring
- Anthropic: https://techcrunch.com/2026/10/20/anthropic-pitches-ai-safety-bill-that-may-block-a-model-if-50-people-could-be-killed/
- Tencent: https://www.techradar.com/pro/some-agents-exhibited-unintended-web-browsing-behavior-tencent-admits-ai-agents-it-was-testing-made-more-than-2-600-attempts-in-11-days-to-slip-past-alibabas-map-defenses-just-to-find-out-which-zoo-gate-people-use
- Meta: https://techcrunch.com/2026/10/21/meta-says-muse-has-over-10m-users-with-shopping-a-top-activity/
