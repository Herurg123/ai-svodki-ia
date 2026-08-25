"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");

function read(name) {
  return fs.readFileSync(path.join(ROOT, name), "utf8");
}

const manifest = JSON.parse(read("package.json"));
const lock = JSON.parse(read("package-lock.json"));

assert.strictEqual(lock.lockfileVersion, 3, "video lockfile must stay on npm lockfile v3");
assert.ok(lock.packages && lock.packages[""], "lockfile must contain the root package");
assert.strictEqual(lock.name, manifest.name, "lockfile package name must match package.json");
assert.strictEqual(lock.version, manifest.version, "lockfile package version must match package.json");
assert.deepStrictEqual(
  lock.packages[""].dependencies,
  manifest.dependencies,
  "root dependencies in package-lock.json must exactly match package.json"
);

for (const [name, version] of Object.entries(manifest.dependencies || {})) {
  const locked = lock.packages[`node_modules/${name}`];
  assert.ok(locked, `direct dependency must exist in lockfile: ${name}`);
  assert.strictEqual(
    locked.version,
    version,
    `direct dependency version must be locked exactly: ${name}`
  );
}

const setup = read("setup-local.ps1");
assert.match(setup, /["']package-lock\.json["']/, "setup must copy package-lock.json");
assert.match(setup, /\bnpm ci --no-audit --no-fund\b/, "setup must install from the lockfile with npm ci");
assert.doesNotMatch(setup, /\bnpm install\b/, "setup must not fall back to npm install");

const helper = read("install-ftp-support.cmd");
assert.match(helper, /\bnpm ci --no-audit --no-fund\b/, "dependency helper must use npm ci");
assert.doesNotMatch(helper, /\bnpm install\b/, "dependency helper must not mutate the lockfile");

console.log("Video lockfile contract smoke test: OK");
