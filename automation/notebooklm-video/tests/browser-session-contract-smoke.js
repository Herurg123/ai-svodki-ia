"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const browserSession = fs.readFileSync(path.join(ROOT, "browser-session.js"), "utf8");
const runner = fs.readFileSync(path.join(ROOT, "dzen-browser-runner.js"), "utf8");
const liveCmd = fs.readFileSync(path.join(ROOT, "run-dzen-publish.cmd"), "utf8");
const dryCmd = fs.readFileSync(path.join(ROOT, "run-dzen-dry-run.cmd"), "utf8");

for (const required of [
  "--user-data-dir=${config.browserProfile}",
  "--remote-debugging-address=${config.browserDebugHost}",
  "--remote-debugging-port=${config.browserDebugPort}",
  "--disable-renderer-backgrounding",
  "--disable-background-timer-throttling",
  "about:blank",
  "waitForCdp(config)",
  "chromium.connectOverCDP(endpoint)",
]) {
  assert(browserSession.includes(required), `browser-session.js missing worker bootstrap contract: ${required}`);
}

assert(!browserSession.includes("timeout: 3000"), "shared bootstrap must not restore the 3s CDP timeout");
assert(!browserSession.includes("open-robot-browser"), "shared bootstrap must not depend on legacy launcher scripts");
assert(!browserSession.includes("Sessions"), "Dzen bootstrap must not delete browser profile session files");

assert(runner.includes('require("./browser-session")'), "runner must use browser-session.js");
assert(runner.includes('"dzen-publish-direct.js"'), "runner must invoke the direct live publisher");
assert(runner.includes("OPERATOR_WINDOW_MS = 10 * 60 * 1000"), "runner must bound one operator child to ten minutes");
assert(runner.includes("taskkill.exe"), "Windows child process tree must remain bounded by the operator window");
assert(runner.includes("inter-run resume отключён"), "live runner must explicitly disable inter-run resume");
assert(runner.includes("Новый child, reopen draft и автоматический retry не выполняются"), "failed live child must stop cleanly");

for (const forbidden of [
  "recoverDraftCreatedBeforeChildExit",
  "resetClearlyEmptyDraft",
  "isClearlyEmptyRemoteDraft",
  "previousDrafts",
  "DRAFT_PROBE_TIMEOUT_MS",
  "RETRY_DELAY_MS",
  "runDryRunWithRecovery",
]) {
  assert(!runner.includes(forbidden), `Simplified runner must not contain legacy draft recovery: ${forbidden}`);
}

assert(liveCmd.includes("dzen-browser-runner.js"), "live command must route through shared bootstrap");
assert(dryCmd.includes("dzen-browser-runner.js"), "dry-run command must route through shared bootstrap");
assert(!liveCmd.toLowerCase().includes("powershell"), "live command must not require a PowerShell launcher");
assert(!dryCmd.toLowerCase().includes("powershell"), "dry-run command must not require a PowerShell launcher");

console.log("browser session fresh-upload contract smoke: OK");
