"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(ROOT, "dzen-publish.js"), "utf8");
const helpers = require(path.join(ROOT, "dzen-publish.js"));

assert.strictEqual(
  helpers.buildDzenTitle("2026-08-27"),
  "ИИ-Сводка на 27 августа 2026 | Подпишись, чтоб получать свежее!"
);
assert.strictEqual(helpers.formatRussianNumericDate("2026-08-27"), "27.08.2026");
const description = helpers.buildDzenDescription(
  "2026-08-27",
  "https://rybalka.one/posts/2026-08-27/",
  "https://dzen.ru/suite/test"
);
assert(description.includes("Без рекламы и воды на 27.08.2026:"));
assert(description.includes("https://rybalka.one/posts/2026-08-27/"));
assert(description.includes("https://dzen.ru/suite/test"));

const defaults = helpers.applyDzenConfigDefaults({});
assert.strictEqual(defaults.dzenUpload.enabled, false, "Dzen upload не должен включаться по умолчанию");
assert.deepStrictEqual(
  defaults.dzenUpload.tags,
  ["ии", "ai", "полезныесоветы", "будущее", "лайфхак"],
  "Dzen contract должен фиксировать ровно пять согласованных тегов"
);
assert.strictEqual(defaults.dzenUpload.commentsAudience, "Все пользователи");
helpers.normalizeTags(defaults.dzenUpload.tags);

for (const marker of [
  'data-testid="add-publication-button"',
  "Загрузить видео",
  "videoEditorPublicationId",
  "Загрузили и обработали видео",
  "Добавить обложку",
  "Теги через запятую",
  "Все пользователи",
  "!!! DZEN:",
  "READY_TO_PUBLISH",
  "Финальная кнопка НЕ нажата",
  "DZEN_FILE_TRANSFER_TIMEOUT_MS = 120000",
  "DZEN_DRAFT_DISCOVERY_TIMEOUT_MS = 180000",
  "Новый draft не создаю",
  "повторно MP4 не отправляю",
]) {
  assert(source.includes(marker), `В dzen-publish.js отсутствует контрактный маркер: ${marker}`);
}

assert(source.includes("waitForEvent(\"filechooser\""), "MP4/PNG должны загружаться через Playwright filechooser");
assert(source.includes("selected.length !== 5"), "Должна быть финальная проверка пяти тегов");
assert(source.includes("Продолжаем подготовку публикации"), "Ошибка комментариев должна быть non-fatal и логироваться");
assert.strictEqual(
  helpers.readVideoDraftFromUrl("https://dzen.ru/profile/editor/rybv?videoEditorPublicationId=abc-123").draftId,
  "abc-123",
  "Draft recovery должен извлекать videoEditorPublicationId из текущего URL"
);
assert.strictEqual(
  helpers.readVideoDraftFromUrl("https://dzen.ru/profile/editor/rybv"),
  null,
  "Обычный URL студии не должен считаться созданным draft"
);
assert.throws(() => helpers.parseArgs(["--publish"]), /не включён/i);
assert.doesNotThrow(() => helpers.parseArgs(["--dry-run", "--date=2026-08-27"]));

console.log("Dzen video dry-run contract smoke: OK");
