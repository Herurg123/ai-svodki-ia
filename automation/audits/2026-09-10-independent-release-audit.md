# Независимый аудит выпуска 2026-09-10

## Итог

**Publication mechanics: PASS.**

**Recovery / at-most-once: PASS.**

**Freshness policy: PASS как fail-closed, но Source Freshness coverage: FAIL по практической полноте.**

**High-signal completeness: FAIL.**

Выпуск опубликован с 7 сюжетами и технически корректен, однако независимый контроль на свежем окне показывает, что несколько событий существенно выше части опубликованных материалов не дошли до публикации. Главный новый вывод: сегодня проблема делится на два разных слоя, причём первый уже можно считать доказанным повторными наблюдениями:

1. **source resolution / Source Freshness теряет уже найденные сильные события;**
2. **upstream discovery / Reuters rescue продолжает не доставлять ряд крупных событий вообще.**

Это важное уточнение относительно промежуточной гипотезы о ranking/editorial: два сильных кандидата были не проигнорированы редактором, а сняты техническим freshness-gate до финального отбора.

## Production evidence

Фактическая цепочка выпуска:

- scheduled production run `34423913431` выполнил full research/editorial, но остановился на mandatory coverage audit со `retrieval_quality_resolution_unresolved`;
- recovery run `34428040410` восстановил уже оплаченный artifact, не повторял full research/editorial, завершил coverage audit, сгенерировал обложку и опубликовал выпуск;
- повторный dispatch `34432025380` корректно завершился как no-op, потому что выпуск уже был опубликован;
- release commit: `ced45730a586a0a3e439214efb3b448f0abdca6e`;
- последующий PR #163 не менял опубликованный bundle и находится уже поверх release commit.

Это подтверждает, что recovery/at-most-once сейчас выполняет свою функцию: ошибка downstream не заставила повторно оплачивать основной research/editorial.

### Search budget

Сохранённый production artifact показывает:

- Primary: `12/12`;
- Agency Rescue: `1/1`;
- Hybrid: `5/5` из допустимых `4 + 1` при двойном regional gap;
- Coverage: `6/7`;
- всего: `24` Web Search operations при допустимом double-gap ceiling `25`.

Один формально свободный Coverage slot не объясняет масштаб пропусков: независимый контроль находит несколько крупных событий в разных категориях, а Reuters-only rescue уже потратил свой единственный специализированный slot и вернул `raw_count=0`, `accepted_count=0`, `consulted_sources=[]`, при этом source metadata для поисковой операции отсутствует.

## Выпущенные 7 сюжетов

1. Arm Neoverse CSS N4.
2. Apple Watch Audio Intelligence / Live Rewind / Siri Recap.
3. Massachusetts clean-power requirements for large data centers.
4. Paul Christiano joins OpenAI Foundation Board / SSC.
5. Suno v6 on licensed training data.
6. Cymphony funding / AI-agent identity security.
7. Runway + Kinetix team / world models / robotics.

Технически все 7 прошли текущий publication gate.

## Независимый B-control

Использован assistant-owned ordinary web search, без production API budget владельца. Standalone Terra в этой сессии не экспонирована, поэтому обычный web search не выдаётся за Terra. Search-query wording production в рамках этого аудита не менялся.

Консервативный strict control set состоит из 11 событий. В него включались только материалы, подтверждённые авторитетным secondary либо first-party source и попадающие в текущее main window `2026-09-09T04:15:13+03:00 → 2026-09-10T04:04:18+03:00`, либо непосредственно связанные с material update внутри этого окна.

### Контроли, которые production опубликовал

1. **Suno v6 / licensed music** — опубликован.
   - https://suno.com/blog/introducing-v6
   - https://techcrunch.com/2026/09/09/suno-replaces-its-ai-models-with-a-new-one-trained-on-licensed-music-as-copyright-suits-pile-up/
2. **Massachusetts data-center clean-power requirements** — опубликован.
   - https://techcrunch.com/2026/09/09/massachusetts-hits-data-centers-with-new-clean-power-rules/
3. **Paul Christiano joins OpenAI Foundation Board / SSC** — опубликован.
   - https://openai.com/index/paul-christiano-joins-openai-foundation-board/

### Контроли, которые production нашёл, но потерял до публикации

4. **Anthropic: alignment assessment of four real-world cybersecurity incidents**.
   - production candidate `cand-004`, initial recommendation `include`, significance `4`;
   - event freshness: `fresh`;
   - Source Freshness: `unknown`;
   - direct Anthropic page returned HTTP 200, but current source parser reported `no_publication_date`;
   - independent page visibly states `Sep 9, 2026`.
   - https://www.anthropic.com/research/alignment-assessment-cybersecurity-incidents

5. **China response / U.S. NSA-FBI-CISA distillation advisory**.
   - production candidate `cand-001`, initial recommendation `include`, significance `4`;
   - event freshness: `fresh`;
   - Source Freshness: `unknown` because AP direct fetch returned HTTP 403;
   - independent verification finds the AP update plus dated official NSA/CISA material.
   - https://apnews.com/article/0f6ca61301630134607551b1dab0d632
   - https://www.nsa.gov/Press-Room/Press-Releases-Statements/Press-Release-View/Article/4592113/nsa-and-others-warn-china-based-ai-companies-are-distilling-us-frontier-ai-mode/
   - CISA advisory AA26-251A, release date 2026-09-08.

### Strong controls missing from validated candidate surface

6. **Google: €13 billion AI/digital infrastructure investment in Finland**.
   - production did notice the event only as a HuggingNews model rejection and discarded it as `weak_source`;
   - exact first-party Google Press Corner release exists and is dated Sep 9;
   - Reuters independently covered the same investment.
   - https://www.googlecloudpresscorner.com/2026-09-09-Google-Deepens-Commitment-to-Finland-with-Two-Year-EUR13-Billion-investment-in-AI-Infrastructure
   - https://www.reuters.com/business/media-telecom/google-invest-15-billion-ai-infrastructure-finland-2026-09-09/

7. **Harvey: $550M round at $15.5B valuation**.
   - absent from final production candidate surface;
   - first-party + Reuters verification.
   - https://www.harvey.ai/blog/harvey-raises-dollar550m-at-a-dollar155b-valuation-to-help-legal-teams-own-their-intelligence
   - https://www.reuters.com/legal/government/legal-ai-startup-harvey-reaches-155-billion-valuation-new-funding-round-2026-09-09/

8. **DeepSeek taps CITIC Securities for domestic IPO preparation**.
   - absent from final production candidate surface;
   - Reuters dated Sep 9.
   - https://www.reuters.com/world/chinas-deepseek-taps-citic-securities-domestic-ipo-sources-say-2026-09-09/

9. **OpenAI rogue agents used 10+ additional sites for unauthorized communications**.
   - production Coverage saw older/tangential OpenAI incident pages but did not create this new Reuters event as candidate;
   - Reuters dated Sep 9.
   - https://www.reuters.com/world/openais-rogue-agents-used-least-10-more-sites-unauthorized-comms-researchers-say-2026-09-09/

10. **NVIDIA + Australian partners: up to 2 GW AI-factory capacity by 2027**.
    - absent from final candidate surface;
    - NVIDIA announcement and Reuters both fall before the production end cutoff.
    - https://www.reuters.com/world/asia-pacific/nvidia-teams-up-with-australian-partners-build-ai-factory-capacity-2026-09-10/

11. **OpenAI pushes for mandatory national AI safety requirements and supports four California bills**.
    - absent from final candidate surface;
    - OpenAI first-party + Reuters dated Sep 9.
    - https://openai.com/index/ai-policy-window/

## A/B metrics

На этом conservative strict set:

- **A, validated candidate recall:** `5/11 = 45.5%`;
- **A, published strict recall:** `3/11 = 27.3%`;
- **independent awareness/control discovery:** `11/11` controls independently verified;
- production дополнительно **видел Google Finland как weak-source rejection**, то есть часть missing recall является не discovery miss, а source-resolution miss.

Нельзя интерпретировать `11/11` как точность независимого поисковика: controls по определению собраны после независимой проверки. Полезная метрика здесь — разница между существованием подтверждённых high-signal событий и тем, сколько из них дошло до validated candidate/published stages.

### Narrow source-resolution treatment

Без изменения editorial policy можно отдельно рассмотреть уже наблюдавшиеся production события:

- Google Finland: weak-source-only → существует exact first-party Google release;
- Anthropic cyber incidents: HTTP 200 + visible `Sep 9, 2026` → current parser не извлекает дату;
- China/US distillation: AP fetch 403, но существуют dated official NSA/CISA sources и Reuters coverage.

Следовательно, как минимум часть recall loss находится **после discovery и до editorial**. Это уже доказанный слой для следующего controlled treatment. До фактического replay с production parser нельзя честно объявлять точное число recovered candidates, поэтому данный audit не записывает гипотетическое улучшение как достигнутый recall.

## Source Pulse P5: первый live reality check

PR #162 ожидал, что три новых zero-paid official routes улучшат исторический bounded recall. Первый live production после merge показывает, что treatment **архитектурно полезен, но фактически ещё не принят live-средой**:

### OpenAI official RSS

- registry/source fetch: `ok`;
- `parsed_items=16`;
- `window_items=8`;
- `accepted_leads=8`;
- несколько релевантных OpenAI items реально обнаружены;
- все pulse-only OpenAI leads были отклонены promotion как `source_fetch_error: HTTP 403` при direct-page Source Freshness Proof;
- Paul Christiano не является доказательством пользы нового route, потому что он уже был найден Primary и имел `fusion_both_exact_url`.

**Realized new-candidate contribution from OpenAI P5 route: 0.**

### Qualcomm official newsroom

- index HTTP 200;
- source status `ok`;
- `parsed_items=0`, `window_items=0`, `accepted_leads=0`.

Это особенно важный диагностический дефект: route фактически не работает, но source-level status выглядит как `ok`. Для fixed HTML source `200 + parsed_items=0` при заведомо непустой newsroom нельзя считать надёжным healthy signal.

**Realized new-candidate contribution: 0.**

### NSA AI route

- HTTP 403;
- source status `source_unavailable`;
- `accepted_leads=0`.

Независимый web path видит тот же NSA AI page и direct press release с датой Sep 8, то есть событие существует, но production transport не может его получить.

**Realized new-candidate contribution: 0.**

### Вывод по P5

На первом live production все три новых routes дали **0 новых promoted candidates**. Это не означает, что идея fixed official Source Pulse неверна: OpenAI RSS отлично обнаруживает события. Но offline A/B PR #162 был слишком оптимистичен относительно реального transport/freshness layer. Теперь это подтверждено фактическим production artifact, и дальнейшее добавление новых source rows без live acceptance treatment не имеет смысла.

## Reuters / Agency Rescue

Agency Rescue снова является наиболее явным recurring failure:

- triggered because `major_agencies_raw_zero`;
- one Reuters-only search executed;
- exact configured query сохранён;
- `raw_count=0`;
- `accepted_count=0`;
- `consulted_sources=[]`;
- source metadata unavailable.

При этом независимый Reuters control в том же main window подтверждает как минимум:

- Google Finland €13B;
- Harvey $550M / $15.5B;
- DeepSeek IPO / CITIC;
- OpenAI rogue agents on 10+ sites;
- NVIDIA Australia up to 2GW;
- OpenAI mandatory safety requirements.

После Sep 8–10 это уже нельзя считать случайным плохим днём. Специализированный Reuters rescue выполняется, тратит slot и неоднократно не обеспечивает свою функцию.

## Что хорошо

1. **Recovery работает правильно.** Full paid research/editorial не повторился; сохранённый artifact был переиспользован.
2. **At-most-once publication работает.** Следующий dispatch корректно стал no-op.
3. **Freshness остаётся fail-closed.** Pipeline не опубликовал кандидатов, для которых не смог доказать source freshness.
4. **Source Pulse действительно умеет обнаруживать OpenAI через RSS.** Проблема теперь локализована после discovery, а не в самом RSS collection.
5. **Primary увидел Google Finland хотя бы как weak-source event.** Это доказывает, что часть потерь можно исправлять source resolution, не только большим поиском.
6. **Search ceilings не нарушены.** Никакого budget overrun.

## Что плохо

1. **Validated high-signal recall остаётся низким: 45.5% на conservative control set.**
2. **Published strict recall ещё ниже: 27.3%.**
3. **Source Freshness теряет сильные официальные материалы:** Anthropic HTTP 200 с видимой датой всё равно получает `no_publication_date`; AP и OpenAI direct pages часто упираются в 403.
4. **Weak-source rejection слишком легко становится окончательной потерей события.** Google Finland найден, но exact first-party source не был разрешён до исключения.
5. **Agency Rescue фактически не выполняет Reuters rescue.** Повторный `0` при наличии множества Reuters событий уже является системным сигналом.
6. **P5 official routes пока не дали live contribution.** Qualcomm `200 + parsed=0` выглядит ложным healthy; NSA 403; OpenAI discovery блокируется direct-page 403.
7. **Publisher concentration остаётся следствием upstream source availability.** В выпуске снова три TechCrunch story, потому что альтернативные сильные источники не доходят до publishable state.
8. **Coverage использовал 6 операций и всё равно не восстановил новый Reuters OpenAI incident.** Ещё один общий slot не выглядит адекватным лекарством.

## Что уже точно пора менять

### P0 — Source Freshness / source resolution

Это следующий runtime treatment с самым сильным доказательством.

Нужно отдельно A/B проверить и затем, если проходит gate, внедрить:

1. **publisher-specific visible-date extraction для Anthropic** из bounded article header / structured page surface, не generic body scraping;
2. **first-party feed freshness proof для exact-bound official RSS item**, прежде всего OpenAI: если RSS от официального домена содержит exact article URL + authoritative publication timestamp, direct article 403 не должен автоматически уничтожать event, но это требует отдельного policy/audit change и строгой exact-URL binding;
3. **weak-source high-signal resolver**: найденный крупный event на aggregator не должен сразу умирать как weak_source, если в уже доступном first-party surface можно разрешить exact source без увеличения общего search ceiling;
4. **source-specific fallback для AP/official government sources**, где direct transport часто 403, но существует официальный dated mirror/advisory.

Цель P0: вернуть уже обнаруженные события, не увеличивая Web Search budget и не ослабляя freshness fail-closed.

### P1 — Agency Rescue redesign

После P0 необходимо менять не просто формулировку Reuters query, а сам механизм/transport диагностики.

Требования к следующему эксперименту:

- сохранить max `1` Agency Search operation;
- различать `provider returned no Reuters source`, `source metadata unavailable`, `model rejected`, `navigation/source-resolution failed`;
- прогнать исторические controls Sep 8–10;
- обязательные positive controls: Google Finland, Harvey, DeepSeek IPO, OpenAI rogue agents, NVIDIA Australia, OpenAI safety policy;
- не объявлять `completed_no_addition` здоровым исходом, если provider path не дал source metadata вообще.

Search-query wording следует менять только с Terra-side validation согласно проектному контракту. Если Terra недоступна, treatment должен быть transport/source-resolution, а не неподтверждённый query rewrite.

### P2 — Source Pulse live acceptance

До добавления новых source rows необходимо чинить три уже добавленных:

- Qualcomm: `HTTP 200 + parsed_items=0` должен диагностироваться как `parse_empty/indeterminate` либо parser нужно адаптировать к текущей newsroom structure;
- NSA: использовать реально доступный официальный endpoint/mirror или CISA joint advisory surface вместо мёртвого 403 path;
- OpenAI: решить exact official RSS → source-freshness proof contract.

После этого повторить live/offline acceptance на тех же controls. Простое расширение registry сейчас только увеличит количество красивых строк конфигурации, а не recall.

### P3 — Editorial ranking только после P0/P1

Сегодня нет достаточных оснований первым делом менять редакторский ranking. `cand-001` и `cand-004` имели score 4 / initial include, но были технически переведены в exclude из-за Source Freshness. Cymphony и Runway заняли место уже после этого.

Ranking можно оценивать повторно только после того, как сильные кандидаты действительно доходят до publishable candidate pool.

## Решение

**Audit verdict: search/retrieval stack требует следующего runtime treatment.**

Первым менять **Source Freshness + source resolution**, вторым **Agency Rescue**, третьим **live acceptance Source Pulse**. Editorial ranking пока не является P0.

Не рекомендуется:

- увеличивать ceiling выше 25;
- ослаблять freshness;
- вводить региональные или количественные publication quotas;
- добавлять ещё official sources до исправления уже наблюдаемого transport/parser failure;
- лечить Reuters пропуски только ещё одним общим Coverage query.

README / `automation/README.md` / `automation/ARCHITECTURE.md` в этом audit-only PR не меняются: runtime contract не изменён. Следующий runtime PR по P0 уже потребует архитектурного и regression review.
