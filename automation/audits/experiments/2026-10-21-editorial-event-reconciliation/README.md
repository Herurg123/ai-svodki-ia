# 21 октября 2026: границы исправления Editorial/Recovery

Исторический исходный отчёт: `INCIDENT_REVIEW_2026-10-21.md` и
`HANDOFF_2026-10-21.md` из независимого review Astra. Не заменяют собственные
регрессионные проверки и не являются permission на paid API или publication.

## Инцидент и доказательства

- Exact production SHA: `b9a959f0dbacafe1d3539d7022edec7aefc6b106`.
- Failed run `39528130380`, persisted final artifact `12314885810`,
  research checkpoint `12314271679`. Recovery runs `39531026599` и
  `39536705583` воспроизвели ту же редакционную ошибку.
- Три Editorial calls (две незавершённые структуры и один `response_saved`).
  До Image дело не дошло. Coverage Search на этом пути = 0.
- Третье тело provider response содержит восемь `<h3>` при семи selected IDs:
  сюжет MiniMax `cand-002` дважды представлен в мировой и китайской секциях;
  исходные абзацы **различаются**, поэтому general HTML dedup запрещён.
- Raw JSON SHA256: `abd3462ebd7ff46c8db09a733e0bc2e3b432bc600c3bc151cd3b65daef997478`.
  Raw article UTF-8 SHA256:
  `c508c6f5b8d0c71beed991439386a06137d7a7b34e7f6d00828f2d5d27bbfd78`.
  MiniMax full story subtrees SHA256:
  `b8af33710578bf6b8c3bb16d206d3a029ab5d10bee881582b67cd58eacca2778`
  и `3f27b416369e71513b3b1609d0a901c9fe4db07d0b040e8bd08f5f1234bc7978`.
- В оригинальном `editorial-repair-2026-10-21.json` состояние
  `response_saved`, response seal
  `e9ff7b2a69c6345a448ece17d1f0a560474b91909e89e08541434056202ad127`;
  request SHA256
  `7a7406864201da05ea07ecec6b18b049d512cc0dd3a8f6fba3b3c3e9c33e7074`.
- Коммитированный `archive/index.json` отличается от исторического
  bootstrap archive на same SHA. Recovery обязан доказать именно историческую
  semantic archive identity при штатном bootstrap. Никакой подмены/обнуления
  journal/archive/request для обхода guard.

## Принятое решение

1. Единственный одобренный смысловой выбор для **точного** 21.10.2026:
   перенести неизменный подробный блок MiniMax world→China вместо пересказа,
   сохранить весь original provider response и raw; selected set неизменен.
   Только при совпадении полного raw/article/candidate story hash, journal
   seal, post-Freshness pool hash и archive hash. Без совпадения: fail-closed.
2. Общая защита будущих выпусков: повторное использование однозначно
   сопоставленного **события-кандидата**, даже если HTML совершенно другой,
   блокирует publication. Для разных кандидатных IDs только консервативный
   event-signature signal (organization, event type, title, summary, actual h3);
   такой сигнал **не** даёт автоматической операции удаления или слияния.
   Общий supporting URL или одна организация **не достаточны**.
   Это ограниченный deterministic guard; он не доказывает semantic equivalence
   всех парафразов и не заменяет будущий structured renderer.
3. Runtime и независимый public validator проверяют фактическое расположение
   каждого h3 по h2 с действующей tracked-China classification.
4. Raw каждого Editorial сохраняется по provider response ID до parsing
   независимо от удаления dated preview. Уже оплаченный response не
   инициирует новой модели/API. Подмена immutable записи с тем же ID блокируется.

## Приёмка и ограничения

- Evidence ZIP из Astra проверен; оригинальные архивы и logs сохраняются
  вне tracked source. В repo не коммитятся provider secrets/ZIP.
- Использовать red-first tests, exact future/incident identity tests,
  positive/negative section и event-detection cases, full Main CI
  и exact-head PR Gate.
- Внешние HTTP, OpenAI/Terra/Web Search, Image, FTP и публикация **запрещены**
  в данном offline review.
- Не менять retrieval models/prompts, budgets, ranking, Source Freshness,
  P0 repair request identity, spend guard, journal transition или archive hash.
- Этот PR нельзя merge по одним зелёным тестам. Требуются независимый
  scope/diff review и отдельное явное разрешение владельца.

### Известная граница semantic detection

Смысла произвольных парафразов нельзя надёжно вывести только из совпадения
URL, заголовка или близости слов. Реализованная проверка использует
уже проверенные event/candidate identities и высокопороговые событийные
признаки. Ложные или непойманные случаи без общих identity/признаков
возможны. Отдельный более широкий semantic matcher или новый structured
stories renderer потребует самостоятельного аудита, оценки costs и approval;
он не выполняется при восстановлении уже сохранённого provider response.

## Independent offline PR replay on exact saved inputs (21 October)

После первоначального review извлечены **оригинальные** ZIP из EVIDENCE:
final 12314885810, research checkpoint 12314271679, recovery runs
12315500758/12317891800 и успешные контрольные Coverage checkpoints
12235467270 (20 октября), 12157985571 (19 октября). Для получения текущего
PR source в изолированной локальной среде использован одноразовый исходный
снимок Main CI: temporary artifact 12323272721, затем artifact 12323138961
с опубликованными content и RSS. Temporary CI instrumentation удалена из PR
после копирования исходников; кодовая ветка/research code не менялись
в рамках этого transfer.

Настоящий saved bundle для 21 октября с journal state=response_saved
пропущен через реальную публичную цепочку
`run_editorial_repair.main → run_digest_preview.main → generate_digest_preview.main`.
В SDK установлен offline tripwire; socket connect запрещён; Source Freshness
читает точно сохранённый post-Freshness pool (hash identity подтверждает
штатный guard). Дополнительный monkeypatch HTML-normalizer не используется.
Детерминированная relocation производится production-кодом PR, а не
экспериментальным helper-исправлением.

Результаты:
- child exit code=0, provider calls=0, network calls=0, freshness fixture uses=1;
- journal `response_saved → validated`, selected IDs
  `[cand-001,cand-003,cand-004,cand-005,cand-006,cand-013,cand-002]`;
- `editorial-reconciliation.json.status=applied`, исходный raw SHA256
  `abd3462ebd7ff46c8db09a733e0bc2e3b432bc600c3bc151cd3b65daef997478`;
- approved before-normalization HTML SHA256
  `afa9c7c31aa01900b5a2b8fe18de3b7b64731029ca04f34befa4f4e3051c52a7`;
- 7 final HTML stories; Chinese h2 содержит подробный MiniMax;
- после штатного Coverage parent `_finalize_report` публичный
  `validate_digest_artifact.py` returned 0, errors=0, warnings=0.
  До parent finalize публикационный guard отвергал незавершённый Coverage,
  как и требуется.

Archive identity проверена отдельно:
- committed `automation/archive/index.json` at exact incident SHA:
  semantic hash `bf6beb167ff417cc58f9ab77ea50486ceeea0dfbdf227a1bc5007c413744d096`;
- исторический journal требует
  `87eae526295da7ee791619cacfb9d7f16c07425d5efe85eb3fdcfe327a35347d`;
- прямой offline recovery с committed archive вернул
  `EditorialRepairError: editorial repair input changed: archive_sha256`,
  provider=0;
- **реальный** `bootstrap_archive.py` на published
  `automation/content` + `posts/rss.xml` собрал 95 archive items
  и вернул **точно** `87eae526295da7ee791619cacfb9d7f16c07425d5efe85eb3fdcfe327a35347d`.
  Повторный replay с этим rebuilt archive завершился validated без provider/network.
  Никакой исторической подмены текущего archive или отключения guard не требуется.

Отрицательные original-bundle probes после PR:
- `drop_last` rejected из-за фактического отсутствия MiniMax в China (до
  фикса валидатор принимал этот дефект);
- `request_started` без целого response → unknown_after_request/no retry;
  `request_started` с целым response → validated без transport;
- повреждённый/отсутствующий response, model drift,
  selected partition mismatch → fail-closed;
- exact duplicate/paraphrase и alternate event с same candidate URL →
  no auto-delete/fail-closed; unselected URL/alias → mapping rejected;
- `drop_second`/explicit `move_detailed_to_china` в независимом
  враждебном in-memory transformer могут успешно пройти, поскольку это
  искусственно разрешённый прямой alteration **до** новой correction seam;
  production code PR не делает эти операции без exact signed manifest.
  Это подтверждённая граница теста, а не разрешение general deletion.
- historical Oct19 and Oct20 successful checkpoint copies pass updated
  public validator: returned 0, errors=0, warnings=0 each.

Итог: независимое воспроизведение подтверждает работу exact incident
reconciliation и безопасного Recovery без повторения уже оплаченных вызовов.
Тест не включает live-source fetch, Image API, FTP/deploy или публикацию.
Не является merge/production authorization.
