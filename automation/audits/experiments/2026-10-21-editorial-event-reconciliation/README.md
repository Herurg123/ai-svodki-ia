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
