"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");

function read(name) {
  return fs.readFileSync(path.join(ROOT, name), "utf8");
}

const config = JSON.parse(read("config.example.json"));
assert.strictEqual(config.ftpUpload.enabled, false, "FTP must stay disabled by default");
assert.strictEqual(config.ftpUpload.remoteDir, "video", "FTP root must stay confined to video");
assert.strictEqual(
  config.ftpUpload.remoteFilenamePrefix,
  "ai-svodka",
  "published media names must use the expected prefix"
);

const worker = read("worker.js");
assert.match(
  worker,
  /config\.ftpUpload\.remoteDir\s*!==\s*["']video["']/,
  "worker must reject any configured FTP directory other than video"
);
assert.match(
  worker,
  /ensureDir\(\s*["']video["']\s*\)/,
  "worker must explicitly enter/create only the video FTP directory"
);
assert.match(
  worker,
  /ai-svodka|remoteFilenamePrefix/,
  "worker must keep deterministic remote media naming"
);

const ignore = read(".gitignore");
for (const required of [
  "config.json",
  "ftp-access.json",
  "state.json",
  "worker.log",
  "downloads/",
  "yandex-profile/",
  "node_modules/",
]) {
  assert.ok(ignore.includes(required), `local runtime asset must stay ignored: ${required}`);
}

const agents = read("AGENTS.md");
assert.match(agents, /Video CI/i, "subproject rules must name the dedicated Video CI boundary");
assert.match(
  agents,
  /Main CI/i,
  "subproject rules must explicitly distinguish Video CI from Main CI"
);

console.log("Video runtime boundary smoke test: OK");
