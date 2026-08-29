"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const scheduled = require(path.join(ROOT, "scheduled-worker.js"));

assert.strictEqual(scheduled.shouldRunFreshUpload("PENDING"), true);
assert.strictEqual(scheduled.shouldRunFreshUpload("RETRYABLE_PRE_CLICK"), true);
assert.strictEqual(scheduled.shouldRunFreshUpload("PUBLISH_ARMED"), false);
assert.strictEqual(scheduled.shouldRunFreshUpload("CLICKED_UNVERIFIED"), false);
assert.strictEqual(scheduled.shouldRunFreshUpload("BLOCKED_AMBIGUOUS"), false);
assert.strictEqual(scheduled.shouldRunFreshUpload("PUBLISHED"), false);

for (const status of ["PUBLISH_ARMED", "CLICKED_UNVERIFIED", "BLOCKED_AMBIGUOUS"]) {
  assert.strictEqual(
    scheduled.isVerificationOnlyStatus(status),
    true,
    `${status} must be verification-only`
  );
}
assert.strictEqual(scheduled.isVerificationOnlyStatus("PENDING"), false);
assert.strictEqual(scheduled.isVerificationOnlyStatus("RETRYABLE_PRE_CLICK"), false);

const latestDone = scheduled.findLatestDoneJob(
  {
    jobs: {
      old: { date: "2026-08-26", status: "DONE", updatedAt: "2026-08-26T10:00:00Z" },
      yesterdayOlder: { date: "2026-08-27", status: "DONE", updatedAt: "2026-08-27T08:00:00Z" },
      yesterdayNewer: { date: "2026-08-27", status: "DONE", updatedAt: "2026-08-27T09:00:00Z" },
      todayPending: { date: "2026-08-28", status: "GENERATING", updatedAt: "2026-08-28T09:00:00Z" },
      future: { date: "2026-08-29", status: "DONE", updatedAt: "2026-08-29T09:00:00Z" },
    },
  },
  "2026-08-28"
);
assert.strictEqual(latestDone.updatedAt, "2026-08-27T09:00:00Z");
assert.strictEqual(
  scheduled.findLatestDoneJob({ jobs: { future: { date: "2026-08-29", status: "DONE" } } }, "2026-08-28"),
  null
);

assert.strictEqual(
  scheduled.classifyDzenFailureOutput("direct MVP завершился ошибкой; publishClicked=false; draftId=123"),
  "PRE_CLICK_RETRYABLE"
);
assert.strictEqual(
  scheduled.classifyDzenFailureOutput("direct MVP завершился ошибкой; publishClicked=true; draftId=123"),
  "POST_CLICK_OR_AMBIGUOUS"
);
assert.strictEqual(
  scheduled.classifyDzenFailureOutput("КЛИК ПУБЛИКАЦИИ ВЫПОЛНЕН ОДИН РАЗ"),
  "POST_CLICK_OR_AMBIGUOUS"
);
assert.strictEqual(
  scheduled.classifyDzenFailureOutput("child disappeared without final diagnostic"),
  "AMBIGUOUS"
);

const defaultConfig = scheduled.normalizeAutomaticDzenConfig({
  dzenUpload: {},
});
assert.strictEqual(defaultConfig.dzenUpload.automaticEnabled, true);
assert.strictEqual(
  defaultConfig.dzenUpload.verificationTimeoutMs,
  scheduled.DEFAULT_VERIFY_TIMEOUT_MS
);

const disabledConfig = scheduled.normalizeAutomaticDzenConfig({
  dzenUpload: {
    automaticEnabled: false,
    verificationTimeoutMs: 45_000,
  },
});
assert.strictEqual(disabledConfig.dzenUpload.automaticEnabled, false);
assert.strictEqual(disabledConfig.dzenUpload.verificationTimeoutMs, 45_000);

assert.throws(
  () => scheduled.normalizeAutomaticDzenConfig({ dzenUpload: { automaticEnabled: "yes" } }),
  /automaticEnabled должен быть true или false/
);

const runWorkerCmd = fs.readFileSync(path.join(ROOT, "run-worker.cmd"), "utf8");
assert.match(runWorkerCmd, /full-worker\.js/i);
assert.doesNotMatch(runWorkerCmd, /node\s+"?%~dp0scheduled-worker\.js/i);
assert.doesNotMatch(runWorkerCmd, /node\s+"?%~dp0worker\.js/i);

const source = fs.readFileSync(path.join(ROOT, "scheduled-worker.js"), "utf8");
const workerPhaseIndex = source.indexOf('await runNodeScript("worker.js")');
const doneGateIndex = source.indexOf("findLatestDoneJob(state, currentDateKey)");
const dzenPhaseIndex = source.indexOf('await runAutomaticDzen(config, state, job, dateKey)');
assert(workerPhaseIndex >= 0, "NotebookLM worker child call must exist");
assert(doneGateIndex > workerPhaseIndex, "latest DONE selection must run after NotebookLM worker child");
assert(dzenPhaseIndex > doneGateIndex, "Dzen phase must run after DONE gate");

const armIndex = source.indexOf('updateDzenAutomation(config, state, job, "PUBLISH_ARMED"');
const liveChildIndex = source.indexOf('"dzen-publish-direct.js"');
assert(armIndex >= 0, "PUBLISH_ARMED persistence must exist");
assert(liveChildIndex > armIndex, "PUBLISH_ARMED must be persisted before live child starts");

assert.match(
  source,
  /status=\$\{status\}: разрешена только проверка публикации, новый upload и второй publish click запрещены/
);
assert.match(source, /verification-only: попытка/);
assert.match(source, /publishClicked=false/i);
assert.match(source, /BLOCKED_AMBIGUOUS/);

console.log("scheduled-worker contract smoke: OK");
