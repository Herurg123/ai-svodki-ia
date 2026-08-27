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
assert(runner.includes('"dzen-publish-live.js"'), "runner must invoke the live publisher");
assert(runner.includes("recoverDraftCreatedBeforeChildExit"), "runner must recover a draft created before Playwright child exit");
assert(runner.includes("videoEditorPublicationId"), "draft recovery must key off videoEditorPublicationId");
assert(runner.includes("recoveredAfterUploadTimeout"), "recovered draft must be recorded in state");
assert(runner.includes("повторно запускаю Dzen flow"), "runner must continue the existing draft after recovery");
assert(liveCmd.includes("dzen-browser-runner.js"), "live command must route through shared bootstrap");
assert(dryCmd.includes("dzen-browser-runner.js"), "dry-run command must route through shared bootstrap");
assert(!liveCmd.toLowerCase().includes("powershell"), "live command must not require a PowerShell launcher");
assert(!dryCmd.toLowerCase().includes("powershell"), "dry-run command must not require a PowerShell launcher");

console.log("browser session contract smoke: OK");
