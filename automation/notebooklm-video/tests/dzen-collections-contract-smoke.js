"use strict";
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");
const collections = require(path.join(ROOT, "dzen-collections.js"));
const source = fs.readFileSync(path.join(ROOT, "dzen-collections.js"), "utf8");

assert.deepStrictEqual(
  collections.TARGETS.map((t) => [t.key, t.collectionName, t.collectionUrl]),
  [
    ["video", "Видеосводки по ИИ", "https://dzen.ru/suite/a899d818-52b3-4f87-8e49-4a4bac375244"],
    ["digest", "Сводки по ИИ", "https://dzen.ru/suite/7971db4c-2a4e-449f-b8bf-c3907486d6f1"],
  ]
);
const partial = { dzenCollections: { video: { status: "ADDED" }, digest: { status: "PENDING" } } };
assert.strictEqual(collections.collectionsStatus(partial), "PARTIAL");
assert.strictEqual(collections.collectionsComplete(partial), false);
assert.strictEqual(collections.targetIsAdded(partial, "video"), true);
assert.strictEqual(collections.targetIsAdded(partial, "digest"), false);
const complete = { dzenCollections: { video: { status: "ADDED" }, digest: { status: "ADDED" } } };
assert.strictEqual(collections.collectionsStatus(complete), "COMPLETE");
assert.strictEqual(collections.collectionsComplete(complete), true);

// Regression for the 2026-08-29 scheduled screenshot: the modal shell was visible
// with a spinner, so zero collection-title matches before the deadline is WAIT,
// not an immediate error. Neighboring terminal states remain fail-closed.
assert.strictEqual(collections.classifyCollectionCardLookup(0, false), "WAIT");
assert.strictEqual(collections.classifyCollectionCardLookup(1, false), "FOUND");
assert.strictEqual(collections.classifyCollectionCardLookup(0, true), "TIMEOUT");
assert.strictEqual(collections.classifyCollectionCardLookup(2, false), "AMBIGUOUS");
assert.strictEqual(collections.COLLECTION_CARD_TIMEOUT_MS, 15_000);

// Regression for the 2026-09-13 Dzen UI reorder: exact target cards can exist
// below the modal viewport. Geometry must be unsafe before scroll and safe only
// after the card is brought into the visible modal area.
const viewport = { width: 1365, height: 768 };
const modalBox = { x: 16, y: 8, width: 640, height: 636 };
assert.strictEqual(
  collections.collectionClickGeometry({ x: 40, y: 700, width: 580, height: 90 }, modalBox, viewport).safe,
  false
);
assert.strictEqual(
  collections.collectionClickGeometry({ x: 40, y: 630, width: 580, height: 90 }, modalBox, viewport).safe,
  false
);
assert.strictEqual(
  collections.collectionClickGeometry({ x: 40, y: 500, width: 580, height: 90 }, modalBox, viewport).safe,
  true
);

// Regression for the false-positive video ADDED incident: page-wide success text
// is diagnostic only. Persisting ADDED requires target-local selected/muted state,
// immediately or after exact-target re-open verification.
assert.strictEqual(collections.classifyCollectionConfirmation(true, false, false), "muted-tile");
assert.strictEqual(collections.classifyCollectionConfirmation(false, true, false), "reopened-muted-tile");
assert.strictEqual(collections.classifyCollectionConfirmation(false, false, true), null);
assert.strictEqual(collections.classifyCollectionConfirmation(false, false, false), null);

for (const marker of [
  'alpha <= 0.70',
  'status: "ADDED"',
  'status: "PENDING"',
  'Браузер НЕ открываю',
  'existing-muted-tile',
  'Повторный клик НЕ выполняю',
  'жду загрузку плашки',
  'Не дождался загрузки подборки',
  'scrollIntoViewIfNeeded',
  'document.elementFromPoint',
  'общий success-text, но он НЕ считается подтверждением',
  'reopened-muted-tile',
  'Повторный клик запрещён',
]) assert(source.includes(marker), `Missing collections marker: ${marker}`);

assert(!source.includes('return "success-text"'), "page-wide success text must not confirm ADDED by itself");
const processStart = source.indexOf("async function processTarget(");
const processEnd = source.indexOf("function runSelfTest()", processStart);
const processSource = source.slice(processStart, processEnd);
assert.strictEqual((processSource.match(/page\.mouse\.click\(/g) || []).length, 1, "processTarget must retain exactly one physical collection click");
assert(processSource.indexOf("prepareCollectionCardClick(") < processSource.indexOf("page.mouse.click("), "scroll/hit-test must run before the physical click");
assert(processSource.indexOf("verifyCollectionMembershipAfterClick(") > processSource.indexOf("page.mouse.click("), "target-local reopen verification must be post-click only");

const pendingIndex = source.indexOf("const pending = TARGETS.filter");
const launchIndex = source.indexOf("launchRobotBrowser");
assert(pendingIndex >= 0 && launchIndex > pendingIndex, "completed-target filtering must happen before browser launch");
assert(source.includes('confirmedBy: result.status === "added" ? (result.signal || "target-local-ui-confirmation") : "existing-muted-tile"'));
console.log("Dzen collections persistence contract smoke: OK");
