"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

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

function readNumericRunnerConstant(name) {
  const match = new RegExp(`const ${name} = ([0-9_]+);`).exec(runner);
  assert(match, `Missing runner constant: ${name}`);
  return Number(match[1].replace(/_/g, ""));
}

assert.strictEqual(readNumericRunnerConstant("POST_CLICK_CHALLENGE_PROBE_MS"), 4_000);
assert.strictEqual(readNumericRunnerConstant("POST_CLICK_CHALLENGE_WAIT_MS"), 120_000);

const classifierStart = runner.indexOf("function textLooksLikeManualAntiBotChallenge");
const classifierEnd = runner.indexOf("async function findAntiBotChallengePage", classifierStart);
assert(classifierStart >= 0 && classifierEnd > classifierStart, "Challenge classifier source must exist");
const classifierSource = runner.slice(classifierStart, classifierEnd).trim();
const textLooksLikeManualAntiBotChallenge = vm.runInNewContext(
  `(${classifierSource.replace(/^function\s+textLooksLikeManualAntiBotChallenge/, "function")})`
);

assert.strictEqual(
  textLooksLikeManualAntiBotChallenge(
    "Подтвердите,\nчто вы не робот\nЯ не робот\nУсловия использования"
  ),
  true,
  "Observed post-click challenge must be detected"
);
assert.strictEqual(
  textLooksLikeManualAntiBotChallenge("Готово: можно публиковать и смотреть"),
  false,
  "Normal ready state must not be classified as anti-bot challenge"
);
assert.strictEqual(
  textLooksLikeManualAntiBotChallenge("Я не робот"),
  false,
  "A bare phrase without the confirmation prompt is not sufficient"
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

for (const marker of [
  "ПОСЛЕ PUBLISH ПОЯВИЛАСЬ АНТИБОТ-ПРОВЕРКА",
  "Автоматизация НЕ нажимает checkbox и НЕ выполняет других кликов",
  "Окно Яндекс.Браузера восстановлено для ручного подтверждения",
  "Антибот-проверка исчезла",
  "verification-only",
]) {
  assert(runner.includes(marker), `Missing post-click challenge contract marker: ${marker}`);
}

const challengeStart = runner.indexOf("async function waitForOptionalPostClickChallenge");
const challengeEnd = runner.indexOf("function terminateChildTree", challengeStart);
assert(challengeStart >= 0 && challengeEnd > challengeStart, "Post-click challenge wait helper must exist");
const challengeSource = runner.slice(challengeStart, challengeEnd);
assert(
  !challengeSource.includes(".click("),
  "Post-click anti-bot handling must never click the challenge or any other UI"
);
assert(
  runner.includes('if (scriptName === "dzen-publish-direct.js")'),
  "Challenge wait must be limited to the live publish child"
);
assert(
  runner.includes("await waitForOptionalPostClickChallenge();"),
  "Successful live publish child must enter the optional challenge wait before the runner resolves"
);

assert(runner.includes('"dzen-publish-direct.js"'), "Canonical live runner must use dzen-publish-direct.js");
assert(
  runner.includes("live publish выполняется одним child-проходом без автоматического повторного запуска"),
  "Live runner must remain single-pass"
);

console.log("Dzen direct fresh-upload MVP contract smoke: OK");
