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
  const old = new Date("2026-09-19T07:00:00Z");
  fs.utimesSync(config.regularLog, old, old);

  const result = logs.prepareLogForAppend(
    config,
    config.regularLog,
    "worker",
    new Date("2026-09-20T09:00:00Z")
  );
  assert.equal(result.rotated, true);
  assert.ok(fs.existsSync(path.join(dir, "logs", "worker-2026-09-19.log")));
})();

(function untouchedRunnerCannotPermanentlyMaskBoundary() {
  const dir = tempDir("log-sidecar");
  const config = configFor(dir);
  fs.writeFileSync(config.regularLog, "[19.09.2026, 10:00:00] old\r\n", "utf8");

  logs.prepareLogForAppend(
    config,
    config.regularLog,
    "worker",
    new Date("2026-09-19T09:00:00Z")
  );

  // dzen-browser-runner.js intentionally remains unchanged by this fix and may
  // append directly. The sidecar must still preserve the old-day boundary.
  fs.appendFileSync(
    config.regularLog,
    "[20.09.2026, 06:00:00] runner-first\r\n",
    "utf8"
  );

  const result = logs.prepareLogForAppend(
    config,
    config.regularLog,
    "worker",
    new Date("2026-09-20T09:00:00Z")
  );
  assert.equal(result.rotated, true);
  assert.ok(fs.existsSync(result.archivePath));
})();

(function legacyMixedLogMigratesOnce() {
  const dir = tempDir("log-mixed");
  const config = configFor(dir);
  fs.writeFileSync(
    config.regularLog,
    "[18.09.2026, 10:00:00] a\r\n" +
      "[19.09.2026, 10:00:00] b\r\n" +
      "[20.09.2026, 06:00:00] c\r\n",
    "utf8"
  );

  const result = logs.prepareLogForAppend(
    config,
    config.regularLog,
    "worker",
    new Date("2026-09-20T09:00:00Z")
  );
  assert.equal(result.rotated, true);
  assert.equal(path.basename(result.archivePath), "worker-2026-09-20.log");
})();

console.log("LOG ROTATION CONTRACT OK");
