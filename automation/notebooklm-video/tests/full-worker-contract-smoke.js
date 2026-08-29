"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(ROOT, "full-worker.js"), "utf8");
const launcher = fs.readFileSync(path.join(ROOT, "run-worker.cmd"), "utf8");

assert(source.includes('runNodeScript("scheduled-worker.js")'),
  "full worker must run the existing scheduled worker first");
assert(source.includes('runNodeScript("dzen-collections.js", ["--apply"'),
  "collections must be a separate third phase after the existing scheduled worker");
assert(source.includes('scheduled.getAutomationStatus(job) === "PUBLISHED"'),
  "collections phase must wait for confirmed native Dzen video publication");
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
assert(collectionIndex > scheduledIndex, "collections phase must run after video/Dzen phases");

console.log("Full worker collections-stage contract smoke: OK");
