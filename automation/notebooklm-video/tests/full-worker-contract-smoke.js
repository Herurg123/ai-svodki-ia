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
assert(source.includes('runNodeScript("dzen-article-video.js", ["--apply"'),
  "article-video must be a separate fourth phase after collections");
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
const articleVideoIndex = source.indexOf('runNodeScript("dzen-article-video.js"');
assert(collectionIndex > scheduledIndex, "collections phase must run after the video/Dzen attempt");
assert(articleVideoIndex > collectionIndex, "article-video phase must run after collections");

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


assert(source.includes('dzenStatus !== "PUBLISHED" || collectionStatus !== "COMPLETE"'),
  "article-video gate must require PUBLISHED video and COMPLETE collections");
assert(source.includes('["COMPLETE", "SKIPPED_EXISTING"].includes(avStatus)'),
  "terminal article-video success/skip must avoid reopening the browser");
assert(source.includes('avStatus === "ERROR" && canAutoRecoverPreEditLinkError(refreshedJob)'),
  "one proven-safe pre-edit link-resolution ERROR must have a dedicated automatic recovery branch");
assert(source.includes('"--recover-pre-edit-link-error"'),
  "safe scheduled recovery must invoke the guarded article-video recovery flag");
assert(source.includes('} else if (avStatus === "ERROR")'),
  "all other terminal article-video ERROR states must still block automatic retry");
assert(source.includes("Фаза 4/4 НЕ запускается: она разрешена только после полного успеха всех предыдущих фаз."),
  "phase 4 must not run after any earlier phase failure");
assert(source.includes("articleVideoError"),
  "full worker must propagate article-video failure into the overall exit result");

assert.strictEqual(full.articleVideoStatus({}), "PENDING");
assert.strictEqual(full.articleVideoStatus({ dzenArticleVideo: { status: "COMPLETE" } }), "COMPLETE");
assert.strictEqual(full.articleVideoPhase({}), "PENDING");
assert.strictEqual(full.articleVideoPhase({ dzenArticleVideo: { phase: "CLICKED_UNVERIFIED" } }), "CLICKED_UNVERIFIED");

const safeLegacyLinkError = {
  dzenArticleVideo: {
    status: "ERROR",
    phase: "ERROR",
    lastError: "«Скопировать ссылку» не положил в clipboard ожидаемый article URL.",
  },
};
assert.strictEqual(
  full.canAutoRecoverPreEditLinkError(safeLegacyLinkError),
  true,
  "legacy pre-edit clipboard link error without editor/publish markers must be auto-recoverable once"
);
assert.strictEqual(
  full.canAutoRecoverPreEditLinkError({
    dzenArticleVideo: {
      ...safeLegacyLinkError.dzenArticleVideo,
      recoveryHistory: [{ reason: "pre-edit link-resolution recovery" }],
    },
  }),
  false,
  "scheduled pre-edit recovery must be at-most-once"
);
assert.strictEqual(
  full.canAutoRecoverPreEditLinkError({
    dzenArticleVideo: {
      ...safeLegacyLinkError.dzenArticleVideo,
      publishArmedAt: "2026-09-21T00:00:00.000Z",
    },
  }),
  false,
  "any publish marker must keep automatic recovery fail-closed"
);

console.log("Full worker four-stage contract smoke: OK");
