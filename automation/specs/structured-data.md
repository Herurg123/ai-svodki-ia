# Schema.org для ИИ-Сводок

Стабильные сущности:

- `https://rybalka.one/#person` — существующий автор.
- `https://rybalka.one/#website` — сайт.
- `https://rybalka.one/posts/#blog` — раздел «ИИ-Сводки».
- `https://it-expertise.ru/#organization` — работодатель автора.

Каждая новая страница получает JSON-LD `@graph`:

- `BlogPosting`;
- `WebPage`;
- `ImageObject`;
- `BreadcrumbList`;
- `Blog`;
- `Person`;
- `WebSite`;
- `Organization`.

`BlogPosting` строится из `digest.json`, `stories.json` и `sources.json`.
В RSS JSON-LD не вставляется.

Индекс `/posts/` получает `Blog`, `CollectionPage` и `ItemList`.

`/posts/sitemap.xml` создаётся из текущего RSS и включает локальные
обложки через image sitemap namespace.
