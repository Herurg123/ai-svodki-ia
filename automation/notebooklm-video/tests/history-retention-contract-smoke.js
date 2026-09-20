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

  assert.equal(result.archivedJobs, 1);
  const active = history.loadActiveState(config);
  assert.ok(!active.jobs["https://x/2026-09-06/"]);
  assert.ok(active.jobs["https://x/2026-09-07/"]);
  assert.ok(active.jobs["https://x/2026-08-10/"]);
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

console.log("JSON HISTORY CONTRACT OK");
