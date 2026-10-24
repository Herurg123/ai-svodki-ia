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
assert(source.includes("hasTodayLocalMp4(candidate,currentDateKey)"),
  "VK must be admitted by today's local MP4 rather than Dzen completion");
assert(!source.includes("!phasesError && !collectionsError && !articleVideoError"),
  "Dzen failures must not suppress VK");
assert(source.includes('runNodeScript("dzen-article-link.js"'),
  "Missing independent read-only article URL discovery before VK");
assert(source.includes("articleLink.verifiedArticleUrl(verifiedJob)"),
  "VK requires a persisted verified Dzen article URL");
assert(source.indexOf('runNodeScript("dzen-article-link.js"') <
  source.indexOf('runNodeScript("vk-stage.mjs"'),
  "Resolve article before any VK mutation");
assert(!source.includes("articleLink.verifiedArticleUrl(candidate) || candidate.publicationUrl"),
  "Do not fall back from Dzen article to rybalka.one");

assert(source.includes("collections.findJobForDate(fresh,currentDateKey)"),
  "VK may not select yesterday's catch-up job");
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

const vkFixtureDir=fs.mkdtempSync(path.join(require("os").tmpdir(),"vk-ready-mp4-"));
try {
  const video=path.join(vkFixtureDir,"ИИ-Сводка 2026-10-24.mp4");
  const bytes=Buffer.alloc(32);bytes.write("ftyp",4);fs.writeFileSync(video,bytes);
  assert.strictEqual(full.hasTodayLocalMp4({date:"2026-10-24",downloadedFile:video,
    dzenAutomation:{status:"CLICKED_UNVERIFIED"}},"2026-10-24",vkFixtureDir),true);
  assert.strictEqual(full.hasTodayLocalMp4({date:"2026-10-23",downloadedFile:video},"2026-10-24",vkFixtureDir),false);
  assert.strictEqual(full.hasTodayLocalMp4({date:"2026-10-24",downloadedFile:video},"2026-10-25",vkFixtureDir),false);
  assert.strictEqual(full.hasTodayLocalMp4({date:"2026-10-24",downloadedFile:video},
    "2026-10-24",path.join(vkFixtureDir,"not-downloads")),false);
  fs.rmSync(video);
  assert.strictEqual(full.hasTodayLocalMp4({date:"2026-10-24",downloadedFile:video},"2026-10-24",vkFixtureDir),false);
}finally{fs.rmSync(vkFixtureDir,{force:true,recursive:true});}
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
  "safe scheduled recovery must invoke the guarded article-video link recovery flag");
assert(source.includes('"--recover-prepublish-clipboard-error"'),
  "safe scheduled recovery must invoke the guarded pre-publish clipboard recovery flag");
assert(source.includes('"--recover-browser-paste-migration"'),
  "migration recovery must unlock one browser-side paste attempt for legacy clipboard errors");
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

const safeClipboardError = {
  dzenArticleVideo: {
    status: "ERROR",
    phase: "ERROR",
    articleUrl: "https://dzen.ru/a/article-test",
    videoUrl: "https://dzen.ru/video/watch/video-test",
    lastError: "Set-Clipboard : Value cannot be null. ArgumentNullException",
  },
};
assert.strictEqual(
  full.canAutoRecoverPrePublishClipboardError(safeClipboardError),
  true,
  "pre-publish clipboard error with resolved links and no publish markers must be recoverable once"
);
assert.strictEqual(
  full.canAutoRecoverPrePublishClipboardError({
    dzenArticleVideo: {
      ...safeClipboardError.dzenArticleVideo,
      recoveryHistory: [{ reason: "pre-publish clipboard recovery" }],
    },
  }),
  false,
  "clipboard recovery must be at-most-once"
);
assert.strictEqual(
  full.canAutoRecoverPrePublishClipboardError({
    dzenArticleVideo: {
      ...safeClipboardError.dzenArticleVideo,
      saveChangesClickedAt: "2026-09-21T00:00:00.000Z",
    },
  }),
  false,
  "final publish markers must block clipboard recovery"
);

assert.strictEqual(
  full.canAutoRecoverBrowserPasteMigration(safeClipboardError),
  true,
  "old clipboard ERROR must be eligible for one browser-side paste migration even if legacy recovery policy existed"
);
assert.strictEqual(
  full.canAutoRecoverBrowserPasteMigration({
    dzenArticleVideo: {
      ...safeClipboardError.dzenArticleVideo,
      recoveryHistory: [{ reason: "pre-publish clipboard recovery" }],
    },
  }),
  true,
  "legacy clipboard recovery history must not consume the new browser-paste migration attempt"
);
assert.strictEqual(
  full.canAutoRecoverBrowserPasteMigration({
    dzenArticleVideo: {
      ...safeClipboardError.dzenArticleVideo,
      recoveryHistory: [{ reason: "browser-side paste migration recovery; no Windows clipboard" }],
    },
  }),
  false,
  "browser-side paste migration itself must be at-most-once"
);

assert(source.includes('runNodeScript("vk-stage.mjs"'), "full worker must own VK fifth stage");
assert(source.indexOf('runNodeScript("vk-stage.mjs"') > articleVideoIndex,
  "VK must follow the existing Dzen article-video step");
assert(source.includes('collections.findJobForDate(fresh,currentDateKey)'),
  "VK must select only today's job, not an older catch-up job");
assert(source.includes('hasTodayLocalMp4(candidate,currentDateKey)'),
  "VK must use same-day local file gate, not Dzen statuses");
assert(source.includes('config.vkPublish.automaticEnabled === true'),
  "VK default-off gate must be explicit");
assert(source.includes('if (vkError) parts.push'),"VK errors must flow to the shared failure path");
console.log("Full worker five-stage contract smoke: OK");
