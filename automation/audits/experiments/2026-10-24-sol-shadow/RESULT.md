# Итог Terra vs Sol: контрольный Primary 24 октября и решение по 22–24 октября 2026

## Статус и воспроизводимость

Финальный ручной запуск [Main CI 40062804057](https://github.com/Herurg123/ai-svodki-ia/actions/runs/40062804057) (24.10, 04:33–04:42 UTC) завершился общим **failure**, но **платный этап Sol выполнен полностью: 12/12 Responses и 12/12 Web Search**. Причина failure исключительно в бесплатном компараторе: `compare_primary.py` содержал заимствованную из 23 октября проверку даты `2026-10-23` вместо `2026-10-24`. Это не ошибка Sol и не основание для повторного API-вызова. Скрипт даты исправлен отдельно; оригиналы не редактировались.

**Замороженные оригиналы, SHA-256 именно ZIP и внутренних файлов:**

| Доказательство | Actions artifact | Оригинальный SHA-256 |
|---|---|---|
| 24.10 Terra Research, [run 40050398793](https://github.com/Herurg123/ai-svodki-ia/actions/runs/40050398793) | 12542274622 | ZIP `219151cbb68c6b846dab2d0f789261eb5f52af310af1597d8d6a60679c7a316f`; Primary JSON `5240a7a12c9759ce0bd48e260e80faddb17d5e9dff9fb90ec3608729788f56fe` |
| 24.10 Sol полный, [run 40062804057](https://github.com/Herurg123/ai-svodki-ia/actions/runs/40062804057) | 12548745112 | ZIP `498d13b640a493813657fbcc9472f3447224792597ab9614f0e2e992e91f2b81`; `execution.json` `e3031fa609661ab7e31f2fcc47651d33e6203bbccd647e27eca29e42a116e427`; Primary JSON `99ee3fee8f7cf85c1d2955452aca0c9c17418536a08e6b26a95bc836359afe19` |
| 23.10 Terra, [run 39884328846](https://github.com/Herurg123/ai-svodki-ia/actions/runs/39884328846) | 12471524859 | ZIP `b1c8ae91284c3444fcd71c1f9d5d2fd08dbf2084803db3127b479d0ea5d33dfb`; Primary `39f689d1858d11df90ab77f8979e88435695148941cc78440e2d27eeb60a80c9` |
| 23.10 Sol первый 8/12, [run 39891725068](https://github.com/Herurg123/ai-svodki-ia/actions/runs/39891725068) | 12475775291 | ZIP `63f6e570a47abac3f2849525f8c45953014c37fde6931f544bcc0a45bb8bcc28` |
| 23.10 Sol финальный 8+4, [run 39908841706](https://github.com/Herurg123/ai-svodki-ia/actions/runs/39908841706) | 12482321746 | ZIP `86e93b98eb134f0cbe35f6ee2bfb3fcdaccee247ca9ce81bcf255b89305f89a3`; Primary `21ac493046df28ba12d4f953623e0cbc60905fc3ca71a4673eeef0becb787fb8` |
| 22.10 Sol первый частичный, [run 39726774610](https://github.com/Herurg123/ai-svodki-ia/actions/runs/39726774610) | 12402559662 | ZIP `ada53d88eadb3aac9e2508d1a04a5e8b5eb7ed72d1e9aa391a87e336f92a3cc3` |
| 22.10 Sol итоговый 7+5, [run 39748548566](https://github.com/Herurg123/ai-svodki-ia/actions/runs/39748548566) | 12412378520 | ZIP `82585fff3216e5375e8333569e56276204185b0fd73d3af10905ada7fd9a50a6` |

SHA записаны по повторно скачанным оригинальным ZIP, не вычислялись из пересозданных финальных JSON. Сохранённый 22.10 первый run не имеет восьмого ответа/usage: этот неопределённый платёж не следует объявлять нулевым. Исходные артефакты GitHub Actions имеют ограниченное время хранения (24.10 до 7 ноября). Для долговременного хранения скачать оригиналы, не реконструировать из финальных Primary.

**Протокол 24.10:** Sol `gpt-6.1-sol`, `reasoning=medium`, все 12 API имеют `service_tier=default`, 12 уникальных response IDs, 12 сохранённых отдельных `raw-responses/*.json` плюс execution и Primary. Ноль автоматических SDK retries; лимит 12 запросов; исходный prepublication commit `14a62d313dfb153174f410450d023186f8f8ac75`; архив SHA `b72363b533e4eee38f7f34594475c72a12a76f3c57fc8e83352ccd053389d95d`; равное временное окно 22.10 04:31:19 — 24.10 04:35:28 UTC+3; данные Terra не передавались Sol до самостоятельного поиска.

## Численные результаты: только Primary, не редакционная публикация

| День | Terra: raw / accepted | Sol: raw / accepted | Приняты общими | Только Terra | Только Sol |
|---|---:|---:|---:|---:|---:|
| 22 октября | 15 / 12 | 9 / 8 | 4 | 8 | 4 |
| 23 октября | 6 / 5 | 16 / 14 | 3 | 2 | 11 |
| 24 октября | 7 / 7 | 13 / 11 | 3 | 4 | 8 |

22/23 октября см. [первоначальное сравнение 22](https://github.com/Herurg123/ai-svodki-ia/blob/experiment/sol-api-shadow-2026-10-22/automation/audits/experiments/2026-10-22-sol-api-shadow/RESULT.md) и [исследование 23](https://github.com/Herurg123/ai-svodki-ia/blob/experiment/sol-shadow-2026-10-23/automation/audits/experiments/2026-10-23-sol-shadow/RESULT.md). Принятые записи = результат автоматики, **не подтверждённые свежие уникальные события**. Суммы по дням завышают число независимых тем из-за перекрывающихся поисковых окон.

## Ручное разрешение event identity за 24 октября

**Общие 3:** OpenAI отказ от живого интернета при обучении frontier-моделей; Anthropic Claude Duet; Claude Code 2.1.310 (может быть другой URL того же релиза).

**Terra-only Primary 4:** Uber/ChatGPT Work 30 тыс. сотрудников (значимая корпоративная новость); Replit Monitoring Agent (значимая девелоперская); OpenAI Codex CLI rust-v0.164.0 (patch release); Barclays/AI и 5000 рабочих мест (требует уточнения причинно-следственной связи и первоисточника). Sol не обнаружила Uber, Replit и другие темы даже после полного 12/12. Их отсутствие считать потерей recall, а не преимуществом Terra по каждому отдельному сюжету без проверки.

**Sol-only Primary 8, с проверкой origin:**

| Тема | Проверка источника / происхождения | Вывод |
|---|---|---|
| OpenAI: обсуждение $30 млрд при оценке $1.25 трлн | [TechCrunch 22.10](https://techcrunch.com/2026/10/22/openai-working-on-new-30b-raise-at-1-25t-valuation-ahead-of-ipo/); переговоры и сумма упоминались раньше, новая информация касается параметров | **Значимое обновление**, не завершённая инвестиция |
| inDrive–Pony.ai–NVIDIA, роботакси в Казахстане | [официальный Pony.ai 23.10](https://ir.pony.ai/zh-hant/news-releases/news-release-details/pony-ai-inc-and-indrive-announce-collaboration-explore), [inDrive 23.10](https://blog.indrive.com/en-co/article/indrive-and-pony-ai-announce-collaboration-to-explore-autonomous-mobility-in-kazakhstan-built-on-nvidia-hyperion) | **Подтверждённая новая регионально важная тема**, но пока MoU, не действующее роботакси |
| Sea Cloud | [Reuters 20.10](https://www.reuters.com/world/asia-pacific/sea-plans-ipo-financial-services-arm-monee-memo-says-2026-10-20/) vs. Compute Forecast 22.10 | **Событие вне окна**, свежий пересказ |
| Soluna–Applied Digital 50 MW | [официальный анонс 21.10](https://www.solunacomputing.com/news/soluna-applied-digital-chronoscale/) vs. Compute Forecast 23.10 | **Событие вне окна**, свежий пересказ |
| Vultr–AMD 20 MW Chennai | [официальный анонс 21.10](https://blogs.vultr.com/chennai-cloud-data-center-region) vs. Compute Forecast 22.10 | **Событие вне окна**, свежий пересказ |
| Cortex DC 2 GW India | [PTI 22.10](https://theprint.in/economy/tcg-arm-cortex-dc-to-develop-2-gw-ai-ready-data-centre-capacity-in-india/3078798/) | **Подтверждённая свежая тема**, план, не построенная мощность |
| Claude Code 2.1.309 sandbox | [официальный GitHub release](https://github.com/anthropics/claude-code/releases/tag/v2.1.309), 22.10 | Свежий реальный security patch, но **уже присутствовал в Sol 23.10**, не новая трехдневная находка |
| 302.ai: 17.6 млн файлов | [TechRadar 23.10](https://www.techradar.com/pro/security/security-breach-at-ai-aggregator-exposes-over-18-million-files-including-some-very-embarrassing-chat-records); обнаружение хранилища в августе, сообщение опубликовано в октябре | Отличать **свежее раскрытие** от даты инцидента; был в Sol 23.10; требует origin-proof |

**Отклонения валидатора Sol:** Kimi K3.1 Pro (Moonshot) и MiniMax M3.1 Flash weights были в *сырых* записях Sol, но оба отклонены с `primary source URL уже опубликован в архиве`, поскольку ссылались на один общий `https://chinaapi.ai/model-updates`. Это **не доказанные пропуски поисковой модели**: обнаружение было, но не удалось пройти URL-based archive dedupe и exact-source proof. Ключевые события независимо подтверждаются [Reuters о Kimi от 24.10](https://www.reuters.com/technology/moonshot-curbs-hacking-ability-new-kimi-model-fears-grow-over-ai-powered-2026-10-24/) и [официальным объявлением MiniMax / ссылками на веса 22–23.10](https://www.advanceintelligence.ai/2026-10-22). Требуется изолированная проверка identity по первоисточнику, **не ослабление блокировки всего архивного URL**.

Terra за 24.10 имела дополнительно Source Pulse: 6 принятых supplemental candidates, после него общий исследовательский пул `2026-10-24/candidates.json` содержал **13**, а не 7; это NVIDIA Kazakhstan compute, NVIDIA Minerva и четыре новости OpenAI (FDE, Decisions API, NASK partnership, storage architecture). Agency Rescue выполнил 1 search и добавил 0; Hybrid выполнил пять направлений в разрешённом double-region режиме и добавил 0. **Не приписывать Sol NVIDIA Minerva как эксклюзив полного конвейера Terra**: Minerva уже была в Source Pulse Terra и 23.10 также имела пересечения. Ни Terra Primary, ни Sol Primary за 24.10 не дали приемлемого покрытия России, China/Asia также страдает от раннего отклонения по архивному URL.

## Как читать трёхдневную серию

- **22.10:** Terra 12 vs. Sol 8, найдены важные Terra-only Anthropic/Walmart/OpenAI misalignment/Frenos. Sol раньше Terra обнаружила PHP2Shell, но Daytona не была эксклюзивной: Terra видела её в raw. Вывод дня: преимущество Terra по охвату, Sol компенсирует пропуски.
- **23.10:** Sol 14 vs. Terra 5 и реальные сильные находки Legora $550 млн, Amp Self-Hosted Orbs. Но Sol пропустила PHP2Shell, обнаруженную ею днём ранее; исследование Anthropic от 20.10 было подано как новое по статье 22.10; VS Code Insiders не имеет доказанного свежего релиза. Source Pulse Terra уже содержал часть формально Sol-only материалов.
- **24.10:** Sol 11 vs. Terra 7 accepted, но **как минимум 3 Sol-only за пределами origin window**, ещё два сюжета повторялись в Sol 23.10; подтверждённые дополнительные inDrive/Kazakhstan, Cortex DC и изменившиеся условия финансирования OpenAI полезны. Terra удержала Uber/Replit; Kimi/MiniMax потеряны валидатором Sol, а не самим поиском.

## Расходы: estimate отдельно от Billing

Sol 24.10: **12 новых Responses, 12 поисков, default (12/12)**; `input_tokens=563462`, `output_tokens=19848`, в том числе `cached_tokens=51800`, `cache_write_tokens=177380`. Сохранённый Standard/tier estimate **$1.435674**; фактический provider invoice **не проверен**. До эксперимента владельцем зафиксировано **$0.38 за 24 октября UTC** в Usage; последующего сопоставимого Billing пока нет, реальное приращение по проекту не установлено.

Sol 23.10: 12 новых Responses = **$1.443632 расчётно**; OpenAI Usage показывал **$1.21 суммарно за 23 октября UTC**, из чего владелец условно относил около $0.40 к штатной Terra, около $0.81 к экспериментам. Это распределение **не является доказанным per-response billing**. Sol 22.10: рассчитанные $0.587131 касались **пяти последних** вызовов и не охватывают достоверно стоимость всех предыдущих семи или неопределённый восьмой ответ первой попытки. Не суммировать клиентские тарифные оценки как реальные списания.

## Решение

**Не переключать production с Terra на Sol.** По трём Primary-контролям Sol показала более высокий raw recall в двух днях, но преимущество по *свежим подтверждённым значимым событиям* меньше: найдены многодневные дубликаты, устаревшие первоанонсы и ошибочные archive URL отклонения. Sol неоднократно пропускала серьёзные истории Terra, а Terra неоднократно теряла важные Sol discoveries. Полный Sol Editorial, Coverage, Hybrid, Image, end-to-end и публикация не тестировались, поисковые индексы сдвигались между запусками.

**Рабочая рекомендация:** сохранить Terra как штатную Primary-модель; **проектировать отдельный ограниченный, offline-проверяемый Sol catch-up** для подтверждённых региональных/высокозначимых пропусков, но НЕ включать его в production без отдельного согласования API-бюджета, тестирования по `search-change-validation-matrix.md`, event/source freshness и полного dependency/recovery/architecture audit. Для свежих Kimi/MiniMax сначала проверить штатный exact-source binder и archive URL semantics на сохранённых кандидатах обеих моделей, без платных поисков. Не менять действующие Primary/Source Pulse/Hybrid/дедупликацию в рамках этого PR.

**Завершение:** оригинальные артефакты сохранены в GitHub Actions, comparator date-only bug исправлен, одноразовые paid/offline workflow jobs возвращены к исходному Main CI, PR остаётся draft, не сливать. README/ARCHITECTURE/AGENTS production behavior не менялись, поэтому изменения этих канонических документов не требуются. Это архив экспериментального результата, а не production rollout.
