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

for (const marker of [
  'alpha <= 0.70',
  'status: "ADDED"',
  'status: "PENDING"',
  'Браузер НЕ открываю',
  'existing-muted-tile',
  'Повторный клик НЕ выполняю',
  'жду загрузку плашки',
  'Не дождался загрузки подборки',
]) assert(source.includes(marker), `Missing collections marker: ${marker}`);

const pendingIndex = source.indexOf("const pending = TARGETS.filter");
const launchIndex = source.indexOf("launchRobotBrowser");
assert(pendingIndex >= 0 && launchIndex > pendingIndex, "completed-target filtering must happen before browser launch");
assert(source.includes('confirmedBy: result.status === "added" ? "ui-success-after-click" : "existing-muted-tile"'));
console.log("Dzen collections persistence contract smoke: OK");
