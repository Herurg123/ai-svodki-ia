"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(ROOT, "dzen-publish-direct.js"), "utf8");
const runner = fs.readFileSync(path.join(ROOT, "dzen-browser-runner.js"), "utf8");
const direct = require(path.join(ROOT, "dzen-publish-direct.js"));

const expectedDescription = direct.buildLiveDescription(
  "2026-08-27",
  "https://rybalka.one/posts/2026-08-27/",
  "https://dzen.ru/suite/7971db4c-2a4e-449f-b8bf-c3907486d6f1"
);
assert(
  expectedDescription.includes(
    "Этот выпуск:\n\n- https://rybalka.one/posts/2026-08-27/\n- https://dzen.ru/suite/7971db4c-2a4e-449f-b8bf-c3907486d6f1"
  ),
  "Video description URLs must be separate bullet lines"
);

const whitespaceOnlyVariant = expectedDescription.replace("c3907486", "c39   07486");
const changedVariant = expectedDescription.replace("c3907486", "c39X07486");

assert.strictEqual(
  direct.descriptionMatchesIgnoringWhitespace(whitespaceOnlyVariant, expectedDescription),
  true,
  "Whitespace-only formatting must not trigger another metadata write"
);
assert.strictEqual(
  direct.descriptionMatchesIgnoringWhitespace(changedVariant, expectedDescription),
  false,
  "Non-whitespace description changes must still be detected"
);

const tags = ["ии", "ai", "полезныесоветы", "будущее", "лайфхак"];
assert.strictEqual(direct.tagSetComplete(tags, tags), true);
assert.strictEqual(direct.tagSetComplete(tags.slice(0, 4), tags), false);

assert.strictEqual(direct.STUDIO_CHANNEL_TIMEOUT_MS, 30_000);
assert.strictEqual(direct.processingStageFromText("Загружаем видео: не закрывайте Дзен"), "uploading");
assert.strictEqual(direct.processingStageFromText("Загрузили видео\nОбрабатываем..."), "processing");
assert.strictEqual(
  direct.processingStageFromText("Загрузили и обработали видео\nГотово: можно публиковать и смотреть"),
  "ready"
);

for (const marker of [
  "только новый upload; previous drafts/state resume полностью игнорируются",
  "metadata заполнены один раз",
  "PNG-обложка передана один раз",
  "подтверждены все 5 тегов",
  "Metadata/cover/tags больше не трогаю",
  "Загрузили и обработали видео",
  "Готово: можно публиковать и смотреть",
  "Кто может комментировать",
  "КЛИК ПУБЛИКАЦИИ ВЫПОЛНЕН ОДИН РАЗ",
  "post-click verification и повторное открытие draft в этом MVP отсутствуют",
]) {
  assert(source.includes(marker), `Missing direct MVP contract marker: ${marker}`);
}

for (const forbidden of [
  "tryOpenUsableDraft",
  "archiveUnusableDraft",
  "previousDrafts.push",
  "PUBLISH_CLICKED_UNVERIFIED",
  "verifyPublishedVideo",
  "baselineSameTitleVideoCount",
]) {
  assert(!source.includes(forbidden), `Fresh-upload MVP must not contain legacy resume/verify code: ${forbidden}`);
}

assert(runner.includes('"dzen-publish-direct.js"'), "Canonical live runner must use dzen-publish-direct.js");
assert(
  runner.includes("live publish выполняется одним child-проходом без автоматического повторного запуска"),
  "Live runner must remain single-pass"
);

console.log("Dzen direct fresh-upload MVP contract smoke: OK");
