"use strict";

const assert = require("assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const logs = require("../log-utils");

function tempDir(name) {
  return fs.mkdtempSync(path.join(os.tmpdir(), `ai-svodki-${name}-`));
}

function configFor(dir) {
  return {
    workDir: dir,
    regularLog: path.join(dir, "worker.log"),
    errorLog: path.join(dir, "!!! ERROR !!!.log"),
    timeZone: "Europe/Moscow",
    logRotation: {
      enabled: true,
      archiveDir: path.join(dir, "logs"),
      workerRetentionDays: 7,
      errorRetentionDays: 30,
      maxFileSizeMb: 25,
    },
  };
}

(function dayBoundaryRotatesBeforeFirstCentralAppend() {
  const dir = tempDir("log-day");
  const config = configFor(dir);
  fs.writeFileSync(config.regularLog, "[19.09.2026, 10:00:00] old\r\n", "utf8");

  const result = logs.prepareLogForAppend(
    config,
    config.regularLog,
    "worker",
    new Date("2026-09-20T09:00:00Z")
  );

  assert.equal(result.rotated, true);
  assert.ok(fs.existsSync(path.join(dir, "archive", "worker-2026-09-19.log")));
  assert.equal(
    logs.getRotationConfig(config).archiveDir,
    path.join(dir, "archive"),
    "legacy default logs path must transparently resolve to shared archive"
  );
  assert.equal(fs.existsSync(config.regularLog), false);
})();

(function repeatedSameDayRunDoesNotRotateAgain() {
  const dir = tempDir("log-repeat");
  const config = configFor(dir);
  fs.writeFileSync(
    config.regularLog,
    "[21.09.2026, 06:40:02] FULL-WORKER: first run\r\n" +
      "[21.09.2026, 06:40:03] FULL-WORKER: first run end\r\n",
    "utf8"
  );

  const first = logs.prepareLogForAppend(
    config,
    config.regularLog,
    "worker",
    new Date("2026-09-21T03:55:00Z")
  );
  assert.equal(first.rotated, false);

  fs.appendFileSync(
    config.regularLog,
    "[21.09.2026, 06:55:30] FULL-WORKER: second run\r\n",
    "utf8"
  );

  const second = logs.prepareLogForAppend(
    config,
    config.regularLog,
    "worker",
    new Date("2026-09-21T04:00:00Z")
  );
  assert.equal(second.rotated, false);

  const text = fs.readFileSync(config.regularLog, "utf8");
  assert.match(text, /06:40:02/);
  assert.match(text, /06:55:30/);
  assert.equal(fs.existsSync(path.join(dir, "archive", "worker-2026-09-21.log")), false);
})();

(function untouchedRunnerCurrentDayLineIsPreservedActive() {
  const dir = tempDir("log-runner");
  const config = configFor(dir);
  fs.writeFileSync(
    config.regularLog,
    "[20.09.2026, 10:00:00] yesterday\r\n" +
      "[21.09.2026, 06:39:59] DZEN: direct runner wrote before shared logger\r\n",
    "utf8"
  );

  // dzen-browser-runner.js intentionally remains unchanged and can still write
  // directly. Shared rotation must archive only the old prefix, not today's
  // direct-runner line.
  const result = logs.prepareLogForAppend(
    config,
    config.regularLog,
    "worker",
    new Date("2026-09-21T03:40:00Z")
  );

  assert.equal(result.rotated, true);
  const archive = fs.readFileSync(result.archivePath, "utf8");
  const active = fs.readFileSync(config.regularLog, "utf8");
  assert.match(archive, /yesterday/);
  assert.doesNotMatch(archive, /direct runner/);
  assert.match(active, /direct runner/);

  const second = logs.prepareLogForAppend(
    config,
    config.regularLog,
    "worker",
    new Date("2026-09-21T03:55:00Z")
  );
  assert.equal(second.rotated, false);
})();

(function legacyLogArchivesMigrateIntoSharedArchiveWithoutTouchingJson() {
  const dir = tempDir("log-migrate");
  const config = configFor(dir);
  const legacyDir = path.join(dir, "logs");
  const archiveDir = path.join(dir, "archive");
  fs.mkdirSync(legacyDir, { recursive: true });
  fs.mkdirSync(archiveDir, { recursive: true });

  fs.writeFileSync(path.join(legacyDir, "worker-2026-09-18.log"), "old worker", "utf8");
  fs.writeFileSync(path.join(legacyDir, "error-2026-09-17.log"), "old error", "utf8");
  fs.writeFileSync(
    path.join(legacyDir, ".rotation-state.json"),
    JSON.stringify({ version: 1, workerDate: "2026-09-18" }),
    "utf8"
  );
  fs.writeFileSync(
    path.join(archiveDir, "state-2026-09.json"),
    JSON.stringify({ version: 1, jobs: { keep: true } }),
    "utf8"
  );
  fs.writeFileSync(
    path.join(archiveDir, "downloaded-videos-2026-09.json"),
    JSON.stringify({ version: 1, videos: [{ publicationUrl: "keep" }] }),
    "utf8"
  );

  const result = logs.performLogMaintenance(
    config,
    new Date("2026-09-21T04:00:00Z")
  );

  assert.equal(result.migratedLegacyLogFiles, 2);
  assert.equal(result.removedLegacySidecar, true);
  assert.equal(result.removedLegacyLogDir, true);
  assert.ok(fs.existsSync(path.join(archiveDir, "worker-2026-09-18.log")));
  assert.ok(fs.existsSync(path.join(archiveDir, "error-2026-09-17.log")));
  assert.ok(fs.existsSync(path.join(archiveDir, "state-2026-09.json")));
  assert.ok(fs.existsSync(path.join(archiveDir, "downloaded-videos-2026-09.json")));
  assert.equal(fs.existsSync(legacyDir), false);
})();

(function logCleanupIgnoresJsonHistoryInSharedArchive() {
  const dir = tempDir("log-cleanup-json");
  const config = configFor(dir);
  const archiveDir = path.join(dir, "archive");
  fs.mkdirSync(archiveDir, { recursive: true });
  fs.writeFileSync(path.join(archiveDir, "worker-2026-09-01.log"), "expired", "utf8");
  fs.writeFileSync(
    path.join(archiveDir, "state-2026-08.json"),
    JSON.stringify({ version: 1, jobs: { old: true } }),
    "utf8"
  );
  fs.writeFileSync(
    path.join(archiveDir, "downloaded-videos-2026-08.json"),
    JSON.stringify({ version: 1, videos: [{ publicationUrl: "old" }] }),
    "utf8"
  );

  const result = logs.cleanupOldLogArchives(
    config,
    new Date("2026-09-21T04:00:00Z")
  );

  assert.equal(result.deletedFiles, 1);
  assert.equal(fs.existsSync(path.join(archiveDir, "worker-2026-09-01.log")), false);
  assert.ok(fs.existsSync(path.join(archiveDir, "state-2026-08.json")));
  assert.ok(fs.existsSync(path.join(archiveDir, "downloaded-videos-2026-08.json")));
})();

(function disabledRotationDoesNotMigrateLegacyLogs() {
  const dir = tempDir("log-disabled");
  const config = configFor(dir);
  config.logRotation.enabled = false;
  const legacyDir = path.join(dir, "logs");
  fs.mkdirSync(legacyDir, { recursive: true });
  fs.writeFileSync(path.join(legacyDir, "worker-2026-09-18.log"), "keep", "utf8");

  const result = logs.performLogMaintenance(
    config,
    new Date("2026-09-21T04:00:00Z")
  );

  assert.equal(result.enabled, false);
  assert.equal(result.migratedLegacyLogFiles, 0);
  assert.ok(fs.existsSync(path.join(legacyDir, "worker-2026-09-18.log")));
})();

(function staleLegacySidecarCannotForceSameDayRotation() {
  const dir = tempDir("log-stale-sidecar");
  const config = configFor(dir);
  fs.mkdirSync(config.logRotation.archiveDir, { recursive: true });
  fs.writeFileSync(
    path.join(config.logRotation.archiveDir, ".rotation-state.json"),
    JSON.stringify({ version: 1, workerDate: "2026-09-20", errorDate: "2026-09-20" }),
    "utf8"
  );
  fs.writeFileSync(
    config.regularLog,
    "[21.09.2026, 06:40:02] current day\r\n",
    "utf8"
  );

  const result = logs.prepareLogForAppend(
    config,
    config.regularLog,
    "worker",
    new Date("2026-09-21T03:55:00Z")
  );

  assert.equal(result.rotated, false);
  assert.match(fs.readFileSync(config.regularLog, "utf8"), /current day/);
})();

(function sizeRotationStillWorks() {
  const dir = tempDir("log-size");
  const config = configFor(dir);
  config.logRotation.maxFileSizeMb = 0.00001;
  fs.writeFileSync(
    config.regularLog,
    "[21.09.2026, 06:40:02] " + "x".repeat(512) + "\r\n",
    "utf8"
  );

  const result = logs.prepareLogForAppend(
    config,
    config.regularLog,
    "worker",
    new Date("2026-09-21T03:55:00Z")
  );

  assert.equal(result.rotated, true);
  assert.equal(result.reason, "превышение размера");
  assert.ok(fs.existsSync(result.archivePath));
})();

console.log("LOG ROTATION CONTRACT OK");
