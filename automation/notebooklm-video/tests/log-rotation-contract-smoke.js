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
  assert.ok(fs.existsSync(path.join(dir, "logs", "worker-2026-09-19.log")));
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
  assert.equal(fs.existsSync(path.join(dir, "logs", "worker-2026-09-21.log")), false);
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
