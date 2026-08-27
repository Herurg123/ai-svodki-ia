"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(ROOT, "dzen-publish-direct.js"), "utf8");
const direct = require(path.join(ROOT, "dzen-publish-direct.js"));

const expected = [
  "Что происходит в мире Искусственного Интеллекта (ИИ, AI)",
  "Этот выпуск:",
  "https://rybalka.one/posts/2026-08-27/",
  "https://dzen.ru/suite/7971db4c-2a4e-449f-b8bf-c3907486d6f1",
].join("\n");
const whitespaceOnlyVariant = expected.replace("c3907486", "c39   07486");
const changedVariant = expected.replace("c3907486", "c39X07486");

assert.strictEqual(
  direct.descriptionMatchesIgnoringWhitespace(whitespaceOnlyVariant, expected),
  true,
  "Dzen whitespace-only formatting must not trigger metadata rewrite loops"
);
assert.strictEqual(
  direct.descriptionMatchesIgnoringWhitespace(changedVariant, expected),
  false,
  "Non-whitespace description changes must still be detected"
);
assert.strictEqual(
  direct.processingStageFromText("Загружаем видео: не закрывайте Дзен"),
  "uploading"
);
assert.strictEqual(
  direct.processingStageFromText("Загрузили видео\nОбрабатываем..."),
  "processing"
);
assert.strictEqual(
  direct.processingStageFromText("Загрузили и обработали видео\nГотово: можно публиковать и смотреть"),
  "ready"
);

for (const marker of [
  "dzen-publish-direct.js",
  "Больше metadata не меняю",
  "Загрузили и обработали видео",
  "Готово: можно публиковать и смотреть",
  'name: "Опубликовать", exact: true',
  "baselineSameTitleVideoCount",
  "PUBLISH_CLICKED_UNVERIFIED",
  "повторный клик запрещён",
]) {
  assert(source.includes(marker), `Missing direct-publish contract marker: ${marker}`);
}

assert(!source.includes("жду устойчивого сохранения метаданных"), "Direct live flow must not restore metadata rewrite loop");
assert(!source.includes("первое отличие описания"), "Direct live flow must not block on character-by-character description diffs");

console.log("Dzen direct publish contract smoke: OK");
