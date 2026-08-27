"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(ROOT, "dzen-publish-direct.js"), "utf8");
const runner = fs.readFileSync(path.join(ROOT, "dzen-browser-runner.js"), "utf8");
const direct = require(path.join(ROOT, "dzen-publish-direct.js"));

const expected = [
  "Что происходит в мире Искусственного Интеллекта (ИИ, AI)",
  "Этот выпуск:",
  "https://rybalka.one/posts/2026-08-27/",
  "https://dzen.ru/suite/7971db4c-2a4e-449f-b8bf-c3907486d6f1",
].join("\n");
const whitespaceOnlyVariant = expected.replace("c3907486", "c39   07486");
const changedVariant = expected.replace("c3907486", "c39X07486");
const expectedTags = ["ии", "ai", "полезныесоветы", "будущее", "лайфхак"];

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
  direct.tagSetComplete([...expectedTags].reverse(), expectedTags),
  true,
  "A resumed draft with all five configured tag chips must be accepted even when the tag input is hidden"
);
assert.strictEqual(
  direct.tagSetComplete(expectedTags.slice(0, 4), expectedTags),
  false,
  "Missing fifth tag must remain a blocking preparation error"
);
assert.strictEqual(direct.DIRECT_FLOW_REVISION, 2, "Failed live resume semantics must force one clean direct-flow draft revision");
assert.strictEqual(direct.STUDIO_CHANNEL_TIMEOUT_MS, 20_000, "Studio channel confirmation must tolerate bounded UI hydration delay");
assert.strictEqual(direct.processingStageFromText("Загружаем видео: не закрывайте Дзен"), "uploading");
assert.strictEqual(direct.processingStageFromText("Загрузили видео\nОбрабатываем..."), "processing");
assert.strictEqual(
  direct.processingStageFromText("Загрузили и обработали видео\nГотово: можно публиковать и смотреть"),
  "ready"
);
assert.strictEqual(
  direct.draftIdFromUrl("https://dzen.ru/profile/editor/rybv?videoEditorPublicationId=abc123"),
  "abc123"
);

for (const marker of [
  "Больше metadata не меняю",
  "Загрузили и обработали видео",
  "Готово: можно публиковать и смотреть",
  'name: "Опубликовать", exact: true',
  "baselineSameTitleVideoCount",
  "PUBLISH_CLICKED_UNVERIFIED",
  "повторный клик запрещён",
  "все 5 тегов уже подтверждены как плашки",
  "продолжаю существующий video draft без новой вкладки",
  "не трогаю клавиатурой",
  "жду подтверждение канала",
  "add-publication-button=",
]) {
  assert(source.includes(marker), `Missing direct-publish contract marker: ${marker}`);
}

assert(runner.includes('"dzen-publish-direct.js"'), "Canonical live runner must use dzen-publish-direct.js");
assert(
  runner.includes("live publish выполняется одним child-проходом без автоматического повторного запуска"),
  "Live publish must explicitly run as a single child attempt"
);
assert(
  runner.includes("Автоматический повтор live-flow в этом запуске отключён"),
  "A failed live child must stop instead of silently restarting the whole direct flow"
);
assert(
  runner.includes("runDryRunWithRecovery"),
  "Legacy retry window may remain isolated to diagnostic dry-run"
);
const mainStart = runner.indexOf("async function main");
const liveStart = runner.indexOf('if (mode === "publish") {', mainStart);
const dryRunDispatch = runner.indexOf("return await runDryRunWithRecovery", liveStart);
assert(mainStart >= 0 && liveStart >= 0 && dryRunDispatch > liveStart, "Cannot locate live single-pass branch in runner");
const liveBranch = runner.slice(liveStart, dryRunDispatch);
assert(!liveBranch.includes("while ("), "Live publish branch must not contain an automatic retry loop");
assert(!liveBranch.includes("RETRY_DELAY_MS"), "Live publish branch must not schedule delayed retries");

assert(!source.includes('descriptionInput.press("Tab")'), "Resume path must not press Tab inside the controlled description textarea");
assert(!source.includes('status: "PUBLISHING",\n      editorPublicationsUrl'), "New direct flow must not mark a pre-click baseline as PUBLISHING");
assert(!source.includes("жду устойчивого сохранения метаданных"), "Direct live flow must not restore metadata rewrite loop");
assert(!source.includes("первое отличие описания"), "Direct live flow must not block on character-by-character description diffs");

console.log("Dzen direct publish contract smoke: OK");
