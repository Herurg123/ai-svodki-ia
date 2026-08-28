"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const runner = fs.readFileSync(path.join(ROOT, "dzen-browser-runner.js"), "utf8");

const guardCall = runner.indexOf("duplicateGuard.checkBeforeUpload");
const childCall = runner.indexOf("await runNodeScript", guardCall);
const duplicateReturn = runner.indexOf("if (duplicate.existing)", guardCall);

assert(guardCall >= 0, "Runner must call duplicate guard");
assert(duplicateReturn > guardCall, "Runner must branch on duplicate result");
assert(childCall > duplicateReturn, "Live child must be after duplicate short-circuit");
assert(
  runner.includes("live child не запускается"),
  "Duplicate path must explicitly skip live child"
);

console.log("Dzen duplicate guard runner order smoke: OK");
