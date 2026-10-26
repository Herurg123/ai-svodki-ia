# Исторический архив сравнения Terra и Sol: 22–24 октября 2026

**Статус:** историческое свидетельство, не production, новые платные API-запросы запрещены. Архив подготовлен из неизменённых файлов трёх экспериментальных веток:
- [22 октября](../2026-10-22-sol-api-shadow/RESULT.md), исходный PR #213;
- [23 октября](../2026-10-23-sol-shadow/RESULT.md), исходный PR #214;
- [24 октября](../2026-10-24-sol-shadow/RESULT.md), исходный PR #215.

Проверены и перенесены **17 файлов** из оригинальных деревьев исходных веток: `README.md`, `RESULT.md`, frozen/replay/billing-протоколы и исторические скрипты сравнения и вызовов. Скрипты здесь **только для анализа** и не подключены к Actions. Коммит не меняет `daily-production.yml`, `ci.yml`, редакционный пайплайн, модель Terra и настройки проекта.

## Оригинальные GitHub Actions ZIP

Сохранено **восемь исходных ZIP**. Они извлечены непосредственно из указанных Actions artifacts, не восстановлены из финальных JSON. Проверены CRC всех ZIP и SHA-256. Контрольные суммы относятся **именно к оригинальному ZIP**, не к пересобранному внешнему архиву.

| День | Источник | Artifact | SHA-256 оригинального ZIP | Истечение (UTC) |
|---|---|---|---|---|
| 22.10 | Terra Research | [12395720578](https://github.com/Herurg123/ai-svodki-ia/actions/artifacts/12395720578) | `7fb23f7ecf5dbec10de52c1d0fe5ae464573bab554a24eaeb9494d1536de9951` | 2026-11-05 |
| 22.10 | Sol first partial | [12402559662](https://github.com/Herurg123/ai-svodki-ia/actions/artifacts/12402559662) | `ada53d88eadb3aac9e2508d1a04a5e8b5eb7ed72d1e9aa391a87e336f92a3cc3` | 2026-11-05 |
| 22.10 | Sol final 7+5 | [12412378520](https://github.com/Herurg123/ai-svodki-ia/actions/artifacts/12412378520) | `82585fff3216e5375e8333569e56276204185b0fd73d3af10905ada7fd9a50a6` | 2026-11-05 |
| 23.10 | Terra Research | [12471524859](https://github.com/Herurg123/ai-svodki-ia/actions/artifacts/12471524859) | `b1c8ae91284c3444fcd71c1f9d5d2fd08dbf2084803db3127b479d0ea5d33dfb` | 2026-11-06 |
| 23.10 | Sol first partial 8/12 | [12475775291](https://github.com/Herurg123/ai-svodki-ia/actions/artifacts/12475775291) | `63f6e570a47abac3f2849525f8c45953014c37fde6931f544bcc0a45bb8bcc28` | 2026-11-06 |
| 23.10 | Sol final 8+4 | [12482321746](https://github.com/Herurg123/ai-svodki-ia/actions/artifacts/12482321746) | `86e93b98eb134f0cbe35f6ee2bfb3fcdaccee247ca9ce81bcf255b89305f89a3` | 2026-11-06 |
| 24.10 | Terra Research | [12542274622](https://github.com/Herurg123/ai-svodki-ia/actions/artifacts/12542274622) | `219151cbb68c6b846dab2d0f789261eb5f52af310af1597d8d6a60679c7a316f` | 2026-11-07 |
| 24.10 | Sol final 12/12 | [12548745112](https://github.com/Herurg123/ai-svodki-ia/actions/artifacts/12548745112) | `498d13b640a493813657fbcc9472f3447224792597ab9614f0e2e992e91f2b81` | 2026-11-07 |

Оригиналы **не коммитятся в публичный GitHub**: архивы содержат сырые ответы и служебные API-метаданные. Они сохранены отдельным скачиваемым комплектом `Terra_Sol_original_evidence_2026-10-22_to_24.zip`, который передан владельцу в ChatGPT. Внутри этого комплекта `originals/` содержит исходные ZIP неизменёнными, `MANIFEST.json` и `SHA256SUMS.txt` фиксируют контрольные суммы, а `verify.py` проверяет повторно CRC и SHA-256. **Чтобы хранение пережило 5–7 ноября, владелец должен скачать этот комплект и сохранить в собственном долговременном хранилище.** Этот Git-архив сохраняет ссылки, хэши, отчёты и инструментарий, но не заменяет оригинальные ZIP.

Ранее не зафиксированный SHA-256 Terra Research за 22.10 рассчитан напрямую по скачанному оригинальному ZIP: `7fb23f7ecf5dbec10de52c1d0fe5ae464573bab554a24eaeb9494d1536de9951`.

## Ограничения результатов

- 22.10 первая Sol-попытка содержит неполный учёт одного API-ответа. Ничего не реконструировано задним числом.
- Не путать client-side расчёт стоимости с подтверждённым provider invoice.
- Результаты сравнивают Primary, не полный Editorial / Coverage / Image / публикацию.
- Прежние experimental CI jobs уже удалены из экспериментальных веток; здесь нет активируемых workflow.
- Не запускать `run_shadow.py`, `run_primary.py`, `resume_four.py` на платном API без отдельного санкционированного бюджета.
- Оригинальные PR #213–215 можно закрывать **после** архивирования и независимой сверки. Их ветки удаляются отдельно, без merge.
