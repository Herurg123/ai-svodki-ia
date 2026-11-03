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
  const archivedError = history.findJobForDateIncludingArchive(config, active, "2026-08-10");
  assert.equal(archivedError.source, "archive");
  assert.equal(archivedError.job.dzenArticleVideo.status, "ERROR");
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
  assert.ok(!active.jobs.pending,"old uncertain VK checkpoint must be archived");
  assert.ok(!active.jobs.finished,"old completed VK publication must be archived");
  const restored = history.findJobForDateIncludingArchive(config, active, "2026-08-01");
  assert.equal(restored.source, "archive");
  assert.equal(restored.job.vkPublication.phase, "POST_REQUESTED");
})();

(function unconditional14DayArchivingAndBoundary() {
  const dir = tempDir("history-all-statuses");
  const config = configFor(dir);
  const now = new Date("2026-11-03T09:00:00Z");
  const state = {version:1,jobs:{
    oldDone: {date:"2026-10-20",status:"DONE"},
    oldGenerating: {date:"2026-10-11",status:"GENERATING"},
    oldArticleError: {date:"2026-10-12",status:"DONE",
      dzenArticleVideo:{status:"ERROR",phase:"ERROR"}},
    oldDzenClickUnverified: {date:"2026-10-19",status:"DONE",
      dzenAutomation:{status:"CLICKED_UNVERIFIED",draftId:"pinned-id"}},
    oldVkSaveUnknown: {date:"2026-10-15",status:"DONE",
      vkPublication:{status:"ERROR",phase:"STORY_SAVE_REQUESTED",
        videoId:"456239101",postId:"200"}},
    oldVkUploadError: {date:"2026-10-13",status:"DONE",
      vkPublication:{status:"ERROR",phase:"STORY_UPLOAD_REQUESTED",
        storyUploadAttempts:3,videoId:"456239102",postId:"201"}},
    boundaryDone: {date:"2026-10-21",status:"DONE"},
    boundaryError: {date:"2026-10-21",status:"DONE",
      dzenArticleVideo:{status:"ERROR",phase:"ERROR"}},
    recentGenerating: {date:"2026-11-02",status:"GENERATING"},
    undated: {status:"ERROR"}
  }};
  fs.writeFileSync(config.stateFile,JSON.stringify(state),"utf8");
  const result=history.saveStateWithRetention(config,state,now);
  assert.equal(result.archivedJobs,6);
  const active=history.loadActiveState(config);
  for(const key of ["oldDone","oldGenerating","oldArticleError",
    "oldDzenClickUnverified","oldVkSaveUnknown","oldVkUploadError"])
    assert.ok(!active.jobs[key],key+" must be archived");
  for(const key of ["boundaryDone","boundaryError","recentGenerating","undated"])
    assert.ok(active.jobs[key],key+" must stay active");
  const archived=history.findJobForDateIncludingArchive(config,active,"2026-10-15");
  assert.equal(archived.source,"archive");
  assert.equal(archived.job.vkPublication.phase,"STORY_SAVE_REQUESTED");
  assert.equal(archived.job.vkPublication.postId,"200");
})();

(function rehydratedOldJobPersistsMultipleCheckpointWrites() {
  const dir=tempDir("history-old-checkpoints");
  const config=configFor(dir);
  const now=new Date("2026-11-03T09:00:00Z");
  const state={version:1,jobs:{
    old:{date:"2026-10-12",status:"DONE",
      vkPublication:{status:"ERROR",phase:"STORY_UPLOAD_REQUESTED",
        storyUploadAttempts:3,videoId:"456239111",postId:"202"}}
  }};
  history.saveStateWithRetention(config,state,now);
  assert.equal(Object.keys(history.loadActiveState(config).jobs).length,0);
  const session=history.loadActiveState(config);
  const found=history.findJobForDateIncludingArchive(config,session,"2026-10-12");
  assert.equal(found.source,"archive");
  for(const phase of ["STORY_UPLOAD_ACK","STORY_SAVE_REQUESTED","STORY_SAVE_ACK"]){
    found.job.vkPublication.phase=phase;
    history.saveStateWithRetention(config,session,now);
    assert.equal(history.loadActiveState(config).jobs.old.vkPublication.phase,phase,
      "explicit old-date process must persist "+phase);
  }
  found.job.vkPublication.status="COMPLETE";
  found.job.vkPublication.phase="COMPLETE";
  found.job.vkPublication.storyId=456239113;
  history.saveStateWithRetention(config,session,now);
  assert.equal(history.loadActiveState(config).jobs.old.vkPublication.storyId,456239113);
  const compacted=history.compactJsonHistory(config,now);
  assert.equal(compacted.archivedJobs,1);
  assert.equal(Object.keys(history.loadActiveState(config).jobs).length,0);
  const restored=history.findJobForDateIncludingArchive(
    config,history.loadActiveState(config),"2026-10-12");
  assert.equal(restored.source,"archive");
  assert.equal(restored.job.vkPublication.storyId,456239113);
})();
console.log("JSON HISTORY CONTRACT OK");
