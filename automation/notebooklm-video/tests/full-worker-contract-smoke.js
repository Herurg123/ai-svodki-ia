"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(ROOT, "full-worker.js"), "utf8");
const launcher = fs.readFileSync(path.join(ROOT, "run-worker.cmd"), "utf8");
const full = require(path.join(ROOT, "full-worker.js"));

assert(source.includes('runNodeScript("scheduled-worker.js")'),
  "full worker must run the existing scheduled worker first");
assert(source.includes('runNodeScript("dzen-collections.js", ["--apply"'),
  "collections must be a separate third phase after the existing scheduled worker attempt");
assert(source.includes("Третья фаза всё равно проверит доступные same-day публикации"),
  "collections must remain independently useful after a phases-1/2 failure");
assert(source.includes("collections.collectionsComplete(job)"),
  "full worker must skip collections child when both targets are already persisted");
assert(source.includes("Браузер для подборок НЕ открываю"),
  "full worker must document no-browser skip for completed collections");
assert(source.includes("FULL_WORKER_LOCK_PATH"),
  "outer lock must cover scheduled worker plus collection phase");
assert.match(launcher, /full-worker\.js/i);
assert.doesNotMatch(launcher, /node\s+"?%~dp0scheduled-worker\.js/i,
  "run-worker.cmd must use the outer full worker, not bypass it");

const scheduledIndex = source.indexOf('runNodeScript("scheduled-worker.js")');
const collectionIndex = source.indexOf('runNodeScript("dzen-collections.js"');
assert(collectionIndex > scheduledIndex, "collections phase must run after the video/Dzen attempt");

const state = {
  jobs: {
    yesterday: { date: "2026-08-28", status: "DONE", updatedAt: "2026-08-28T10:00:00Z" },
    today: { date: "2026-08-29", status: "GENERATING", updatedAt: "2026-08-29T08:00:00Z" },
  },
};
assert.strictEqual(
  full.selectCollectionsJob(state, "2026-08-29", null).date,
  "2026-08-28",
  "normal successful flow must stay aligned with the latest DONE/catch-up job"
);
assert.strictEqual(
  full.selectCollectionsJob(state, "2026-08-29", new Error("video phase failed")).date,
  "2026-08-29",
  "failed video flow must prefer today's existing job so a same-day digest can still be collected"
);

console.log("Full worker collections-stage contract smoke: OK");
