"use strict";

const assert = require("assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const history = require("../history-utils");

function tempDir(name) {
  return fs.mkdtempSync(path.join(os.tmpdir(), `ai-svodki-${name}-`));
}

function configFor(dir) {
  return {
    workDir: dir,
    stateFile: path.join(dir, "state.json"),
    successRegistryFile: path.join(dir, "downloads", "_СКАЧАННЫЕ_ВИДЕО.json"),
    timeZone: "Europe/Moscow",
    historyRetention: {
      enabled: true,
      activeDays: 14,
      errorActiveDays: 7,
      archiveDir: path.join(dir, "archive"),
    },
  };
}

(function activeWindowAndPendingSafety() {
  const dir = tempDir("history-state");
  const config = configFor(dir);
  const state = {
    version: 1,
    jobs: {
      "https://x/2026-09-06/": { date: "2026-09-06", status: "DONE" },
      "https://x/2026-09-07/": { date: "2026-09-07", status: "DONE" },
      "https://x/2026-08-10/": {
        date: "2026-08-10",
        status: "DONE",
        dzenArticleVideo: { status: "ERROR", phase: "ERROR" },
      },
    },
  };

  fs.writeFileSync(config.stateFile, JSON.stringify(state), "utf8");
  const result = history.saveStateWithRetention(
    config,
    state,
    new Date("2026-09-20T09:00:00Z")
  );

  assert.equal(result.archivedJobs, 2);
  const active = history.loadActiveState(config);
  assert.ok(!active.jobs["https://x/2026-09-06/"]);
  assert.ok(active.jobs["https://x/2026-09-07/"]);
  assert.ok(!active.jobs["https://x/2026-08-10/"]);
  const restored = history.findJobForDateIncludingArchive(config, active, "2026-08-10");
  assert.equal(restored.source, "archive");
  assert.equal(restored.job.dzenArticleVideo.status, "ERROR");
})();

(function archivedOldDateCanBeRehydrated() {
  const dir = tempDir("history-rehydrate");
  const config = configFor(dir);
  fs.mkdirSync(config.historyRetention.archiveDir, { recursive: true });
  fs.writeFileSync(config.stateFile, JSON.stringify({ version: 1, jobs: {} }), "utf8");
  fs.writeFileSync(
    path.join(config.historyRetention.archiveDir, "state-2026-08.json"),
    JSON.stringify({
      version: 1,
      jobs: {
        "https://x/2026-08-20/": {
          date: "2026-08-20",
          status: "DONE",
          updatedAt: "2026-08-20T05:00:00Z",
        },
      },
    }),
    "utf8"
  );

  const state = history.loadActiveState(config);
  const found = history.findJobForDateIncludingArchive(
    config,
    state,
    "2026-08-20"
  );
  assert.equal(found.source, "archive");
  assert.equal(found.job.date, "2026-08-20");
  assert.ok(state.jobs["https://x/2026-08-20/"]);
})();

(function registryArchiveRemainsLookupVisible() {
  const dir = tempDir("history-registry");
  const config = configFor(dir);
  fs.mkdirSync(path.dirname(config.successRegistryFile), { recursive: true });
  const registry = {
    version: 1,
    videos: [
      { publicationDate: "2026-09-06", publicationUrl: "https://x/old" },
      { publicationDate: "2026-09-07", publicationUrl: "https://x/keep" },
    ],
  };

  fs.writeFileSync(config.successRegistryFile, JSON.stringify(registry), "utf8");
  const result = history.saveRegistryWithRetention(
    config,
    registry,
    new Date("2026-09-20T09:00:00Z")
  );
  assert.equal(result.archivedRecords, 1);

  const active = history.loadActiveRegistry(config);
  assert.equal(active.videos.length, 1);
  const found = history.findRegistryRecord(config, active, "https://x/old");
  assert.equal(found.source, "archive");
})();

(function pendingVkKeepsStateActive() {
  const dir=tempDir("history-vk-pending");
  const config=configFor(dir);
  const state={version:1,jobs:{
    pending:{date:"2026-08-01",status:"DONE",vkPublication:{status:"ERROR",phase:"POST_REQUESTED"}},
    finished:{date:"2026-08-01",status:"DONE",vkPublication:{status:"COMPLETE",phase:"COMPLETE"}}
  }};
  history.saveStateWithRetention(config,state,new Date("2026-09-20T09:00:00Z"));
  const active=history.loadActiveState(config);
  assert.ok(active.jobs.pending,"uncertain VK publication must never be archived");
  assert.ok(!active.jobs.finished,"completed VK publication is archiveable");
})();

(function expiredErrorsAndPublicationSafety() {
  const dir = tempDir("history-error-window");
  const config = configFor(dir);
  const now = new Date("2026-11-03T09:00:00Z");
  const state = { version: 1, jobs: {
    expiredArticleError: {
      date: "2026-10-11", status: "DONE",
      dzenAutomation: { status: "PUBLISHED" },
      dzenCollections: { status: "COMPLETE" },
      dzenArticleVideo: { status: "ERROR", phase: "ERROR" },
    },
    expiredVkUploadError: {
      date: "2026-10-27", status: "DONE",
      dzenAutomation: { status: "PUBLISHED" },
      dzenCollections: { status: "COMPLETE" },
      dzenArticleVideo: { status: "COMPLETE", phase: "VERIFIED" },
      vkPublication: { status: "ERROR", phase: "STORY_UPLOAD_REQUESTED",
        videoId: "456239152", postId: "229", storyUploadAttempts: 3 },
    },
    recentArticleError: {
      date: "2026-10-28", status: "DONE",
      dzenArticleVideo: { status: "ERROR", phase: "ERROR" },
    },
    unsafeVkPost: {
      date: "2026-10-11", status: "DONE",
      vkPublication: { status: "ERROR", phase: "POST_REQUESTED" },
    },
    unsafeVkSave: {
      date: "2026-10-11", status: "DONE",
      vkPublication: { status: "ERROR", phase: "STORY_SAVE_REQUESTED" },
    },
    articleErrorWithPendingCollections: {
      date: "2026-10-11", status: "DONE",
      dzenCollections: { status: "PARTIAL" },
      dzenArticleVideo: { status: "ERROR", phase: "ERROR" },
    },
    unknownDzenPublish: {
      date: "2026-10-11", status: "DONE",
      dzenAutomation: { status: "ERROR", phase: "CLICKED_UNVERIFIED",
        draftId: "already-created" },
    },
    activeGeneration: {
      date: "2026-10-11", status: "GENERATING",
    },
    ordinaryCompletedWithin14: {
      date: "2026-10-21", status: "DONE",
    },
    ordinaryCompletedOlderThan14: {
      date: "2026-10-20", status: "DONE",
    },
  }};
  fs.writeFileSync(config.stateFile, JSON.stringify(state), "utf8");
  const result = history.saveStateWithRetention(config, state, now);
  assert.equal(result.archivedJobs, 3);
  const active = history.loadActiveState(config);
  for (const key of ["expiredArticleError", "expiredVkUploadError",
    "ordinaryCompletedOlderThan14"]) assert.ok(!active.jobs[key], key);
  for (const key of ["recentArticleError", "unsafeVkPost", "unsafeVkSave",
    "articleErrorWithPendingCollections", "unknownDzenPublish",
    "activeGeneration", "ordinaryCompletedWithin14"]) assert.ok(active.jobs[key], key);
  const archivedVk = history.findJobForDateIncludingArchive(config, active, "2026-10-27");
  assert.equal(archivedVk.source, "archive");
  assert.equal(archivedVk.job.vkPublication.videoId, "456239152");
  assert.equal(archivedVk.job.vkPublication.postId, "229");
  assert.equal(archivedVk.job.vkPublication.storyUploadAttempts, 3);
  // Re-archiving a restored old error is non-destructive and preserves checkpoint.
  history.saveStateWithRetention(config, active, now);
  const reread = history.findJobForDateIncludingArchive(
    config, history.loadActiveState(config), "2026-10-27");
  assert.equal(reread.job.vkPublication.phase, "STORY_UPLOAD_REQUESTED");
})();

(function expiryWindowIsConfigurable() {
  const dir = tempDir("history-error-config");
  const config = configFor(dir);
  assert.equal(history.getHistoryConfig(config).errorActiveDays, 7);
  config.historyRetention.errorActiveDays = 10;
  const state = {version:1,jobs:{
    oldError: {date:"2026-10-25",status:"DONE",
      dzenArticleVideo:{status:"ERROR",phase:"ERROR"}},
  }};
  history.saveStateWithRetention(config,state,new Date("2026-11-03T09:00:00Z"));
  assert.ok(history.loadActiveState(config).jobs.oldError,
    "explicit 10-day error window must override the default seven days");
})();

console.log("JSON HISTORY CONTRACT OK");
